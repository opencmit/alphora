---
name: deep-research
description: "Use this skill for any task that requires in-depth research, investigation, or comprehensive report generation on a topic. This includes: producing industry analysis, market research, technology surveys, competitive intelligence, trend reports, or any deliverable that synthesizes information from multiple sources into a structured long-form document; answering complex questions that require gathering evidence from the web, analyzing data, and presenting findings with charts and citations; any request where the user explicitly asks for a 'report', 'research', 'survey', 'white paper', or 'deep dive'. Trigger especially when the task cannot be answered from memory alone and requires active information gathering. Do NOT trigger for simple factual Q&A, code-only tasks, single-file data analysis (use data-analysis skill), or creative writing without research backing."
license: Apache-2.0
metadata:
  author: alphora-team
  version: "1.0"
  tags: ["research", "report", "web-search", "data-analysis", "markdown"]
---

# Requirements for Outputs

## Final Report

### Structure
- **Title page**: Topic, date, author line
- **Executive summary**: 3-5 sentence overview of key findings (written last)
- **Table of contents**: Auto-generated from headings
- **Body sections**: Logically organized with H2/H3 headings
- **Conclusion & recommendations**: Actionable takeaways
- **References**: Numbered list of all sources with URLs

### Quality Standards
- Every factual claim MUST cite its source with `[n]` notation linking to the references section
- Charts and images MUST have captions explaining what they show
- Data tables MUST include units and time periods
- Minimum 3 distinct sources for any major conclusion
- No hallucinated statistics — every number must trace to collected evidence or computed code output

### Visual Requirements
- Include at least one data-driven chart per major section (bar, line, pie, etc.)
- Reference images should be downloaded locally and embedded via relative paths
- All images saved under `/mnt/workspace/report/assets/`
- Image references in markdown: `![Caption](assets/filename.png)`

### Formatting
- Use consistent heading hierarchy (H1 for title, H2 for sections, H3 for subsections)
- Use tables for structured comparisons
- Use blockquotes for key findings or direct quotes
- Number formatting: thousands separator for large numbers, 1 decimal for percentages

## Intermediate Artifacts

All research materials MUST be persisted in the workspace so findings are not lost between iterations:

| Directory | Purpose |
|-----------|---------|
| `/mnt/workspace/research/sources/` | Extracted web page content (.txt files) |
| `/mnt/workspace/research/data/` | Downloaded datasets and raw data |
| `/mnt/workspace/research/images/` | Downloaded reference images |
| `/mnt/workspace/research/notes/` | Research notes and outlines |
| `/mnt/workspace/report/` | Final report markdown |
| `/mnt/workspace/report/assets/` | Report images (charts + reference images) |

# Sandbox Environment

| Path | Purpose | Access |
|------|---------|--------|
| `/mnt/workspace/` | Working directory for all research materials and outputs | **Read/Write** |
| `/mnt/skills/deep-research/` | Skill scripts and references | **Read-only** |

The sandbox has **network access** for web searches and downloads.

## Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/web_search.py` | Search the web and return structured results | `python /mnt/skills/deep-research/scripts/web_search.py "query" --max-results 10` |
| `scripts/fetch_page.py` | Fetch a URL and extract clean text content | `python /mnt/skills/deep-research/scripts/fetch_page.py "https://example.com" --output /mnt/workspace/research/sources/page.txt` |
| `scripts/download_file.py` | Download files (images, data, PDFs) to workspace | `python /mnt/skills/deep-research/scripts/download_file.py "https://example.com/chart.png" --output /mnt/workspace/research/images/chart.png` |
| `scripts/compile_report.py` | Validate and compile the final report | `python /mnt/skills/deep-research/scripts/compile_report.py /mnt/workspace/report/report.md --validate --to-html` |

## Reference Documentation

| Document | Content |
|----------|---------|
| `references/REPORT_TEMPLATE.md` | Report structure template — use as starting skeleton |

## Dependency Installation

If dependencies are missing, install them first:

```bash
pip install requests beautifulsoup4 duckduckgo-search pandas matplotlib -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

# Research Workflow

## CRITICAL: Research is Iterative, Not Linear

Deep research follows a **collect → analyze → identify gaps → collect more** loop. Do NOT attempt to write the final report in one pass. Instead, accumulate materials over multiple iterations, then synthesize.

## Phase 1: Planning

Before any searching, create a research plan:

```python
plan = """
# Research Plan: [Topic]

## Core Questions
1. [Primary question to answer]
2. [Secondary question]
3. [...]

## Information Needs
- Market data: [what numbers/trends are needed]
- Expert opinions: [whose perspectives matter]
- Case studies: [specific examples to find]
- Comparisons: [what to compare against]

## Planned Sections
1. [Section title] — sources needed: [type]
2. [Section title] — sources needed: [type]
3. [...]
"""
with open('/mnt/workspace/research/notes/plan.md', 'w') as f:
    f.write(plan)
```

Save the plan to `/mnt/workspace/research/notes/plan.md` so it persists across iterations.

## Phase 2: Material Collection

### Web Search
Search broadly first, then narrow down:

```bash
# Broad search
python /mnt/skills/deep-research/scripts/web_search.py "topic overview" --max-results 10

