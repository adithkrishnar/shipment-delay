import pandas as pd

from app.services.data_validation import validate_dataset


def test_validate_clean_sales_data_scores_100():
    df = pd.DataFrame({
        "product_id": ["P1", "P2", "P3"],
        "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "quantity": [10, 20, 30],
    })
    report = validate_dataset("sales", df)
    assert report["data_quality_score"] == 100
    assert report["errors"] == []
    assert report["valid_row_count"] == 3


def test_validate_catches_negative_quantity():
    df = pd.DataFrame({
        "product_id": ["P1", "P2"],
        "date": ["2026-01-01", "2026-01-02"],
        "quantity": [10, -5],
    })
    report = validate_dataset("sales", df)
    assert any("negative" in e["message"] for e in report["errors"])
    assert report["data_quality_score"] < 100


def test_validate_catches_missing_required_values():
    df = pd.DataFrame({
        "product_id": ["P1", None],
        "date": ["2026-01-01", "2026-01-02"],
        "quantity": [10, 20],
    })
    report = validate_dataset("sales", df)
    assert any("missing required value" in e["message"] for e in report["errors"])


def test_validate_catches_missing_required_field_entirely():
    df = pd.DataFrame({"product_id": ["P1"], "date": ["2026-01-01"]})  # no quantity column at all
    report = validate_dataset("sales", df)
    assert "quantity" in report["missing_required_fields"]
    assert report["data_quality_score"] < 100


def test_validate_negative_inventory_flagged():
    df = pd.DataFrame({
        "product_id": ["P1", "P2"],
        "date": ["2026-01-01", "2026-01-02"],
        "inventory_level": [100, -10],
    })
    report = validate_dataset("inventory", df)
    assert any("negative" in e["message"] for e in report["errors"])


def test_validate_supplier_reliability_out_of_range_is_warning_not_error():
    df = pd.DataFrame({
        "supplier_id": ["S1", "S2"],
        "supplier_name": ["Acme", "Globex"],
        "reliability": [0.9, 1.5],  # 1.5 is out of the valid 0-1 range
    })
    report = validate_dataset("suppliers", df)
    assert any("reliability" in w["message"] for w in report["warnings"])
