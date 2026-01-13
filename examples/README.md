# Alphora 框架示例集

本目录包含 Alphora 智能体开发框架的完整示例，帮助你快速上手各项功能。

## 目录结构

```
examples/
├── README.md                        # 本文件
├── 01_quickstart/                   # 快速入门
│   ├── basic_agent.py               # 基础智能体 (6个示例)
│   └── simple_chat.py               # 简单对话 (6个示例)
├── 02_llm/                          # LLM 模型使用
│   ├── openai_like.py               # OpenAI 兼容接口 (10个示例)
│   └── multimodal.py                # 多模态消息 (10个示例)
├── 03_prompter/                     # 提示词模板
│   ├── basic_prompt.py              # 基础提示词 (10个示例)
│   ├── template_file.py             # 模板文件 (6个示例)
│   ├── memory_prompt.py             # 带记忆的提示词 (8个示例)
│   └── parallel_prompt.py           # 并行提示词 (7个示例)
├── 04_memory/                       # 记忆系统
│   ├── basic_memory.py              # 基础记忆管理 (8个示例)
│   └── advanced_memory.py           # 高级记忆功能 (8个示例)
├── 05_postprocess/                  # 后处理器
│   └── postprocessors.py            # 各种后处理器 (9个示例)
├── 06_tools/                        # 工具系统
│   └── tools.py                     # 工具定义和执行 (10个示例)
├── 07_storage/                      # 存储系统
│   └── storage.py                   # 存储后端 (10个示例)
├── 08_sandbox/                      # 沙箱系统
│   └── sandbox.py                   # 代码执行沙箱 (10个示例)
├── 09_server/                       # API 服务
│   └── server_api.py                # API发布 (10个示例)
└── 10_advanced/                     # 高级用法
    └── advanced_examples.py         # 高级示例 (8个示例)
```

## 示例统计

| 模块 | 文件数 | 示例数 | 主要内容 |
|------|--------|--------|----------|
| 01_quickstart | 2 | 12 | Agent创建、配置、派生、会话管理 |
| 02_llm | 2 | 20 | LLM初始化、调用、流式、负载均衡、多模态 |
| 03_prompter | 4 | 31 | Prompt创建、模板、记忆集成、并行执行 |
| 04_memory | 2 | 16 | 记忆管理、搜索、衰减、持久化、反思 |
| 05_postprocess | 1 | 9 | 过滤、替换、JSON提取、模式匹配 |
| 06_tools | 1 | 10 | 工具定义、装饰器、执行器、异步工具 |
| 07_storage | 1 | 10 | 内存/JSON/SQLite存储、批量操作 |
| 08_sandbox | 1 | 10 | 代码执行、文件操作、安全限制 |
| 09_server | 1 | 10 | API发布、流式、认证、部署 |
| 10_advanced | 1 | 8 | 自定义Agent、派生、工作流、协作 |
| **总计** | **16** | **136** | |

## 环境准备

### 1. 安装依赖

```bash
pip install alphora
```

### 2. 配置环境变量

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DEFAULT_LLM="qwen-plus"
```

## 快速开始

```python
import asyncio
from alphora.agent import BaseAgent
from alphora.models import OpenAILike

# 创建 LLM
llm = OpenAILike(
    api_key="your-api-key",
    base_url="https://api.openai.com/v1",
    model_name="gpt-4"
)

# 创建智能体
agent = BaseAgent(llm=llm)

# 创建提示词并调用
prompt = agent.create_prompt(
    system_prompt="你是一个友好的助手"
)

async def main():
    response = await prompt.acall(query="你好！")
    print(response)

asyncio.run(main())
```

## 各模块详解

### 01_quickstart - 快速入门
- **basic_agent.py**: Agent的创建、配置、LLM设置、派生、会话管理
- **simple_chat.py**: 简单对话、流式输出、模板使用、记忆集成

### 02_llm - LLM模块
- **openai_like.py**: OpenAI兼容接口的完整用法，包括初始化、调用、流式、负载均衡
- **multimodal.py**: 多模态消息构建，支持文本、图片、音频、视频

### 03_prompter - 提示词模块
- **basic_prompt.py**: 两种Prompt模式、占位符、流式输出、JSON输出、思考过程
- **template_file.py**: 从文件加载模板、Jinja2语法、模板组合
- **memory_prompt.py**: 记忆集成、多会话隔离、历史控制、手动管理
- **parallel_prompt.py**: 并行执行、多角度分析、投票机制

### 04_memory - 记忆模块
- **basic_memory.py**: 记忆管理器创建、添加记忆、构建历史、会话隔离
- **advanced_memory.py**: 记忆搜索、衰减策略、检索策略、持久化、LLM反思

### 05_postprocess - 后处理器
- **postprocessors.py**: FilterPP、ReplacePP、JsonKeyExtractorPP、PatternMatcherPP等

### 06_tools - 工具系统
- **tools.py**: Tool类、@tool装饰器、ToolExecutor、异步工具、工具链

### 07_storage - 存储系统
- **storage.py**: InMemoryStorage、JSONStorage、SQLiteStorage、批量操作

### 08_sandbox - 沙箱系统
- **sandbox.py**: 代码执行、文件操作、FileReaderFactory、安全限制

### 09_server - API服务
- **server_api.py**: publish_agent_api、流式API、认证、部署配置

### 10_advanced - 高级用法
- **advanced_examples.py**: 自定义Agent、派生、多组件集成、工作流、Agent协作

## 核心概念

| 组件 | 描述 |
|------|------|
| **BaseAgent** | 智能体基类，提供 LLM 调用、记忆管理、派生等核心功能 |
| **BasePrompt** | 提示词模板，支持占位符、记忆集成、流式输出 |
| **MemoryManager** | 记忆管理器，支持多会话、持久化、搜索等功能 |
| **Tool** | 工具定义和执行系统，支持装饰器和类定义方式 |
| **Storage** | 统一的存储接口，支持 JSON、SQLite、内存等后端 |
| **Sandbox** | 安全的代码执行环境，支持资源限制和超时控制 |
| **PostProcessor** | 流式输出后处理器，支持过滤、替换、提取等操作 |

## 学习路径建议

1. **入门**: 01_quickstart → 02_llm/openai_like.py
2. **进阶**: 03_prompter → 04_memory
3. **实用**: 05_postprocess → 06_tools
4. **部署**: 07_storage → 08_sandbox → 09_server
5. **精通**: 10_advanced

## 示例运行

```bash
# 运行单个示例
cd examples/01_quickstart
python basic_agent.py

# 运行特定模块的示例
python -m examples.06_tools.tools
```

## 注意事项

1. 运行示例前请确保配置了正确的环境变量
2. 部分示例需要安装额外依赖（如 pypdf、openpyxl）
3. 涉及网络请求的示例需要稳定的网络连接
4. 生产环境使用建议参考 10_advanced 中的最佳实践