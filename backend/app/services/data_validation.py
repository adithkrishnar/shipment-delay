"""
Data validation & quality scoring.

Runs on a pandas DataFrame that has ALREADY been renamed to standard field
names (see services/data_import.py, which applies the column mapping before
calling this). Produces a ValidationReport-shaped dict with errors, warnings,
and a 0-100 data quality score.
"""
from __future__ import annotations

import pandas as pd

from app.services.schema_registry import STANDARD_SCHEMA


def _is_missing(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def validate_dataset(dataset_type: str, df: pd.DataFrame) -> dict:
    schema = STANDARD_SCHEMA[dataset_type]
    required_fields = schema["required"]

    errors: list[dict] = []
    warnings: list[dict] = []

    row_count = len(df)
    missing_required_fields = [f for f in required_fields if f not in df.columns]
    for field in missing_required_fields:
        errors.append({
            "field": field, "row": None, "severity": "error",
            "message": f"Required field '{field}' is not mapped to any column.",
        })

    invalid_row_mask = pd.Series(False, index=df.index)

    # --- Missing values in required fields that ARE present ---
    for field in required_fields:
        if field not in df.columns:
            continue
        missing_mask = _is_missing(df[field])
        n_missing = int(missing_mask.sum())
        if n_missing > 0:
            severity = "error" if n_missing / max(row_count, 1) > 0.02 else "warning"
            (errors if severity == "error" else warnings).append({
                "field": field, "row": None, "severity": severity,
                "message": f"{n_missing} row(s) missing required value for '{field}'.",
            })
            invalid_row_mask |= missing_mask

    # --- Duplicate rows ---
    key_cols = [c for c in ("product_id", "date", "shipment_id", "supplier_id") if c in df.columns]
    if key_cols:
        dup_mask = df.duplicated(subset=key_cols, keep="first")
        n_dupes = int(dup_mask.sum())
        if n_dupes > 0:
            warnings.append({
                "field": None, "row": None, "severity": "warning",
                "message": f"{n_dupes} duplicate row(s) detected based on {key_cols}.",
            })

    # --- Dataset-specific numeric/date sanity checks ---
    if dataset_type == "sales":
        if "quantity" in df.columns:
            neg_mask = pd.to_numeric(df["quantity"], errors="coerce") < 0
            n_neg = int(neg_mask.fillna(False).sum())
            if n_neg:
                errors.append({
                    "field": "quantity", "row": None, "severity": "error",
                    "message": f"{n_neg} row(s) have negative quantity sold.",
                })
                invalid_row_mask |= neg_mask.fillna(False)
        if "date" in df.columns:
            bad_dates = pd.to_datetime(df["date"], errors="coerce").isna() & ~_is_missing(df["date"])
            n_bad = int(bad_dates.sum())
            if n_bad:
                errors.append({
                    "field": "date", "row": None, "severity": "error",
                    "message": f"{n_bad} row(s) have an unparseable date.",
                })
                invalid_row_mask |= bad_dates

    if dataset_type == "inventory":
        if "inventory_level" in df.columns:
            neg_mask = pd.to_numeric(df["inventory_level"], errors="coerce") < 0
            n_neg = int(neg_mask.fillna(False).sum())
            if n_neg:
                errors.append({
                    "field": "inventory_level", "row": None, "severity": "error",
                    "message": f"{n_neg} row(s) have negative inventory levels.",
                })
                invalid_row_mask |= neg_mask.fillna(False)

    if dataset_type == "shipments":
        if {"planned_delivery", "actual_delivery"}.issubset(df.columns):
            planned = pd.to_datetime(df["planned_delivery"], errors="coerce")
            actual = pd.to_datetime(df["actual_delivery"], errors="coerce")
            bad_order = actual.notna() & planned.notna() & (actual < planned - pd.Timedelta(days=365))
            n_bad = int(bad_order.sum())
            if n_bad:
                warnings.append({
                    "field": "actual_delivery", "row": None, "severity": "warning",
                    "message": f"{n_bad} row(s) have an actual delivery date implausibly earlier than planned.",
                })
        if "distance" in df.columns:
            neg_mask = pd.to_numeric(df["distance"], errors="coerce") < 0
            if neg_mask.fillna(False).any():
                warnings.append({
                    "field": "distance", "row": None, "severity": "warning",
                    "message": "Some rows have a negative distance value.",
                })

    if dataset_type == "suppliers":
        if "lead_time" in df.columns:
            impossible = pd.to_numeric(df["lead_time"], errors="coerce") < 0
            n_bad = int(impossible.fillna(False).sum())
            if n_bad:
                errors.append({
                    "field": "lead_time", "row": None, "severity": "error",
                    "message": f"{n_bad} row(s) have a negative/impossible lead time.",
                })
                invalid_row_mask |= impossible.fillna(False)
        if "reliability" in df.columns:
            out_of_range = ~pd.to_numeric(df["reliability"], errors="coerce").between(0, 1)
            n_bad = int(out_of_range.fillna(False).sum())
            if n_bad:
                warnings.append({
                    "field": "reliability", "row": None, "severity": "warning",
                    "message": f"{n_bad} row(s) have a reliability value outside the expected 0-1 range.",
                })

    valid_row_count = row_count - int(invalid_row_mask.sum())

    # --- Score: start at 100, deduct for errors/warnings proportionally ---
    score = 100.0
    if row_count > 0:
        score -= 40 * (int(invalid_row_mask.sum()) / row_count)
    score -= 15 * len(missing_required_fields)
    score -= 2 * len(warnings)
    score = max(0, min(100, round(score)))

    return {
        "data_quality_score": int(score),
        "row_count": row_count,
        "valid_row_count": max(valid_row_count, 0),
        "errors": errors,
        "warnings": warnings,
        "missing_required_fields": missing_required_fields,
    }
