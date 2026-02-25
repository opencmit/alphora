#!/usr/bin/env python3
"""
Universal Chart Generator

Generates common chart types from tabular data with Chinese font support
pre-configured. Designed to be called from the sandbox by the LLM.

Usage:
    python visualize.py --type TYPE --data FILE --x COL --y COL [options]

Chart Types:
    bar      - Bar chart (vertical)
    barh     - Bar chart (horizontal)
    line     - Line chart
    pie      - Pie chart (uses --x for labels, --y for values)
    scatter  - Scatter plot
    hist     - Histogram (uses --x only)
    box      - Box plot (uses --x for grouping, --y for values)
    heatmap  - Heatmap / correlation matrix (ignores --x and --y)

Examples:
    python visualize.py --type bar --data sales.csv --x month --y revenue --output chart.png
    python visualize.py --type line --data trend.csv --x date --y value --title "Monthly Trend"
    python visualize.py --type pie --data share.csv --x category --y amount
    python visualize.py --type heatmap --data data.csv --output corr.png
    python visualize.py --type hist --data data.csv --x age --bins 20
    python visualize.py --type bar --data data.csv --x month --y revenue --hue region
"""

import argparse
import os
import sys
from pathlib import Path


def setup_chinese_fonts():
    """Configure matplotlib to display Chinese characters."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    font_candidates = [
        "Source Han Sans CN",
        "WenQuanYi Micro Hei",
        "SimHei",
        "Microsoft YaHei",
        "PingFang SC",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["font.sans-serif"] = font_candidates
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def load_data(filepath: str, encoding: str = None):
    import pandas as pd

    ext = Path(filepath).suffix.lower()
    if encoding is None:
        encoding = "utf-8"

    if ext in (".csv", ".tsv", ".txt"):
        try:
            return pd.read_csv(filepath, encoding=encoding)
        except UnicodeDecodeError:
            return pd.read_csv(filepath, encoding="gbk")
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(filepath, engine="openpyxl")
    elif ext == ".json":
        return pd.read_json(filepath, encoding=encoding)
    elif ext == ".parquet":
        return pd.read_parquet(filepath)
    else:
        return pd.read_csv(filepath, encoding=encoding)


def chart_bar(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    if args.hue and args.hue in df.columns:
        pivot = df.pivot_table(index=args.x, columns=args.hue, values=args.y, aggfunc="sum")
        pivot.plot(kind="bar", ax=ax)
    else:
        ax.bar(df[args.x].astype(str), df[args.y])

    ax.set_xlabel(args.x)
    ax.set_ylabel(args.y)
    ax.set_title(args.title or f"{args.y} by {args.x}")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    return fig


def chart_barh(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    ax.barh(df[args.x].astype(str), df[args.y])
    ax.set_ylabel(args.x)
    ax.set_xlabel(args.y)
    ax.set_title(args.title or f"{args.y} by {args.x}")
    plt.tight_layout()
    return fig


def chart_line(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    if args.hue and args.hue in df.columns:
        for name, group in df.groupby(args.hue):
            ax.plot(group[args.x].astype(str), group[args.y], marker="o", label=str(name))
        ax.legend()
    else:
        ax.plot(df[args.x].astype(str), df[args.y], marker="o")

    ax.set_xlabel(args.x)
    ax.set_ylabel(args.y)
    ax.set_title(args.title or f"{args.y} Trend")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    return fig


def chart_pie(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    labels = df[args.x].astype(str)
    values = df[args.y]
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title(args.title or f"{args.y} Distribution")
    plt.tight_layout()
    return fig


def chart_scatter(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    if args.hue and args.hue in df.columns:
        for name, group in df.groupby(args.hue):
            ax.scatter(group[args.x], group[args.y], label=str(name), alpha=0.7)
        ax.legend()
    else:
        ax.scatter(df[args.x], df[args.y], alpha=0.7)

    ax.set_xlabel(args.x)
    ax.set_ylabel(args.y)
    ax.set_title(args.title or f"{args.x} vs {args.y}")
    plt.tight_layout()
    return fig


def chart_hist(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    ax.hist(df[args.x].dropna(), bins=args.bins, edgecolor="white", alpha=0.8)
    ax.set_xlabel(args.x)
    ax.set_ylabel("Frequency")
    ax.set_title(args.title or f"Distribution of {args.x}")
    plt.tight_layout()
    return fig


def chart_box(df, args):
    plt = setup_chinese_fonts()
    fig, ax = plt.subplots(figsize=(args.width, args.height))

    if args.x and args.y:
        groups = df.groupby(args.x)[args.y].apply(list).to_dict()
        labels = list(groups.keys())
        data = list(groups.values())
        ax.boxplot(data, labels=[str(l) for l in labels])
        ax.set_xlabel(args.x)
        ax.set_ylabel(args.y)
    else:
        col = args.y or args.x
        ax.boxplot(df[col].dropna())
        ax.set_ylabel(col)

    ax.set_title(args.title or "Box Plot")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    return fig


def chart_heatmap(df, args):
    plt = setup_chinese_fonts()
    import numpy as np

    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        print("[ERROR] No numeric columns found for heatmap.")
        sys.exit(1)

    corr = numeric_df.corr()
    fig, ax = plt.subplots(figsize=(args.width, args.height))
    im = ax.imshow(corr, cmap="RdBu_r", aspect="auto", vmin=-1, vmax=1)
    fig.colorbar(im, ax=ax, shrink=0.8)

    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.columns)

    for i in range(len(corr)):
        for j in range(len(corr)):
            val = corr.iloc[i, j]
            color = "white" if abs(val) > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=8)

    ax.set_title(args.title or "Correlation Heatmap")
    plt.tight_layout()
    return fig


CHART_FUNCTIONS = {
    "bar": chart_bar,
    "barh": chart_barh,
    "line": chart_line,
    "pie": chart_pie,
    "scatter": chart_scatter,
    "hist": chart_hist,
    "box": chart_box,
    "heatmap": chart_heatmap,
}


def main():
    parser = argparse.ArgumentParser(description="Universal chart generator")
    parser.add_argument("--type", required=True, choices=CHART_FUNCTIONS.keys(), help="Chart type")
    parser.add_argument("--data", required=True, help="Path to data file")
    parser.add_argument("--x", default=None, help="X-axis column name")
    parser.add_argument("--y", default=None, help="Y-axis column name")
    parser.add_argument("--hue", default=None, help="Grouping column for color coding")
    parser.add_argument("--title", default=None, help="Chart title")
    parser.add_argument("--output", default=None, help="Output file path (default: auto-generated)")
    parser.add_argument("--width", type=float, default=10, help="Figure width in inches")
    parser.add_argument("--height", type=float, default=6, help="Figure height in inches")
    parser.add_argument("--dpi", type=int, default=150, help="Output DPI")
    parser.add_argument("--bins", type=int, default=30, help="Number of bins for histogram")
    parser.add_argument("--encoding", default=None, help="File encoding")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"[ERROR] Data file not found: {args.data}")
        sys.exit(1)

    chart_type = args.type
    needs_x = chart_type not in ("heatmap",)
    needs_y = chart_type not in ("heatmap", "hist")

    if needs_x and not args.x:
        print(f"[ERROR] --x is required for chart type '{chart_type}'")
        sys.exit(1)
    if needs_y and not args.y:
        print(f"[ERROR] --y is required for chart type '{chart_type}'")
        sys.exit(1)

    df = load_data(args.data, args.encoding)
    print(f"Loaded {len(df)} rows from {args.data}")

    if args.x and args.x not in df.columns:
        print(f"[ERROR] Column '{args.x}' not found. Available: {list(df.columns)}")
        sys.exit(1)
    if args.y and args.y not in df.columns:
        print(f"[ERROR] Column '{args.y}' not found. Available: {list(df.columns)}")
        sys.exit(1)

    chart_fn = CHART_FUNCTIONS[chart_type]
    fig = chart_fn(df, args)

    if args.output is None:
        basename = Path(args.data).stem
        args.output = f"/mnt/workspace/{basename}_{chart_type}.png"

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    fig.savefig(args.output, dpi=args.dpi, bbox_inches="tight", facecolor="white")
    print(f"[OK] Chart saved: {args.output}")

    import matplotlib.pyplot as plt
    plt.close(fig)


if __name__ == "__main__":
    main()
