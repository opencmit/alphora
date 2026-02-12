# Alphora Evo - 自进化 AI 智能体系统

基于 Alphora 框架的自进化智能体系统，通过 **执行者-审查者** 闭环架构，让 AI 以极高质量自主完成复杂任务。

## 架构

```
                    ┌─────────────────┐
                    │   User Query    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     Planner     │  将复杂需求分解为子任务序列
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │     Evolution Loop          │  对每个子任务:
              │  ┌──────────────────────┐   │
              │  │     Executor         │   │  ① 在沙箱中执行任务
              │  │  (Shell / 文件操作)   │   │
              │  └──────────┬───────────┘   │
              │             │               │
              │  ┌──────────▼───────────┐   │
              │  │     Reviewer         │   │  ② 审查产出质量
              │  │  (查看文件/运行测试)  │   │
              │  └──────────┬───────────┘   │
              │             │               │
              │      PASS?──┤               │
              │     yes │   │ no            │
              │         │   └──→ 带修改指令  │  ③ 未通过 → 回到 Executor
              │         │       回到 ①      │     最多 N 轮修订
              │         ▼                   │
              └─────── next task ───────────┘
                             │
                    ┌────────▼────────┐
                    │  Final Review   │  全局质量验收
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     Report      │  执行报告
                    └─────────────────┘
```

## 核心特性

| 特性 | 说明 |
|------|------|
| **任务规划** | Planner 自动将复杂需求拆分为有序子任务，带依赖关系 |
| **执行-审查闭环** | 每个子任务经过 执行→审查→修订 循环，直到质量达标 |
| **智能记忆管理** | MemoryGuard 自动压缩长链对话，Pin 关键信息，防止上下文溢出 |
| **结构化审查** | Reviewer 输出 JSON 评分报告，包含具体问题和可操作的修复建议 |
| **多模型支持** | 执行者和审查者可使用不同 LLM，增加审查多样性 |
| **进度回调** | 支持 on_progress 回调，适合集成到 Web UI / API |
| **持久化沙箱** | 通过 Storage 后端持久化工作文件，支持断点续做 |

## 快速开始

```python
import asyncio
from alphora.models import OpenAILike
from alphora.sandbox import Sandbox
from alphora_evo import EvolutionEngine

async def main():
    llm = OpenAILike(model_name="qwen-max")
    
    sandbox = Sandbox(workspace_root="/tmp/evo", runtime="docker", allow_network=True)
    
    async with sandbox:
        engine = EvolutionEngine(llm=llm, sandbox=sandbox)
        report = await engine.run("用 Python 写一个贪吃蛇游戏")
        print(report.summary())

asyncio.run(main())
```

## 命令行使用

```bash
# 基础
python -m alphora_evo.run "做一个 Todo 应用（HTML+CSS+JS）"

# 指定模型
python -m alphora_evo.run "构建 REST API" --model gpt-4

# 双模型（执行者快速/审查者精准）
python -m alphora_evo.run "写博客系统" --model qwen-plus --reviewer-model qwen-max

# 保留沙箱文件
python -m alphora_evo.run "做游戏合集" --keep-sandbox --sandbox-path /data/my_games
```

## 组件说明

### EvolutionEngine

核心编排器，驱动整个自进化流程。

```python
engine = EvolutionEngine(
    llm=llm,                      # 主 LLM
    sandbox=sandbox,              # 沙箱实例
    reviewer_llm=reviewer_llm,    # 审查者 LLM（可选，默认同主 LLM）
    max_revisions_per_task=3,     # 每个子任务最大修订次数
    pass_threshold=80,            # 审查通过分数阈值（0-100）
    skip_planning=False,          # 跳过规划阶段
    on_progress=callback_fn,      # 进度回调
    verbose=True,                 # 详细输出
)
```

### PlannerAgent

将用户需求分解为子任务序列，输出结构化的 JSON 任务计划。

```python
planner = PlannerAgent(sandbox=sandbox, llm=llm)
plan = await planner.plan("做一个游戏合集，包含五子棋和贪吃蛇")
# plan = {
#     "goal": "...",
#     "tasks": [...],
#     "quality_criteria": [...]
# }
```

### ExecutorAgent

