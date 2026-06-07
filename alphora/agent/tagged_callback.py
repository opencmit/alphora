# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""通用打标 callback —— 给子 agent 的所有输出统一注入身份与协作 meta。

子 agent 与父 agent 共享同一条 SSE 流。包一层 ``TaggedCallback`` 后，子 agent 的
**所有**输出（LLM 正文、tool_call/参数、stdout/stderr、status、路书…）都会自动带上：

  - ``agent_id`` / ``agent_name``：产出该内容的子 agent 身份；
  - ``group``：协作分组标识（默认 ``"swarm"``）；
  - ``task_id``（可选）：派活实例 id；
  - ``collab_id`` / ``collab_kind``：**自动**从 ContextVar 读取（若当前处于
    :func:`alphora.agent.agent_collab.AgentCollabScope` 内），让前端确定性归组，
    无需任何并发推断。

``stop()`` 为 no-op，避免子 agent 提前关闭与父 agent 共享的流。
"""

from __future__ import annotations

from typing import Optional

from alphora.agent.agent_collab import current_collab_id, current_collab_kind
from alphora.agent.events import MetaKey


class TaggedCallback:
    def __init__(
        self,
        callback,
        *,
        agent_id: str,
        agent_name: Optional[str] = None,
        task_id=None,
        group: Optional[str] = "swarm",
        extra_meta: Optional[dict] = None,
    ):
        self._callback = callback
        self._agent_id = agent_id
        self._agent_name = agent_name or agent_id
        self._task_id = task_id
        self._group = group
        # 额外静态 meta（每条输出都 setdefault 注入）。用于议会等场景给一段发言统一打
        # round/turn 等标识——按发言重建一个 TaggedCallback 即可，无需框架感知具体语义。
        self._extra_meta = dict(extra_meta) if extra_meta else {}

    async def send_data(self, content_type: str, content: str = None, meta: dict = None):
        if not self._callback:
            return
        merged = dict(meta) if meta else {}
        merged.setdefault(str(MetaKey.AGENT_ID), self._agent_id)
        merged.setdefault(str(MetaKey.AGENT_NAME), self._agent_name)
        if self._group is not None:
            merged.setdefault(str(MetaKey.GROUP), self._group)
        if self._task_id is not None:
            merged.setdefault(str(MetaKey.TASK_ID), self._task_id)
        for _k, _v in self._extra_meta.items():
            if _v is not None:
                merged.setdefault(str(_k), _v)
        # 自动注入协作块标识（若处于某段 AgentCollabScope 内）。
        cid = current_collab_id.get()
        if cid is not None:
            merged.setdefault(str(MetaKey.COLLAB_ID), cid)
            kind = current_collab_kind.get()
            if kind is not None:
                merged.setdefault(str(MetaKey.COLLAB_KIND), kind)
        await self._callback.send_data(content_type=content_type, content=content, meta=merged)

    async def stop(self, stop_reason: str = "stop"):
        # 子 agent 不应关闭与父 agent 共享的流
        return

    async def usage(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        if self._callback and hasattr(self._callback, "usage"):
            await self._callback.usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
