"""
generate_report.py - 从主题分析结果生成 Markdown 研究报告

读取 extract_topics.py 输出的主题分析 JSON，生成结构化的 Markdown 报告。

Usage:
    python generate_report.py <topics_json_path> [output_path]

Args:
    topics_json_path: extract_topics.py 输出的 topics.json 路径
    output_path: 报告输出路径（默认: 同目录下的 research_report.md）
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def generate_report(data: dict) -> str:
    """从主题分析数据生成 Markdown 报告"""
    topic = data.get("topic", "Unknown Topic")
    themes = data.get("themes", [])
    keywords = data.get("keywords", [])
    total_sources = data.get("total_sources", 0)

    lines = []

    # 标题
    lines.append(f"# 深度研究报告: {topic}")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 分析源数量: {total_sources}")
    lines.append(f"> 识别主题数: {len(themes)}")
    lines.append("")

    # 执行摘要
    lines.append("## 执行摘要")
    lines.append("")
    if themes:
        top_themes = [t["name"] for t in themes[:5]]
        lines.append(
            f"本报告对「{topic}」进行了系统性研究，"
            f"共分析了 {total_sources} 个信息源，"
            f"识别出 {len(themes)} 个关键主题。"
        )
        lines.append("")
        lines.append(f"**核心发现**: {', '.join(top_themes)}")
    else:
        lines.append("未能从收集的信息中提取有效主题，建议扩大搜索范围。")
    lines.append("")

    # 关键词概览
    if keywords:
        lines.append("## 关键词云")
        lines.append("")
        lines.append(" | ".join(f"`{k}`" for k in keywords[:15]))
        lines.append("")

    # 主题详细分析
    if themes:
        lines.append("## 主题详细分析")
        lines.append("")

        for i, theme in enumerate(themes, 1):
            lines.append(f"### {i}. {theme['name'].title()}")
            lines.append("")
            lines.append(
                f"**提及频次**: {theme['mention_count']} 次 | "
                f"**来源数**: {theme['source_count']} 个"
            )
            lines.append("")

            # 来源摘录
            lines.append("**关键信息**:")
            lines.append("")
            for src in theme.get("sources", [])[:3]:
                excerpt = src["excerpt"].replace("\n", " ").strip()
                lines.append(f"- [{src['source']}] {excerpt}")
            lines.append("")

    # 数据来源
    lines.append("## 数据来源")
    lines.append("")
    all_sources = set()
    for theme in themes:
        for src in theme.get("sources", []):
            all_sources.add(src["source"])

    if all_sources:
        for i, src in enumerate(sorted(all_sources), 1):
            lines.append(f"{i}. {src}")
    else:
        lines.append("无可用来源信息。")
    lines.append("")

    # 结论
    lines.append("## 结论与建议")
    lines.append("")
    if themes:
        lines.append(
            f"基于对 {total_sources} 个信息源的分析，"
            f"「{topic}」领域的核心关注点集中在以下方面："
        )
        lines.append("")
        for theme in themes[:5]:
            lines.append(f"- **{theme['name'].title()}**: 被 {theme['mention_count']} 个源提及")
        lines.append("")
        lines.append("建议进一步深入研究上述高频主题，并关注各主题之间的关联性。")
    else:
        lines.append("数据不足，建议扩大搜索范围后重新分析。")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <topics_json_path> [output_path]")
        sys.exit(1)

    topics_path = Path(sys.argv[1])

    if not topics_path.exists():
        print(f"Error: File not found: {topics_path}")
        sys.exit(1)

    # 读取主题分析
    with open(topics_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 生成报告
    report = generate_report(data)

    # 确定输出路径
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = topics_path.parent / "research_report.md"

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report generated: {output_path}")
    print(f"  Topic: {data.get('topic', 'N/A')}")
    print(f"  Themes: {len(data.get('themes', []))}")
    print(f"  Length: {len(report)} characters")


if __name__ == "__main__":
    main()
