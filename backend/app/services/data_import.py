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


def import_sales(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int]:
    imported, skipped = 0, 0
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("product_id")) or pd.isna(row.get("date")) or pd.isna(row.get("quantity")):
                skipped += 1
                continue
            product = _get_or_create_product(db, company_id, row["product_id"])
            date_val = pd.to_datetime(row["date"], errors="coerce")
            if pd.isna(date_val):
                skipped += 1
                continue
            qty = float(row["quantity"])
            if qty < 0:
                skipped += 1
                continue
            db.add(Sale(
                company_id=company_id,
                product_id=product.id,
                date=date_val.date(),
                quantity=qty,
                region=str(row["region"]) if "region" in df.columns and pd.notna(row.get("region")) else None,
                price=float(row["price"]) if "price" in df.columns and pd.notna(row.get("price")) else None,
                promotion=int(bool(row.get("promotion"))) if "promotion" in df.columns and pd.notna(row.get("promotion")) else 0,
            ))
            imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped


def import_inventory(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int]:
    imported, skipped = 0, 0
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
            db.add(InventoryRecord(
                company_id=company_id,
                product_id=product.id,
                warehouse_id=warehouse.id if warehouse else None,
                date=date_val.date(),
                inventory_level=level,
                safety_stock=float(row["safety_stock"]) if "safety_stock" in df.columns and pd.notna(row.get("safety_stock")) else None,
            ))
            imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped


def import_shipments(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int]:
    imported, skipped = 0, 0
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

            db.add(Shipment(
                company_id=company_id,
                product_id=product.id,
                external_shipment_id=str(row["shipment_id"]),
                origin=str(row["origin"]) if "origin" in df.columns and pd.notna(row.get("origin")) else None,
                destination=str(row["destination"]) if "destination" in df.columns and pd.notna(row.get("destination")) else None,
                carrier=str(row["carrier"]) if "carrier" in df.columns and pd.notna(row.get("carrier")) else None,
                transport_mode=str(row["transport_mode"]) if "transport_mode" in df.columns and pd.notna(row.get("transport_mode")) else None,
                distance_km=float(row["distance"]) if "distance" in df.columns and pd.notna(row.get("distance")) else None,
                weight_kg=float(row["weight"]) if "weight" in df.columns and pd.notna(row.get("weight")) else None,
                quantity=float(row["quantity"]) if "quantity" in df.columns and pd.notna(row.get("quantity")) else None,
                planned_delivery=planned.date(),
                actual_delivery=actual.date() if pd.notna(actual) else None,
            ))
            imported += 1
        except (ValueError, TypeError):
            skipped += 1
    return imported, skipped


def import_suppliers(db: Session, company_id: int, df: pd.DataFrame) -> tuple[int, int]:
    imported, skipped = 0, 0
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("supplier_id")) or pd.isna(row.get("supplier_name")):
                skipped += 1
                continue
            supplier = _get_or_create_supplier(db, company_id, row["supplier_id"], row.get("supplier_name"))
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
    return imported, skipped


IMPORTERS = {
    "sales": import_sales,
    "inventory": import_inventory,
    "shipments": import_shipments,
    "suppliers": import_suppliers,
}


def import_dataset(db: Session, company_id: int, dataset_type: str, df: pd.DataFrame) -> tuple[int, int]:
    """Runs the correct importer, commits, and returns (imported_count, skipped_count)."""
    importer = IMPORTERS[dataset_type]
    imported, skipped = importer(db, company_id, df)
    db.commit()
    return imported, skipped


def revalidate_after_mapping(dataset_type: str, mapped_df: pd.DataFrame) -> dict:
    """Re-run validation on the already-mapped DataFrame right before import."""
    return validate_dataset(dataset_type, mapped_df)
