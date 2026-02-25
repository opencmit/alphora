# Deep Research - Alphora Skills 综合示例

基于 Alphora 框架的深度研究智能体，展示 **Skills + Sandbox + Tools + Agent + Hooks** 的完整协作方式。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                   用户: "研究 XXX"                    │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              DeepResearchAgent                       │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Skills 层 (策略层 / "知道怎么做")             │   │
│  │                                             │   │
│  │  deep-research Skill 被激活：                │   │
│  │  - 定义了完整的研究方法论                     │   │
│  │  - 指导 Agent 按步骤执行研究                  │   │
│  │  - 引用 scripts/ 和 references/             │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │ Tools 层 (执行层 / "实际去做")               │   │
│  │                                             │   │
│  │  ① web_search      → 搜索信息               │   │
│  │  ② fetch_webpage    → 抓取网页内容           │   │
│  │  ③ read_skill       → 加载 Skill 指令       │   │
│  │  ④ run_skill_script → 在沙箱中执行分析脚本   │   │
│  │  ⑤ run_python_code  → 在沙箱中执行代码       │   │
│  │  ⑥ save_file        → 保存文件到沙箱         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Sandbox (安全执行环境)                       │   │
│  │  - 运行研究分析脚本                          │   │
│  │  - 处理和清洗数据                            │   │
│  │  - 生成最终研究报告                          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 本示例演示了什么

| 组件 | 演示内容 |
|------|---------|
| **Skills** | Skill 发现、激活、资源读取、脚本执行的完整生命周期 |
| **Sandbox** | 本地/Docker 沙箱中执行 Python 脚本和代码 |
| **Tools** | 自定义工具定义、与 Skill 内置工具混合使用 |
| **Agent** | SkillAgent 驱动的 ReAct 循环 |
| **Hooks** | 进度追踪和执行日志 |

## 目录结构

```
deep_research/
├── README.md              ← 本文件
├── run.py                 ← 启动入口
├── agent.py               ← DeepResearchAgent 定义
├── tools.py               ← 自定义工具（搜索、抓取网页等）
└── skills/                ← Skill 目录
    └── deep-research/     ← 深度研究 Skill（符合 agentskills.io 标准）
        ├── SKILL.md       ← 核心指令文件
        ├── scripts/       ← 可执行脚本
        │   ├── extract_topics.py     提取关键主题
        │   └── generate_report.py    生成 Markdown 报告
        └── references/    ← 参考文档
            └── METHODOLOGY.md        研究方法论详解
```

## 快速开始

### 1. 设置环境变量

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选
```

### 2. 运行

```bash
# 基础用法
python -m examples.deep_research.run "Agent Skills 技术趋势分析"

# 指定模型
python -m examples.deep_research.run "量子计算最新进展" --model gpt-4

# 使用 Docker 沙箱（更安全）
python -m examples.deep_research.run "AI Agent 框架对比" --runtime docker
```

### 3. 输出

执行完成后，研究报告会保存到沙箱工作目录中：
- `research_report.md` - 完整研究报告
- `topics.json` - 提取的关键主题
- `sources.json` - 引用的信息源

## 核心概念说明

### Skill 与 Tool 的协作

这是本示例最核心的概念。`deep-research` Skill 不直接执行任何操作，它做的是：

1. **告诉 LLM 应该做什么** - SKILL.md 中定义了研究的步骤和方法论
2. **告诉 LLM 用什么工具** - 指令中引用了 `web_search`、`fetch_webpage` 等工具
3. **告诉 LLM 如何使用脚本** - 指令中说明了 `scripts/` 下的脚本用途和参数

LLM 读取 Skill 指令后，自主决定调用哪些 Tool 来完成研究任务。

### Sandbox 的作用

Skill 中的 `scripts/extract_topics.py` 和 `scripts/generate_report.py` 需要在隔离环境中执行。Sandbox 提供：

- **安全隔离** - 脚本不会影响宿主机
- **文件管理** - 研究过程中的中间文件和最终报告都保存在沙箱中
- **包管理** - 可按需安装脚本依赖的 Python 包
