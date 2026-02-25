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


SKILLS_DIR = str(Path(__file__).parent / "skills")

SYSTEM_PROMPT = """\
你是一个专业的数据分析助手。用户会上传数据文件并提出分析需求。

## 你的工作方式

1. 首先使用 read_skill 工具加载「data-analysis」技能，获取完整的操作指南
2. 严格按照技能指南中的工作流程（5 个阶段）执行任务
3. 在沙箱环境中执行代码，所有文件操作都在沙箱内完成

## 行为准则

- 循证：一切结论必须有据可查，绝不编造
- 渐进：复杂任务分层推进，先探查后执行
- 协作：遇到歧义主动澄清，关键决策交给用户
- 透明：展示完整推理过程，让用户理解你的思考

## 执行协议

进入任务后，遵循 Thought → Action → Observation 循环：
- 每次调用工具之前，先用一两句话告诉用户你在做什么
- 工具调用之前，用一段话描述你将要进行的操作
- 工具调用结果返回后，评估结果并决定下一步
- 任务完成后，总结关键发现并列出生成的文件

## 关键提醒

- 如果缺少依赖包，使用清华镜像源安装：pip install <pkg> -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
- matplotlib 画图时必须配置中文字体（详见技能指南）
- 所有列名必须来自实际的数据探查结果，严禁猜测
"""


async def main(
    query: str = "请分析工作目录中的数据文件",
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
    parser.add_argument("--query", default="分析广东的各项指标，并给我一个报告", help="User query")
    parser.add_argument("--runtime", default="docker", choices=["local", "docker"])
    parser.add_argument("--workspace", default="/Users/tiantiantian/其他/sandbox", help="Workspace directory")
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
