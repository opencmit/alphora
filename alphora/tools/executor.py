"""
工具执行器

使用示例:
```python
from alphora.tools import ToolExecutor, ToolRegistry
from alphora.memory import MemoryManager

# 初始化
registry = ToolRegistry()
registry.register(get_weather_tool)

executor = ToolExecutor(registry)
memory = MemoryManager()

# 用户输入
memory.add_user("北京天气怎么样？")

# 获取 LLM 响应
history = memory.build_history()
response = await prompt.acall(query=None, history=history, tools=registry.get_tools())

# 智能记录 assistant
memory.add_assistant(response)

# 如果有工具调用
if getattr(response, 'has_tool_calls', False):
    # 执行工具
    results = await executor.execute(response)

    # 一行记录所有结果
    memory.add_tool_result(results)

    # 继续对话
    history = memory.build_history()
    final_response = await prompt.acall(query=None, history=history)
    memory.add_assistant(final_response)
```
"""

import json
import asyncio
import logging
from typing import List, Dict, Any, Union, Optional, Callable
from pydantic import BaseModel

from .core import Tool
from .registry import ToolRegistry
from .exceptions import ToolValidationError, ToolExecutionError
from alphora.models.llms.types import ToolCall
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

logger = logging.getLogger(__name__)


class ToolExecutionResult(BaseModel):
    """
    单个工具执行的标准化结果

    Attributes:
        tool_call_id: 对应 LLM 返回的 call_id (必须原样返回给 LLM)
        tool_name: 工具名称
        content: 执行结果 (字符串格式)
        status: 执行状态 ("success" | "error")
        error_type: 错误类型 (仅当 status="error" 时)
    """
    tool_call_id: str
    tool_name: str
    content: str
    status: str = "success"
    error_type: Optional[str] = None

    def to_openai_message(self) -> Dict[str, Any]:
        """
        转换为 OpenAI 消息格式 (role='tool')

        可直接用于 memory.add_tool_result() 或传入 LLM
        """
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.tool_name,
            "content": self.content
        }

    def to_memory_args(self) -> Dict[str, Any]:
        """
        转换为 MemoryManager.add_tool_result() 的参数

        Example:
            result = await executor.execute_single(tool_call)
            memory.add_tool_result(**result.to_memory_args())
        """
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.tool_name,
            "content": self.content
        }


