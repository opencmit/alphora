"""
Deep Research - 自定义工具集

定义研究场景所需的工具函数。这些工具与 Skill 内置工具一起注册到 ToolRegistry，
共同为 LLM 提供执行能力。

工具清单:
    - web_search: 模拟网络搜索（可替换为真实搜索 API）
    - fetch_webpage: 模拟网页抓取（可替换为真实抓取逻辑）

注意:
    本示例中搜索和抓取使用模拟数据，实际使用时请替换为真实的
    搜索引擎 API（如 SerpAPI、Bing API）和网页抓取库（如 httpx、playwright）。
"""

from alphora.tools.decorators import tool


# ─────────────────────────────────────────────────────
#  Tool 1: 网络搜索
# ─────────────────────────────────────────────────────

@tool(
    name="web_search",
    description=(
        "Search the web for information on a given query. "
        "Returns a list of search results with titles, URLs, and snippets. "
        "Use this to find relevant sources for research."
    ),
)
def web_search(query: str, num_results: int = 5) -> str:
    """
    搜索网络信息。

    Args:
        query: 搜索关键词
        num_results: 返回结果数量，默认 5

    Returns:
        格式化的搜索结果
    """
    # ┌──────────────────────────────────────────────┐
    # │  模拟搜索结果                                  │
    # │  实际使用时替换为真实搜索 API 调用：             │
    # │                                              │
    # │  import httpx                                │
    # │  resp = httpx.get(                           │
    # │      "https://serpapi.com/search",           │
    # │      params={"q": query, "num": num_results} │
    # │  )                                           │
    # │  return format_results(resp.json())          │
    # └──────────────────────────────────────────────┘

    mock_results = _get_mock_search_results(query)
    results = mock_results[:num_results]

    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: \"{query}\"\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r['title']}**")
        lines.append(f"   URL: {r['url']}")
        lines.append(f"   {r['snippet']}")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────
#  Tool 2: 网页内容抓取
# ─────────────────────────────────────────────────────

@tool(
    name="fetch_webpage",
    description=(
        "Fetch and extract the main text content from a webpage URL. "
        "Use this to get detailed information from a specific source "
        "found through web_search."
    ),
)
def fetch_webpage(url: str) -> str:
    """
    抓取网页的主要文本内容。

    Args:
        url: 网页 URL

    Returns:
        网页的主要文本内容
    """
    # ┌──────────────────────────────────────────────┐
    # │  模拟网页抓取                                  │
    # │  实际使用时替换为真实抓取逻辑：                   │
    # │                                              │
    # │  import httpx                                │
    # │  from readability import Document            │
    # │  resp = httpx.get(url, follow_redirects=True)│
    # │  doc = Document(resp.text)                   │
    # │  return doc.summary()                        │
    # └──────────────────────────────────────────────┘

    content = _get_mock_webpage_content(url)

    if content:
        return f"Content from {url}:\n\n{content}"
    else:
        return f"Failed to fetch content from {url}. The page may be unavailable."


# ─────────────────────────────────────────────────────
#  模拟数据
#  以下数据仅用于演示，实际使用时删除并接入真实 API
# ─────────────────────────────────────────────────────

def _get_mock_search_results(query: str) -> list[dict]:
    """生成基于查询的模拟搜索结果"""
    query_lower = query.lower()

    # 通用技术研究的模拟结果
    base_results = [
        {
            "title": f"{query} - Comprehensive Overview and Analysis",
            "url": "https://example.com/tech-analysis/overview",
            "snippet": (
                f"A comprehensive analysis of {query}. This article covers "
                f"the current state, key players, technical architecture, "
                f"and future trends in this rapidly evolving field."
            ),
        },
        {
            "title": f"The State of {query} in 2026",
            "url": "https://example.com/blog/state-of-tech-2026",
            "snippet": (
                f"An in-depth look at how {query} has evolved in 2026. "
                f"Key developments include improved performance, wider adoption, "
                f"and new standards that are reshaping the industry."
            ),
        },
        {
            "title": f"{query}: Technical Deep Dive",
            "url": "https://example.com/engineering/deep-dive",
            "snippet": (
                f"Technical deep dive into {query}. Covers architecture design, "
                f"implementation patterns, performance benchmarks, and best practices "
                f"for production deployment."
            ),
        },
        {
            "title": f"Industry Adoption of {query} - Case Studies",
            "url": "https://example.com/case-studies/adoption",
            "snippet": (
                f"Real-world case studies of {query} adoption across industries. "
                f"Includes examples from finance, healthcare, and technology sectors, "
                f"with measurable outcomes and lessons learned."
            ),
        },
        {
            "title": f"Future Trends: Where is {query} Heading?",
            "url": "https://example.com/research/future-trends",
            "snippet": (
                f"Expert predictions and analysis of future trends in {query}. "
                f"Emerging patterns include standardization efforts, ecosystem growth, "
                f"and integration with adjacent technologies."
            ),
        },
        {
            "title": f"Comparing Approaches to {query}",
            "url": "https://example.com/comparisons/approaches",
            "snippet": (
                f"A detailed comparison of different approaches to {query}. "
                f"Evaluates trade-offs in performance, scalability, cost, and "
                f"developer experience across leading solutions."
            ),
        },
    ]

    return base_results