# Targeted follow-up
python /mnt/skills/deep-research/scripts/web_search.py "topic specific aspect 2024 data" --max-results 5
```

### Content Extraction
For promising URLs, fetch the full content:

```bash
python /mnt/skills/deep-research/scripts/fetch_page.py "https://example.com/article" \
  --output /mnt/workspace/research/sources/article_name.txt
```

### Image and Data Collection
Download relevant images, datasets, or charts:

```bash
python /mnt/skills/deep-research/scripts/download_file.py "https://example.com/chart.png" \
  --output /mnt/workspace/research/images/market_share.png
```

### Collection Strategy
- Search in **multiple languages** if the topic is international
- Use **different query angles** for the same topic (statistics, trends, opinions, case studies)
- Save **every useful source** — you can filter later
- Record the source URL in each saved file for citation

## Phase 3: Data Analysis

When you have quantitative data, analyze it with Python:

```python
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Source Han Sans CN', 'WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Load collected data
df = pd.read_csv('/mnt/workspace/research/data/market_data.csv')

# Analyze
summary = df.groupby('category')['revenue'].sum().sort_values(ascending=False)
print(summary)

# Generate chart for the report
fig, ax = plt.subplots(figsize=(10, 6))
summary.plot(kind='bar', ax=ax)
ax.set_title('Revenue by Category')
ax.set_ylabel('Revenue (¥)')
plt.tight_layout()
plt.savefig('/mnt/workspace/report/assets/revenue_by_category.png', dpi=150, bbox_inches='tight')
plt.close()
print("Chart saved.")
```

For predictive analysis, use appropriate statistical methods:
- **Trend extrapolation**: Linear/polynomial regression with `numpy.polyfit`
- **Growth rates**: Compound annual growth rate (CAGR) calculations
- **Comparisons**: Percentage differences, ratio analysis

**Always state the methodology and limitations of any prediction.**

## Phase 4: Report Drafting

### Step 1: Load the template
Read `references/REPORT_TEMPLATE.md` for the structural skeleton.

### Step 2: Write section by section
Do NOT write the entire report at once. Write each section as a separate operation, referencing your collected materials:

```python
section = """
## Market Overview

The global market for [X] reached ¥{value} billion in 2024, 
representing a {growth}% year-over-year increase [1]. 

![Market Size Trend](assets/market_trend.png)
*Figure 1: Market size evolution from 2020 to 2024. Source: [1]*

Key drivers include:
- **Factor A**: Description with evidence [2]
- **Factor B**: Description with evidence [3]

| Region | Market Share | Growth Rate |
|--------|-------------|-------------|
| Asia   | 45.2%       | 12.3%       |
| Europe | 28.1%       | 8.7%        |
| Americas | 26.7%     | 10.1%       |

*Table 1: Regional market distribution. Source: [1][4]*
"""
```

### Step 3: Assemble the full report
Once all sections are written, assemble them into the final document and save to `/mnt/workspace/report/report.md`.

### Step 4: Write executive summary last
After the full report is written, compose the executive summary based on the actual findings.

## Phase 5: Validation and Polish

### Compile and validate
```bash
python /mnt/skills/deep-research/scripts/compile_report.py \
  /mnt/workspace/report/report.md --validate --to-html
```

This checks:
- All image references resolve to existing files
- Citation numbers `[n]` match entries in the references section
- Report structure is complete (title, TOC, body, references)

### Review checklist
- [ ] Every factual claim has a `[n]` citation
- [ ] Every chart has a caption and source attribution
- [ ] Numbers are formatted consistently (thousands separator, decimal places)
- [ ] All images exist at their referenced paths
- [ ] Executive summary accurately reflects the report content
- [ ] References section lists all cited sources with URLs
- [ ] No placeholder text remains (`[TODO]`, `[TBD]`, `xxx`)

# Verification Checklist

### Research Quality
- [ ] At least 5 distinct sources consulted
- [ ] Data from multiple independent sources for key claims
- [ ] Recency check: primary data is from the last 1-2 years
- [ ] Conflicting viewpoints acknowledged where they exist

### Report Completeness
- [ ] Executive summary present
- [ ] All planned sections written
- [ ] At least one chart/figure per major section
- [ ] References section with numbered entries
- [ ] Conclusion with actionable recommendations

### Technical Accuracy
- [ ] All code-generated numbers match the report text
- [ ] Charts accurately represent the underlying data
- [ ] Predictions clearly labeled as estimates with methodology stated
- [ ] Units and time periods specified for all data

# Error Handling

- **Search returns no results**: Try alternative queries, different keywords, or broader terms
- **Page fetch fails**: Try with different headers, or note the URL for manual review
- **Image download fails**: Skip and note in report, or find alternative image
- **Missing dependencies**: `pip install requests beautifulsoup4 duckduckgo-search pandas matplotlib -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple`
- **Network timeout**: Retry with longer timeout, or move to next source
- **Encoding issues**: Try `encoding='utf-8'`, then `'gbk'`, then `'latin1'`
