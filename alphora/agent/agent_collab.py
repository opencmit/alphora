# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""多智能体协作块（collab）—— 框架级通用基础能力。

「协作块（collab）」是一段**多个 agent 一起产出**的活动的统一抽象：一次并行批次、
一次议会讨论，都属于一段 collab。框架只提供**通用容器**：

  - 生成一个与对话 session 无关的 ``collab_id``；
  - 进入时发 ``agent_collab_start``、退出时发 ``agent_collab_end`` 生命周期事件；
  - 通过 ContextVar 把 ``collab_id``/``kind`` 暴露给协作内的子调用，便于打标。

本模块**不含任何具体业务语义**（如「议会」的辩论/收敛/决议）——那些应由上层
（如 alphadata-core 的编排器）基于此通用能力自行实现。前端只需按 ``collab_id`` + ``size``
确定性地分组渲染（``size>=2`` 出多智能体面板，否则内联）。
"""

from __future__ import annotations

import contextvars
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from uuid import uuid4

from alphora.agent.events import ContentType, MetaKey

logger = logging.getLogger(__name__)

# 当前协作块 id / 种类。在 AgentCollabScope 内被设置；协作内通过 asyncio.gather/create_task
# 派生的子任务会复制进入时的上下文，因此子调用（如派活工具）可直接读到这两个值。
current_collab_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_collab_id", default=None
)
current_collab_kind: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_collab_kind", default=None
)


def new_collab_id() -> str:
    """生成一个协作块 id（与对话 session id 无关，仅用于把同一段协作的事件串起来）。"""
    return f"collab_{uuid4().hex[:12]}"


@asynccontextmanager
async def AgentCollabScope(
    stream,
    *,
    kind: str,
    members: Optional[List[Dict[str, Any]]] = None,
    title: str = "",
    collab_id: Optional[str] = None,
):
    """开启一段「多智能体协作块」。

    用法::

        async with AgentCollabScope(self.stream, kind="batch", members=[...]) as cid:
            # 这段内由 gather/create_task 派生的子 agent 输出
            # 都能读到 current_collab_id == cid
            await run_subagents_in_parallel()

    Args:
        stream: 用于发送生命周期事件的 ``Stream``（需有 ``astream_message``）；None 则不发事件。
        kind: 协作种类。框架内置约定 ``"batch"``（并行执行）；上层可扩展任意字符串（如 ``"council"``）。
        members: 名册，每项形如 ``{"agent_id", "agent_name", "role"?, "task_id"?}``；``size`` 由其长度推得。
        title: 可选展示标题。
        collab_id: 可选外部指定的 id；缺省自动生成。

    Yields:
        本次协作块的 ``collab_id``。
    """
    cid = collab_id or new_collab_id()
    member_list = list(members or [])
    size = len(member_list)

    tok_id = current_collab_id.set(cid)
    tok_kind = current_collab_kind.set(kind)
    status = "ok"

    if stream is not None:
        try:
            await stream.astream_message(
                content=json.dumps(
                    {
                        "collab_id": cid,
                        "kind": kind,
                        "title": title,
                        "size": size,
                        "members": member_list,
                    },
                    ensure_ascii=False,
                ),
                content_type=str(ContentType.AGENT_COLLAB_START),
                meta={str(MetaKey.COLLAB_ID): cid, str(MetaKey.COLLAB_KIND): kind},
            )
        except Exception:
            logger.debug("emit agent_collab_start failed", exc_info=True)

    try:
        yield cid
    except BaseException:
        status = "error"
        raise
    finally:
        current_collab_id.reset(tok_id)
        current_collab_kind.reset(tok_kind)
        if stream is not None:
            try:
                await stream.astream_message(
                    content=json.dumps(
                        {"collab_id": cid, "kind": kind, "status": status},
                        ensure_ascii=False,
                    ),
                    content_type=str(ContentType.AGENT_COLLAB_END),
                    meta={str(MetaKey.COLLAB_ID): cid},
                )
            except Exception:
                logger.debug("emit agent_collab_end failed", exc_info=True)