class ToolExecutor:
    """
    工具执行引擎

    负责解析和执行工具调用。

    Example:
        executor = ToolExecutor(registry)

        # 执行工具调用
        results = await executor.execute(tool_calls)

        # 开发者手动记录到记忆
        for result in results:
            memory.add_tool_result(**result.to_memory_args())
    """

    def __init__(
            self,
            registry: ToolRegistry,
            hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
            before_execute: Optional[Callable] = None,
            after_execute: Optional[Callable] = None,
            on_error: Optional[Callable] = None,
    ):
        """
        Args:
            registry: 工具注册表
        """
        self.registry = registry
        self._hooks = build_manager(
            hooks,
            short_map={
                "before_execute": HookEvent.TOOLS_BEFORE_EXECUTE,
                "after_execute": HookEvent.TOOLS_AFTER_EXECUTE,
                "on_error": HookEvent.TOOLS_ON_ERROR,
            },
            before_execute=before_execute,
            after_execute=after_execute,
            on_error=on_error,
        )

    async def execute(
            self,
            tool_calls: Union[ToolCall, List[Dict[str, Any]], Dict[str, Any]],
            parallel: bool = True,
    ) -> List[ToolExecutionResult]:
        """
        执行工具调用

        Args:
            tool_calls: 工具调用数据，支持:
                - ToolCall 对象 (直接传入 LLM 响应)
                - 单个工具调用字典
                - 工具调用字典列表
            parallel: 是否并行执行 (默认 True)

        Returns:
            ToolExecutionResult 列表

        Example:
            # 直接传入 LLM 响应
            results = await executor.execute(response)
            memory.add_tool_result(results)
        """
        if not tool_calls:
            return []

        # 规范化输入
        normalized_calls = self._normalize_tool_calls(tool_calls)

        if not normalized_calls:
            return []

        # 执行
        if parallel:
            tasks = [self._execute_single_tool(call) for call in normalized_calls]
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for call in normalized_calls:
                result = await self._execute_single_tool(call)
                results.append(result)

        return results

    async def execute_single(
            self,
            tool_call: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        执行单个工具调用

        Args:
            tool_call: 工具调用字典

        Returns:
            ToolExecutionResult
        """
        return await self._execute_single_tool(tool_call)

    def _normalize_tool_calls(
            self,
            tool_calls: Union[ToolCall, List[Dict[str, Any]], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """规范化工具调用输入"""

        if isinstance(tool_calls, list) and hasattr(tool_calls, 'content'):
            return list(tool_calls) if tool_calls else []

        # 处理单个字典
        if isinstance(tool_calls, dict):
            return [tool_calls]

        # 处理普通列表
        if isinstance(tool_calls, list):
            return tool_calls

        logger.warning(f"Unknown tool_calls type: {type(tool_calls)}")
        return []

    async def _execute_single_tool(self, tool_call: Dict[str, Any]) -> ToolExecutionResult:
        """
        执行单个工具调用
        """
        call_id = tool_call.get("id", "unknown")
        function_data = tool_call.get("function", {})
        tool_name = function_data.get("name", "unknown")
        arguments_str = function_data.get("arguments", "{}")

        logger.info(f"Executing tool: {tool_name} [id={call_id}]")

        try:
            # 1. 查找工具
            tool = self.registry.get_tool(tool_name)
            if not tool:
                error_result = ToolExecutionResult(
                    tool_call_id=call_id,
                    tool_name=tool_name,
                    content=f"Error: Tool '{tool_name}' not found in registry.",
                    status="error",
                    error_type="ToolNotFoundError"
                )
                await self._hooks.emit(
                    HookEvent.TOOLS_ON_ERROR,
                    HookContext(
                        event=HookEvent.TOOLS_ON_ERROR,
                        component="tools",
                        data={
                            "tool_call": tool_call,
                            "tool_call_id": call_id,
                            "tool_name": tool_name,
                            "tool_args": None,
                            "tool": None,
                            "tool_result": error_result,
                        },
                    ),
                )
                return error_result

            # 2. 解析 JSON 参数
            try:
                if isinstance(arguments_str, str):
                    arguments = self._parse_tool_arguments(arguments_str)
                else:
                    arguments = arguments_str or {}
            except (json.JSONDecodeError, ValueError) as e:
                error_result = ToolExecutionResult(
                    tool_call_id=call_id,
                    tool_name=tool_name,
                    content=f"Error: Invalid JSON arguments - {str(e)}",
                    status="error",
                    error_type="JSONDecodeError"
                )
                await self._hooks.emit(
                    HookEvent.TOOLS_ON_ERROR,
                    HookContext(
                        event=HookEvent.TOOLS_ON_ERROR,
                        component="tools",
                        data={
                            "tool_call": tool_call,
                            "tool_call_id": call_id,
                            "tool_name": tool_name,
                            "tool_args": None,
                            "tool": tool,
                            "tool_result": error_result,
                        },
                    ),
                )
                return error_result

            # 3. 执行工具
            before_ctx = HookContext(
                event=HookEvent.TOOLS_BEFORE_EXECUTE,
                component="tools",
                data={
                    "tool_call": tool_call,
                    "tool_call_id": call_id,
                    "tool_name": tool_name,
                    "tool_args": arguments,
                    "tool": tool,
                },
            )
            before_ctx = await self._hooks.emit(HookEvent.TOOLS_BEFORE_EXECUTE, before_ctx)
            arguments = before_ctx.data.get("tool_args", arguments)

            result_data = await tool.arun(**arguments)

            # 4. 序列化结果
            if not isinstance(result_data, str):
                content = json.dumps(result_data, ensure_ascii=False)
            else:
                content = result_data

            logger.info(f"Tool {tool_name} executed successfully")

            execution_result = ToolExecutionResult(
                tool_call_id=call_id,
                tool_name=tool_name,
                content=content,
                status="success"
            )
            after_ctx = HookContext(
                event=HookEvent.TOOLS_AFTER_EXECUTE,
                component="tools",
                data={
                    "tool_call": tool_call,
                    "tool_call_id": call_id,
                    "tool_name": tool_name,
                    "tool_args": arguments,
                    "tool": tool,
                    "tool_result": execution_result,
                },
            )
            after_ctx = await self._hooks.emit(HookEvent.TOOLS_AFTER_EXECUTE, after_ctx)
            return after_ctx.data.get("tool_result", execution_result)

        except ToolValidationError as e:
            logger.warning(f"Validation failed for {tool_name}: {e}")
            error_result = ToolExecutionResult(
                tool_call_id=call_id,
                tool_name=tool_name,
                content=f"Error: Arguments validation failed - {str(e)}",
                status="error",
                error_type="ValidationError"
            )
            await self._hooks.emit(
                HookEvent.TOOLS_ON_ERROR,
                HookContext(
                    event=HookEvent.TOOLS_ON_ERROR,
                    component="tools",
                    data={
                        "tool_call": tool_call,
                        "tool_call_id": call_id,
                        "tool_name": tool_name,
                        "tool_args": arguments_str,
                        "tool": None,
                        "tool_result": error_result,
                    },
                ),
            )
            return error_result

        except ToolExecutionError as e:
            logger.error(f"Runtime error in {tool_name}: {e}")
            error_result = ToolExecutionResult(
                tool_call_id=call_id,
                tool_name=tool_name,
                content=f"Error: Execution failed - {str(e)}",
                status="error",
                error_type="ExecutionError"
            )
            await self._hooks.emit(
                HookEvent.TOOLS_ON_ERROR,
                HookContext(
                    event=HookEvent.TOOLS_ON_ERROR,
                    component="tools",
                    data={
                        "tool_call": tool_call,
                        "tool_call_id": call_id,
                        "tool_name": tool_name,
                        "tool_args": arguments_str,
                        "tool": None,
                        "tool_result": error_result,
                    },
                ),
            )
            return error_result

        except Exception as e:
            logger.exception(f"Unexpected error in {tool_name}")
            error_result = ToolExecutionResult(
                tool_call_id=call_id,
                tool_name=tool_name,
                content=f"Error: Unexpected internal error - {str(e)}",
                status="error",
                error_type="InternalError"
            )
            await self._hooks.emit(
                HookEvent.TOOLS_ON_ERROR,
                HookContext(
                    event=HookEvent.TOOLS_ON_ERROR,
                    component="tools",
                    data={
                        "tool_call": tool_call,
                        "tool_call_id": call_id,
                        "tool_name": tool_name,
                        "tool_args": arguments_str,
                        "tool": None,
                        "tool_result": error_result,
                    },
                ),
            )
            return error_result

    @staticmethod
    def _parse_tool_arguments(raw: str) -> dict:
        """Parse JSON arguments from LLM, with tolerance for common errors.

        LLMs frequently produce invalid JSON escape sequences such as ``\\'``
        (backslash + single-quote) inside double-quoted strings.  Standard
        ``json.loads`` rejects these.  This helper attempts a strict parse
        first, then falls back to a lenient repair pass before giving up.
        """
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Repair pass: fix common LLM JSON errors
        repaired = raw
        # \' is not valid JSON escape — replace with bare '
        repaired = repaired.replace("\\'", "'")
        # Trailing commas before } or ] (e.g.  {"a":1,} )
        import re
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        return json.loads(repaired)

    def execute_sync(
            self,
            tool_calls: Union[ToolCall, List[Dict[str, Any]], Dict[str, Any]],
    ) -> List[ToolExecutionResult]:
        """
        同步执行工具调用

        在非异步环境中使用

        Args:
            tool_calls: 工具调用数据

        Returns:
            ToolExecutionResult 列表
        """
        return asyncio.run(self.execute(tool_calls))


# ==================== 便捷函数 ====================

async def execute_tools(
        registry: ToolRegistry,
        tool_calls: Union[ToolCall, List[Dict[str, Any]]],
) -> List[ToolExecutionResult]:
    """
    执行工具调用

    Args:
        registry: 工具注册表
        tool_calls: 工具调用数据

    Returns:
        ToolExecutionResult 列表

    Example:
        results = await execute_tools(registry, tool_response.tool_calls)
        for result in results:
            memory.add_tool_result(**result.to_memory_args())
    """
    executor = ToolExecutor(registry)
    return await executor.execute(tool_calls)


def add_tool_results_to_memory(
        memory: "MemoryManager",
        results: List[ToolExecutionResult],
        session_id: str = "default"
) -> None:
    """
    将工具执行结果添加到记忆

    Args:
        memory: MemoryManager 实例
        results: ToolExecutionResult 列表
        session_id: 会话ID

    Example:
        results = await executor.execute(tool_calls)
        add_tool_results_to_memory(memory, results)
    """
    for result in results:
        memory.add_tool_result(
            tool_call_id=result.tool_call_id,
            name=result.tool_name,
            content=result.content,
            session_id=session_id
        )

