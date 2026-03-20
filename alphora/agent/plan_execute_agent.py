# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
PlanExecuteAgent - Plan-and-Execute 模式的智能体

先规划、再执行、可动态调整计划的智能体架构。

核心流程：
    1. Planner  - 将用户任务分解为可执行的步骤计划
    2. Executor - 逐步执行，每步可调用工具（ReAct 子循环）
    3. Replanner - 根据执行结果动态调整剩余计划
    4. Synthesizer - 汇总全部结果，生成最终回答

基础用法：
    agent = PlanExecuteAgent(
        llm=OpenAILike(),
        tools=[search_web, read_file, write_file],
        system_prompt="你是一个高效的任务规划与执行助手",
    )
    response = await agent.run("帮我调研 AI Agent 的主流框架并写一份对比报告")

带 Sandbox 的用法：
    async with Sandbox(runtime="local") as sandbox:
        agent = PlanExecuteAgent(
            llm=OpenAILike(),
            tools=[search_web],
            sandbox=sandbox,
            system_prompt="你是一个数据分析师",
        )
        response = await agent.run("分析 sales.csv 的趋势并生成可视化报告")
"""

from typing import (
    List, Union, Optional, Dict, Any, AsyncIterator, Callable, TYPE_CHECKING,
)
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import time

from .base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.decorators import Tool, tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.memory import MemoryManager
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

if TYPE_CHECKING:
    from alphora.sandbox import Sandbox

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """计划中的单个步骤"""
    id: int
    title: str
    description: str
    depends_on: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    tool_calls_count: int = 0
    elapsed_seconds: float = 0.0

    def to_progress_str(self) -> str:
        icon = {
            StepStatus.PENDING: "○",
            StepStatus.RUNNING: "◉",
            StepStatus.COMPLETED: "✓",
            StepStatus.FAILED: "✗",
            StepStatus.SKIPPED: "⊘",
        }[self.status]
        return f"{icon} Step {self.id}: {self.title}"


@dataclass
class Plan:
    """完整的执行计划"""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0
    is_complete: bool = False
    revision_count: int = 0

    @property
    def completed_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    @property
    def failed_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    @property
    def pending_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def progress_summary(self) -> str:
        total = len(self.steps)
        done = len(self.completed_steps)
        failed = len(self.failed_steps)
        return f"[{done}/{total} completed, {failed} failed]"

    def to_display_str(self) -> str:
        lines = [f"📋 Plan: {self.goal}", f"   {self.progress_summary()}", ""]
        for step in self.steps:
            lines.append(f"   {step.to_progress_str()}")
        return "\n".join(lines)


class PlanExecuteStep:
    """
    PlanExecuteAgent 单步执行结果

    Attributes:
        phase: 当前阶段 ('plan', 'execute', 'replan', 'synthesize')
        step_id: 计划步骤 ID（execute 阶段有效）
        content: 本步输出内容
        plan: 当前计划快照
        tool_calls: 工具调用列表
        tool_results: 工具执行结果列表
        is_final: 是否为最终步骤
    """

    def __init__(
        self,
        phase: str,
        content: str,
        plan: Optional[Plan] = None,
        step_id: Optional[int] = None,
        tool_calls: Optional[List] = None,
        tool_results: Optional[List] = None,
        is_final: bool = False,
    ):
        self.phase = phase
        self.content = content
        self.plan = plan
        self.step_id = step_id
        self.tool_calls = tool_calls
        self.tool_results = tool_results
        self.is_final = is_final

    def __repr__(self) -> str:
        parts = [f"PlanExecuteStep(phase='{self.phase}'"]
        if self.step_id is not None:
            parts.append(f"step_id={self.step_id}")
        parts.append(f"is_final={self.is_final})")
        return ", ".join(parts)


PLANNER_SYSTEM_PROMPT = """\
You are an expert task planner. Given a user's request and a set of available tools, \
decompose the task into a clear, actionable step-by-step plan.

