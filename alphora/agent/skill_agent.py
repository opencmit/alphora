# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
SkillAgent - 支持 Agent Skills 标准的智能体

基于 BaseAgent，内置 SkillManager 和工具调用循环，
可直接加载符合 agentskills.io 标准的 Skill 目录。

基础用法：
    agent = SkillAgent(
        llm=OpenAILike(),
        skill_paths=["./skills"],
        system_prompt="你是一个智能助手",
    )
    response = await agent.run("帮我处理这个 PDF 文件")

带额外工具和沙箱：
    async with Sandbox.create_local() as sandbox:
        agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=["./skills"],
            tools=[my_custom_tool],
            sandbox=sandbox,
            system_prompt="你是一个数据分析助手",
        )
        response = await agent.run("分析这份数据")

使用已有的 SkillManager：
    manager = SkillManager(["./skills", "/shared/skills"])
    agent = SkillAgent(
        llm=OpenAILike(),
        skill_manager=manager,
    )
"""

from typing import Callable, List, Union, Optional, Dict, Any, AsyncIterator, TYPE_CHECKING
from pathlib import Path
import logging

from .base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.decorators import Tool, tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.memory import MemoryManager
from alphora.skills import SkillManager, create_skill_tools, create_filesystem_skill_tools
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

if TYPE_CHECKING:
    from alphora.sandbox import Sandbox

logger = logging.getLogger(__name__)


class SkillAgent(BaseAgent):
    """
    支持 Agent Skills 标准的智能体

    在 ReAct 循环的基础上集成了 SkillManager，实现：
    - 自动发现并注入 available_skills 到 system prompt
    - 提供内置工具让 LLM 按需激活和使用 Skill
    - 支持与用户自定义工具混合使用
    - 可选集成 Sandbox 执行 Skill 脚本

    与 ReActAgent 的区别：
    - ReActAgent 面向「有明确工具列表」的场景
    - SkillAgent 面向「有 Skill 目录、需要 LLM 自主选择 Skill」的场景
    - SkillAgent 同时支持 tools 和 skills，两者可以混合使用

    Args:
        llm: LLM 实例
        skill_paths: Skill 目录搜索路径列表
        skill_manager: 已创建的 SkillManager 实例（与 skill_paths 二选一）
        tools: 额外的工具列表（与 Skills 内置工具合并使用）
        system_prompt: 系统提示词
        max_iterations: 最大迭代次数
        sandbox: 可选的 Sandbox 实例，传入后可执行 Skill 脚本
        filesystem_mode: 使用文件系统模式（提供路径让 LLM 自行 cat 文件）
        memory: 可选的 MemoryManager
        **kwargs: 传递给 BaseAgent 的其他参数

    Example:
        # 最简用法
        agent = SkillAgent(
            llm=OpenAILike(model_name="gpt-4"),
            skill_paths=["./skills"],
        )
        result = await agent.run("帮我创建一份 PDF 报告")

        # 完整配置
        agent = SkillAgent(
            llm=llm,
            skill_paths=["./skills", "~/.alphora/skills"],
            tools=[get_weather, search_web],
            system_prompt="你是一个全能助手",
            max_iterations=15,
            sandbox=sandbox,
        )
    """

    agent_type: str = "SkillAgent"

    def __init__(
        self,
        llm: OpenAILike,
        skill_paths: Optional[List[Union[str, Path]]] = None,
        skill_manager: Optional[SkillManager] = None,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        system_prompt: str = "",
        max_iterations: int = 100,
        sandbox: Optional["Sandbox"] = None,
        filesystem_mode: bool = False,
        memory: Optional[MemoryManager] = None,
        hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
        before_run: Optional[Callable] = None,
        after_run: Optional[Callable] = None,
        before_iteration: Optional[Callable] = None,
        after_iteration: Optional[Callable] = None,
        **kwargs,
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

        # Skill Manager

        if skill_manager is not None:
            self._skill_manager = skill_manager
        elif skill_paths:
            self._skill_manager = SkillManager(
                skill_paths=skill_paths,
                auto_discover=True,
            )
        else:
            self._skill_manager = SkillManager(auto_discover=False)

        # Sandbox
        self._sandbox = sandbox
        self._filesystem_mode = filesystem_mode

        # Tool Registry
        self._registry = ToolRegistry()

        # 注册用户自定义工具
        if tools:
            for t in tools:
                self._registry.register(t)

        # 注册 Skill 内置工具
        if filesystem_mode:
            skill_tools = create_filesystem_skill_tools(self._skill_manager)
        else:
            skill_tools = create_skill_tools(self._skill_manager, sandbox=sandbox)

        for t in skill_tools:
            self._registry.register(t)

        # 如果有沙箱但不是 filesystem_mode，也注册沙箱工具
        if sandbox is not None:
            self._setup_sandbox_tools(sandbox)

        self._executor = ToolExecutor(self._registry)

        # Prompt
        full_system_prompt = self._build_system_prompt(system_prompt)
        self._system_prompt = full_system_prompt
        self._prompt = self.create_prompt(system_prompt=full_system_prompt)
        self._max_iterations = max_iterations

    def _build_system_prompt(self, user_system_prompt: str) -> str:
        """
        组装完整的 system prompt

        顺序：
        1. 用户自定义 system prompt
        2. Skill 系统指令（包含 available_skills 清单）
        3. 默认提示（如果用户未提供）
        """
        parts = []

        if user_system_prompt:
            parts.append(user_system_prompt)
        else:
            parts.append(self._get_default_system_prompt())

        # 注入 Skill 清单
        skill_instruction = self._skill_manager.to_system_instruction()
        if skill_instruction:
            parts.append(skill_instruction)

        return "\n\n".join(parts)

    def _get_default_system_prompt(self) -> str:
        """生成默认 system prompt"""
        prompt = "你是一个 AI 助手，可以使用工具和技能来帮助用户完成任务。"

        if self._sandbox is not None:
            prompt += "\n你可以执行代码来分析数据和处理文件。"

        return prompt

    def _setup_sandbox_tools(self, sandbox: "Sandbox") -> None:
        """注册沙箱工具（如果尚未通过 Skill 工具注册脚本执行能力）"""
        try:
            from alphora.sandbox import SandboxTools

            sandbox_tools = SandboxTools(sandbox)

            # 仅注册不与 skill 工具冲突的沙箱能力
            safe_tools = [
                sandbox_tools.save_file,
                sandbox_tools.list_files,
                sandbox_tools.run_shell_command,
            ]

            for t in safe_tools:
                try:
                    self._registry.register(t)
                except Exception:
                    # 如果已注册同名工具（如 run_skill_script 与 run_shell_command），跳过
                    pass

        except ImportError:
            logger.debug("Sandbox module not available, skipping sandbox tools")

    # 执行
    async def run(self, query: str) -> str:
        """
        执行完整的 Skill + 工具调用循环

        流程：
        1. 将用户查询加入记忆
        2. 构建包含 available_skills 的上下文
        3. LLM 推理并决定是否调用工具/激活 Skill
        4. 执行工具调用，结果回写记忆
        5. 循环直到 LLM 给出最终回答或达到最大迭代次数

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
        self.memory.add_user(content=query)

        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            logger.debug(
                f"SkillAgent iteration {iteration + 1}/{self._max_iterations}"
            )

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
                runtime_system_prompt=(
                    "如果你认为用户的任务已经完成，请直接回复最终结果。"
                ),
            )

            # 记录助手响应
            self.memory.add_assistant(content=response)

            # 没有工具调用则任务完成
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
                return response.content

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
                    preview = result.content[:100].replace("\n", " ")
                    logger.info(f"  [{status}] {result.tool_name}: {preview}...")

        # 达到最大迭代次数
        logger.warning(
            f"SkillAgent reached max iterations ({self._max_iterations})"
        )
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

    async def run_steps(self, query: str) -> AsyncIterator["SkillAgentStep"]:
        """
        逐步执行循环，yield 每一步结果

        适用于需要观察或控制执行过程的场景。

        Args:
            query: 用户查询

        Yields:
            SkillAgentStep: 每一步的执行详情
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
                yield SkillAgentStep(
                    iteration=iteration + 1,
                    action="respond",
                    content=response.content,
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

            # 检测是否有 Skill 激活
            activated_skills = [
                tc.get("function", {}).get("arguments", "")
                for tc in (response.tool_calls or [])
                if tc.get("function", {}).get("name") == "read_skill"
            ]

            yield SkillAgentStep(
                iteration=iteration + 1,
                action="tool_call",
                content=response.content,
                tool_calls=response.tool_calls,
                tool_results=tool_results,
                activated_skills=activated_skills,
                is_final=False,
            )

        yield SkillAgentStep(
            iteration=self._max_iterations,
            action="max_iterations",
            content="达到最大迭代次数",
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

    # Skill 管理（便捷代理方法）
    def add_skill_path(self, path: Union[str, Path]) -> "SkillAgent":
        """
        动态添加 Skill 搜索路径并重新发现

        Args:
            path: Skill 目录路径

        Returns:
            self（支持链式调用）
        """
        self._skill_manager.add_path(path)
        self._skill_manager.discover()
        self._refresh_system_prompt()
        return self

    def add_skill(self, skill_dir: Union[str, Path]) -> "SkillAgent":
        """
        动态注册单个 Skill 目录

        Args:
            skill_dir: Skill 目录路径

        Returns:
            self（支持链式调用）
        """
        self._skill_manager.add_skill_dir(skill_dir)
        self._refresh_system_prompt()
        return self

    def _refresh_system_prompt(self) -> None:
        """Skill 变更后刷新 system prompt"""
        # 提取用户原始 system prompt（去掉之前的 skill instruction 部分）
        # 重新构建
        full_system = self._build_system_prompt(
            self._system_prompt.split("\n\nYou have access to")[0]
        )
        self._system_prompt = full_system
        self._prompt = self.create_prompt(system_prompt=full_system)

    @property
    def skill_manager(self) -> SkillManager:
        """获取 SkillManager 实例"""
        return self._skill_manager

    @property
    def skills(self) -> List[str]:
        """获取所有已发现的 Skill 名称"""
        return self._skill_manager.skill_names

    @property
    def tools(self) -> List[Tool]:
        """获取所有已注册的工具"""
        return self._registry.get_all_tools()

    @property
    def sandbox(self) -> Optional["Sandbox"]:
        """获取 Sandbox 实例"""
        return self._sandbox


class SkillAgentStep:
    """
    SkillAgent 单步执行结果

    Attributes:
        iteration: 当前迭代次数
        action: 动作类型 ('tool_call', 'respond', 'max_iterations')
        content: LLM 响应内容
        tool_calls: 工具调用列表
        tool_results: 工具执行结果列表
        activated_skills: 本轮激活的 Skill 名称列表
        is_final: 是否为最终步骤
    """

    def __init__(
        self,
        iteration: int,
        action: str,
        content: str,
        tool_calls: Optional[List] = None,
        tool_results: Optional[List] = None,
        activated_skills: Optional[List[str]] = None,
        is_final: bool = False,
    ):
        self.iteration = iteration
        self.action = action
        self.content = content
        self.tool_calls = tool_calls
        self.tool_results = tool_results
        self.activated_skills = activated_skills or []
        self.is_final = is_final

    def __repr__(self) -> str:
        parts = [
            f"SkillAgentStep(iteration={self.iteration}",
            f"action='{self.action}'",
            f"is_final={self.is_final})",
        ]
        base = " ".join(parts)

        extras = []
        if self.activated_skills:
            extras.append(f"skills={self.activated_skills}")
        if self.tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in self.tool_calls]
            extras.append(f"tools={names}")

        if extras:
            return f"{base} [{', '.join(extras)}]"
        return base
