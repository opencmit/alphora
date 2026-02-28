"""
LLM 用量统计器。

通过 Hook 机制自动采集每次 LLM 调用的 token 用量与耗时，
支持按模型、按会话分组统计和性能指标。

基本用法::

    from alphora.hooks.builtins import UsageTracker
    from alphora.models import OpenAILike

    tracker = UsageTracker()
    llm = OpenAILike(model_name="gpt-4", hooks={"after_call": tracker})

    await llm.ainvoke("你好")

    print(tracker.total_tokens)   # 50
    print(tracker.summary())
    # {'calls': 1, 'prompt_tokens': 30, 'completion_tokens': 20, ...}

按会话分组（异步安全）::

    tracker.set_session("user_123")
    await agent.run("分析数据")
    print(tracker.by_session())
"""

import time
import threading
import contextvars
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from alphora.hooks.context import HookContext


_current_session: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "usage_tracker_session", default=None
)


@dataclass
class UsageRecord:
    """单次 LLM 调用的用量记录。"""
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    elapsed: float
    tokens_per_second: float
    session_id: Optional[str]
    timestamp: float


class UsageTracker:
    """
    LLM 用量统计器。

    实现 ``__call__`` 协议，可直接作为 hook 函数传入::

        llm = OpenAILike(hooks={"after_call": tracker})
    """

    def __init__(self) -> None:
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Hook 入口
    # ------------------------------------------------------------------ #

    def __call__(self, ctx: HookContext) -> None:
        data = ctx.data
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        elapsed = data.get("elapsed", 0.0)
        tps = total_tokens / elapsed if elapsed > 0 else 0.0

        record = UsageRecord(
            model_name=data.get("model_name", ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            elapsed=elapsed,
            tokens_per_second=round(tps, 2),
            session_id=_current_session.get(),
            timestamp=time.time(),
        )
        with self._lock:
            self._records.append(record)

    # ------------------------------------------------------------------ #
    # 会话上下文
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_session(session_id: Optional[str]) -> None:
        """设置当前异步任务/线程的会话标识（基于 contextvars，并发安全）。"""
        _current_session.set(session_id)

    # ------------------------------------------------------------------ #
    # 累计属性
    # ------------------------------------------------------------------ #

    @property
    def records(self) -> List[UsageRecord]:
        with self._lock:
            return list(self._records)

    @property
    def calls(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(r.total_tokens for r in self._records)

    @property
    def prompt_tokens(self) -> int:
        with self._lock:
            return sum(r.prompt_tokens for r in self._records)

    @property
    def completion_tokens(self) -> int:
        with self._lock:
            return sum(r.completion_tokens for r in self._records)

    @property
    def total_elapsed(self) -> float:
        with self._lock:
            return round(sum(r.elapsed for r in self._records), 2)

    @property
    def avg_response_time(self) -> float:
        with self._lock:
            if not self._records:
                return 0.0
            return round(sum(r.elapsed for r in self._records) / len(self._records), 2)

    @property
    def avg_tokens_per_second(self) -> float:
        with self._lock:
            total_elapsed = sum(r.elapsed for r in self._records)
            total_tokens = sum(r.total_tokens for r in self._records)
            if total_elapsed <= 0:
                return 0.0
            return round(total_tokens / total_elapsed, 2)

    # ------------------------------------------------------------------ #
    # 查询方法
    # ------------------------------------------------------------------ #

    def summary(self) -> Dict[str, Any]:
        """返回汇总统计（用量 + 性能）。"""
        with self._lock:
            records = list(self._records)
        return self._aggregate(records)

    def by_model(self) -> Dict[str, Dict[str, Any]]:
        """按 model_name 分组统计。"""
        with self._lock:
            records = list(self._records)
        groups: Dict[str, List[UsageRecord]] = {}
        for r in records:
            groups.setdefault(r.model_name, []).append(r)
        return {model: self._aggregate(recs) for model, recs in groups.items()}

    def by_session(self) -> Dict[str, Dict[str, Any]]:
        """按 session_id 分组统计。"""
        with self._lock:
            records = list(self._records)
        groups: Dict[str, List[UsageRecord]] = {}
        for r in records:
            key = r.session_id or "__no_session__"
            groups.setdefault(key, []).append(r)
        return {sid: self._aggregate(recs) for sid, recs in groups.items()}

    def detail(self) -> List[Dict[str, Any]]:
        """
        返回每个模型的完整明细清单，适合后处理、展示或导出。

        返回示例::

            [
                {
                    "model_name": "gpt-4",
                    "calls": 5,
                    "prompt_tokens": 2000,
                    "completion_tokens": 800,
                    "total_tokens": 2800,
                    "total_elapsed": 6.5,
                    "avg_response_time": 1.3,
                    "avg_tokens_per_second": 430.77,
                    "avg_prompt_tokens_per_call": 400,
                    "avg_completion_tokens_per_call": 160,
                    "first_call": "2026-02-28 17:00:12",
                    "last_call": "2026-02-28 17:05:30",
                    "records": [<UsageRecord>, ...],
                },
                ...
            ]
        """
        from datetime import datetime

        with self._lock:
            records = list(self._records)

        groups: Dict[str, List[UsageRecord]] = {}
        for r in records:
            groups.setdefault(r.model_name, []).append(r)

        result = []
        for model_name, recs in sorted(groups.items()):
            n = len(recs)
            prompt_sum = sum(r.prompt_tokens for r in recs)
            completion_sum = sum(r.completion_tokens for r in recs)
            total_sum = sum(r.total_tokens for r in recs)
            elapsed_sum = sum(r.elapsed for r in recs)

            result.append({
                "model_name": model_name,
                "calls": n,
                "prompt_tokens": prompt_sum,
                "completion_tokens": completion_sum,
                "total_tokens": total_sum,
                "total_elapsed": round(elapsed_sum, 2),
                "avg_response_time": round(elapsed_sum / n, 2),
                "avg_tokens_per_second": round(total_sum / elapsed_sum, 2) if elapsed_sum > 0 else 0.0,
                "avg_prompt_tokens_per_call": round(prompt_sum / n),
                "avg_completion_tokens_per_call": round(completion_sum / n),
                "first_call": datetime.fromtimestamp(recs[0].timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "last_call": datetime.fromtimestamp(recs[-1].timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "records": recs,
            })

        return result

    def to_dict(self) -> Dict[str, Any]:
        """完整快照，方便序列化。"""
        return {
            **self.summary(),
            "by_model": self.by_model(),
            "by_session": self.by_session(),
        }

    def reset(self) -> None:
        """清空所有记录。"""
        with self._lock:
            self._records.clear()

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #

    @staticmethod
    def _aggregate(records: List[UsageRecord]) -> Dict[str, Any]:
        if not records:
            return {
                "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0, "total_elapsed": 0.0,
                "avg_response_time": 0.0, "avg_tokens_per_second": 0.0,
            }
        total_elapsed = sum(r.elapsed for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        return {
            "calls": len(records),
            "prompt_tokens": sum(r.prompt_tokens for r in records),
            "completion_tokens": sum(r.completion_tokens for r in records),
            "total_tokens": total_tokens,
            "total_elapsed": round(total_elapsed, 2),
            "avg_response_time": round(total_elapsed / len(records), 2),
            "avg_tokens_per_second": round(total_tokens / total_elapsed, 2) if total_elapsed > 0 else 0.0,
        }

    def __repr__(self) -> str:
        return f"UsageTracker(calls={self.calls}, total_tokens={self.total_tokens})"
