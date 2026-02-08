# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


"""
ReAct Agent - 支持自动工具调用循环的智能体

基础用法：
    agent = ReActAgent(
        llm=OpenAILike(),
        tools=[get_weather, search],
        system_prompt="你是一个智能助手",
    )
    response = await agent.run("今天北京天气怎么样？")

带 Sandbox 的用法：
    async with Sandbox.create_local() as sandbox:
        agent = ReActAgent(
            llm=OpenAILike(),
            tools=[get_weather],
            system_prompt="你是一个数据分析助手",
            sandbox=sandbox,  # 自动注册代码执行工具
        )
        response = await agent.run("用 Python 分析这个数据")
"""

from typing import Callable, List, Union, Optional, AsyncIterator, TYPE_CHECKING, Dict, Any
import logging

from .base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.decorators import Tool, tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.memory import MemoryManager
from alphora.sandbox import Sandbox, SandboxTools
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning + Acting) 智能体

    自动处理 LLM 推理和工具调用的循环，直到任务完成或达到最大迭代次数

    Args:
        llm: LLM 实例
        tools: 工具列表，可以是 Tool 实例或被 @tool 装饰的函数
        system_prompt: 系统提示词
        max_iterations: 最大迭代次数，防止无限循环
        sandbox: 可选的 Sandbox 实例，传入后自动注册代码执行相关工具
        memory: 可选的 MemoryManager，用于多轮对话
        **kwargs: 传递给 BaseAgent 的其他参数

    Example:
        # 基础用法
        agent = ReActAgent(
            llm=OpenAILike(model_name="gpt-4"),
            tools=[get_weather, search_web],
            system_prompt="你是一个智能助手",
            max_iterations=10
        )
        result = await agent.run("北京今天天气怎么样？")

        # 带 Sandbox
        async with Sandbox.create_local() as sandbox:
            agent = ReActAgent(
                llm=llm,
                tools=[read_csv],
                sandbox=sandbox,
                system_prompt="你是一个数据分析师"
            )
            result = await agent.run("分析 data.csv 中的销售趋势")
    """

    agent_type: str = "ReActAgent"

    def __init__(
            self,
            llm: OpenAILike,
            tools: List[Union[Tool, Callable]],
            system_prompt: str = "",
            max_iterations: int = 100,
            sandbox: Optional[Sandbox] = None,
            memory: Optional[MemoryManager] = None,
            hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
            before_run: Optional[Callable] = None,
            after_run: Optional[Callable] = None,
            before_iteration: Optional[Callable] = None,
            after_iteration: Optional[Callable] = None,
            **kwargs
    ):
        hook_manager = build_manager(
            hooks,
            short_map={
                "before_run": HookEvent.AGENT_BEFORE_RUN,
                "after_run": HookEvent.AGENT_AFTER_RUN,
                "before_iteration": HookEvent.AGENT_BEFORE_ITERATION,
                "after_iteration": HookEvent.AGENT_AFTER_ITERATION,
            },
            before_run=before_run,
            after_run=after_run,
            before_iteration=before_iteration,
            after_iteration=after_iteration,
        )
        super().__init__(llm=llm, memory=memory, hooks=hook_manager, **kwargs)

        self._registry = ToolRegistry()
        self._sandbox = sandbox
        self._sandbox_tools: Optional["SandboxTools"] = None

        # 注册用户提供的工具
        for t in tools:
            self._registry.register(t)

        if sandbox is not None:
            self._setup_sandbox_tools(sandbox)

        self._executor = ToolExecutor(self._registry)

        # 默认系统提示
        if system_prompt == "":
            system_prompt = self._get_default_system_prompt()

        self._system_prompt = system_prompt
        self._prompt = self.create_prompt(system_prompt=system_prompt)
        self._max_iterations = max_iterations

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        base_prompt = "你是一个 AI 助手，可以使用工具来帮助用户完成任务。"

        if self._sandbox is not None:
            base_prompt += "\n\n你可以执行 Python 代码来分析数据、处理文件等。"
            base_prompt += "当需要编程解决问题时，请使用代码执行工具。"

        return base_prompt

    def _setup_sandbox_tools(self, sandbox: Sandbox) -> None:
        """
        设置沙箱工具， 将 Sandbox 的能力注册为可被 LLM 调用的工具
        """
        from alphora.sandbox import SandboxTools

        self._sandbox_tools = SandboxTools(sandbox)

        self._registry.register(self._sandbox_tools.save_file)
        self._registry.register(self._sandbox_tools.list_files)
        self._registry.register(self._sandbox_tools.run_shell_command)
        # self._registry.register(self._sandbox_tools.read_file)

    async def run(
            self,
            query: str
    ) -> str:
        """
        执行完整的 ReAct 循环

        Args:
            query: 用户查询

        Returns:
            最终响应文本
        """
        await self._hooks.emit(
            HookEvent.AGENT_BEFORE_RUN,
            HookContext(
                event=HookEvent.AGENT_BEFORE_RUN,
                component="agent",
                data={
                    "query": query,
                    "agent_type": self.agent_type,
                    "agent_id": self.agent_id,
                },
            ),
        )
        # 添加用户消息到记忆

        self.memory.add_user(content=query)

        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            logger.debug(f"ReAct iteration {iteration + 1}/{self._max_iterations}")

            # 构建历史
            history = self.memory.build_history()
            await self._hooks.emit(
                HookEvent.AGENT_BEFORE_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_BEFORE_ITERATION,
                    component="agent",
                    data={
                        "iteration": iteration + 1,
                        "history": history,
                        "query": query,
                    },
                ),
            )

            # 调用 LLM
            response = await self._prompt.acall(
                query=query if iteration == 0 else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
                runtime_system_prompt='如果你认为用户的任务已经完成，请直接输出 TASK_FINISHED'
            )

            # 记录助手响应
            self.memory.add_assistant(content=response)

            # 检查是否有工具调用
            if not response.has_tool_calls:
                if "TASK_FINISHED" in response.content:
                    await self._hooks.emit(
                        HookEvent.AGENT_AFTER_RUN,
                        HookContext(
                            event=HookEvent.AGENT_AFTER_RUN,
                            component="agent",
                            data={
                                "result": "",
                                "iteration": iteration + 1,
                            },
                        ),
                    )
                    return ""
                else:
                    await self.stream.astream_message(content=response.content)
                    self.memory.add_assistant(content=response.content)
                    await self._hooks.emit(
                        HookEvent.AGENT_AFTER_ITERATION,
                        HookContext(
                            event=HookEvent.AGENT_AFTER_ITERATION,
                            component="agent",
                            data={
                                "iteration": iteration + 1,
                                "response": response,
                                "tool_results": None,
                            },
                        ),
                    )

            # 执行工具调用
            tool_results = await self._executor.execute(response.tool_calls)

            self.memory.add_tool_result(result=tool_results)
            await self._hooks.emit(
                HookEvent.AGENT_AFTER_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_AFTER_ITERATION,
                    component="agent",
                    data={
                        "iteration": iteration + 1,
                        "response": response,
                        "tool_results": tool_results,
                    },
                ),
            )

            if self.verbose:
                for result in tool_results:
                    status = "✓" if result.status == "success" else "✗"
                    logger.info(f"  [{status}] {result.tool_name}: {result.content[:100]}...")

        # 达到最大迭代次数
        logger.warning(f"ReAct 达到最大迭代次数 ({self._max_iterations})")
        result = "抱歉，我无法在限定步骤内完成这个任务。"
        await self._hooks.emit(
            HookEvent.AGENT_AFTER_RUN,
            HookContext(
                event=HookEvent.AGENT_AFTER_RUN,
                component="agent",
                data={
                    "result": result,
                    "iteration": self._max_iterations,
                },
            ),
        )
        return result

    async def run_steps(
            self,
            query: str
    ) -> AsyncIterator["ReActStep"]:
        """
        逐步执行 ReAct 循环，yield 每一步的结果

        用于需要观察或控制执行过程的场景

        Args:
            query: 用户查询

        Yields:
            ReActStep: 每一步的执行结果
        """

        await self._hooks.emit(
            HookEvent.AGENT_BEFORE_RUN,
            HookContext(
                event=HookEvent.AGENT_BEFORE_RUN,
                component="agent",
                data={
                    "query": query,
                    "agent_type": self.agent_type,
                    "agent_id": self.agent_id,
                },
            ),
        )
        self.memory.add_user(content=query)

        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            history = self.memory.build_history()
            await self._hooks.emit(
                HookEvent.AGENT_BEFORE_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_BEFORE_ITERATION,
                    component="agent",
                    data={
                        "iteration": iteration + 1,
                        "history": history,
                        "query": query,
                    },
                ),
            )

            response = await self._prompt.acall(
                query=query if iteration == 0 else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
            )

            self.memory.add_assistant(content=response)

            if not response.has_tool_calls:
                await self._hooks.emit(
                    HookEvent.AGENT_AFTER_ITERATION,
                    HookContext(
                        event=HookEvent.AGENT_AFTER_ITERATION,
                        component="agent",
                        data={
                            "iteration": iteration + 1,
                            "response": response,
                            "tool_results": None,
                        },
                    ),
                )
                yield ReActStep(
                    iteration=iteration + 1,
                    action="respond",
                    content=response.content,
                    tool_calls=None,
                    tool_results=None,
                    is_final=True,
                )
                await self._hooks.emit(
                    HookEvent.AGENT_AFTER_RUN,
                    HookContext(
                        event=HookEvent.AGENT_AFTER_RUN,
                        component="agent",
                        data={
                            "result": response.content,
                            "iteration": iteration + 1,
                        },
                    ),
                )
                return

            tool_results = await self._executor.execute(response.tool_calls)

            self.memory.add_tool_result(result=tool_results)
            await self._hooks.emit(
                HookEvent.AGENT_AFTER_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_AFTER_ITERATION,
                    component="agent",
                    data={
                        "iteration": iteration + 1,
                        "response": response,
                        "tool_results": tool_results,
                    },
                ),
            )

            yield ReActStep(
                iteration=iteration + 1,
                action="tool_call",
                content=response.content,
                tool_calls=response.tool_calls,
                tool_results=tool_results,
                is_final=False,
            )

        yield ReActStep(
            iteration=self._max_iterations,
            action="max_iterations",
            content="达到最大迭代次数",
            tool_calls=None,
            tool_results=None,
            is_final=True,
        )
        await self._hooks.emit(
            HookEvent.AGENT_AFTER_RUN,
            HookContext(
                event=HookEvent.AGENT_AFTER_RUN,
                component="agent",
                data={
                    "result": "达到最大迭代次数",
                    "iteration": self._max_iterations,
                },
            ),
        )

    @property
    def tools(self) -> List[Tool]:
        """获取已注册的工具列表"""
        return self._registry.get_all_tools()

    @property
    def sandbox(self) -> Optional["Sandbox"]:
        """获取 sandbox 实例"""
        return self._sandbox


class ReActStep:
    """
    ReAct 单步执行结果

    Attributes:
        iteration: 当前迭代次数
        action: 动作类型 ('tool_call', 'respond', 'max_iterations')
        content: LLM 响应内容
        tool_calls: 工具调用列表（如果有）
        tool_results: 工具执行结果列表（如果有）
        is_final: 是否是最终步骤
    """

    def __init__(
            self,
            iteration: int,
            action: str,
            content: str,
            tool_calls: Optional[List] = None,
            tool_results: Optional[List] = None,
            is_final: bool = False,
    ):
        self.iteration = iteration
        self.action = action
        self.content = content
        self.tool_calls = tool_calls
        self.tool_results = tool_results
        self.is_final = is_final

    def __repr__(self) -> str:

        base_info = f"ReActStep(iteration={self.iteration}, action='{self.action}', is_final={self.is_final})"

        extra_parts = []

        if self.tool_calls:
            tool_names = [call.get("name", str(call)) for call in self.tool_calls]
            extra_parts.append(f"工具调用({len(tool_names)})={tool_names}")

        if self.tool_results:
            result_status = [f"{res.tool_name}[{res.status}]" for res in self.tool_results]
            extra_parts.append(f"工具结果({len(result_status)})={result_status}")

        content_preview = self.content[:50].replace("\n", " ")
        if len(self.content) > 50:
            content_preview += "..."
        extra_parts.append(f"内容预览='{content_preview}'")

        if extra_parts:
            return f"{base_info} [{', '.join(extra_parts)}]"
        return base_info

    # def __repr__(self) -> str:
    #     return f"ReActStep(iteration={self.iteration}, action='{self.action}', is_final={self.is_final})"

