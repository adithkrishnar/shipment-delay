"""
Column mapping service.

Given the raw column headers from an uploaded file, suggest a mapping from
each source column to a standard internal field, using:
  1. Exact normalized-name match
  2. Known alias match
  3. Fuzzy string similarity as a fallback

This never assumes exact column names from the company - see project spec
section "DATA UPLOAD SYSTEM".
"""
import difflib

from app.services.schema_registry import (
    FIELD_ALIASES,
    STANDARD_SCHEMA,
    all_standard_fields,
    normalize_column_name,
)

FUZZY_MATCH_THRESHOLD = 0.72


def _alias_lookup(normalized_col: str) -> str | None:
    for standard_field, aliases in FIELD_ALIASES.items():
        if normalized_col in aliases:
            return standard_field
    return None


def _fuzzy_lookup(normalized_col: str, candidate_fields: list[str]) -> str | None:
    """Fall back to closest alias by string similarity."""
    best_field, best_score = None, 0.0
    for standard_field in candidate_fields:
        aliases = FIELD_ALIASES.get(standard_field, [standard_field])
        for alias in aliases:
            score = difflib.SequenceMatcher(None, normalized_col, alias).ratio()
            if score > best_score:
                best_score, best_field = score, standard_field
    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_field
    return None


def suggest_column_mapping(dataset_type: str, source_columns: list[str]) -> dict[str, str | None]:
    """
    Returns {source_column: standard_field_or_None}.

    A standard field is only suggested once - if two source columns would
    both fuzzy-match the same standard field, only the stronger match keeps it.
    """
    if dataset_type not in STANDARD_SCHEMA:
        raise ValueError(f"Unknown dataset_type: {dataset_type}")

    candidate_fields = all_standard_fields(dataset_type)
    mapping: dict[str, str | None] = {}
    used_standard_fields: set[str] = set()

    # Pass 1: exact normalized match + alias match (highest confidence)
    for col in source_columns:
        norm = normalize_column_name(col)
        match = norm if norm in candidate_fields else _alias_lookup(norm)
        if match and match in candidate_fields and match not in used_standard_fields:
            mapping[col] = match
            used_standard_fields.add(match)
        else:
            mapping[col] = None

    # Pass 2: fuzzy match for anything still unmapped
    remaining_fields = [f for f in candidate_fields if f not in used_standard_fields]
    for col in source_columns:
        if mapping[col] is not None:
            continue
        norm = normalize_column_name(col)
        match = _fuzzy_lookup(norm, remaining_fields)
        if match:
            mapping[col] = match
            used_standard_fields.add(match)
            remaining_fields.remove(match)

    return mapping


def unmapped_required_fields(dataset_type: str, column_mapping: dict[str, str | None]) -> list[str]:
    required = STANDARD_SCHEMA[dataset_type]["required"]
    mapped_targets = {v for v in column_mapping.values() if v is not None}
    return [f for f in required if f not in mapped_targets]
