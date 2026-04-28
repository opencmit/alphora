# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""Request scope / per-task isolation 回归测试。

覆盖核心契约：

1. ``RequestScoped`` 描述符在没有激活作用域时与普通实例属性等价。
2. ``enter_request_scope`` 后，对 ``BaseAgent`` 五个请求级属性的写入只
   影响当前任务，不会污染单例或其它并发任务。
3. ``self.update_config(key, value)`` 写入的 sandbox / session_id 在并发
   场景下不会出现"串号"。
4. 派生子智能体（``derive``）在同一个请求作用域里能正确读到父 agent 的
   per-request 值。
5. 通过 FastAPI ``TestClient`` + ``publish_agent_api`` 模拟两个并发请求，
   确认每个会话各自看到自己的 sandbox 标识。

注意：本文件不能加 ``from __future__ import annotations``，否则
``alphora.server.quick_api.agent_validator`` 的 ``is OpenAIRequest`` 校验
会因为注解被字符串化而失败。
"""

import asyncio
import json
from typing import Dict

import pytest

from alphora.agent.base_agent import BaseAgent
from alphora.agent._request_scope import (
    RequestScoped,
    current_overrides,
    enter_request_scope,
)
from alphora.server.openai_request_body import OpenAIRequest


# ---------------------------------------------------------------------------
# 1. 描述符基础语义
# ---------------------------------------------------------------------------

def test_descriptor_without_scope_behaves_like_plain_attribute():
    class Holder:
        x = RequestScoped("x")

    h = Holder()
    assert h.x is None  # 未设置时返回 None，行为与未初始化属性近似
    h.x = 42
    assert h.x == 42

    # 没有激活作用域时，写入会落到 __dict__ 的私有键
    assert h.__dict__.get("_singleton_x") == 42


def test_descriptor_with_scope_isolates_writes_from_singleton():
    class Holder:
        x = RequestScoped("x")

    h = Holder()
    h.x = "singleton-default"

    async def request_a():
        enter_request_scope()
        h.x = "value-a"
        await asyncio.sleep(0.01)
        assert h.x == "value-a"
        # 单例底层默认值不应被覆盖
        assert h.__dict__["_singleton_x"] == "singleton-default"

    async def request_b():
        enter_request_scope()
        h.x = "value-b"
        await asyncio.sleep(0.01)
        assert h.x == "value-b"
        assert h.__dict__["_singleton_x"] == "singleton-default"

    async def main():
        await asyncio.gather(request_a(), request_b())
        # 主任务从未 enter_request_scope，应仍读到单例默认值
        assert h.x == "singleton-default"
        assert current_overrides() is None

    asyncio.run(main())


# ---------------------------------------------------------------------------
# 2. BaseAgent 五个请求级属性的并发隔离
# ---------------------------------------------------------------------------

class _StubAgent(BaseAgent):
    """空壳 agent，用来跑并发隔离测试，不依赖真实 LLM/Memory/Sandbox。"""

    async def run(self, task: str) -> str:  # pragma: no cover - 仅供 parallel_run 检查
        return f"echo:{task}"


def test_baseagent_config_writes_isolated_across_tasks():
    agent = _StubAgent()
    initial_config = agent.config

    async def session(session_id: str, sandbox_label: str, hold_seconds: float) -> str:
        enter_request_scope()
        # 仿照 svc-alphadata 的写法：先把 config 克隆成一份请求级 dict
        agent.config = dict(agent.config)
        agent.config["session_id"] = session_id
        agent.config["sandbox"] = sandbox_label

        # 模拟实际服务里"沙箱长时间存活"的窗口
        await asyncio.sleep(hold_seconds)

        # 派生一个子 agent，它必须读到本请求的 sandbox 而不是别人的
        sub = agent.derive(_StubAgent)
        assert sub.get_config("sandbox") == sandbox_label
        assert sub.get_config("session_id") == session_id

        return f"{session_id}:{agent.config['sandbox']}"

    async def main():
        a, b = await asyncio.gather(
            session("123", "sbx-a", 0.05),
            session("456", "sbx-b", 0.02),
        )
        assert a == "123:sbx-a"
        assert b == "456:sbx-b"
        # 单例 config 不被任何一次请求写入污染
        assert "session_id" not in initial_config
        assert "sandbox" not in initial_config

    asyncio.run(main())


def test_baseagent_memory_callback_stream_isolated_across_tasks():
    agent = _StubAgent()
    sentinel_memory = agent.memory  # 单例默认 MemoryManager

    seen: Dict[str, object] = {}

    async def session(label: str, mem_obj: object):
        enter_request_scope()
        agent.memory = mem_obj
        await asyncio.sleep(0.01)
        seen[label] = agent.memory

    async def main():
        m1, m2 = object(), object()
        await asyncio.gather(session("s1", m1), session("s2", m2))
        assert seen["s1"] is m1
        assert seen["s2"] is m2
        # 单例底层 memory 仍然是初始 MemoryManager
        assert agent.memory is sentinel_memory

    asyncio.run(main())


# ---------------------------------------------------------------------------
# 3. update_config / get_config 不串
# ---------------------------------------------------------------------------

def test_update_config_does_not_leak_across_concurrent_sessions():
    """复刻 svc-alphadata 的真实使用模式：serve() 里多次 update_config + derive。"""
    agent = _StubAgent()

    async def serve_like(session_id: str, sandbox: object, hold: float):
        enter_request_scope()
        agent.config = dict(agent.config)
        agent.update_config("session_id", session_id)
        agent.update_config("sandbox", sandbox)

        # 故意让一个请求"挂"久一点，模拟复杂任务
        await asyncio.sleep(hold)

        sub = agent.derive(_StubAgent)
        # 关键断言：子 agent 必须读到本会话写入的 sandbox
        return sub.get_config("sandbox"), sub.get_config("session_id")

    async def main():
        sbx_123 = object()
        sbx_456 = object()
        results = await asyncio.gather(
            serve_like("123", sbx_123, 0.05),
            serve_like("456", sbx_456, 0.02),
        )
        # results[0] 来自 session 123；results[1] 来自 session 456
        assert results[0] == (sbx_123, "123"), f"session 123 串到了 {results[0]}"
        assert results[1] == (sbx_456, "456"), f"session 456 串到了 {results[1]}"

    asyncio.run(main())


# ---------------------------------------------------------------------------
# 4. 端到端：FastAPI TestClient + publish_agent_api
# ---------------------------------------------------------------------------

# 共享记录字典：每次请求把 (session_id, sub_agent 看到的 sandbox) 写入此处，
# 测试结束后断言每个 session 都看到自己的 sandbox（没串号）。
_RECORDS: Dict[str, str] = {}


class _EchoSandboxAgent(BaseAgent):
    """模拟 svc-alphadata 风格的 agent：在 serve 里 update_config 一个 sandbox
    标识，等一段时间，让派生子 agent 读回来并写入 _RECORDS。"""

    async def serve(self, request: OpenAIRequest):
        # 防御性克隆，模拟 svc-alphadata 真实做法
        self.config = dict(self.config)

        session_id = request.session_id or "unknown"
        sandbox_label = f"sbx-for-{session_id}"
        self.update_config("session_id", session_id)
        self.update_config("sandbox", sandbox_label)

        # 给并发请求"重叠"留窗口，逼出潜在的串号问题
        await asyncio.sleep(0.05)

        sub = self.derive(_EchoSandboxAgent)
        observed = sub.get_config("sandbox")
        _RECORDS[session_id] = observed

        await self.stream.astop(stop_reason="end")


@pytest.mark.timeout(15)
def test_publish_agent_api_concurrent_requests_no_sandbox_leak():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

    _RECORDS.clear()

    agent = _EchoSandboxAgent()
    cfg = APIPublisherConfig(
        path="/v1",
        api_title="test",
        api_description="test",
        memory_ttl=60,
        max_memory_items=10,
    )
    app = publish_agent_api(agent=agent, method="serve", config=cfg)
    client = TestClient(app)

    sessions = ["sess-A", "sess-B", "sess-C", "sess-D"]

    def make_call(session_id: str) -> int:
        body = {
            "model": "test",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "session_id": session_id,
        }
        resp = client.post("/v1/chat/completions", json=body)
        return resp.status_code

    # 用线程池并发触发，复刻"短时间内多请求 + 沙箱长存"场景
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(max_workers=len(sessions)) as pool:
        futures = [pool.submit(make_call, s) for s in sessions]
        statuses = [f.result() for f in futures]

    assert all(code == 200 for code in statuses), statuses

    # 关键断言：每个 session 的派生子 agent 必须读到本会话写入的 sandbox
    for s in sessions:
        assert s in _RECORDS, f"session {s} 没有被记录到，可能未执行完成"
        assert _RECORDS[s] == f"sbx-for-{s}", (
            f"会话 {s} 串到了 sandbox: {_RECORDS[s]}"
        )
