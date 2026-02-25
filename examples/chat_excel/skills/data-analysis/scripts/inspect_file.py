#!/usr/bin/env python3
"""
Quick File Structure Inspector

Inspects tabular data files (CSV, Excel, JSON, Parquet, TSV) and prints
a concise structural summary: file type, encoding, shape, column names
and dtypes, and a sample of the first N rows.

Usage:
    python inspect_file.py <file_path> [--rows N] [--encoding ENC]

Examples:
    python inspect_file.py /mnt/workspace/sales.csv
    python inspect_file.py /mnt/workspace/report.xlsx --rows 10
    python inspect_file.py /mnt/workspace/data.csv --encoding gbk
"""

import argparse
import json
import os
import sys
from pathlib import Path


def detect_encoding(filepath: str) -> str:
    """Detect file encoding using chardet if available, otherwise fallback."""
    try:
        import chardet
        with open(filepath, "rb") as f:
            raw = f.read(min(os.path.getsize(filepath), 100_000))
        result = chardet.detect(raw)
        return result.get("encoding") or "utf-8"
    except ImportError:
        return "utf-8"


def detect_separator(filepath: str, encoding: str) -> str:
    """Detect CSV separator by counting common delimiters in first lines."""
    candidates = [",", "\t", ";", "|"]
    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        sample = "".join(f.readline() for _ in range(5))
    counts = {sep: sample.count(sep) for sep in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def inspect_csv(filepath: str, encoding: str, nrows: int):
    import pandas as pd

    sep = detect_separator(filepath, encoding)
    try:
        df = pd.read_csv(filepath, encoding=encoding, sep=sep, nrows=nrows, low_memory=False)
    except UnicodeDecodeError:
        for fallback_enc in ["gbk", "gb18030", "latin1", "cp1252"]:
            try:
                df = pd.read_csv(filepath, encoding=fallback_enc, sep=sep, nrows=nrows, low_memory=False)
                encoding = fallback_enc
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            print(f"[ERROR] Cannot decode file with any known encoding.")
            return

    total_rows = sum(1 for _ in open(filepath, "r", encoding=encoding, errors="replace")) - 1

    print(f"  File Type    : CSV (separator='{sep}')")
    print(f"  Encoding     : {encoding}")
    print(f"  Total Rows   : {total_rows:,}")
    print(f"  Total Columns: {len(df.columns)}")
    print()

    _print_columns(df)
    _print_sample(df, nrows)


def inspect_excel(filepath: str, nrows: int):
    import pandas as pd

    xls = pd.ExcelFile(filepath, engine="openpyxl")
    sheet_names = xls.sheet_names
    print(f"  File Type    : Excel")
    print(f"  Sheets       : {sheet_names}")
    print()

    for sheet in sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, nrows=nrows)
        df_full = pd.read_excel(xls, sheet_name=sheet, nrows=0)
        total_rows_df = pd.read_excel(xls, sheet_name=sheet)

        print(f"  --- Sheet: '{sheet}' ---")
        print(f"  Rows   : {len(total_rows_df):,}")
        print(f"  Columns: {len(df.columns)}")
        _print_columns(df)
        _print_sample(df, nrows)
        print()


def inspect_json(filepath: str, encoding: str, nrows: int):
    import pandas as pd

    with open(filepath, "r", encoding=encoding) as f:
        data = json.load(f)

    if isinstance(data, list):
        df = pd.DataFrame(data[:nrows])
        total = len(data)
    elif isinstance(data, dict):
        if any(isinstance(v, list) for v in data.values()):
            df = pd.DataFrame(data)
            total = len(df)
            df = df.head(nrows)
        else:
            df = pd.DataFrame([data])
            total = 1
    else:
        print(f"  [WARN] Unexpected JSON root type: {type(data).__name__}")
        return

    print(f"  File Type    : JSON")
    print(f"  Total Records: {total:,}")
    print(f"  Total Columns: {len(df.columns)}")
    print()
    _print_columns(df)
    _print_sample(df, nrows)


def inspect_parquet(filepath: str, nrows: int):
    import pandas as pd

    df = pd.read_parquet(filepath)
    total = len(df)
    df_sample = df.head(nrows)

    print(f"  File Type    : Parquet")
    print(f"  Total Rows   : {total:,}")
    print(f"  Total Columns: {len(df.columns)}")
    print()
    _print_columns(df_sample)
    _print_sample(df_sample, nrows)


def _print_columns(df):
    print("  Columns:")
    for col in df.columns:
        non_null = df[col].notna().sum()
        total = len(df)
        null_pct = (1 - non_null / total) * 100 if total > 0 else 0
        null_info = f" ({null_pct:.0f}% null)" if null_pct > 0 else ""
        print(f"    - {col:<30s} {str(df[col].dtype):<15s}{null_info}")
    print()


def _print_sample(df, nrows: int):
    print(f"  Sample (first {min(nrows, len(df))} rows):")
    print(df.head(nrows).to_string(index=False, max_colwidth=50))
    print()


def main():
    parser = argparse.ArgumentParser(description="Quick file structure inspector")
    parser.add_argument("filepath", help="Path to the data file")
    parser.add_argument("--rows", type=int, default=5, help="Number of sample rows (default: 5)")
    parser.add_argument("--encoding", type=str, default=None, help="Force file encoding")
    args = parser.parse_args()

    filepath = args.filepath
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    size = os.path.getsize(filepath)
    print(f"\n=== File Inspection: {os.path.basename(filepath)} ===")
    print(f"  Path         : {filepath}")
    print(f"  Size         : {size:,} bytes ({size / 1024 / 1024:.2f} MB)")

    ext = Path(filepath).suffix.lower()
    encoding = args.encoding or detect_encoding(filepath)

    try:
        if ext in (".csv", ".tsv", ".txt"):
            inspect_csv(filepath, encoding, args.rows)
        elif ext in (".xlsx", ".xls"):
            inspect_excel(filepath, args.rows)
        elif ext == ".json":
            inspect_json(filepath, encoding, args.rows)
        elif ext == ".parquet":
            inspect_parquet(filepath, args.rows)
        else:
            print(f"  [WARN] Unsupported file extension: {ext}")
            print(f"  Trying CSV parser as fallback...")
            inspect_csv(filepath, encoding, args.rows)
    except Exception as e:
        print(f"  [ERROR] Inspection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
