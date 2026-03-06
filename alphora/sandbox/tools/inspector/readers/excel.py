"""
Excel / CSV Reader

依赖:
- .xlsx / .xls → openpyxl (可选依赖，未安装时给出清晰提示)
- .csv → stdlib csv 模块，无额外依赖
"""

import csv
import io
import os
from typing import Optional, Union

from alphora.sandbox.tools.inspector.readers import FileContent, get_file_type


def _read_csv(text: str, path: str, size: int) -> FileContent:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return FileContent(
            text="(empty CSV file)",
            total_lines=0,
            file_type="csv",
            size=size,
            metadata={"rows": 0, "columns": 0},
        )

    headers = rows[0]
    data_rows = rows[1:]
    num_cols = len(headers)

    col_widths = [len(str(h)) for h in headers]
    for row in data_rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(str(cell)))

    max_col_width = 30
    col_widths = [min(w, max_col_width) for w in col_widths]

    def fmt_row(cells, widths):
        parts = []
        for i, cell in enumerate(cells):
            w = widths[i] if i < len(widths) else max_col_width
            val = str(cell)
            if len(val) > w:
                val = val[: w - 1] + "…"
            parts.append(val.ljust(w))
        return "| " + " | ".join(parts) + " |"

    lines = [fmt_row(headers, col_widths)]
    lines.append("|" + "|".join("-" * (w + 2) for w in col_widths) + "|")
    for row in data_rows:
        padded = row + [""] * (num_cols - len(row))
        lines.append(fmt_row(padded[:num_cols], col_widths))

    formatted = "\n".join(lines)
    return FileContent(
        text=formatted,
        total_lines=len(data_rows),
        file_type="csv",
        size=size,
        metadata={
            "rows": len(data_rows),
            "columns": num_cols,
            "headers": headers,
        },
    )


def _read_xlsx(data: bytes, path: str, size: int, sheet: Optional[str] = None) -> FileContent:
    try:
        import openpyxl
    except ImportError:
        return FileContent(
            text="[Error] openpyxl is required to read Excel files. Install: pip install openpyxl",
            total_lines=0,
            file_type="excel",
            size=size,
            metadata={"error": "missing_dependency"},
        )

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    ws = wb[sheet] if sheet and sheet in sheet_names else wb.active
    active_sheet = ws.title

    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([str(cell) if cell is not None else "" for cell in row])

    wb.close()

    if not rows:
        return FileContent(
            text=f"{os.path.basename(path)} — Sheet: {active_sheet} (empty)",
            total_lines=0,
            file_type="excel",
            size=size,
            metadata={
                "sheets": sheet_names,
                "active_sheet": active_sheet,
                "rows": 0,
                "columns": 0,
            },
        )

    headers = rows[0]
    data_rows = rows[1:]
    num_cols = len(headers)

    col_widths = [len(h) for h in headers]
    for row in data_rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))

    max_col_width = 30
    col_widths = [min(w, max_col_width) for w in col_widths]

    def fmt_row(cells, widths):
        parts = []
        for i, cell in enumerate(cells):
            w = widths[i] if i < len(widths) else max_col_width
            val = cell if len(cell) <= w else cell[: w - 1] + "…"
            parts.append(val.ljust(w))
        return "| " + " | ".join(parts) + " |"

    header_line = f"{os.path.basename(path)} — Sheet: {active_sheet} ({len(data_rows)} rows x {num_cols} cols)\n"
    table_lines = [fmt_row(headers, col_widths)]
    table_lines.append("|" + "|".join("-" * (w + 2) for w in col_widths) + "|")
    for row in data_rows:
        padded = row + [""] * (num_cols - len(row))
        table_lines.append(fmt_row(padded[:num_cols], col_widths))

    formatted = header_line + "\n".join(table_lines)
    return FileContent(
        text=formatted,
        total_lines=len(data_rows),
        file_type="excel",
        size=size,
        metadata={
            "sheets": sheet_names,
            "active_sheet": active_sheet,
            "rows": len(data_rows),
            "columns": num_cols,
            "headers": headers,
        },
    )


def read(
        data: Union[str, bytes],
        path: str,
        size: int,
        sheet: Optional[str] = None,
        **_kwargs,
) -> FileContent:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return _read_csv(data if isinstance(data, str) else data.decode("utf-8"), path, size)
    return _read_xlsx(data if isinstance(data, bytes) else data.encode("utf-8"), path, size, sheet)
