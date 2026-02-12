"""
Alphora Evo - 启动入口

Usage:
    # 基础用法
    python run.py "做一个贪吃蛇游戏（HTML+JS+CSS）"
    
    # 指定模型和沙箱路径
    python run.py "构建一个 REST API" --model qwen-max --sandbox-path /tmp/evo_sandbox
    
    # 使用不同的审查模型（增加多样性）
    python run.py "写一个博客系统" --model gpt-4 --reviewer-model claude-3-sonnet
    
    # 跳过规划阶段（简单任务）
    python run.py "写一个排序算法" --skip-planning
"""

import asyncio
import argparse
import sys
import os

from alphora.models import OpenAILike
from alphora.sandbox import Sandbox

from examples.mini_claw.engine import EvolutionEngine


async def main(query):
    """主流程"""

    llm = OpenAILike(model_name="qwen-max")
    reviewer_llm = OpenAILike(model_name="qwen-max")

    sandbox_root = "/Users/tiantiantian/临时/sandbox/my_sandbox"
    os.makedirs(sandbox_root, exist_ok=True)
    sandbox = Sandbox(
        workspace_root=sandbox_root,
        runtime="docker",
        allow_network=True,
    )

    try:
        await sandbox.start()
        print(f"🐳 沙箱已启动 (ID: {sandbox.sandbox_id})")

        # ─── 创建引擎 ───
        engine = EvolutionEngine(
            llm=llm,
            sandbox=sandbox,
            reviewer_llm=reviewer_llm,
            max_revisions_per_task=100,
            pass_threshold=80,
            skip_planning=False,
            verbose=True,
        )

        # ─── 执行 ───
        report = await engine.run(query)

        # ─── 输出报告 ───
        print(f"\n\n{'='*60}")
        print(report.summary())
        print(f"{'='*60}")

        # 保存报告到沙箱
        import json
        report_data = {
            "query": report.query,
            "plan": report.plan,
            "duration": report.duration,
            "total_iterations": report.total_iterations,
            "success": report.success,
            "final_review": report.final_review,
            "task_results": [
                {
                    "task_id": r.task_id,
                    "task_title": r.task_title,
                    "status": r.final_status,
                    "attempts": len(r.attempts),
                    "iterations": r.total_iterations,
                    "passed": r.passed,
                    "final_score": r.final_review.get("score") if r.final_review else None,
                }
                for r in report.task_results
            ],
        }
        await sandbox.write_file(
            "EVOLUTION_REPORT.json",
            json.dumps(report_data, ensure_ascii=False, indent=2),
        )
        print(f"\n📄 报告已保存到沙箱: EVOLUTION_REPORT.json")

    finally:
        await sandbox.destroy()
        print("🧹 沙箱已销毁")


if __name__ == "__main__":
    asyncio.run(main(query='给我做一个贪吃蛇'))
