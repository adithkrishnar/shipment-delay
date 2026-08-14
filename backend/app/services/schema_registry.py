"""
Standard internal data schema.

Every dataset type has required and optional standard fields. Each standard
field carries a list of common aliases so the column-mapping service can
suggest a mapping regardless of what a given company happens to call it.
"""

STANDARD_SCHEMA: dict[str, dict[str, list]] = {
    "sales": {
        "required": ["date", "product_id", "quantity"],
        "optional": ["region", "price", "promotion", "category"],
    },
    "inventory": {
        "required": ["date", "product_id", "inventory_level"],
        "optional": ["warehouse", "safety_stock"],
    },
    "shipments": {
        "required": [
            "shipment_id", "product_id", "origin", "destination",
            "planned_delivery", "actual_delivery",
        ],
        "optional": ["carrier", "distance", "weight", "transport_mode", "quantity"],
    },
    "suppliers": {
        "required": ["supplier_id", "supplier_name"],
        "optional": ["lead_time", "reliability", "cost", "defect_rate"],
    },
}

# Aliases: standard_field -> list of normalized (lowercase, no separators) synonyms
FIELD_ALIASES: dict[str, list[str]] = {
    "date": ["date", "orderdate", "saledate", "transactiondate", "day"],
    "product_id": ["productid", "sku", "itemid", "itemcode", "productcode", "product"],
    "quantity": ["quantity", "qtysold", "unitssold", "qty", "salesqty", "demand", "unitssold"],
    "region": ["region", "market", "territory", "zone"],
    "price": ["price", "unitprice", "saleprice"],
    "promotion": ["promotion", "promo", "onpromotion", "ispromo"],
    "category": ["category", "productcategory", "segment"],

    "inventory_level": ["inventorylevel", "stock", "stocklevel", "onhand", "inventory", "qtyonhand"],
    "warehouse": ["warehouse", "warehousename", "location", "dc", "distributioncenter"],
    "safety_stock": ["safetystock", "minstock", "bufferstock"],

    "shipment_id": ["shipmentid", "shipmentno", "shipment"],
    "origin": ["origin", "source", "shipfrom", "originport"],
    "destination": ["destination", "shipto", "destinationport"],
    "planned_delivery": ["planneddelivery", "expecteddelivery", "eta", "plandate", "duedate"],
    "actual_delivery": ["actualdelivery", "deliverydate", "receiveddate", "arrivaldate"],
    "carrier": ["carrier", "shippingcarrier", "transporter", "courier"],
    "distance": ["distance", "distancekm", "distancemiles"],
    "weight": ["weight", "weightkg", "shipmentweight"],
    "transport_mode": ["transportmode", "mode", "shippingmode"],

    "supplier_id": ["supplierid", "vendorid", "supplierno"],
    "supplier_name": ["suppliername", "vendorname", "supplier"],
    "lead_time": ["leadtime", "leadtimedays", "deliverydays", "avgleadtime"],
    "reliability": ["reliability", "ontimerate", "reliabilityscore"],
    "cost": ["cost", "unitcost", "costindex"],
    "defect_rate": ["defectrate", "qualityissuerate", "rejectrate"],
}


def normalize_column_name(name: str) -> str:
    """Lowercase and strip separators for fuzzy comparison, e.g. 'Qty_Sold' -> 'qtysold'."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def all_standard_fields(dataset_type: str) -> list[str]:
    schema = STANDARD_SCHEMA[dataset_type]
    return schema["required"] + schema["optional"]
