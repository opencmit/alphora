"""
extract_topics.py - 从研究发现中提取关键主题

从包含研究发现的 JSON 文件中提取和聚类关键主题。
输出带有频率和相关来源的主题分析结果。

Usage:
    python extract_topics.py <findings_json_path>

Input JSON format:
    {
        "topic": "研究主题",
        "findings": [
            {"source": "来源URL", "content": "提取的关键信息"}
        ]
    }

Output:
    将主题分析结果写入 <findings_json_path> 同目录的 topics.json
"""

import json
import sys
import re
from pathlib import Path
from collections import Counter


def extract_keywords(text: str, top_n: int = 20) -> list[str]:
    """从文本中提取高频关键词（简易版）"""
    # 清理文本：保留字母、数字、中文
    words = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}', text.lower())

    # 过滤常见停用词
    stopwords = {
        'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are',
        'was', 'were', 'been', 'have', 'has', 'had', 'will', 'can',
        'not', 'but', 'they', 'their', 'which', 'when', 'how', 'what',
        'than', 'more', 'also', 'other', 'some', 'use', 'used', 'using',
    }
    words = [w for w in words if w not in stopwords]

    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def cluster_findings(findings: list[dict], keywords: list[str]) -> dict:
    """将发现按关键词主题聚类"""
    clusters = {}

    for keyword in keywords[:10]:
        related = []
        for f in findings:
            content = f.get("content", "").lower()
            if keyword.lower() in content:
                related.append({
                    "source": f.get("source", "unknown"),
                    "excerpt": f["content"][:200],
                })
        if len(related) >= 1:
            clusters[keyword] = {
                "mention_count": len(related),
                "sources": related[:5],
            }

    return clusters


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_topics.py <findings_json_path>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # 读取研究发现
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    topic = data.get("topic", "Unknown Topic")
    findings = data.get("findings", [])

    if not findings:
        print("Warning: No findings to analyze")
        result = {"topic": topic, "themes": [], "keywords": []}
    else:
        # 合并所有内容
        all_content = " ".join(f.get("content", "") for f in findings)

        # 提取关键词
        keywords = extract_keywords(all_content)

        # 聚类
        clusters = cluster_findings(findings, keywords)

        # 构建主题列表
        themes = []
        for keyword, info in sorted(
            clusters.items(), key=lambda x: x[1]["mention_count"], reverse=True
        ):
            themes.append({
                "name": keyword,
                "mention_count": info["mention_count"],
                "source_count": len(set(s["source"] for s in info["sources"])),
                "sources": info["sources"],
            })

        result = {
            "topic": topic,
            "total_sources": len(findings),
            "keywords": keywords,
            "themes": themes,
        }

    # 输出到文件
    output_path = input_path.parent / "topics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 同时输出到 stdout（供 Agent 读取）
    print(f"Topic analysis complete for: {topic}")
    print(f"  Sources analyzed: {len(findings)}")
    print(f"  Themes found: {len(result.get('themes', []))}")
    print(f"  Output saved to: {output_path}")

    # 打印主题摘要
    for theme in result.get("themes", [])[:5]:
        print(f"  - {theme['name']} (mentioned {theme['mention_count']} times)")


if __name__ == "__main__":
    main()
