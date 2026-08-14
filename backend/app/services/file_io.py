"""
Safe file reading for uploaded datasets.
"""
from pathlib import Path

import pandas as pd


def read_tabular_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    # Normalize column headers: strip whitespace, keep original case for display
    df.columns = [str(c).strip() for c in df.columns]
    return df


def preview_rows(df: pd.DataFrame, n: int = 10) -> list[dict]:
    preview_df = df.head(n).where(pd.notna(df.head(n)), None)
    return preview_df.to_dict(orient="records")
