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

from typing import Callable, List, Union, Optional, AsyncIterator, TYPE_CHECKING
import logging

from .base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.decorators import Tool, tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.memory import MemoryManager
from alphora.sandbox import Sandbox, SandboxTools

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning + Acting) 智能体

    自动处理 LLM 推理和工具调用的循环，直到任务完成或达到最大迭代次数。

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
            max_iterations: int = 10,
            sandbox: Optional[Sandbox] = None,
            memory: Optional[MemoryManager] = None,
            **kwargs
    ):
        super().__init__(llm=llm, memory=memory, **kwargs)

        self._registry = ToolRegistry()
        self._sandbox = sandbox
        self._sandbox_tools: Optional["SandboxTools"] = None

        # 注册用户提供的工具
        for t in tools:
            self._registry.register(t)

        # 如果提供了 sandbox，注册沙箱相关工具
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
        设置沙箱工具

        将 Sandbox 的能力注册为可被 LLM 调用的工具
        """
        from alphora.sandbox import SandboxTools

        self._sandbox_tools = SandboxTools(sandbox)

        # 创建代码执行工具
        @tool(name="execute_python", description="在安全沙箱中执行 Python 代码并返回结果。用于数据分析、计算、文件处理等任务。")
        async def execute_python(code: str) -> str:
            """
            执行 Python 代码

            Args:
                code: 要执行的 Python 代码

            Returns:
                执行结果，包含 stdout 输出或错误信息
            """
            result = await self._sandbox_tools.run_python_code(code)
            if result.get("success"):
                output = result.get("output", "").strip()
                return output if output else "(代码执行成功，无输出)"
            else:
                error = result.get("error", "未知错误")
                return f"执行错误: {error}"

        # 创建文件保存工具
        @tool(name="save_file", description="在沙箱中保存文件")
        async def save_file(filename: str, content: str) -> str:
            """
            保存文件到沙箱

            Args:
                filename: 文件名
                content: 文件内容

            Returns:
                操作结果
            """
            result = await self._sandbox_tools.save_file(filename, content)
            if result.get("success"):
                return f"文件 '{filename}' 保存成功"
            else:
                return f"保存失败: {result.get('error', '未知错误')}"

        # 创建文件读取工具
        @tool(name="read_file", description="从沙箱中读取文件内容")
        async def read_file(filename: str) -> str:
            """
            读取沙箱中的文件

            Args:
                filename: 文件名

            Returns:
                文件内容或错误信息
            """
            result = await self._sandbox_tools.read_file(filename)
            if result.get("success"):
                return result.get("content", "")
            else:
                return f"读取失败: {result.get('error', '未知错误')}"

        # 创建文件列表工具
        @tool(name="list_files", description="列出沙箱中的文件")
        async def list_files(path: str = ".") -> str:
            """
            列出沙箱目录中的文件

            Args:
                path: 目录路径，默认为当前目录

            Returns:
                文件列表
            """
            result = await self._sandbox_tools.list_files(path)
            if result.get("success"):
                files = result.get("files", [])
                if files:
                    return "\n".join(files)
                else:
                    return "(目录为空)"
            else:
                return f"列出失败: {result.get('error', '未知错误')}"

        # 创建包安装工具
        @tool(name="install_package", description="在沙箱中安装 Python 包")
        async def install_package(package_name: str) -> str:
            """
            安装 Python 包

            Args:
                package_name: 包名，如 'pandas' 或 'numpy==1.21.0'

            Returns:
                安装结果
            """
            result = await self._sandbox_tools.install_pip_package(package_name)
            if result.get("success"):
                return f"包 '{package_name}' 安装成功"
            else:
                return f"安装失败: {result.get('error', '未知错误')}"

        # 注册沙箱工具
        self._registry.register(execute_python)
        self._registry.register(save_file)
        self._registry.register(read_file)
        self._registry.register(list_files)
        self._registry.register(install_package)

        logger.info(f"已注册 5 个沙箱工具: execute_python, save_file, read_file, list_files, install_package")

    async def run(
            self,
            query: str,
            session_id: Optional[str] = None,
    ) -> str:
        """
        执行完整的 ReAct 循环

        Args:
            query: 用户查询
            session_id: 可选的会话 ID，用于多轮对话

        Returns:
            最终响应文本
        """
        # 添加用户消息到记忆
        if session_id:
            self.memory.add_user(session_id=session_id, content=query)

        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            logger.debug(f"ReAct iteration {iteration + 1}/{self._max_iterations}")

            # 构建历史
            history = self.memory.build_history(session_id=session_id) if session_id else None

            # 调用 LLM
            response = await self._prompt.acall(
                query=query if iteration == 0 and not session_id else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
            )

            # 记录助手响应
            if session_id:
                self.memory.add_assistant(session_id=session_id, content=response)

            # 检查是否有工具调用
            if not response.has_tool_calls:
                # 没有工具调用，返回文本响应
                return response.content

            # 执行工具调用
            tool_results = await self._executor.execute(response.tool_calls)

            # 记录工具结果到记忆
            if session_id:
                self.memory.add_tool_result(session_id=session_id, result=tool_results)
            else:
                # 无 session 模式：将工具结果添加到 prompt 的临时历史
                self._prompt.add_tool_results(tool_results)

            # 打印工具执行信息（如果 verbose）
            if self.verbose:
                for result in tool_results:
                    status = "✓" if result.status == "success" else "✗"
                    logger.info(f"  [{status}] {result.tool_name}: {result.content[:100]}...")

        # 达到最大迭代次数
        logger.warning(f"ReAct 达到最大迭代次数 ({self._max_iterations})")
        return "抱歉，我无法在限定步骤内完成这个任务。"

    async def run_steps(
            self,
            query: str,
            session_id: Optional[str] = None,
    ) -> AsyncIterator["ReActStep"]:
        """
        逐步执行 ReAct 循环，yield 每一步的结果

        用于需要观察或控制执行过程的场景

        Args:
            query: 用户查询
            session_id: 可选的会话 ID

        Yields:
            ReActStep: 每一步的执行结果
        """
        if session_id:
            self.memory.add_user(session_id=session_id, content=query)

        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            history = self.memory.build_history(session_id=session_id) if session_id else None

            response = await self._prompt.acall(
                query=query if iteration == 0 and not session_id else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
            )

            if session_id:
                self.memory.add_assistant(session_id=session_id, content=response)

            if not response.has_tool_calls:
                yield ReActStep(
                    iteration=iteration + 1,
                    action="respond",
                    content=response.content,
                    tool_calls=None,
                    tool_results=None,
                    is_final=True,
                )
                return

            tool_results = await self._executor.execute(response.tool_calls)

            if session_id:
                self.memory.add_tool_result(session_id=session_id, result=tool_results)
            else:
                self._prompt.add_tool_results(tool_results)

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
        return f"ReActStep(iteration={self.iteration}, action='{self.action}', is_final={self.is_final})"

