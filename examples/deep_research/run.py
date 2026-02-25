"""
Deep Research - 启动入口

演示如何将 Skills + Sandbox + Tools + Agent 组合使用。

Usage:
    # 基础用法
    python -m examples.deep_research.run "AI Agent 技术趋势分析"

    # 指定模型
    python -m examples.deep_research.run "量子计算最新进展" --model gpt-4

    # 使用 Docker 沙箱
    python -m examples.deep_research.run "大模型推理优化" --runtime docker

    # 指定沙箱工作目录
    python -m examples.deep_research.run "研究主题" --workspace /tmp/research
"""

import asyncio
import argparse
import os
import sys

from alphora.sandbox import Sandbox

from examples.deep_research.agent import create_deep_research_agent


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

async def main(
    query: str,
    model_name: str = "gpt-4",
    runtime: str = "local",
    workspace: str = "/tmp/deep_research",
    verbose: bool = True,
):
    """
    执行深度研究的完整流程。

    流程概览：
        1. 启动 Sandbox（安全执行环境）
        2. 创建 DeepResearchAgent（自动发现 Skills + 注册 Tools）
        3. 运行研究任务（Agent 自主执行 ReAct 循环）
        4. 展示最终结果 + 读取沙箱中的报告文件
        5. 清理 Sandbox

    Args:
        query: 研究主题
        model_name: LLM 模型名称
        runtime: 沙箱运行时 ("local" 或 "docker")
        workspace: 沙箱工作目录
        verbose: 是否输出详细日志
    """

    os.makedirs(workspace, exist_ok=True)

    # ─── Step 1: 启动 Sandbox ───
    #
    # Sandbox 提供安全的代码执行环境。
    # - runtime="local": 使用本地 Python（开发调试用）
    # - runtime="docker": 使用 Docker 容器（生产环境推荐）
    # - mount_mode="direct": 直接使用指定目录作为工作空间
    sandbox = Sandbox(
        workspace_root=workspace,
        mount_mode="direct",
        runtime=runtime,
        allow_network=False,
    )

    try:
        await sandbox.start()
        if verbose:
            print(f"  Sandbox 已启动")
            print(f"  ├── Runtime: {runtime}")
            print(f"  ├── Workspace: {workspace}")
            print(f"  └── ID: {sandbox.sandbox_id}")

        # ─── Step 2: 创建 Agent ───
        #
        # create_deep_research_agent 内部会：
        #   1. 创建 OpenAILike LLM
        #   2. 创建 SkillAgent，自动发现 skills/ 下的 Skill
        #   3. 注册自定义工具（web_search, fetch_webpage）
        #   4. 注册 Skill 内置工具（read_skill, run_skill_script 等）
        #   5. 注册 Sandbox 工具（run_python_code, save_file 等）
        #   6. 将 Skill 元数据注入 system prompt
        agent = await create_deep_research_agent(
            model_name=model_name,
            sandbox=sandbox,
            verbose=verbose,
        )

        # ─── (可选) 演示 SkillManager 独立使用 ───
        if verbose:
            _demo_skill_manager(agent)

        # ─── Step 3: 执行研究 ───
        #
        # agent.run() 驱动完整的 ReAct 循环：
        #   用户查询 → LLM 推理 → 调用工具 → 获取结果 → LLM 推理 → ...
        #
        # 典型的执行路径：
        #   1. LLM 看到 system prompt 中的 available_skills 列表
        #   2. LLM 调用 read_skill("deep-research") 加载完整研究指令
        #   3. LLM 按指令调用 web_search 搜索多个子问题
        #   4. LLM 调用 fetch_webpage 获取详细内容
        #   5. LLM 调用 save_file 保存收集的数据到 JSON
        #   6. LLM 调用 run_skill_script 执行 extract_topics.py
        #   7. LLM 调用 run_skill_script 执行 generate_report.py
        #   8. LLM 读取报告内容，整理后返回给用户
        result = await agent.run(query)

        # ─── Step 4: 展示结果 ───
        print(f"\n{'─'*60}")
        print("  研究结果")
        print(f"{'─'*60}\n")
        print(result)

        # 尝试读取沙箱中的报告文件
        await _show_sandbox_files(sandbox, verbose)

    finally:
        # ─── Step 5: 清理 ───
        await sandbox.stop()
        if verbose:
            print(f"\n  Sandbox 已停止")


# ═══════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════

def _demo_skill_manager(agent):
    """演示 SkillManager 的独立使用方法"""
    manager = agent.skill_manager

    print(f"\n  SkillManager 演示:")

    # 查看已发现的 Skill
    print(f"  ├── 已发现 Skill: {manager.skill_names}")

    # 查看 Skill 元数据
    for skill in manager:
        print(f"  ├── {skill.name}:")
        print(f"  │   description: {skill.description[:60]}...")
        print(f"  │   path: {skill.path}")

    # 查看资源目录
    for name in manager.skill_names:
        info = manager.list_resources(name)
        print(f"  ├── {name} 资源:")
        print(f"  │   scripts:    {info.scripts}")
        print(f"  │   references: {info.references}")

    # 校验 Skill
    issues = manager.validate_all()
    if issues:
        for name, problems in issues.items():
            print(f"  ├── ⚠ {name} 校验问题: {problems}")
    else:
        print(f"  └── ✓ 所有 Skill 校验通过")

    # 查看生成的 system prompt 注入内容
    prompt_preview = manager.to_prompt()[:200]
    print(f"\n  System Prompt 注入内容 (前200字符):")
    print(f"  {prompt_preview}...")
    print()


async def _show_sandbox_files(sandbox: Sandbox, verbose: bool):
    """展示沙箱中生成的文件"""
    if not verbose:
        return

    try:
        files = await sandbox.list_files()
        if files:
            print(f"\n  沙箱中的文件:")
            for f in files:
                name = getattr(f, "name", str(f))
                size = getattr(f, "size", None)
                size_str = f" ({size} bytes)" if size else ""
                print(f"    - {name}{size_str}")

            # 尝试读取研究报告
            try:
                report = await sandbox.read_file("research_report.md")
                print(f"\n{'─'*60}")
                print("  生成的研究报告 (research_report.md)")
                print(f"{'─'*60}\n")
                print(report[:2000])
                if len(report) > 2000:
                    print(f"\n  ... (共 {len(report)} 字符，仅展示前 2000)")
            except Exception:
                pass

    except Exception as e:
        logger_msg = f"读取沙箱文件时出错: {e}"
        if verbose:
            print(f"  {logger_msg}")


# ═══════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════

def cli():
    parser = argparse.ArgumentParser(
        description="Deep Research - 基于 Alphora Skills 的深度研究智能体",
    )
    parser.add_argument(
        "query",
        type=str,
        help="研究主题（例如: 'AI Agent 技术趋势分析'）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4",
        help="LLM 模型名称 (默认: gpt-4)",
    )
    parser.add_argument(
        "--runtime",
        type=str,
        default="local",
        choices=["local", "docker"],
        help="沙箱运行时 (默认: local)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="/tmp/deep_research",
        help="沙箱工作目录 (默认: /tmp/deep_research)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="安静模式，仅输出最终结果",
    )

    args = parser.parse_args()

    asyncio.run(main(
        query=args.query,
        model_name=args.model,
        runtime=args.runtime,
        workspace=args.workspace,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    cli()
