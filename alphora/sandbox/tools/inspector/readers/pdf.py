"""
PDF Reader
"""

import io
from typing import Optional

from alphora.sandbox.tools.inspector.readers import FileContent


def read(data: bytes, path: str, size: int, page: Optional[int] = None, **_kwargs) -> FileContent:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return FileContent(
                text="[Error] pypdf is required to read PDF files. Install: pip install pypdf",
                total_lines=0,
                file_type="pdf",
                size=size,
                metadata={"error": "missing_dependency"},
            )

    reader = PdfReader(io.BytesIO(data))
    total_pages = len(reader.pages)

    doc_info = reader.metadata or {}
    title = str(doc_info.get("/Title", "")) if doc_info else ""

    if page is not None:
        if page < 1 or page > total_pages:
            return FileContent(
                text=f"[Error] Page {page} out of range (1-{total_pages})",
                total_lines=0,
                file_type="pdf",
                size=size,
                metadata={"pages": total_pages, "title": title},
            )
        page_text = reader.pages[page - 1].extract_text() or ""
        text = f"── Page {page} of {total_pages} ──\n\n{page_text}"
    else:
        parts = []
        for i, pg in enumerate(reader.pages, 1):
            pg_text = pg.extract_text() or ""
            if pg_text.strip():
                parts.append(f"── Page {i} of {total_pages} ──\n\n{pg_text}")
        text = "\n\n".join(parts) if parts else "(No extractable text in PDF)"

    lines = text.splitlines()
    return FileContent(
        text=text,
        total_lines=len(lines),
        file_type="pdf",
        size=size,
        metadata={
            "pages": total_pages,
            "title": title,
        },
    )