## Rules
1. Each step must be concrete and executable using the available tools or direct reasoning.
2. Steps should be ordered logically; specify dependencies if a step relies on another's output.
3. Keep the plan concise — no more than 8 steps for most tasks. Fewer is better.
4. Each step title should be short (< 15 words). The description should explain *what* to do and *why*.
5. If the task is simple enough to answer directly, create a single-step plan.

## Available Tools
{tools_description}

## Output Format
Return a JSON object (no markdown fences) exactly matching this schema:
{{
  "goal": "<one-line restatement of the user's goal>",
  "steps": [
    {{
      "id": 1,
      "title": "<short step title>",
      "description": "<what to do in this step and what output to produce>",
      "depends_on": []
    }}
  ]
}}
"""

EXECUTOR_SYSTEM_PROMPT = """\
You are executing step {step_id} of a multi-step plan.

## Overall Goal
{goal}

## Current Plan Progress
{plan_progress}

## Your Current Task
**Step {step_id}: {step_title}**
{step_description}

## Previous Steps Results
{previous_results}

## Instructions
- Focus ONLY on completing this specific step.
- Use the available tools as needed.
- When the step is complete, provide a clear, concise summary of what was accomplished and any key findings.
- If you encounter an error, explain what went wrong so the planner can adjust.
"""

REPLANNER_SYSTEM_PROMPT = """\
You are reviewing the progress of a multi-step plan and deciding whether to adjust it.

## Original Goal
{goal}

## Current Plan & Status
{plan_status}

## Latest Step Result
Step {last_step_id} ({last_step_status}): {last_step_result}

## Available Tools
{tools_description}

## Instructions
Analyze the progress and decide:

1. **If the plan is on track**: Return {{"action": "continue"}}
2. **If the plan needs adjustment**: Return a revised plan with the REMAINING steps only \
(do not include already-completed steps):
{{
  "action": "revise",
  "steps": [
    {{"id": <next_id>, "title": "...", "description": "...", "depends_on": []}}
  ],
  "reason": "<why you revised the plan>"
}}
3. **If the goal has been fully achieved**: Return {{"action": "finish", "reason": "..."}}

Return JSON only, no markdown fences.
"""

SYNTHESIZER_SYSTEM_PROMPT = """\
You are synthesizing the results of a completed multi-step plan into a final response.

## Original Goal
{goal}

## Executed Steps & Results
{steps_results}

