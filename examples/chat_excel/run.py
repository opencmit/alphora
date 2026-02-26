"""
ChatExcel (Skill-based)
"""

import asyncio
import argparse
import os
import shutil
from pathlib import Path

from alphora.models import OpenAILike
from alphora.sandbox import Sandbox
from alphora.agent import SkillAgent
from alphora.hooks import HookManager, HookEvent
from alphora.hooks.builtins import make_memory_compressor, make_checkpoint_saver


SKILLS_DIR = str(Path(__file__).parent / "skills")

SYSTEM_PROMPT = """\
你是一位资深数据分析专家，擅长从原始数据中提取有价值的洞察。

## 工作方式

1. 收到任务后，选择最合适的skill作为操作指南
2. 严格按照技能中的SOP工作流执行，先探查数据再编码
3. 代码必须分段执行：每段只做一个目标、每段都打印验证输出
4. 所有代码在沙箱环境中执行，文件操作在 /mnt/workspace/ 下完成

## 交互协议
- 每步操作前简述目的（一句话即可）
- 任务完成后总结关键发现，列出所有生成的文件

## 环境须知
- 依赖缺失时用清华源安装：pip install <pkg> -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
- matplotlib 画图必须配置中文字体（技能指南中有详细说明）
"""


async def main(
    query: str = "你好",
    runtime: str = "docker",
    workspace: str = "/Users/tiantiantian/其他/sandbox",
    file_to_copy: str = None,
    allow_network: bool = True,
):
    os.makedirs(workspace, exist_ok=True)

    if file_to_copy and os.path.exists(file_to_copy):
        dest = os.path.join(workspace, os.path.basename(file_to_copy))
        shutil.copy2(file_to_copy, dest)
        print(f"[setup] Copied {file_to_copy} -> {dest}")

    hooks = HookManager()

    hooks.register(
        HookEvent.AGENT_AFTER_ITERATION,
        make_memory_compressor(threshold=100000),
        timeout=120,
    )

    hooks.register(
        HookEvent.AGENT_AFTER_ITERATION,
        make_checkpoint_saver(),
    )

    sandbox = Sandbox(
        workspace_root=workspace,
        runtime=runtime,
        allow_network=allow_network,
    )

    agent = SkillAgent(
        llm=OpenAILike(max_tokens=8000),
        skill_paths=[SKILLS_DIR],
        sandbox=sandbox,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=30,
        hooks=hooks,
    )

    print(f"[info] Skills dir     : {SKILLS_DIR}")
    print(f"[info] Workspace      : {workspace}")
    print(f"[info] Runtime        : {runtime}")
    print(f"[info] Discovered     : {agent.skills}")
    print(f"[info] Tools          : {[t.name for t in agent.tools]}")
    print()

    print("=" * 60)
    print(f"  Query: {query}")
    print("=" * 60)

    result = await agent.run(query)

    print("\n" + "=" * 60)
    print("  Result:")
    print("=" * 60)
    print(result)

    if sandbox.is_running:
        files = await sandbox.list_files(recursive=True)
        if files:
            print(f"\n[workspace files]")
            for f in files:
                print(f"  {f.path} ({f.size} bytes)")
        await sandbox.stop()


def cli():
    parser = argparse.ArgumentParser(description="ChatExcel (Skill-based)")
    parser.add_argument("--query", default="分析家宽指标，并给我一个报告", help="User query")
    parser.add_argument("--runtime", default="docker", choices=["local", "docker"])
    parser.add_argument("--workspace", default="/Users/tiantiantian/其他/sandbox/new", help="Workspace directory")
    parser.add_argument("--file", default=None, help="Copy a data file into the workspace before running")
    parser.add_argument("--network", action="store_true", default=True, help="Allow network in sandbox")
    args = parser.parse_args()

    asyncio.run(main(
        query=args.query,
        runtime=args.runtime,
        workspace=args.workspace,
        file_to_copy=args.file,
        allow_network=args.network,
    ))


if __name__ == "__main__":
    cli()
