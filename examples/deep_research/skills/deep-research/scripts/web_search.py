#!/usr/bin/env python3
"""
Web Search Script

Searches the web and returns structured results with titles, URLs, and snippets.
Supports multiple backends with automatic fallback.

Usage:
    python web_search.py "query" [--max-results N] [--region REGION] [--save-to PATH]

Examples:
    python web_search.py "AI industry trends 2024"
    python web_search.py "electric vehicle market share" --max-results 20
    python web_search.py "量子计算发展现状" --region cn-zh --save-to /mnt/workspace/research/notes/search_results.txt
"""

import argparse
import json
import os
import sys
from datetime import datetime


def search_duckduckgo(query: str, max_results: int = 10, region: str = "wt-wt") -> list:
    """Search using duckduckgo-search library."""
    from duckduckgo_search import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, region=region, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
            })
    return results


def search_duckduckgo_lite(query: str, max_results: int = 10) -> list:
    """Fallback: scrape DuckDuckGo Lite HTML interface."""
    import requests
    from urllib.parse import quote_plus

    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
    except ImportError:
        soup = None

    results = []
    if soup:
        for link in soup.select("a.result-link"):
            if len(results) >= max_results:
                break
            href = link.get("href", "")
            title = link.get_text(strip=True)
            snippet_td = link.find_parent("tr")
            snippet = ""
            if snippet_td:
                next_tr = snippet_td.find_next_sibling("tr")
                if next_tr:
                    snippet = next_tr.get_text(strip=True)
            if href and title:
                results.append({"title": title, "url": href, "snippet": snippet})

    return results


def search_via_api(query: str, max_results: int = 10) -> list:
    """Search using a custom API configured via environment variables.

    Env vars:
        SEARCH_API_URL: API endpoint (e.g., https://api.tavily.com/search)
        SEARCH_API_KEY: API key
    """
    import requests

    api_url = os.environ.get("SEARCH_API_URL", "")
    api_key = os.environ.get("SEARCH_API_KEY", "")

    if not api_url or not api_key:
        return []

    resp = requests.post(
        api_url,
        json={"query": query, "max_results": max_results, "api_key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", data.get("organic", [])):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", r.get("link", "")),
            "snippet": r.get("content", r.get("snippet", "")),
        })
    return results[:max_results]


def do_search(query: str, max_results: int = 10, region: str = "wt-wt") -> list:
    """Try search backends in order: custom API → duckduckgo-search → DuckDuckGo Lite."""
    # 1. Custom API (if configured)
    if os.environ.get("SEARCH_API_URL"):
        try:
            results = search_via_api(query, max_results)
            if results:
                return results
        except Exception as e:
            print(f"[WARN] Custom API search failed: {e}", file=sys.stderr)

    # 2. duckduckgo-search library
    try:
        return search_duckduckgo(query, max_results, region)
    except ImportError:
        print("[WARN] duckduckgo-search not installed, trying fallback...", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] duckduckgo-search failed: {e}, trying fallback...", file=sys.stderr)

    # 3. DuckDuckGo Lite scraping
    try:
        return search_duckduckgo_lite(query, max_results)
    except Exception as e:
        print(f"[ERROR] All search backends failed. Last error: {e}", file=sys.stderr)
        return []


def format_results(results: list, query: str) -> str:
    """Format search results for display."""
    lines = [
        f"Search: \"{query}\"",
        f"Results: {len(results)}",
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r.get("snippet"):
            snippet = r["snippet"][:300]
            lines.append(f"    {snippet}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Web search with structured results")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max-results", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--region", default="wt-wt", help="Region code (default: wt-wt, use cn-zh for Chinese)")
    parser.add_argument("--save-to", default=None, help="Save results to file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = do_search(args.query, args.max_results, args.region)

    if not results:
        print(f"[WARN] No results found for: {args.query}")
        sys.exit(0)

    if args.json:
        output = json.dumps(results, ensure_ascii=False, indent=2)
    else:
        output = format_results(results, args.query)

    print(output)

    if args.save_to:
        os.makedirs(os.path.dirname(args.save_to) or ".", exist_ok=True)
        with open(args.save_to, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n[OK] Results saved to {args.save_to}")


if __name__ == "__main__":
    main()
