"""
Deep Research (Skill-based)

An agent that conducts iterative deep research: searching the web, collecting
materials, analyzing data, and assembling comprehensive markdown reports with
charts, images, and citations — similar to how a human analyst writes a
research report over multiple passes.
"""

import asyncio
import argparse
import os
from pathlib import Path

from alphora.models import OpenAILike
from alphora.sandbox import Sandbox
from alphora.agent import SkillAgent
from alphora.hooks import HookManager, HookEvent
from alphora.hooks.builtins import make_memory_compressor


SKILLS_DIR = str(Path(__file__).parent / "skills")

SYSTEM_PROMPT = """\
你是一位资深研究分析师，擅长对复杂话题进行深度调研并撰写专业研究报告。

## 工作方式

1. 收到研究任务后，使用 read_skill 加载「deep-research」技能获取完整操作指南
2. 按照技能中的五个阶段推进：规划 → 搜集 → 分析 → 撰写 → 验证
3. 所有操作在沙箱环境中执行，素材和产出保存在 /mnt/workspace/ 下

## 核心原则

- **迭代式研究**：不要试图一次写完报告。先广泛搜索，积累素材，识别信息缺口，再针对性补充，最后综合撰写
- **循证为本**：每个事实性陈述必须有来源支撑，使用 [n] 标注引用
- **数据驱动**：尽可能找到量化数据，用代码分析并生成图表，让报告有说服力
- **图文并茂**：每个主要章节至少包含一个图表或数据表格，增强可读性

## 素材管理

研究过程中持续将素材保存到沙箱本地：
- 搜索结果 → /mnt/workspace/research/notes/
- 网页原文 → /mnt/workspace/research/sources/
- 数据文件 → /mnt/workspace/research/data/
- 参考图片 → /mnt/workspace/research/images/
- 生成图表 → /mnt/workspace/report/assets/

这样即使对话上下文被压缩，素材仍然保留在文件系统中可随时查阅。

## 交互协议

- 研究开始前先输出研究计划，让用户了解你将要调查的方向
- 每完成一个阶段简要汇报进展（如："已收集到 8 个相关资料来源，正在进入数据分析阶段"）
- 如果某个方向搜索不到足够信息，主动说明并调整策略
- 最终交付完整的 markdown 报告和 HTML 版本

## 环境须知

- 沙箱有网络访问能力，可以搜索和下载资料
- 依赖缺失时用清华源安装：pip install <pkg> -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
- matplotlib 画图必须配置中文字体（技能指南中有说明）
"""


async def main(
    query: str = "请对该主题进行深度研究",
    runtime: str = "docker",
    workspace: str = "/tmp/deep_research_workspace",
    allow_network: bool = True,
    max_iterations: int = 50,
):
    os.makedirs(workspace, exist_ok=True)

    # Pre-create research directory structure
    for subdir in [
        "research/sources",
        "research/data",
        "research/images",
        "research/notes",
        "report/assets",
    ]:
        os.makedirs(os.path.join(workspace, subdir), exist_ok=True)

    hooks = HookManager()
    hooks.register(
        HookEvent.AGENT_AFTER_ITERATION,
        make_memory_compressor(threshold=120000),
        timeout=120,
    )

    sandbox = Sandbox(
        workspace_root=workspace,
        runtime=runtime,
        allow_network=allow_network,
    )

    agent = SkillAgent(
        llm=OpenAILike(max_tokens=16000),
        skill_paths=[SKILLS_DIR],
        sandbox=sandbox,
        system_prompt=SYSTEM_PROMPT,
        max_iterations=max_iterations,
        hooks=hooks,
    )

    print(f"[info] Skills dir     : {SKILLS_DIR}")
    print(f"[info] Workspace      : {workspace}")
    print(f"[info] Runtime        : {runtime}")
    print(f"[info] Max iterations : {max_iterations}")
    print(f"[info] Discovered     : {agent.skills}")
    print(f"[info] Tools          : {[t.name for t in agent.tools]}")
    print()

    print("=" * 60)
    print(f"  Research Query: {query}")
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
    parser = argparse.ArgumentParser(
        description="Deep Research — AI-powered research report generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --query "2024年全球AI芯片市场深度分析"
  python run.py --query "新能源汽车产业链全景研究报告"
  python run.py --query "量子计算技术发展现状与商业化前景"
  python run.py --query "Deep dive into global semiconductor supply chain risks"
        """,
    )
    parser.add_argument(
        "--query",
        default="请对2024年中国大模型行业发展现状进行深度研究，撰写一份包含市场规模、主要玩家、技术趋势、应用场景和未来展望的研究报告",
        help="Research topic or question",
    )
    parser.add_argument("--runtime", default="docker", choices=["local", "docker"])
    parser.add_argument("--workspace", default="/tmp/deep_research_workspace", help="Workspace directory")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max agent iterations (default: 50)")
    parser.add_argument("--no-network", action="store_true", help="Disable network access in sandbox")
    args = parser.parse_args()

    asyncio.run(main(
        query=args.query,
        runtime=args.runtime,
        workspace=args.workspace,
        allow_network=not args.no_network,
        max_iterations=args.max_iterations,
    ))


if __name__ == "__main__":
    cli()
