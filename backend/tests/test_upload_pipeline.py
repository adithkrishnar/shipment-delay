import io


def _make_company(client, name="Test Widgets Ltd"):
    r = client.post("/api/companies", json={"name": name, "industry": "Manufacturing"})
    assert r.status_code == 201
    return r.json()["id"]


def _csv_bytes(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode("utf-8"))


SAMPLE_SALES_CSV = (
    "SKU,Qty_Sold,Date,Region,Unit_Price\n"
    "WIDGET-001,120,2026-01-05,North,499.0\n"
    "WIDGET-002,85,2026-01-05,South,299.0\n"
    "WIDGET-001,,2026-01-06,North,499.0\n"          # missing quantity -> should be skipped
    "WIDGET-002,-5,2026-01-06,South,299.0\n"        # negative quantity -> should be skipped
    "WIDGET-001,140,2026-01-07,North,499.0\n"
)


def test_full_upload_validate_map_import_pipeline(client):
    company_id = _make_company(client)

    r = client.post(
        "/api/upload",
        data={"company_id": company_id, "dataset_type": "sales"},
        files={"file": ("external_sales.csv", _csv_bytes(SAMPLE_SALES_CSV), "text/csv")},
    )
    assert r.status_code == 200
    upload = r.json()
    assert upload["row_count"] == 5
    assert upload["suggested_mapping"]["SKU"] == "product_id"
    assert upload["suggested_mapping"]["Qty_Sold"] == "quantity"
    upload_id = upload["upload_id"]
    mapping = upload["suggested_mapping"]

    r = client.post("/api/data/validate", json={"upload_id": upload_id, "column_mapping": mapping})
    assert r.status_code == 200
    validation = r.json()
    assert validation["valid_row_count"] == 3
    assert len(validation["errors"]) == 2  # one missing value, one negative value

    r = client.post("/api/data/map", json={"upload_id": upload_id, "column_mapping": mapping})
    assert r.status_code == 200
    assert r.json()["status"] == "mapped"

    r = client.post("/api/data/import", params={"company_id": company_id, "upload_id": upload_id})
    assert r.status_code == 200
    result = r.json()
    assert result["imported_row_count"] == 3
    assert result["skipped_row_count"] == 2
    assert result["status"] == "imported"

    r = client.get(f"/api/data/uploads/{company_id}")
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert history[0]["status"] == "imported"


def test_import_rejects_when_required_field_unmapped(client):
    company_id = _make_company(client, "Incomplete Mapping Co")

    r = client.post(
        "/api/upload",
        data={"company_id": company_id, "dataset_type": "sales"},
        files={"file": ("sales.csv", _csv_bytes(SAMPLE_SALES_CSV), "text/csv")},
    )
    upload_id = r.json()["upload_id"]

    incomplete_mapping = {"SKU": "product_id", "Qty_Sold": "quantity"}  # date not mapped
    r = client.post("/api/data/map", json={"upload_id": upload_id, "column_mapping": incomplete_mapping})
    assert r.json()["unmapped_required_fields"] == ["date"]

    r = client.post("/api/data/import", params={"company_id": company_id, "upload_id": upload_id})
    assert r.status_code == 400


def test_upload_rejects_unsupported_file_type(client):
    company_id = _make_company(client, "Bad File Co")
    r = client.post(
        "/api/upload",
        data={"company_id": company_id, "dataset_type": "sales"},
        files={"file": ("sales.txt", _csv_bytes("not,real,csv"), "text/plain")},
    )
    assert r.status_code == 400


def test_upload_rejects_invalid_dataset_type(client):
    company_id = _make_company(client, "Bad Type Co")
    r = client.post(
        "/api/upload",
        data={"company_id": company_id, "dataset_type": "not_a_real_type"},
        files={"file": ("sales.csv", _csv_bytes(SAMPLE_SALES_CSV), "text/csv")},
    )
    assert r.status_code == 400


def test_companies_endpoint_isolates_data_per_company(client):
    company_a = _make_company(client, "Company A")
    company_b = _make_company(client, "Company B")

    client.post(
        "/api/upload",
        data={"company_id": company_a, "dataset_type": "sales"},
        files={"file": ("a.csv", _csv_bytes(SAMPLE_SALES_CSV), "text/csv")},
    )

    r = client.get(f"/api/data/uploads/{company_a}")
    assert len(r.json()) == 1

    r = client.get(f"/api/data/uploads/{company_b}")
    assert len(r.json()) == 0  # company B must never see company A's uploads
