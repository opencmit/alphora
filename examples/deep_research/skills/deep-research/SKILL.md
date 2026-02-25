---
name: deep-research
description: >
  Conduct deep research on any topic by searching the web, collecting sources,
  extracting key themes, and generating a structured research report.
  Use when the user asks for in-depth analysis, research, investigation,
  or comprehensive review of a topic.
license: Apache-2.0
metadata:
  author: alphora-team
  version: "1.0"
---

# Deep Research

Conduct thorough, multi-source research on a given topic and produce
a well-structured analytical report.

## Overview

This skill guides you through a systematic research process:
1. Break the topic into sub-questions
2. Search and collect information from multiple sources
3. Extract key themes and synthesize findings
4. Generate a structured Markdown report

## Prerequisites

- `web_search` tool: for searching information
- `fetch_webpage` tool: for retrieving full page content
- Sandbox access: for running analysis scripts and saving reports

## Research Workflow

### Step 1: Understand the Research Topic

Parse the user's request to identify:
- **Core topic**: What is being researched
- **Scope**: How broad or narrow the research should be
- **Perspective**: What angle or framework to use

Formulate 3-5 specific sub-questions that, when answered together,
provide comprehensive coverage of the topic.

### Step 2: Search and Collect Sources

For each sub-question:
1. Use `web_search` to find relevant sources (aim for 3-5 per question)
2. Use `fetch_webpage` on the most promising URLs to get full content
3. Note the source URL and key findings

Aim for source diversity:
- Official documentation and papers
- Industry analysis and blog posts
- Community discussions and expert opinions

### Step 3: Extract Key Themes

After collecting sources, run the topic extraction script to identify
recurring themes across all collected content:

```
run_skill_script("deep-research", "extract_topics.py", "<topics_json_path>")
```

The script reads a JSON file containing collected findings and outputs
a structured topic analysis. Save findings to a JSON file first:

```json
{
  "topic": "the research topic",
  "findings": [
    {
      "source": "URL or source name",
      "content": "key information extracted"
    }
  ]
}
```

### Step 4: Synthesize and Generate Report

Use the report generation script to produce the final Markdown report:

```
run_skill_script("deep-research", "generate_report.py", "<topics_json_path> <output_path>")
```

The script takes the extracted topics and generates a structured report
with executive summary, detailed analysis, and conclusions.

### Step 5: Review and Refine

Review the generated report for:
- Factual accuracy
- Logical coherence
- Coverage completeness
- Clear conclusions

Make manual edits if needed, then present the final report to the user.

## Output Format

The final deliverable is a Markdown report with this structure:
- Executive Summary (2-3 paragraphs)
- Key Findings (organized by theme)
- Detailed Analysis (per sub-question)
- Sources and References
- Conclusions and Recommendations

## Error Handling

- If `web_search` returns no results for a sub-question, try rephrasing
- If `fetch_webpage` fails on a URL, skip it and use search snippets
- If scripts fail, fall back to generating the report directly with code

## Resources

- See [references/METHODOLOGY.md](references/METHODOLOGY.md) for detailed
  research methodology guidelines
- `scripts/extract_topics.py` - Topic extraction and clustering
- `scripts/generate_report.py` - Markdown report generation
