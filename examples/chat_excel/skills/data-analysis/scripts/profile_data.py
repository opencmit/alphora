#!/usr/bin/env python3
"""
Deep Data Profiling Script

Generates a comprehensive profile of a tabular data file including:
- Per-column statistics (mean, median, std, min, max, quartiles)
- Missing value analysis
- Unique value counts and top frequent values
- Data type distribution
- Numeric column distribution characteristics (skewness, kurtosis)

Usage:
    python profile_data.py <file_path> [--output report.json] [--encoding ENC]

Examples:
    python profile_data.py /mnt/workspace/sales.csv
    python profile_data.py /mnt/workspace/data.xlsx --output /mnt/workspace/profile.json
"""

import argparse
import json
import os
import sys
from pathlib import Path


def detect_encoding(filepath: str) -> str:
    try:
        import chardet
        with open(filepath, "rb") as f:
            raw = f.read(min(os.path.getsize(filepath), 100_000))
        result = chardet.detect(raw)
        return result.get("encoding") or "utf-8"
    except ImportError:
        return "utf-8"


def load_dataframe(filepath: str, encoding: str):
    import pandas as pd

    ext = Path(filepath).suffix.lower()

    if ext in (".csv", ".tsv", ".txt"):
        try:
            df = pd.read_csv(filepath, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            for enc in ["gbk", "gb18030", "latin1"]:
                try:
                    df = pd.read_csv(filepath, encoding=enc, low_memory=False)
                    break
                except (UnicodeDecodeError, Exception):
                    continue
            else:
                raise ValueError("Cannot decode CSV with any known encoding")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath, engine="openpyxl")
    elif ext == ".json":
        df = pd.read_json(filepath, encoding=encoding)
    elif ext == ".parquet":
        df = pd.read_parquet(filepath)
    else:
        df = pd.read_csv(filepath, encoding=encoding, low_memory=False)

    return df


def profile_column(series):
    import pandas as pd
    import numpy as np

    profile = {
        "dtype": str(series.dtype),
        "total_count": int(len(series)),
        "non_null_count": int(series.notna().sum()),
        "null_count": int(series.isna().sum()),
        "null_percent": round(series.isna().mean() * 100, 2),
        "unique_count": int(series.nunique()),
    }

    if pd.api.types.is_numeric_dtype(series):
        desc = series.describe()
        profile["type_category"] = "numeric"
        profile["stats"] = {
            "mean": _safe_num(desc.get("mean")),
            "std": _safe_num(desc.get("std")),
            "min": _safe_num(desc.get("min")),
            "25%": _safe_num(desc.get("25%")),
            "50%": _safe_num(desc.get("50%")),
            "75%": _safe_num(desc.get("75%")),
            "max": _safe_num(desc.get("max")),
        }
        clean = series.dropna()
        if len(clean) > 0:
            profile["stats"]["skewness"] = _safe_num(clean.skew())
            profile["stats"]["kurtosis"] = _safe_num(clean.kurtosis())
            profile["stats"]["zeros"] = int((clean == 0).sum())
            profile["stats"]["negatives"] = int((clean < 0).sum())

    elif pd.api.types.is_datetime64_any_dtype(series):
        profile["type_category"] = "datetime"
        clean = series.dropna()
        if len(clean) > 0:
            profile["stats"] = {
                "min": str(clean.min()),
                "max": str(clean.max()),
                "range_days": (clean.max() - clean.min()).days,
            }
    else:
        profile["type_category"] = "categorical"
        clean = series.dropna().astype(str)
        if len(clean) > 0:
            top_values = clean.value_counts().head(10)
            profile["top_values"] = {str(k): int(v) for k, v in top_values.items()}
            lengths = clean.str.len()
            profile["string_stats"] = {
                "min_length": int(lengths.min()),
                "max_length": int(lengths.max()),
                "mean_length": round(float(lengths.mean()), 1),
            }

    return profile


def _safe_num(val):
    """Convert numpy/pandas numeric to Python native, handle NaN/Inf."""
    import math
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None


def generate_profile(df):
    import pandas as pd

    result = {
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "dtype_summary": df.dtypes.astype(str).value_counts().to_dict(),
        "columns": {},
    }

    duplicate_count = df.duplicated().sum()
    result["duplicate_rows"] = int(duplicate_count)

    for col in df.columns:
        result["columns"][col] = profile_column(df[col])

    return result


def print_profile(profile: dict):
    """Print a human-readable profile summary."""
    shape = profile["shape"]
    print(f"\n{'='*60}")
    print(f"  DATA PROFILE REPORT")
    print(f"{'='*60}")
    print(f"  Rows           : {shape['rows']:,}")
    print(f"  Columns        : {shape['columns']}")
    print(f"  Memory Usage   : {profile['memory_usage_mb']:.2f} MB")
    print(f"  Duplicate Rows : {profile['duplicate_rows']:,}")
    print(f"  Dtype Summary  : {profile['dtype_summary']}")
    print()

    for col_name, col_prof in profile["columns"].items():
        cat = col_prof["type_category"]
        null_pct = col_prof["null_percent"]
        unique = col_prof["unique_count"]

        print(f"  --- {col_name} ({cat}, {col_prof['dtype']}) ---")
        print(f"      Non-null: {col_prof['non_null_count']:,} / {col_prof['total_count']:,}"
              f"  |  Null: {null_pct}%  |  Unique: {unique:,}")

        if cat == "numeric" and "stats" in col_prof:
            s = col_prof["stats"]
            print(f"      Mean={s['mean']}  Std={s['std']}  "
                  f"Min={s['min']}  25%={s['25%']}  50%={s['50%']}  "
                  f"75%={s['75%']}  Max={s['max']}")
            if "skewness" in s:
                print(f"      Skew={s['skewness']}  Kurt={s['kurtosis']}  "
                      f"Zeros={s.get('zeros', 0)}  Negatives={s.get('negatives', 0)}")

        elif cat == "datetime" and "stats" in col_prof:
            s = col_prof["stats"]
            print(f"      Range: {s['min']} ~ {s['max']} ({s['range_days']} days)")

        elif cat == "categorical":
            if "top_values" in col_prof:
                top = list(col_prof["top_values"].items())[:5]
                top_str = ", ".join(f"'{k}'({v})" for k, v in top)
                print(f"      Top values: {top_str}")
            if "string_stats" in col_prof:
                ss = col_prof["string_stats"]
                print(f"      String length: min={ss['min_length']} max={ss['max_length']} avg={ss['mean_length']}")

        print()

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Deep data profiling")
    parser.add_argument("filepath", help="Path to the data file")
    parser.add_argument("--output", type=str, default=None, help="Save profile as JSON")
    parser.add_argument("--encoding", type=str, default=None, help="Force file encoding")
    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"[ERROR] File not found: {args.filepath}")
        sys.exit(1)

    encoding = args.encoding or detect_encoding(args.filepath)
    print(f"Loading {args.filepath} (encoding: {encoding})...")

    try:
        df = load_dataframe(args.filepath, encoding)
    except Exception as e:
        print(f"[ERROR] Failed to load file: {e}")
        sys.exit(1)

    profile = generate_profile(df)
    print_profile(profile)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] Profile saved to {args.output}")


if __name__ == "__main__":
    main()
