#!/usr/bin/env python3
"""
Web Page Content Extractor

Fetches a URL and extracts clean, readable text content.
Supports saving extracted text and optionally discovering images.

Usage:
    python fetch_page.py <url> [--output PATH] [--list-images] [--timeout SECONDS]

Examples:
    python fetch_page.py "https://example.com/article"
    python fetch_page.py "https://example.com/article" --output /mnt/workspace/research/sources/article.txt
    python fetch_page.py "https://example.com/article" --list-images
"""

import argparse
import os
import re
import sys
from urllib.parse import urljoin, urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

UNWANTED_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "noscript", "iframe", "svg", "form",
]


def fetch_html(url: str, timeout: int = 20) -> str:
    import requests

    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()

    encoding = resp.apparent_encoding or resp.encoding or "utf-8"
    resp.encoding = encoding
    return resp.text


def extract_with_bs4(html: str, url: str) -> dict:
    """Extract content using BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    for tag_name in UNWANTED_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Try to find main content area
    main_content = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=re.compile(r"(content|article|post|entry|body)", re.I))
        or soup.body
    )

    if main_content is None:
        main_content = soup

    text = main_content.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Extract images
    images = []
    for img in main_content.find_all("img", src=True):
        src = urljoin(url, img["src"])
        alt = img.get("alt", "")
        if src and not src.startswith("data:"):
            images.append({"src": src, "alt": alt})

    return {"title": title, "text": text, "images": images}


def extract_plain(html: str) -> dict:
    """Fallback extraction without BeautifulSoup."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = title_match.group(1).strip() if title_match else ""

    for pattern in UNWANTED_TAGS:
        html = re.sub(rf"<{pattern}[^>]*>.*?</{pattern}>", "", html, flags=re.I | re.S)

    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    img_matches = re.findall(r'<img[^>]+src="([^"]+)"[^>]*(?:alt="([^"]*)")?', html, re.I)
    images = [{"src": src, "alt": alt} for src, alt in img_matches if not src.startswith("data:")]

    return {"title": title, "text": text, "images": images}


def format_output(data: dict, url: str) -> str:
    """Format extracted content for saving/display."""
    lines = [
        f"Source: {url}",
        f"Title: {data['title']}",
        f"Extracted: {len(data['text'])} characters",
        "---",
        "",
        data["text"],
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Fetch and extract web page content")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--output", default=None, help="Save extracted text to file")
    parser.add_argument("--list-images", action="store_true", help="List discovered images")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds")
    parser.add_argument("--max-chars", type=int, default=50000, help="Max characters to output (default: 50000)")
    args = parser.parse_args()

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"Fetching: {url}")

    try:
        html = fetch_html(url, timeout=args.timeout)
    except Exception as e:
        print(f"[ERROR] Failed to fetch URL: {e}")
        sys.exit(1)

    print(f"Downloaded: {len(html):,} bytes")

    # Extract content
    try:
        data = extract_with_bs4(html, url)
    except ImportError:
        print("[WARN] BeautifulSoup not available, using basic extraction")
        data = extract_plain(html)

    if not data["text"]:
        print("[WARN] No text content extracted from page")
        sys.exit(0)

    # Truncate if too long
    if len(data["text"]) > args.max_chars:
        data["text"] = data["text"][:args.max_chars] + f"\n\n[TRUNCATED at {args.max_chars:,} characters]"

    output = format_output(data, url)
    print(f"\nTitle: {data['title']}")
    print(f"Content length: {len(data['text']):,} characters")

    if args.list_images and data["images"]:
        print(f"\nImages found: {len(data['images'])}")
        for i, img in enumerate(data["images"][:20], 1):
            alt_text = f' — "{img["alt"]}"' if img["alt"] else ""
            print(f"  [{i}] {img['src']}{alt_text}")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n[OK] Content saved to {args.output}")
    else:
        print("\n--- Content Preview (first 2000 chars) ---")
        preview = data["text"][:2000]
        print(preview)
        if len(data["text"]) > 2000:
            print(f"\n... [{len(data['text']) - 2000:,} more characters]")


if __name__ == "__main__":
    main()