在沙箱中执行具体任务，通过 Shell 命令和文件操作完成工作。

```python
executor = ExecutorAgent(
    sandbox=sandbox,
    memory_guard=memory_guard,
    llm=llm,
    max_iterations=50,
)
result = await executor.execute_task(
    task=task_dict,
    goal="...",
    quality_criteria=[...],
    completed_tasks=[...],
    revision_instructions=None,  # 修订模式时传入审查者指令
)
```

### ReviewerAgent

审查执行者的产出，输出结构化评分报告。

```python
reviewer = ReviewerAgent(
    sandbox=sandbox,
    llm=reviewer_llm,
    pass_threshold=80,
)
review = await reviewer.review(
    original_query="...",
    task_plan=plan,
    quality_criteria=[...],
)
# review = {
#     "verdict": "PASS",
#     "score": 92,
#     "summary": "代码质量优秀...",
#     "issues": [...]
# }
```

### MemoryGuard

智能记忆管理器，解决长链调用的上下文膨胀问题。

```python
guard = MemoryGuard(
    memory=MemoryManager(),
    llm=llm,
    max_rounds_before_compress=15,  # 超过此轮数自动触发压缩
    keep_recent_rounds=8,           # 压缩时保留最近 N 轮
)

# 正常使用
guard.add_user("...")
guard.add_assistant(response)
guard.tick()  # 每轮后调用

# 自动检测 + 压缩
if guard.should_compress():
    await guard.compress(sandbox=sandbox)

# 构建优化后的历史
history = guard.build_history(max_rounds=20)
```

## 自进化机制

核心理念：**通过独立的审查者 Agent 形成质量闭环**。

1. **规划阶段**：Planner 分析需求复杂度，生成带质量标准的子任务序列
2. **执行阶段**：Executor 在沙箱中独立完成每个子任务
3. **审查阶段**：Reviewer 实际查看文件、运行代码，给出评分和具体修改建议
4. **修订阶段**：如果未达标，Executor 根据审查反馈进行定向修改
5. **收敛保障**：设置最大修订次数，避免无限循环

### 为什么有效？

- **分离关注点**：执行者专注完成任务，审查者专注挑毛病，避免"自我感觉良好"
- **具体反馈**：审查报告包含文件位置、严重程度、修复建议，修订有据可循
- **多模型增强**：执行和审查使用不同模型，避免系统性盲点
- **记忆管理**：MemoryGuard 确保长链调用不会因上下文溢出而降质

## 与原始 mini_claw 的对比

| 维度 | mini_claw | alphora_evo |
|------|-----------|-------------|
| 架构 | 单体 Agent + 被动 Supervisor | Planner + Executor + Reviewer 三角 |
| 任务管理 | 无规划，一次性执行 | 自动分解子任务，逐个执行审查 |
| 质量保障 | Supervisor 提示词占位 | 结构化评分 + 定向修订闭环 |
| 记忆管理 | 手动 clear_memory | MemoryGuard 自动压缩 + Pin + 持久化 |
| 记忆策略 | 全部清除 | 保留 pinned 关键信息 + LLM 摘要 |
| 错误恢复 | 无 | 审查驱动的定向修复 |
| 可观测性 | 无 | 进度回调 + 结构化报告 |
| 可配置性 | 硬编码 | 全面参数化 + CLI |

## 进阶配置

### 进度回调（适合 Web 集成）

```python
def on_progress(event: str, data: dict):
    if event == "planning_done":
        ws.send(json.dumps({"type": "plan", "tasks": len(data["plan"]["tasks"])}))
    elif event == "task_review_done":
        ws.send(json.dumps({"type": "review", "score": data["review"]["score"]}))
    elif event == "completed":
        ws.send(json.dumps({"type": "done"}))

engine = EvolutionEngine(llm=llm, sandbox=sandbox, on_progress=on_progress)
```

### 自定义评分阈值

```python
# 严格模式（适合生产环境）
engine = EvolutionEngine(
    llm=llm, sandbox=sandbox,
    pass_threshold=90,
    max_revisions_per_task=5,
)

# 宽松模式（适合快速原型）
engine = EvolutionEngine(
    llm=llm, sandbox=sandbox,
    pass_threshold=60,
    max_revisions_per_task=1,
)
```
