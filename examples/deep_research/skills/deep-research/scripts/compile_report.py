#!/usr/bin/env python3
"""
Report Compiler and Validator

Validates a research report markdown file for completeness, checks image
references, citation consistency, and optionally converts to HTML.

Usage:
    python compile_report.py <report.md> [--validate] [--to-html] [--output PATH]

Examples:
    python compile_report.py /mnt/workspace/report/report.md --validate
    python compile_report.py /mnt/workspace/report/report.md --validate --to-html
    python compile_report.py /mnt/workspace/report/report.md --to-html --output /mnt/workspace/report/report.html
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def read_report(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def validate_report(content: str, report_dir: str) -> dict:
    """Validate report structure, references, and images."""
    issues = []
    warnings = []
    stats = {}

    lines = content.split("\n")
    stats["total_lines"] = len(lines)
    stats["total_chars"] = len(content)
    stats["word_count_approx"] = len(content.replace("\n", " ").split())

    # Check structure
    headings = [(i + 1, line) for i, line in enumerate(lines) if line.startswith("#")]
    stats["heading_count"] = len(headings)

    h1_headings = [h for h in headings if h[1].startswith("# ") and not h[1].startswith("## ")]
    if not h1_headings:
        issues.append("Missing H1 title heading")

    # Check for essential sections
    heading_text_lower = " ".join(h[1].lower() for h in headings)
    essential_keywords = {
        "summary": ["摘要", "概要", "summary", "executive summary", "概述"],
        "conclusion": ["结论", "总结", "conclusion", "建议", "recommendation"],
        "references": ["参考", "引用", "reference", "来源", "source", "bibliography"],
    }
    for section, keywords in essential_keywords.items():
        if not any(kw in heading_text_lower for kw in keywords):
            warnings.append(f"Missing recommended section: {section} (looked for: {', '.join(keywords)})")

    # Check image references
    image_refs = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)
    stats["image_count"] = len(image_refs)
    missing_images = []
    for alt, path in image_refs:
        if path.startswith(("http://", "https://")):
            continue
        full_path = os.path.join(report_dir, path)
        if not os.path.exists(full_path):
            missing_images.append(path)
            issues.append(f"Image not found: {path}")
    stats["missing_images"] = len(missing_images)

    # Check citations [n]
    citations_used = set(int(m) for m in re.findall(r"\[(\d+)\]", content))
    stats["citation_count"] = len(citations_used)

    # Check references section for numbered entries
    ref_section = ""
    ref_match = re.search(
        r"(?:^#{1,3}\s*(?:参考|引用|Reference|来源|Source|Bibliography).*$)(.*?)(?=^#{1,3}\s|\Z)",
        content, re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if ref_match:
        ref_section = ref_match.group(1)

    ref_entries = set(int(m) for m in re.findall(r"^\s*\[?(\d+)\]?[\.\s]", ref_section, re.MULTILINE))
    stats["reference_entries"] = len(ref_entries)

    orphan_citations = citations_used - ref_entries
    orphan_refs = ref_entries - citations_used
    if orphan_citations:
        issues.append(f"Citations without reference entries: {sorted(orphan_citations)}")
    if orphan_refs:
        warnings.append(f"Reference entries not cited in text: {sorted(orphan_refs)}")

    # Check for placeholder text
    placeholders = re.findall(r"\[(?:TODO|TBD|FIXME|XXX|待补充|待完善)\]", content, re.IGNORECASE)
    if placeholders:
        issues.append(f"Found {len(placeholders)} placeholder(s): {placeholders[:5]}")

    # Check tables
    table_count = len(re.findall(r"^\|.+\|$", content, re.MULTILINE))
    stats["table_rows"] = table_count

    result = {
        "status": "pass" if not issues else "issues_found",
        "issues": issues,
        "warnings": warnings,
        "stats": stats,
    }
    return result


def generate_toc(content: str) -> str:
    """Generate a markdown table of contents from headings."""
    lines = content.split("\n")
    toc_lines = ["## 目录\n"]

    for line in lines:
        match = re.match(r"^(#{2,4})\s+(.+)$", line)
        if not match:
            continue
        level = len(match.group(1)) - 2  # H2=0, H3=1, H4=2
        title = match.group(2).strip()
        anchor = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", title).strip().replace(" ", "-").lower()
        indent = "  " * level
        toc_lines.append(f"{indent}- [{title}](#{anchor})")

    return "\n".join(toc_lines)


def to_html(content: str, title: str = "Research Report") -> str:
    """Convert markdown to styled HTML."""
    try:
        import markdown
        body = markdown.markdown(
            content,
            extensions=["tables", "fenced_code", "toc"],
            output_format="html5",
        )
    except ImportError:
        body = basic_md_to_html(content)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{
    max-width: 900px;
    margin: 2em auto;
    padding: 0 1.5em;
    font-family: -apple-system, "Noto Sans SC", "Source Han Sans CN", sans-serif;
    line-height: 1.8;
    color: #333;
  }}
  h1 {{ border-bottom: 2px solid #2c3e50; padding-bottom: 0.3em; color: #2c3e50; }}
  h2 {{ border-bottom: 1px solid #eee; padding-bottom: 0.2em; margin-top: 2em; color: #34495e; }}
  h3 {{ color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f7fa; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  img {{ max-width: 100%; height: auto; margin: 1em 0; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  blockquote {{ border-left: 4px solid #3498db; margin: 1em 0; padding: 0.5em 1em; background: #f8f9fa; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  pre {{ background: #f5f5f5; padding: 1em; border-radius: 6px; overflow-x: auto; }}
  .caption {{ text-align: center; color: #666; font-style: italic; font-size: 0.9em; margin-top: -0.5em; }}
  a {{ color: #3498db; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
    return html


def basic_md_to_html(content: str) -> str:
    """Minimal markdown to HTML conversion without external libraries."""
    html = content
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1"><p class="caption">\1</p>', html)
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    paragraphs = html.split("\n\n")
    processed = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("<"):
            p = f"<p>{p}</p>"
        processed.append(p)
    return "\n".join(processed)


def main():
    parser = argparse.ArgumentParser(description="Validate and compile research report")
    parser.add_argument("report", help="Path to report markdown file")
    parser.add_argument("--validate", action="store_true", help="Validate report structure and references")
    parser.add_argument("--to-html", action="store_true", help="Convert to styled HTML")
    parser.add_argument("--output", default=None, help="Output path for HTML (default: same dir as report)")
    parser.add_argument("--add-toc", action="store_true", help="Insert generated table of contents")
    args = parser.parse_args()

    if not os.path.exists(args.report):
        print(f"[ERROR] Report file not found: {args.report}")
        sys.exit(1)

    content = read_report(args.report)
    report_dir = os.path.dirname(os.path.abspath(args.report))

    print(f"Report: {args.report}")
    print(f"Size: {len(content):,} characters")

    if args.add_toc:
        toc = generate_toc(content)
        first_h2 = re.search(r"^## ", content, re.MULTILINE)
        if first_h2:
            pos = first_h2.start()
            content = content[:pos] + toc + "\n\n" + content[pos:]
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(content)
            print("[OK] Table of contents inserted")

    if args.validate:
        result = validate_report(content, report_dir)
        print(f"\n{'='*50}")
        print(f"  VALIDATION REPORT")
        print(f"{'='*50}")
        print(f"  Status: {result['status'].upper()}")
        print(f"  Lines: {result['stats']['total_lines']:,}")
        print(f"  Characters: {result['stats']['total_chars']:,}")
        print(f"  Words (approx): {result['stats']['word_count_approx']:,}")
        print(f"  Headings: {result['stats']['heading_count']}")
        print(f"  Images: {result['stats']['image_count']} ({result['stats']['missing_images']} missing)")
        print(f"  Citations: {result['stats']['citation_count']}")
        print(f"  Reference entries: {result['stats']['reference_entries']}")
        print(f"  Table rows: {result['stats']['table_rows']}")

        if result["issues"]:
            print(f"\n  Issues ({len(result['issues'])}):")
            for issue in result["issues"]:
                print(f"    ✗ {issue}")

        if result["warnings"]:
            print(f"\n  Warnings ({len(result['warnings'])}):")
            for w in result["warnings"]:
                print(f"    ⚠ {w}")

        if not result["issues"] and not result["warnings"]:
            print(f"\n  ✓ All checks passed")

        print(f"\n{json.dumps(result, ensure_ascii=False, indent=2)}")

    if args.to_html:
        # Extract title from first H1
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "Research Report"

        html = to_html(content, title=title)

        if args.output:
            html_path = args.output
        else:
            html_path = os.path.splitext(args.report)[0] + ".html"

        os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n[OK] HTML report saved to {html_path}")


if __name__ == "__main__":
    main()