## Instructions
- Combine all step results into a coherent, comprehensive final answer.
- Address the user's original goal directly.
- Be thorough but concise. Use structured formatting (headers, lists, etc.) when appropriate.
- If any steps failed, acknowledge what was not completed and suggest alternatives.
- Respond in the same language as the user's original query.
"""


class PlanExecuteAgent(BaseAgent):
    """
    Plan-and-Execute 智能体

    核心思想：先想清楚，再动手做
    通过将复杂任务分解为结构化的计划步骤，逐步执行并动态调整，

    特性：
    - 自动任务分解：LLM 将复杂任务拆解为可管理的子步骤
    - 逐步执行：每个步骤在独立的 ReAct 子循环中执行，可调用工具
    - 动态重规划：根据执行结果自适应调整后续计划
    - 进度追踪：实时展示计划状态和执行进度
    - 失败恢复：步骤失败时自动触发重规划，而非直接终止
    - 结果综合：将所有步骤结果汇总为高质量的最终回答

    Args:
        llm: LLM 实例
        tools: 工具列表
        system_prompt: 用户自定义系统提示（追加到内置提示之后）
        max_steps: 计划最大步骤数
        max_step_iterations: 单步骤内最大工具调用轮数
        max_replans: 最大重规划次数
        enable_replan: 是否启用动态重规划
        sandbox: 可选的 Sandbox 实例
        memory: 可选的 MemoryManager
        hooks: 可选的 HookManager
        **kwargs: 传递给 BaseAgent 的参数

    Example:
        agent = PlanExecuteAgent(
            llm=OpenAILike(model_name="qwen-plus"),
            tools=[web_search, file_reader],
            system_prompt="你是一个研究助手",
        )
        result = await agent.run("帮我对比 LangChain 和 CrewAI 的优缺点")

        # 逐步观察
        async for step in agent.run_steps("分析数据并生成报告"):
            print(f"[{step.phase}] {step.content[:100]}")
    """

    agent_type: str = "PlanExecuteAgent"

    def __init__(
        self,
        llm: OpenAILike,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        system_prompt: str = "",
        max_steps: int = 8,
        max_step_iterations: int = 15,
        max_replans: int = 3,
        enable_replan: bool = True,
        sandbox: Optional["Sandbox"] = None,
        memory: Optional[MemoryManager] = None,
        hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
        **kwargs,
    ):
        hook_manager = build_manager(hooks)
        super().__init__(llm=llm, memory=memory, hooks=hook_manager, **kwargs)

        self._registry = ToolRegistry()
        self._sandbox = sandbox

        if tools:
            for t in tools:
                self._registry.register(t)

        if sandbox is not None:
            self._setup_sandbox_tools(sandbox)

        self._executor = ToolExecutor(self._registry, hooks=hook_manager)

        self._user_system_prompt = system_prompt
        self._max_steps = max_steps
        self._max_step_iterations = max_step_iterations
        self._max_replans = max_replans
        self._enable_replan = enable_replan

        self._plan: Optional[Plan] = None

    def _setup_sandbox_tools(self, sandbox: "Sandbox") -> None:
        try:
            from alphora.sandbox import SandboxTools
            sandbox_tools = SandboxTools(sandbox)
            for t in [sandbox_tools.save_file, sandbox_tools.list_files, sandbox_tools.run_shell_command, sandbox_tools.markdown_to_pdf]:
                try:
                    self._registry.register(t)
                except Exception:
                    pass
        except ImportError:
            logger.debug("Sandbox module not available, skipping sandbox tools")

    async def _ensure_sandbox_ready(self) -> None:
        if self._sandbox is not None and not self._sandbox.is_running:
            logger.info("Sandbox not running, auto-starting...")
            await self._sandbox.start()

    def _get_tools_description(self) -> str:
        tools = self._registry.get_all_tools()
        if not tools:
            return "No tools available. You can only use reasoning."
        lines = []
        for t in tools:
            lines.append(f"- **{t.name}**: {t.description}")
        return "\n".join(lines)

    async def _create_plan(self, query: str) -> Plan:
        """调用 LLM 生成执行计划"""
        planner_prompt = self.create_prompt(
            system_prompt=PLANNER_SYSTEM_PROMPT.format(
                tools_description=self._get_tools_description(),
            ),
        )

        response = await planner_prompt.acall(
            query=query,
            is_stream=False,
        )

        plan_data = self._parse_json_response(response.content)

        steps = []
        for i, s in enumerate(plan_data.get("steps", [])[:self._max_steps]):
            steps.append(PlanStep(
                id=s.get("id", i + 1),
                title=s.get("title", f"Step {i + 1}"),
                description=s.get("description", ""),
                depends_on=s.get("depends_on", []),
            ))

        if not steps:
            steps = [PlanStep(id=1, title="Direct answer", description=query)]

        plan = Plan(
            goal=plan_data.get("goal", query),
            steps=steps,
        )

        logger.info(f"Plan created with {len(steps)} steps for: {plan.goal}")
        return plan

    async def _execute_step(self, plan: Plan, step: PlanStep) -> str:
        """
        执行计划中的单个步骤
        使用独立的 MemoryManager 运行 ReAct 子循环，避免污染主对话记忆
        """
        step.status = StepStatus.RUNNING
        start_time = time.time()

        previous_results = self._format_previous_results(plan, step)
        system_prompt = EXECUTOR_SYSTEM_PROMPT.format(
            step_id=step.id,
            goal=plan.goal,
            plan_progress=plan.to_display_str(),
            step_title=step.title,
            step_description=step.description,
            previous_results=previous_results,
        )
        if self._user_system_prompt:
            system_prompt = self._user_system_prompt + "\n\n" + system_prompt

        step_prompt = self.create_prompt(system_prompt=system_prompt)
        step_memory = MemoryManager()
        tools_schema = self._registry.get_openai_tools_schema()

        step_query = f"Execute: {step.title}\n\n{step.description}"
        step_memory.add_user(content=step_query)

        final_content = ""

        for iteration in range(self._max_step_iterations):
            history = step_memory.build_history()

            response = await step_prompt.acall(
                query=step_query if iteration == 0 else None,
                history=history,
                tools=tools_schema if tools_schema else None,
                is_stream=True,
                runtime_system_prompt="当你完成了当前步骤的任务后，直接给出步骤结果摘要，不要调用更多工具。",
            )

            step_memory.add_assistant(content=response)

            if not response.has_tool_calls:
                final_content = response.content
                break

            tool_results = await self._executor.execute(response.tool_calls)
            step_memory.add_tool_result(result=tool_results)
            step.tool_calls_count += len(response.tool_calls)

        step.elapsed_seconds = time.time() - start_time

        if final_content:
            step.status = StepStatus.COMPLETED
            step.result = final_content
        else:
            step.status = StepStatus.COMPLETED
            step.result = "Step executed but no explicit summary was produced."

        return step.result

    def _format_previous_results(self, plan: Plan, current_step: PlanStep) -> str:
        lines = []
        for s in plan.steps:
            if s.id >= current_step.id:
                break
            if s.status == StepStatus.COMPLETED:
                result_preview = s.result[:500] if len(s.result) > 500 else s.result
                lines.append(f"### Step {s.id}: {s.title}\n{result_preview}")
            elif s.status == StepStatus.FAILED:
                lines.append(f"### Step {s.id}: {s.title}\n[FAILED] {s.error}")
        return "\n\n".join(lines) if lines else "No previous steps."

    async def _maybe_replan(self, plan: Plan, last_step: PlanStep) -> Plan:
        """根据最新执行结果决定是否调整计划"""
        if not self._enable_replan or plan.revision_count >= self._max_replans:
            return plan

        remaining = [s for s in plan.steps if s.status == StepStatus.PENDING]
        if not remaining:
            return plan

        plan_status_lines = []
        for s in plan.steps:
            status_str = s.status.value
            if s.status == StepStatus.COMPLETED:
                plan_status_lines.append(f"  Step {s.id} [{status_str}]: {s.title} → {s.result[:200]}")
            elif s.status == StepStatus.FAILED:
                plan_status_lines.append(f"  Step {s.id} [{status_str}]: {s.title} → ERROR: {s.error}")
            else:
                plan_status_lines.append(f"  Step {s.id} [{status_str}]: {s.title}")

        replanner_prompt = self.create_prompt(
            system_prompt=REPLANNER_SYSTEM_PROMPT.format(
                goal=plan.goal,
                plan_status="\n".join(plan_status_lines),
                last_step_id=last_step.id,
                last_step_status=last_step.status.value,
                last_step_result=last_step.result[:500] if last_step.result else last_step.error[:500],
                tools_description=self._get_tools_description(),
            ),
        )

        response = await replanner_prompt.acall(
            query="Review the plan progress and decide the next action.",
            is_stream=False,
        )

        decision = self._parse_json_response(response.content)
        action = decision.get("action", "continue")

        if action == "finish":
            plan.is_complete = True
            for s in plan.steps:
                if s.status == StepStatus.PENDING:
                    s.status = StepStatus.SKIPPED
            logger.info(f"Replanner decided to finish early: {decision.get('reason', '')}")

        elif action == "revise":
            new_step_data = decision.get("steps", [])
            if new_step_data:
                max_existing_id = max(s.id for s in plan.steps)
                new_steps = []
                for i, s in enumerate(new_step_data[:self._max_steps]):
                    new_steps.append(PlanStep(
                        id=s.get("id", max_existing_id + i + 1),
                        title=s.get("title", f"Revised Step {i + 1}"),
                        description=s.get("description", ""),
                        depends_on=s.get("depends_on", []),
                    ))

                completed = [s for s in plan.steps if s.status in (StepStatus.COMPLETED, StepStatus.FAILED)]
                plan.steps = completed + new_steps
                plan.revision_count += 1
                logger.info(
                    f"Plan revised (#{plan.revision_count}): "
                    f"{len(new_steps)} new steps. Reason: {decision.get('reason', '')}"
                )

        return plan

    async def _synthesize(self, plan: Plan, query: str) -> str:
        """综合所有步骤结果，生成最终回答"""
        steps_results = []
        for s in plan.steps:
            if s.status == StepStatus.COMPLETED:
                steps_results.append(f"### Step {s.id}: {s.title}\n{s.result}")
            elif s.status == StepStatus.FAILED:
                steps_results.append(f"### Step {s.id}: {s.title}\n[FAILED] {s.error}")
            elif s.status == StepStatus.SKIPPED:
                steps_results.append(f"### Step {s.id}: {s.title}\n[SKIPPED]")

        system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
            goal=plan.goal,
            steps_results="\n\n".join(steps_results),
        )
        if self._user_system_prompt:
            system_prompt = self._user_system_prompt + "\n\n" + system_prompt

        synth_prompt = self.create_prompt(system_prompt=system_prompt)

        response = await synth_prompt.acall(
            query=f"请根据以上执行结果，回答用户的原始问题：\n{query}",
            is_stream=True,
        )

        return response.content

    async def run(self, query: str) -> str:
        """
        执行完整的 Plan-Execute 循环

        流程：
        1. 接收用户请求，调用 Planner 生成步骤计划
        2. 逐步执行每个步骤（每步内部运行 ReAct 子循环）
        3. 每步完成后调用 Replanner 决定是否调整计划
        4. 所有步骤完成后，调用 Synthesizer 生成最终回答

        Args:
            query: 用户查询

        Returns:
            最终综合回答
        """
        if self._sandbox is not None:
            await self._ensure_sandbox_ready()

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

        # Phase 1: Planning
        await self.stream.astream_message(
            content="正在分析任务并制定执行计划...\n\n",
            content_type="plan_status",
        )
        plan = await self._create_plan(query)
        self._plan = plan

        await self.stream.astream_message(
            content=plan.to_display_str() + "\n\n",
            content_type="plan_status",
        )

        # Phase 2 & 3: Execute + Replan loop
        while not plan.is_complete:
            pending = plan.pending_steps
            if not pending:
                plan.is_complete = True
                break

            step = pending[0]

            await self._hooks.emit(
                HookEvent.AGENT_BEFORE_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_BEFORE_ITERATION,
                    component="agent",
                    data={
                        "iteration": step.id,
                        "query": query,
                        "step_title": step.title,
                        "plan": plan,
                    },
                ),
            )

            await self.stream.astream_message(
                content=f"▶ 正在执行 Step {step.id}: {step.title}\n",
                content_type="plan_status",
            )

            try:
                result = await self._execute_step(plan, step)
                logger.info(
                    f"Step {step.id} completed in {step.elapsed_seconds:.1f}s "
                    f"({step.tool_calls_count} tool calls)"
                )
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                result = ""
                logger.error(f"Step {step.id} failed: {e}")

            await self._hooks.emit(
                HookEvent.AGENT_AFTER_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_AFTER_ITERATION,
                    component="agent",
                    data={
                        "iteration": step.id,
                        "step_status": step.status.value,
                        "step_result": result,
                        "plan": plan,
                        "memory": self.memory,
                        "sandbox": self._sandbox,
                        "llm": self.llm,
                    },
                ),
            )

            # Phase 3: Replan
            plan = await self._maybe_replan(plan, step)

        # Phase 4: Synthesize
        await self.stream.astream_message(
            content="\n正在综合执行结果...\n\n",
            content_type="plan_status",
        )

        final_answer = await self._synthesize(plan, query)

        self.memory.add_assistant(content=final_answer)

        await self._hooks.emit(
            HookEvent.AGENT_AFTER_RUN,
            HookContext(
                event=HookEvent.AGENT_AFTER_RUN,
                component="agent",
                data={
                    "result": final_answer,
                    "plan": plan,
                    "total_steps": len(plan.steps),
                    "completed_steps": len(plan.completed_steps),
                    "failed_steps": len(plan.failed_steps),
                    "revision_count": plan.revision_count,
                },
            ),
        )

        return final_answer

    async def run_steps(self, query: str) -> AsyncIterator[PlanExecuteStep]:
        """
        逐步执行 Plan-Execute 循环，yield 每个阶段的结果

        适用于需要观察或控制执行过程的场景。

        Args:
            query: 用户查询

        Yields:
            PlanExecuteStep: 每个阶段的执行详情
        """
        if self._sandbox is not None:
            await self._ensure_sandbox_ready()

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

        # Phase 1: Plan
        plan = await self._create_plan(query)
        self._plan = plan

        yield PlanExecuteStep(
            phase="plan",
            content=plan.to_display_str(),
            plan=plan,
        )

        # Phase 2 & 3: Execute + Replan
        while not plan.is_complete:
            pending = plan.pending_steps
            if not pending:
                plan.is_complete = True
                break

            step = pending[0]

            await self._hooks.emit(
                HookEvent.AGENT_BEFORE_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_BEFORE_ITERATION,
                    component="agent",
                    data={
                        "iteration": step.id,
                        "query": query,
                        "step_title": step.title,
                    },
                ),
            )

            try:
                result = await self._execute_step(plan, step)
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                result = f"Error: {e}"

            yield PlanExecuteStep(
                phase="execute",
                content=result,
                plan=plan,
                step_id=step.id,
            )

            await self._hooks.emit(
                HookEvent.AGENT_AFTER_ITERATION,
                HookContext(
                    event=HookEvent.AGENT_AFTER_ITERATION,
                    component="agent",
                    data={
                        "iteration": step.id,
                        "step_status": step.status.value,
                        "step_result": result,
                        "plan": plan,
                        "memory": self.memory,
                        "sandbox": self._sandbox,
                        "llm": self.llm,
                    },
                ),
            )

            # Replan
            old_step_count = len(plan.steps)
            plan = await self._maybe_replan(plan, step)

            if len(plan.steps) != old_step_count or plan.is_complete:
                yield PlanExecuteStep(
                    phase="replan",
                    content=plan.to_display_str(),
                    plan=plan,
                )

        # Phase 4: Synthesize
        final_answer = await self._synthesize(plan, query)
        self.memory.add_assistant(content=final_answer)

        yield PlanExecuteStep(
            phase="synthesize",
            content=final_answer,
            plan=plan,
            is_final=True,
        )

        await self._hooks.emit(
            HookEvent.AGENT_AFTER_RUN,
            HookContext(
                event=HookEvent.AGENT_AFTER_RUN,
                component="agent",
                data={
                    "result": final_answer,
                    "plan": plan,
                },
            ),
        )

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """从 LLM 响应中提取 JSON，容忍 markdown 代码围栏"""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            cleaned = "\n".join(lines[start:end]).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to find JSON object in text
            brace_start = cleaned.find("{")
            brace_end = cleaned.rfind("}")
            if brace_start != -1 and brace_end != -1:
                try:
                    return json.loads(cleaned[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON from LLM response: {text[:200]}...")
            return {"goal": "execute task", "steps": [], "action": "continue"}

    @property
    def plan(self) -> Optional[Plan]:
        """获取当前计划"""
        return self._plan

    @property
    def tools(self) -> List[Tool]:
        """获取所有已注册的工具"""
        return self._registry.get_all_tools()

    @property
    def sandbox(self) -> Optional["Sandbox"]:
        """获取 Sandbox 实例"""
        return self._sandbox