def _get_mock_webpage_content(url: str) -> str:
    """生成基于 URL 的模拟网页内容"""
    content_map = {
        "overview": (
            "## Comprehensive Overview\n\n"
            "This technology represents a paradigm shift in how AI systems are built. "
            "The key innovation is the modular, composable approach that allows "
            "developers to extend agent capabilities without rebuilding the core system.\n\n"
            "### Key Components\n"
            "- **Modular Architecture**: Skills can be added, removed, and updated independently\n"
            "- **Progressive Disclosure**: Information is loaded on-demand to optimize token usage\n"
            "- **Security Model**: Tiered trust levels ensure safe execution of third-party code\n"
            "- **Cross-Platform**: Open standards enable portability across different AI platforms\n\n"
            "### Market Impact\n"
            "The industry has seen rapid adoption, with major players including Anthropic, "
            "OpenAI, Microsoft, and Google all supporting or adopting similar approaches."
        ),
        "state-of-tech-2026": (
            "## The State of AI Agent Technology in 2026\n\n"
            "The AI agent ecosystem has matured significantly. Key trends include:\n\n"
            "1. **Standardization**: Open standards like agentskills.io have emerged, "
            "enabling interoperability between different platforms\n"
            "2. **Enterprise Adoption**: 60% of Fortune 500 companies now use AI agents "
            "in production workflows\n"
            "3. **Developer Tools**: Rich ecosystems of skills, tools, and frameworks "
            "have lowered the barrier to building effective agents\n"
            "4. **Safety Improvements**: Sandboxing, trust models, and audit mechanisms "
            "have addressed early security concerns\n\n"
            "The total addressable market for AI agent platforms is projected to reach "
            "$15 billion by 2027."
        ),
        "deep-dive": (
            "## Technical Architecture Deep Dive\n\n"
            "### Core Design Principles\n"
            "- **Separation of Knowledge and Execution**: Skills provide domain knowledge, "
            "tools provide execution capability\n"
            "- **LLM-Driven Decision Making**: The language model makes all routing decisions, "
            "no algorithmic classifiers needed\n"
            "- **File-System as Interface**: Skills are just directories with markdown files, "
            "making them easy to create, version, and share\n\n"
            "### Performance Considerations\n"
            "- Metadata loading: ~100 tokens per skill at startup\n"
            "- Full activation: ~2000-5000 tokens per skill\n"
            "- Script execution: Output only enters context, not source code\n"
            "- Context management is critical for scaling to many skills"
        ),
        "adoption": (
            "## Industry Adoption Case Studies\n\n"
            "### Finance Sector\n"
            "Major banks have deployed agent skills for automated compliance checking, "
            "reducing review time by 70% while improving accuracy.\n\n"
            "### Healthcare\n"
            "Hospital systems use research skills to analyze medical literature and "
            "generate evidence summaries for clinical decision support.\n\n"
            "### Technology\n"
            "Software teams use coding skills to automate code review, documentation "
            "generation, and testing workflows, reporting 40% productivity improvements."
        ),
        "future-trends": (
            "## Future Trends and Predictions\n\n"
            "### Short-term (2026-2027)\n"
            "- Skill marketplaces will become mainstream\n"
            "- Multi-agent collaboration protocols will mature\n"
            "- Enterprise skill management platforms will emerge\n\n"
            "### Medium-term (2027-2028)\n"
            "- AI agents will compose skills autonomously\n"
            "- Real-time skill creation and adaptation\n"
            "- Cross-organization skill sharing networks\n\n"
            "### Long-term (2028+)\n"
            "- Self-evolving skill ecosystems\n"
            "- Skill-aware hardware optimization\n"
            "- Universal agent interoperability standards"
        ),
        "approaches": (
            "## Comparing Approaches\n\n"
            "| Approach | Pros | Cons |\n"
            "|----------|------|------|\n"
            "| Skills (File-based) | Simple, portable, version-controlled | Limited to text |\n"
            "| MCP (Protocol-based) | Real-time, bi-directional | Requires server |\n"
            "| Plugin Systems | Tightly integrated | Platform-specific |\n"
            "| RAG Pipelines | Good for retrieval | Less structured |\n\n"
            "The emerging best practice is to combine Skills (for knowledge and workflow) "
            "with MCP (for tool connectivity), creating a \"brain + hands\" architecture."
        ),
    }

    for key, content in content_map.items():
        if key in url:
            return content

    return ""
