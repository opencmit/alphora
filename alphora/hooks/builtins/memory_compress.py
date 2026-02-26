# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
内置钩子：记忆压缩

当循环中上下文长度超过阈值时，自动调用 LLM 总结当前对话，
将摘要通过 sandbox.write_file 写入沙箱，然后清除 tool 相关消息以释放上下文空间。

注册到 AGENT_AFTER_ITERATION 事件，从 ctx.data 中获取 memory / sandbox / llm。
"""

import logging
from datetime import datetime
from typing import Callable, Optional

from alphora.memory import MemoryManager

from alphora.hooks.context import HookContext

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "你是一个对话总结助手。请用 500 字以内总结对话的关键信息："
    "用户需求、执行了什么操作、得到什么结果、当前进展到哪一步。"
)


def make_memory_compressor(
        threshold: int = 20000,
        summary_file: str = "memory_{ts}.md",
        summary_system_prompt: Optional[str] = None,
        keep_recent_messages: int = 8,
) -> Callable[[HookContext], None]:
    """
    创建记忆压缩钩子，注册到 AGENT_AFTER_ITERATION。

    从 ctx.data 中获取 memory / sandbox / llm，无需手动传入。
    """
    sys_prompt = summary_system_prompt or SUMMARY_SYSTEM_PROMPT
    _summarizer = {}

    async def _hook(ctx: HookContext) -> None:
        memory: MemoryManager = ctx.get("memory")
        sandbox = ctx.get("sandbox")
        llm = ctx.get("llm")

        if not memory or not sandbox or not llm:
            return

        history = memory.build_history()
        chars = history.count_context_length(mode="chars")
        if chars < threshold:
            return

        logger.info(f"[memory_compress] {chars} chars > {threshold}, compressing...")

        if "prompt" not in _summarizer:
            from alphora.prompter import BasePrompt
            s = BasePrompt(system_prompt=sys_prompt)
            s.add_llm(llm)
            _summarizer["prompt"] = s

        lines = []
        for msg in history.messages:
            role = msg.get("role", "?")
            content = msg.get("content") or ""
            if role == "system":
                continue

            if msg.get("tool_calls"):
                names = [
                    tc.get("function", {}).get("name", "?")
                    for tc in msg["tool_calls"]
                ]
                lines.append(f"[assistant] 调用工具: {', '.join(names)}")
            elif role == "tool":
                name = msg.get("name", "tool")
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"[{name}] {content}")
            else:
                lines.append(f"[{role}] {content}")

        conversation = "\n".join(lines)[-10000:]

        try:
            summary = str(await _summarizer["prompt"].acall(
                query=f"请总结以下对话：\n\n{conversation}",
                is_stream=False,
            ))

        except Exception as e:
            logger.error(f"[memory_compress] LLM summarization failed: {e}")
            summary = f"（总结失败）{len(history.messages)} 条消息, {chars} 字符"

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = summary_file.replace("{ts}", ts)

        try:
            await sandbox.write_file(filename, f"# 对话摘要 {ts}\n\n{summary}\n")
            logger.info(f"[memory_compress] Saved summary -> {filename}")
        except Exception as e:
            logger.error(f"[memory_compress] write_file failed: {e}")

        from alphora.memory import Message

        # 先移除工具调用链，避免后续裁剪导致工具链不完整
        memory.remove(lambda m: m.role == "tool")
        memory.remove(lambda m: m.role == "assistant" and m.has_tool_calls)

        # 保留最近窗口，删除更早的 user/assistant 明细，降低噪声并保持近端连续性
        non_system_messages = [m for m in memory.get_messages() if m.role != "system"]
        keep_n = max(0, keep_recent_messages)
        keep_ids = {m.id for m in non_system_messages[-keep_n:]} if keep_n > 0 else set()
        memory.remove(lambda m: m.role != "system" and m.id not in keep_ids)

        # 清理旧的压缩标记，避免多次压缩时重复堆叠
        memory.remove(
            lambda m: m.role == "system"
            and (m.content or "").startswith("[MEMORY_COMPRESSED]")
        )

        memory_pointer = (
            "[MEMORY_COMPRESSED]\n"
            f"- summary_file: {filename}\n"
            f"- compressed_at: {ts}\n"
            f"- kept_recent_messages: {keep_n}\n"
            "- note: 较早历史已持久化到 summary_file，不再内联在上下文中。\n"
            "- instruction: 若需要更早细节，请读取 summary_file 后再继续推理。"
        )
        memory.inject(Message.system(memory_pointer), position="start")

        new_chars = memory.build_history().count_context_length(mode="chars")
        logger.info(f"[memory_compress] {chars} -> {new_chars} chars")

    return _hook

