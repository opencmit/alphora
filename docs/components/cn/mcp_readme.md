# Alphora MCP

将 MCP Server 的工具接入 Alphora 现有工具链（`ToolRegistry` / `ReActAgent`），无需改写 Agent。支持三种传输：

- `stdio`：本地子进程（`command` + `args`）
- `sse`：远程 SSE（`url`）
- `streamable_http`：远程 Streamable HTTP（`url`）

## 安装

```bash
pip install "alphora[mcp]"
```

未安装 `mcp` 时，`import alphora.mcp` 会提示上述命令。

## 快速开始

```python
import asyncio
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.mcp import setup_mcp

async def main():
    llm = OpenAILike()

    async with setup_mcp(
        servers=[
            {
                "name": "filesystem",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/path/to/workspace",
                ],
            },
        ],
    ) as tools:
        agent = ReActAgent(
            llm=llm,
            tools=tools,
            system_prompt="你可以使用 MCP 工具。工具名格式为 filesystem__<tool_name>。",
        )
        print(await agent.run("列出工作区根目录下的文件"))

asyncio.run(main())
```

## 远程 URL 用法（SSE / Streamable HTTP）

面向托管/多用户场景推荐用远程 URL，不在本机执行任何命令：

```python
async with setup_mcp(
    servers=[
        {
            "name": "deepwiki",
            "transport": "sse",
            "url": "https://mcp.deepwiki.com/sse",
        },
        {
            "name": "myapi",
            "transport": "streamable_http",
            "url": "https://example.com/mcp",
            "headers": {"Authorization": "Bearer xxx"},
        },
    ],
) as tools:
    agent = ReActAgent(llm=llm, tools=tools)
    await agent.run("...")
```

只给 `url`、不写 `transport` 时默认按 `streamable_http` 处理。

## 配置说明

`servers` 中每一项需要 `name`，再按传输方式给出对应字段：

| 字段 | 适用 | 必填 | 说明 |
|------|------|------|------|
| `name` | 全部 | 是 | 逻辑服务名，会作为工具名前缀 |
| `transport` | 全部 | 否 | `stdio` / `sse` / `streamable_http`，可省略由字段推断 |
| `command` | stdio | 是 | 启动 MCP Server 的可执行文件 |
| `args` | stdio | 是 | 命令行参数列表 |
| `env` | stdio | 否 | 环境变量覆盖 |
| `cwd` | stdio | 否 | 子进程工作目录 |
| `url` | sse / http | 是 | 远程 MCP 服务地址 |
| `headers` | sse / http | 否 | 自定义请求头（鉴权 token 等） |
| `timeout` / `sse_read_timeout` | sse / http | 否 | 连接 / 读取超时 |

`setup_mcp(..., tool_timeout=30, fail_fast=False)`：`tool_timeout` 为单次工具调用超时；`fail_fast=False` 时某个 server 连接失败会跳过而不中断其余 server。

## 工具命名

默认：`{name}__{mcp_tool_name}`，例如 `filesystem__list_directory`。

多 Server 时避免重名；请在 prompt 中说明前缀规则。

## 生命周期

`setup_mcp` 是 **异步上下文管理器**。`async with` 块结束后会关闭子进程连接。

- 单次脚本：`async with` 必须包住 `agent.run()`
- 长驻服务：在应用 lifespan 内保持连接（二期文档补充 FastAPI 示例）

## 与本地 `@tool` 混用

```python
from alphora.tools import tool

@tool
def helper(x: str) -> str:
    return x

async with setup_mcp(servers=[...]) as mcp_tools:
    agent = ReActAgent(llm=llm, tools=[*mcp_tools, helper])
```

## 范围与后续

**当前支持：** stdio + 远程（SSE / Streamable HTTP）、Python `servers` 配置、多 Server、并发锁、调用超时、Tools only。

**后续可选：** 读取 Cursor `mcp.json`、`prefix_tools=False`、MCP Resources / Prompts。

## API

- `setup_mcp(servers)` — 异步上下文，yield `list[Tool]`
- `mcp_tool_name(server, tool)` — 计算 Alphora 工具名
- `MCPTool` — 内部桥接类（高级用法一般不需要直接使用）
