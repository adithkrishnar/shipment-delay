from app.services.column_mapping import suggest_column_mapping, unmapped_required_fields


def test_suggest_mapping_handles_exact_and_alias_names():
    mapping = suggest_column_mapping("sales", ["SKU", "Qty_Sold", "Date", "Region", "Unit_Price"])
    assert mapping["SKU"] == "product_id"
    assert mapping["Qty_Sold"] == "quantity"
    assert mapping["Date"] == "date"
    assert mapping["Region"] == "region"
    assert mapping["Unit_Price"] == "price"


def test_suggest_mapping_handles_differently_named_columns():
    """A second, unrelated company's schema should map correctly too - proves it's not hard-coded."""
    mapping = suggest_column_mapping("inventory", ["Product_ID", "Stock", "Delivery_Days", "Date"])
    assert mapping["Product_ID"] == "product_id"
    assert mapping["Stock"] == "inventory_level"
    assert mapping["Date"] == "date"
    # "Delivery_Days" isn't a valid inventory field (it's a supplier/shipment concept) - should be left unmapped
    assert mapping["Delivery_Days"] is None


def test_suggest_mapping_does_not_double_map_same_target():
    mapping = suggest_column_mapping("shipments", ["shipment_id", "product_id", "carrier", "Carrier_Name"])
    targets = [v for v in mapping.values() if v is not None]
    assert len(targets) == len(set(targets))  # no target field used twice


def test_unmapped_required_fields_detects_gaps():
    mapping = {"SKU": "product_id", "Qty_Sold": "quantity"}  # missing 'date'
    missing = unmapped_required_fields("sales", mapping)
    assert missing == ["date"]


def test_unmapped_required_fields_empty_when_complete():
    mapping = {"SKU": "product_id", "Qty_Sold": "quantity", "Date": "date"}
    missing = unmapped_required_fields("sales", mapping)
    assert missing == []
