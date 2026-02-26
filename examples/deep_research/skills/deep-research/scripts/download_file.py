#!/usr/bin/env python3
"""
File Downloader

Downloads files (images, data, PDFs) from URLs to the local workspace.
Validates downloads and reports file details.

Usage:
    python download_file.py <url> [--output PATH] [--timeout SECONDS]

Examples:
    python download_file.py "https://example.com/chart.png" --output /mnt/workspace/research/images/chart.png
    python download_file.py "https://example.com/data.csv" --output /mnt/workspace/research/data/dataset.csv
    python download_file.py "https://example.com/image.jpg"
"""

import argparse
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

MAX_SIZE = 50 * 1024 * 1024  # 50 MB

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet", ".tsv", ".xml"}


def guess_filename(url: str, content_type: str = None, content_disposition: str = None) -> str:
    """Derive a filename from URL, Content-Type, or Content-Disposition."""
    # Try Content-Disposition header first
    if content_disposition:
        match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', content_disposition)
        if match:
            return unquote(match.group(1).strip())

    # Extract from URL path
    parsed = urlparse(url)
    path = unquote(parsed.path)
    basename = os.path.basename(path)
    if basename and "." in basename:
        return basename

    # Guess from Content-Type
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return f"download{ext}"

    return "download.bin"


def download(url: str, output_path: str, timeout: int = 30) -> dict:
    """Download a file and return metadata."""
    import requests

    resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True)
    resp.raise_for_status()

    content_length = int(resp.headers.get("Content-Length", 0))
    if content_length > MAX_SIZE:
        raise ValueError(f"File too large: {content_length / 1024 / 1024:.1f} MB (max {MAX_SIZE / 1024 / 1024:.0f} MB)")

    content_type = resp.headers.get("Content-Type", "")
    content_disposition = resp.headers.get("Content-Disposition", "")

    # Determine output path
    if not output_path:
        filename = guess_filename(url, content_type, content_disposition)
        output_path = os.path.join("/mnt/workspace/research/downloads", filename)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Stream download
    downloaded = 0
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > MAX_SIZE:
                    f.close()
                    os.remove(output_path)
                    raise ValueError(f"Download exceeded max size ({MAX_SIZE / 1024 / 1024:.0f} MB)")

    ext = Path(output_path).suffix.lower()
    file_type = "image" if ext in IMAGE_EXTENSIONS else "data" if ext in DATA_EXTENSIONS else "other"

    return {
        "path": output_path,
        "size": downloaded,
        "content_type": content_type,
        "file_type": file_type,
        "url": url,
    }


def validate_image(filepath: str) -> bool:
    """Quick check if a file is a valid image."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        # Check common image magic bytes
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return True
        if header[:2] in (b'\xff\xd8', b'\xff\xe0', b'\xff\xe1'):
            return True  # JPEG
        if header[:4] == b'GIF8':
            return True
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return True
        if b'<svg' in header:
            return True
        return False
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Download files from URLs")
    parser.add_argument("url", help="URL to download")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--timeout", type=int, default=30, help="Download timeout in seconds")
    args = parser.parse_args()

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"Downloading: {url}")

    try:
        info = download(url, args.output, timeout=args.timeout)
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        sys.exit(1)

    size_kb = info["size"] / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"

    print(f"[OK] Downloaded: {info['path']}")
    print(f"  Size: {size_str}")
    print(f"  Type: {info['content_type']}")

    if info["file_type"] == "image":
        if validate_image(info["path"]):
            print(f"  Validation: Valid image")
        else:
            print(f"  [WARN] File may not be a valid image")


if __name__ == "__main__":
    main()
