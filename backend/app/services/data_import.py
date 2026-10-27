"""
Data import service.

Takes a raw DataFrame + a confirmed column_mapping ({source_col: standard_field}),
renames/subsets to standard fields, re-validates, and (if row is valid) upserts
into the appropriate ORM tables scoped to a single company_id.

Get-or-create helpers keep Product/Supplier/Warehouse rows unique per company
even across multiple uploads referencing the same external_product_id etc.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.models import InventoryRecord, Product, Sale, Shipment, Supplier, Warehouse
from app.services.data_validation import validate_dataset


def apply_mapping(df: pd.DataFrame, column_mapping: dict[str, str | None]) -> pd.DataFrame:
    """Rename source columns -> standard fields, keep only mapped columns."""
    rename = {src: tgt for src, tgt in column_mapping.items() if tgt}
    mapped = df[[c for c in df.columns if c in rename]].rename(columns=rename)
    # If two source columns mapped to the same target (shouldn't happen from
    # suggest_column_mapping, but a user could force it), keep first occurrence.
    mapped = mapped.loc[:, ~mapped.columns.duplicated()]
    return mapped


def _get_or_create_product(db: Session, company_id: int, external_id: str) -> Product:
    product = (
        db.query(Product)
        .filter(Product.company_id == company_id, Product.external_product_id == str(external_id))
        .first()
    )
    if product is None:
        product = Product(
            company_id=company_id,
            external_product_id=str(external_id),
            name=str(external_id),
        )
        db.add(product)
        db.flush()
    return product


def _get_or_create_warehouse(db: Session, company_id: int, name: str | None) -> Warehouse | None:
    if not name or (isinstance(name, float) and pd.isna(name)):
        return None
    warehouse = (
        db.query(Warehouse)
        .filter(Warehouse.company_id == company_id, Warehouse.name == str(name))
        .first()
    )
    if warehouse is None:
        warehouse = Warehouse(company_id=company_id, name=str(name))
        db.add(warehouse)
        db.flush()
    return warehouse


def _get_or_create_supplier(db: Session, company_id: int, external_id: str, name: str | None = None) -> Supplier:
    supplier = (
        db.query(Supplier)
        .filter(Supplier.company_id == company_id, Supplier.external_supplier_id == str(external_id))
        .first()
    )
    if supplier is None:
        supplier = Supplier(
            company_id=company_id,
            external_supplier_id=str(external_id),
            name=str(name) if name else str(external_id),
        )
        db.add(supplier)
        db.flush()
    return supplier


def import_sales(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int, int]:
    imported, skipped, updated = 0, 0, 0
    products_touched = set()
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("product_id")) or pd.isna(row.get("date")) or pd.isna(row.get("quantity")):
                skipped += 1
                continue
            product = _get_or_create_product(db, company_id, row["product_id"])
            if "category" in df.columns and pd.notna(row.get("category")) and not product.category:
                product.category = str(row["category"])
            if "price" in df.columns and pd.notna(row.get("price")):
                try:
                    price_val = float(row["price"])
                    if product.unit_price is None or product.unit_price <= 0:
                        product.unit_price = price_val
                    if product.unit_cost is None or product.unit_cost <= 0:
                        product.unit_cost = round(price_val * 0.7, 2)
                except (ValueError, TypeError):
                    pass
            if "product_name" in df.columns and pd.notna(row.get("product_name")):
                product.name = str(row["product_name"])

            date_val = pd.to_datetime(row["date"], errors="coerce")
            if pd.isna(date_val):
                skipped += 1
                continue
            qty = float(row["quantity"])
            if qty < 0:
                skipped += 1
                continue

            region_str = str(row["region"]) if "region" in df.columns and pd.notna(row.get("region")) else None
            wh = _get_or_create_warehouse(db, company_id, region_str) if region_str else None

            # Natural key for Sale: (company_id, product_id, date, region)
            existing_sale = (
                db.query(Sale)
                .filter(
                    Sale.company_id == company_id,
                    Sale.product_id == product.id,
                    Sale.date == date_val.date(),
                    Sale.region == region_str,
                )
                .first()
            )
            price_val = float(row["price"]) if "price" in df.columns and pd.notna(row.get("price")) else None
            promo_val = int(bool(row.get("promotion"))) if "promotion" in df.columns and pd.notna(row.get("promotion")) else 0

            if existing_sale:
                existing_sale.quantity = qty
                if price_val is not None:
                    existing_sale.price = price_val
                existing_sale.promotion = promo_val
                updated += 1
            else:
                db.add(Sale(
                    company_id=company_id,
                    product_id=product.id,
                    date=date_val.date(),
                    quantity=qty,
                    region=region_str,
                    price=price_val,
                    promotion=promo_val,
                ))
                imported += 1

            products_touched.add((product.id, wh.id if wh else None))
        except (ValueError, TypeError):
            skipped += 1

    # Ensure baseline inventory record exists if this product has no inventory snapshot
    for pid, wid in products_touched:
        has_inv = db.query(InventoryRecord).filter(
            InventoryRecord.company_id == company_id,
            InventoryRecord.product_id == pid
        ).first()
        if not has_inv:
            recent_sales = db.query(Sale.quantity).filter(
                Sale.company_id == company_id,
                Sale.product_id == pid
            ).limit(30).all()
            avg_demand = sum(float(s[0] or 0) for s in recent_sales) / max(1, len(recent_sales)) if recent_sales else 10.0
            initial_stock = max(20.0, round(avg_demand * 25.0, 1))
            safety = round(avg_demand * 7.0, 1)
            import datetime as _dt
            db.add(InventoryRecord(
                company_id=company_id,
                product_id=pid,
                warehouse_id=wid,
                date=_dt.date.today(),
                inventory_level=initial_stock,
                safety_stock=safety
            ))
    return imported, skipped, updated


def import_inventory(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int, int]:
    imported, skipped, updated = 0, 0, 0
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("product_id")) or pd.isna(row.get("date")) or pd.isna(row.get("inventory_level")):
                skipped += 1
                continue
            product = _get_or_create_product(db, company_id, row["product_id"])
            warehouse = _get_or_create_warehouse(db, company_id, row.get("warehouse")) if "warehouse" in df.columns else None
            date_val = pd.to_datetime(row["date"], errors="coerce")
            if pd.isna(date_val):
                skipped += 1
                continue
            level = float(row["inventory_level"])
            if level < 0:
                skipped += 1
                continue

            wh_id = warehouse.id if warehouse else None
            safety_val = float(row["safety_stock"]) if "safety_stock" in df.columns and pd.notna(row.get("safety_stock")) else None

            # Natural key for InventoryRecord: (company_id, product_id, warehouse_id, date)
            existing_inv = (
                db.query(InventoryRecord)
                .filter(
                    InventoryRecord.company_id == company_id,
                    InventoryRecord.product_id == product.id,
                    InventoryRecord.warehouse_id == wh_id,
                    InventoryRecord.date == date_val.date(),
                )
                .first()
            )
            if existing_inv:
                existing_inv.inventory_level = level
                if safety_val is not None:
                    existing_inv.safety_stock = safety_val
                updated += 1
            else:
                db.add(InventoryRecord(
                    company_id=company_id,
                    product_id=product.id,
                    warehouse_id=wh_id,
                    date=date_val.date(),
                    inventory_level=level,
                    safety_stock=safety_val,
                ))
                imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped, updated


def import_shipments(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int, int]:
    imported, skipped, updated = 0, 0, 0
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("shipment_id")) or pd.isna(row.get("product_id")) or pd.isna(row.get("planned_delivery")):
                skipped += 1
                continue
            product = _get_or_create_product(db, company_id, row["product_id"])
            planned = pd.to_datetime(row["planned_delivery"], errors="coerce")
            if pd.isna(planned):
                skipped += 1
                continue
            actual = pd.to_datetime(row.get("actual_delivery"), errors="coerce") if "actual_delivery" in df.columns else pd.NaT

            shipment_ext_id = str(row["shipment_id"])
            # Natural key for Shipment: (company_id, external_shipment_id)
            existing_shipment = (
                db.query(Shipment)
                .filter(
                    Shipment.company_id == company_id,
                    Shipment.external_shipment_id == shipment_ext_id,
                )
                .first()
            )

            origin_str = str(row["origin"]) if "origin" in df.columns and pd.notna(row.get("origin")) else None
            dest_str = str(row["destination"]) if "destination" in df.columns and pd.notna(row.get("destination")) else None
            carrier_str = str(row["carrier"]) if "carrier" in df.columns and pd.notna(row.get("carrier")) else None
            transport_str = str(row["transport_mode"]) if "transport_mode" in df.columns and pd.notna(row.get("transport_mode")) else None
            dist_val = float(row["distance"]) if "distance" in df.columns and pd.notna(row.get("distance")) else None
            weight_val = float(row["weight"]) if "weight" in df.columns and pd.notna(row.get("weight")) else None
            qty_val = float(row["quantity"]) if "quantity" in df.columns and pd.notna(row.get("quantity")) else None

            if existing_shipment:
                existing_shipment.product_id = product.id
                existing_shipment.origin = origin_str
                existing_shipment.destination = dest_str
                existing_shipment.carrier = carrier_str
                existing_shipment.transport_mode = transport_str
                existing_shipment.distance_km = dist_val
                existing_shipment.weight_kg = weight_val
                existing_shipment.quantity = qty_val
                existing_shipment.planned_delivery = planned.date()
                existing_shipment.actual_delivery = actual.date() if pd.notna(actual) else None
                updated += 1
            else:
                db.add(Shipment(
                    company_id=company_id,
                    product_id=product.id,
                    external_shipment_id=shipment_ext_id,
                    origin=origin_str,
                    destination=dest_str,
                    carrier=carrier_str,
                    transport_mode=transport_str,
                    distance_km=dist_val,
                    weight_kg=weight_val,
                    quantity=qty_val,
                    planned_delivery=planned.date(),
                    actual_delivery=actual.date() if pd.notna(actual) else None,
                ))
                imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped, updated


def import_suppliers(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int, int]:
    imported, skipped, updated = 0, 0, 0
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("supplier_id")) or pd.isna(row.get("supplier_name")):
                skipped += 1
                continue
            ext_id = str(row["supplier_id"])
            # Natural key for Supplier: (company_id, external_supplier_id)
            existing = (
                db.query(Supplier)
                .filter(Supplier.company_id == company_id, Supplier.external_supplier_id == ext_id)
                .first()
            )
            if existing:
                existing.name = str(row["supplier_name"])
                if "lead_time" in df.columns and pd.notna(row.get("lead_time")):
                    existing.lead_time_days = float(row["lead_time"])
                if "reliability" in df.columns and pd.notna(row.get("reliability")):
                    existing.reliability = float(row["reliability"])
                if "cost" in df.columns and pd.notna(row.get("cost")):
                    existing.cost_index = float(row["cost"])
                if "defect_rate" in df.columns and pd.notna(row.get("defect_rate")):
                    existing.defect_rate = float(row["defect_rate"])
                updated += 1
            else:
                supplier = _get_or_create_supplier(db, company_id, ext_id, row.get("supplier_name"))
                supplier.name = str(row["supplier_name"])
                if "lead_time" in df.columns and pd.notna(row.get("lead_time")):
                    supplier.lead_time_days = float(row["lead_time"])
                if "reliability" in df.columns and pd.notna(row.get("reliability")):
                    supplier.reliability = float(row["reliability"])
                if "cost" in df.columns and pd.notna(row.get("cost")):
                    supplier.cost_index = float(row["cost"])
                if "defect_rate" in df.columns and pd.notna(row.get("defect_rate")):
                    supplier.defect_rate = float(row["defect_rate"])
                imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped, updated


IMPORTERS = {
    "sales": import_sales,
    "inventory": import_inventory,
    "shipments": import_shipments,
    "suppliers": import_suppliers,
}


def import_dataset(db: Session, company_id: int, dataset_type: str, df: pd.DataFrame) -> tuple[int, int, int]:
    """Runs the correct importer in a transactional block, commits, and returns (imported, skipped, updated)."""
    total_imported, total_skipped, total_updated = 0, 0, 0
    try:
        if dataset_type in IMPORTERS:
            total_imported, total_skipped, total_updated = IMPORTERS[dataset_type](db, company_id, df)
        else:
            for name, importer in IMPORTERS.items():
                imp, skp, upd = importer(db, company_id, df)
                total_imported += imp
                total_skipped += skp
                total_updated += upd
        db.commit()
    except Exception:
        db.rollback()
        raise
    return total_imported, total_skipped, total_updated


def revalidate_after_mapping(dataset_type: str, mapped_df: pd.DataFrame) -> dict:
    """Re-run validation on the already-mapped DataFrame right before import."""
    return validate_dataset(dataset_type, mapped_df)
