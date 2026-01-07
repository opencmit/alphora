"""
工具调用执行器

用于在Agent中执行工具调用，支持：
1. 自动解析LLM返回的工具调用
2. 执行工具并返回结果
3. 多轮工具调用循环
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass

from alphora.tools.base import Tool, ToolResult, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """工具调用请求"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCallResult:
    """工具调用结果"""
    call_id: str
    tool_name: str
    result: ToolResult

    def to_message(self) -> Dict[str, Any]:
        """转换为消息格式"""
        return {
            "role": "tool",
            "tool_call_id": self.call_id,
            "name": self.tool_name,
            "content": str(self.result)
        }


class ToolExecutor:
    """
    工具执行器

    用于解析和执行工具调用

    使用方式：
    ```python
    # 注册工具
    registry = ToolRegistry()
    registry.register(search_tool)
    registry.register(calculator_tool)

    executor = ToolExecutor(registry)

    # 解析LLM返回的工具调用
    tool_calls = executor.parse_tool_calls(llm_response)

    # 执行工具调用
    results = await executor.execute_all(tool_calls)

    # 构建新的消息
    messages = executor.build_tool_messages(results)
    ```
    """

    def __init__(
            self,
            registry: ToolRegistry,
            on_tool_start: Optional[Callable[[ToolCall], None]] = None,
            on_tool_end: Optional[Callable[[ToolCallResult], None]] = None
    ):
        self.registry = registry
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end

    def parse_tool_calls(self, response: Union[str, Dict, Any]) -> List[ToolCall]:
        """
        从LLM响应中解析工具调用

        支持多种格式：
        1. OpenAI格式的tool_calls
        2. 自定义JSON格式
        """
        tool_calls = []

        # 处理OpenAI格式
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments)
                ))
            return tool_calls

        # 处理字典格式
        if isinstance(response, dict):
            # OpenAI消息格式
            if 'tool_calls' in response:
                for tc in response['tool_calls']:
                    func = tc.get('function', tc)
                    tool_calls.append(ToolCall(
                        id=tc.get('id', f"call_{len(tool_calls)}"),
                        name=func['name'],
                        arguments=json.loads(func['arguments'])
                        if isinstance(func['arguments'], str)
                        else func['arguments']
                    ))
                return tool_calls

            # 简单格式 {"tool": "name", "args": {...}}
            if 'tool' in response:
                tool_calls.append(ToolCall(
                    id=f"call_0",
                    name=response['tool'],
                    arguments=response.get('args', response.get('arguments', {}))
                ))
                return tool_calls

        # 处理字符串格式（尝试JSON解析）
        if isinstance(response, str):
            try:
                data = json.loads(response)
                return self.parse_tool_calls(data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    async def execute(self, tool_call: ToolCall) -> ToolCallResult:
        """执行单个工具调用"""
        if self.on_tool_start:
            self.on_tool_start(tool_call)

        tool = self.registry.get(tool_call.name)

        if tool is None:
            result = ToolResult.fail(f"Tool '{tool_call.name}' not found")
        else:
            try:
                result = await tool(**tool_call.arguments)
            except Exception as e:
                logger.exception(f"Tool execution failed: {tool_call.name}")
                result = ToolResult.fail(str(e))

        call_result = ToolCallResult(
            call_id=tool_call.id,
            tool_name=tool_call.name,
            result=result
        )

        if self.on_tool_end:
            self.on_tool_end(call_result)

        return call_result

    async def execute_all(self, tool_calls: List[ToolCall]) -> List[ToolCallResult]:
        """执行所有工具调用"""
        results = []
        for tc in tool_calls:
            result = await self.execute(tc)
            results.append(result)
        return results

    def build_tool_messages(self, results: List[ToolCallResult]) -> List[Dict[str, Any]]:
        """构建工具结果消息"""
        return [result.to_message() for result in results]

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """获取LLM可用的工具定义"""
        return self.registry.to_openai_tools()


class ToolAgentMixin:
    """
    工具Agent混入类

    为BaseAgent添加工具调用能力

    使用方式：
    ```python
    class MyAgent(BaseAgent, ToolAgentMixin):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.setup_tools()

            # 注册工具
            @self.tool
            async def search(query: str) -> str:
                '''搜索互联网'''
                return f"搜索结果: {query}"

        async def chat(self, query: str):
            # 使用工具增强的对话
            response = await self.chat_with_tools(query)
            return response
    ```
    """

    def setup_tools(self):
        """初始化工具系统"""
        self._tool_registry = ToolRegistry()
        self._tool_executor = ToolExecutor(
            self._tool_registry,
            on_tool_start=self._on_tool_start,
            on_tool_end=self._on_tool_end
        )

    def _on_tool_start(self, tool_call: ToolCall):
        """工具开始执行回调"""
        logger.info(f"Executing tool: {tool_call.name}")

    def _on_tool_end(self, result: ToolCallResult):
        """工具执行完成回调"""
        status = "success" if result.result.success else "failed"
        logger.info(f"Tool {result.tool_name} {status}")

    def register_tool(self, tool: Tool):
        """注册工具"""
        self._tool_registry.register(tool)

    def tool(
            self,
            func: Optional[Callable] = None,
            *,
            name: Optional[str] = None,
            description: Optional[str] = None
    ):
        """
        工具装饰器

        用于将方法注册为工具
        """
        from alphora.tools.decorators import tool as tool_decorator

        def decorator(fn):
            tool_instance = tool_decorator(
                fn,
                name=name,
                description=description,
                register=False
            )
            self._tool_registry.register(tool_instance)
            return tool_instance

        if func is not None:
            return decorator(func)
        return decorator

    async def execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolCallResult]:
        """执行工具调用"""
        return await self._tool_executor.execute_all(tool_calls)

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取工具Schema"""
        return self._tool_executor.get_tools_for_llm()

    async def chat_with_tools(
            self,
            query: str,
            max_iterations: int = 5,
            system_prompt: Optional[str] = None
    ) -> str:
        """
        带工具调用的对话

        自动处理工具调用循环
        """
        if not hasattr(self, 'llm') or self.llm is None:
            raise ValueError("LLM not configured")

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": query})

        tools = self.get_tools_schema()

        for iteration in range(max_iterations):
            # 调用LLM
            # 这里需要根据具体LLM实现来调整
            # 暂时返回简单实现
            response = await self.llm.aget_non_stream_response(
                message=query,
                system_prompt=system_prompt
            )

            # 解析工具调用
            tool_calls = self._tool_executor.parse_tool_calls(response)

            if not tool_calls:
                # 没有工具调用，返回响应
                return response

            # 执行工具
            results = await self.execute_tools(tool_calls)

            # 构建工具结果消息
            tool_messages = self._tool_executor.build_tool_messages(results)
            messages.extend(tool_messages)

            # 将工具结果添加到query中继续对话
            tool_results_str = "\n".join([
                f"[{r.tool_name}]: {r.result}"
                for r in results
            ])
            query = f"工具调用结果:\n{tool_results_str}\n\n请基于以上结果回答用户问题。"

        return "达到最大迭代次数，无法完成任务"
