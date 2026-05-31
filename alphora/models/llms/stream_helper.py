# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

from dataclasses import dataclass
from typing import Iterator, AsyncIterator, Generic, TypeVar, Optional, Coroutine, Any, Dict
from abc import ABC, abstractmethod

from alphora.server.stream_responser import DataStreamer


T = TypeVar('T')


@dataclass
class GeneratorOutput:
    """流式输出生成器 数据结构

    Attributes:
        content: 本次 chunk 的文本内容。
        content_type: 内容类型标签，供前端差异化渲染。
        meta: 可选的开放结构化元数据，原样透传到客户端 ``delta.meta``。
            约定（非强制）的保留键：``id``(block 分组键)、``state``(running/done/error)、
            ``agent_id``(子智能体分组)、``name``(工具名) 等；开发者可塞任意 key/value。
    """
    content: str
    content_type: str = 'char'
    meta: Optional[Dict[str, Any]] = None


class BaseGenerator(ABC, Generic[T]):
    def __init__(self, content_type: str = 'text'):
        self.content_type = content_type
        self.instruction: Optional[str] = None
        self.finish_reason: Optional[str] = None

    def get_finish_reason(self) -> str:
        return self.finish_reason

    def generate(self) -> Iterator[T]:
        raise NotImplementedError

    async def agenerate(self) -> AsyncIterator[T]:
        raise NotImplementedError

    def __iter__(self) -> Iterator[T]:
        return self.generate()

    def __aiter__(self) -> Coroutine[Any, Any, AsyncIterator[T]]:
        return self.agenerate()

