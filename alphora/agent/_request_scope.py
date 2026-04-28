# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""请求作用域支持。

提供 ContextVar 驱动的"请求级覆盖字典 + 描述符"机制，让单例 ``BaseAgent``
在并发请求下也能保证 ``config / memory / callback / stream / llm`` 这些
随请求变化的属性互不污染。

设计要点：

- ``_OVERRIDES`` 是一个 ContextVar，每个 asyncio Task 由 ``copy_context()``
  自动得到独立副本，因此一个任务里 ``set(...)`` 不会影响其它任务。
- ``RequestScoped`` 是类级描述符。读/写时若处于激活的请求作用域，会路由到
  per-task 覆盖字典；否则回落到 ``instance.__dict__`` 的私有键
  （``_singleton_<name>``）—— 即"单例默认值"语义。
- 覆盖字典以 ``(id(instance), name)`` 为键，使得一次请求里同时存在的
  父智能体和派生子智能体彼此互不干扰。
"""

from __future__ import annotations

import contextvars
from typing import Any, Optional

__all__ = [
    "RequestScoped",
    "enter_request_scope",
    "current_overrides",
]

_OVERRIDES: "contextvars.ContextVar[Optional[dict]]" = contextvars.ContextVar(
    "alphora_request_overrides", default=None
)

_SENTINEL = object()


def enter_request_scope() -> dict:
    """在当前 asyncio Task 的上下文里激活一个全新的请求级覆盖字典。

    必须在每个请求处理任务的开始处调用一次（见
    ``alphora.server.quick_api.api_endpoints``）。返回的字典可以用于
    调试/观测，但调用方通常无需直接持有它 —— 描述符会自动读写。
    """
    overrides: dict = {}
    _OVERRIDES.set(overrides)
    return overrides


def current_overrides() -> Optional[dict]:
    """返回当前任务上下文里的覆盖字典；未激活作用域时返回 ``None``。"""
    return _OVERRIDES.get()


class RequestScoped:
    """类级描述符：把属性的读写在请求作用域内路由到 per-task 字典。

    用法（在 ``BaseAgent`` 类体里）::

        class BaseAgent:
            config = RequestScoped("config")
            memory = RequestScoped("memory")
            ...

    语义：

    - 读：先看当前任务有没有覆盖；命中则返回覆盖值，否则回落到
      ``instance.__dict__["_singleton_<name>"]``（"单例默认值"）。
    - 写：当前任务激活了作用域则只写到覆盖字典；否则写到实例 ``__dict__``
      的私有键（构造时为单例设默认值就走这一支）。

    这样得到三件好事：

    1. 框架原有的 ``self.config = ...`` / ``self.config[key] = value`` 写法
       完全不需要修改。
    2. 同一个单例 ``agent`` 实例在并发请求下，每个任务看到的 ``agent.config``
       是各自独立的字典 —— 真正实现"per-request isolation"。
    3. 没有激活作用域的场景（脚本、单元测试、CLI、模块加载阶段的构造）
       行为与传统实例属性完全一致，向后兼容。
    """

    __slots__ = ("public", "private")

    def __init__(self, name: str) -> None:
        self.public = name
        self.private = f"_singleton_{name}"

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        overrides = _OVERRIDES.get()
        if overrides is not None:
            value = overrides.get((id(instance), self.public), _SENTINEL)
            if value is not _SENTINEL:
                return value
        return instance.__dict__.get(self.private)

    def __set__(self, instance: Any, value: Any) -> None:
        overrides = _OVERRIDES.get()
        if overrides is not None:
            overrides[(id(instance), self.public)] = value
        else:
            instance.__dict__[self.private] = value

    def __delete__(self, instance: Any) -> None:
        overrides = _OVERRIDES.get()
        key = (id(instance), self.public)
        if overrides is not None and key in overrides:
            del overrides[key]
            return
        instance.__dict__.pop(self.private, None)
