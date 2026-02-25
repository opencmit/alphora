"""
DeepResearchAgent - 深度研究智能体

基于 SkillAgent 构建，展示如何将 Skills + Sandbox + Tools + Hooks
组合为一个完整的研究型智能体。

本文件演示了以下组件用法：
    - SkillAgent:  作为基座，自动处理 Skill 发现和工具调用循环
    - SkillManager: Skill 的发现、激活、资源访问
    - Sandbox:     安全执行研究分析脚本
    - Tools:       自定义工具与 Skill 内置工具混合使用
    - Hooks:       追踪执行进度、记录关键事件

Usage:
    agent = await create_deep_research_agent(
        model_name="gpt-4",
        sandbox=sandbox,
    )
    result = await agent.run("研究 AI Agent 技术趋势")
"""

from pathlib import Path
from typing import Optional, Callable
import logging

from alphora.agent import SkillAgent
from alphora.models import OpenAILike
from alphora.sandbox import Sandbox
from alphora.hooks import HookContext

from .tools import web_search, fetch_webpage

logger = logging.getLogger(__name__)

# Skill 目录：相对于本文件的路径
SKILLS_DIR = Path(__file__).parent / "skills"

# 系统提示词
SYSTEM_PROMPT = """\
你是一个专业的深度研究助手。你的任务是对用户提出的主题进行系统性、多角度的深入研究，
并产出一份结构化的研究报告。

工作原则：
- 多源验证：同一观点至少从 2 个独立来源获取佐证
- 客观中立：呈现多方观点，标注共识与分歧
- 结构清晰：按主题组织发现，而非按来源罗列
- 引用规范：每个关键论断都标注信息来源

当你加载了 deep-research Skill 的指令后，请严格按照其中定义的研究工作流执行。
研究过程中产生的中间文件和最终报告都保存在沙箱的工作目录中。
"""


async def create_deep_research_agent(
    model_name: str = "gpt-4",
    sandbox: Optional[Sandbox] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    on_progress: Optional[Callable] = None,
    verbose: bool = True,
) -> SkillAgent:
    """
    创建深度研究智能体。

    这个工厂函数演示了 SkillAgent 的完整初始化流程：
    1. 创建 LLM 实例
    2. 准备自定义工具
    3. 配置 Hooks（可选）
    4. 创建带 Skill + Sandbox 的 SkillAgent

    Args:
        model_name: LLM 模型名称
        sandbox: Sandbox 实例（传入后可执行 Skill 脚本）
        api_key: API Key（默认从环境变量读取）
        base_url: API Base URL（默认从环境变量读取）
        on_progress: 进度回调函数 fn(event: str, data: dict)
        verbose: 是否输出详细日志

    Returns:
        配置好的 SkillAgent 实例

    Example:
        async with Sandbox(runtime="local") as sandbox:
            agent = await create_deep_research_agent(
                model_name="gpt-4",
                sandbox=sandbox,
            )
            result = await agent.run("研究量子计算的商业应用前景")
    """

    # ─── Step 1: 创建 LLM ───
    llm_kwargs = {"model_name": model_name}
    if api_key:
        llm_kwargs["api_key"] = api_key
    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = OpenAILike(**llm_kwargs)

    # ─── Step 2: 准备自定义工具 ───
    #
    # 这些工具会与 Skill 内置工具（read_skill, read_skill_resource,
    # list_skill_resources, run_skill_script）一起注册到 ToolRegistry。
    # LLM 在 ReAct 循环中可以自由组合使用所有工具。
    custom_tools = [web_search, fetch_webpage]

    # ─── Step 3: 配置 Hooks ───
    #
    # Hooks 提供非侵入式的执行追踪能力。
    # 这里演示了三个常用的 Hook 事件：
    #   - AGENT_BEFORE_RUN: Agent 开始执行前
    #   - AGENT_AFTER_ITERATION: 每轮工具调用完成后
    #   - AGENT_AFTER_RUN: Agent 执行完成后
    hooks = _build_hooks(on_progress, verbose)

    # ─── Step 4: 创建 SkillAgent ───
    #
    # SkillAgent 初始化时会自动：
    #   1. 创建 SkillManager 并扫描 skill_paths 下的 Skill 目录
    #   2. 将 Skill 元数据（name + description）注入 system prompt
    #   3. 注册 Skill 内置工具（read_skill 等）到 ToolRegistry
    #   4. 注册用户自定义工具（web_search 等）到同一个 ToolRegistry
    #   5. 如果有 Sandbox，注册脚本执行工具和沙箱文件工具
    agent = SkillAgent(
        llm=llm,
        skill_paths=[str(SKILLS_DIR)],
        tools=custom_tools,
        system_prompt=SYSTEM_PROMPT,
        sandbox=sandbox,
        max_iterations=30,
        hooks=hooks,
        verbose=verbose,
    )

    if verbose:
        _print_agent_info(agent)

    return agent


def _build_hooks(
    on_progress: Optional[Callable],
    verbose: bool,
) -> dict:
    """
    构建 Hook 配置字典。

    Alphora 的 Hooks 机制支持两种注册方式：
      1. 快捷方式：传入 before_run / after_run 等命名参数
      2. 字典方式：{HookEvent: handler} 映射（需 import HookEvent）

    这里使用快捷方式，更直观。
    """

    async def before_run(ctx: HookContext):
        """Agent 开始执行前触发"""
        query = ctx.data.get("query", "")
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Deep Research Agent 启动")
            print(f"  研究主题: {query}")
            print(f"{'='*60}\n")
        if on_progress:
            on_progress("start", {"query": query})

    async def after_iteration(ctx: HookContext):
        """每轮迭代完成后触发（包含工具调用结果）"""
        iteration = ctx.data.get("iteration", 0)
        tool_results = ctx.data.get("tool_results")

        if tool_results and verbose:
            for result in tool_results:
                tool_name = getattr(result, "tool_name", "unknown")
                status = getattr(result, "status", "unknown")
                content = getattr(result, "content", "")
                icon = "✓" if status == "success" else "✗"
                preview = content[:80].replace("\n", " ")
                print(f"  [{icon}] Step {iteration} | {tool_name}: {preview}...")

        if on_progress:
            on_progress("iteration", {
                "iteration": iteration,
                "has_tool_calls": tool_results is not None,
            })

    async def after_run(ctx: HookContext):
        """Agent 执行完成后触发"""
        iteration = ctx.data.get("iteration", 0)
        if verbose:
            print(f"\n{'='*60}")
            print(f"  研究完成 (共 {iteration} 轮迭代)")
            print(f"{'='*60}\n")
        if on_progress:
            on_progress("complete", {"iterations": iteration})

    return {
        "before_run": before_run,
        "after_iteration": after_iteration,
        "after_run": after_run,
    }


def _print_agent_info(agent: SkillAgent):
    """打印 Agent 初始化信息（便于调试）"""
    print(f"\n  Agent 初始化完成:")
    print(f"  ├── Skills: {agent.skills}")
    print(f"  ├── Tools:  {[t.name for t in agent.tools]}")
    print(f"  ├── Sandbox: {'已配置' if agent.sandbox else '未配置'}")
    print(f"  └── Max iterations: 30")
    print()
