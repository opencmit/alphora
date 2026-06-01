"""
Tutorial 20: 用 Hook（类-对象形式）拦截指定工具。

  - 工具执行前：若触发了「查询工具」，print 出告警。
  - 工具执行后：把该工具输出里的电话号码抹成 ***。

钩子用一个类的实例来承载状态与逻辑（而不是散落的函数），
通过 HookResult(replace={...}) 把修改写回 ctx.data。

  python tutorials/20_hook_tool_redact_encrypt.py
"""

import asyncio
import json

from alphora.tools import tool, ToolRegistry, ToolExecutor
from alphora.tools.executor import ToolExecutionResult
from alphora.models.llms.types import ToolCall
from alphora.hooks import HookManager, HookEvent, HookResult, HookContext


class QueryToolGuard:
    """监控某个查询工具：触发时告警，并抹除输出中的电话号码。"""

    def __init__(self, target_tool: str):
        self.target_tool = target_tool

    def before_execute(self, ctx: HookContext):
        """执行前：命中目标工具则 print 告警。"""
        if ctx.data.get("tool_name") != self.target_tool:
            return None
        print(f"[告警] 检测到敏感查询工具被调用: {self.target_tool} "
              f"args={ctx.data.get('tool_args')}")
        return None

    def after_execute(self, ctx: HookContext):
        """执行后：把目标工具输出里的电话号码换成 ***。"""
        if ctx.data.get("tool_name") != self.target_tool:
            return None

        result: ToolExecutionResult = ctx.data["tool_result"]
        data = json.loads(result.content)
        if "phone" in data:
            data["phone"] = "***"

        new_result = result.model_copy(
            update={"content": json.dumps(data, ensure_ascii=False)}
        )
        return HookResult(replace={"tool_result": new_result})


@tool
def query_user_account(account_id: str) -> dict:
    """查询用户账户信息。"""
    return {"account_id": account_id, "phone": "13800138000"}


async def main() -> None:
    guard = QueryToolGuard(target_tool="query_user_account")

    hooks = HookManager()
    hooks.register(HookEvent.TOOLS_BEFORE_EXECUTE, guard.before_execute)
    hooks.register(HookEvent.TOOLS_AFTER_EXECUTE, guard.after_execute)

    registry = ToolRegistry()
    registry.register(query_user_account)

    executor = ToolExecutor(registry, hooks=hooks)

    tool_calls: ToolCall = ToolCall.create(
        ("query_user_account", {"account_id": "U-10086"}),
    )
    results = await executor.execute(tool_calls)

    for r in results:
        print(f"{r.tool_name} -> {r.content}")


if __name__ == "__main__":
    asyncio.run(main())
