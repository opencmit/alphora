# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

from dataclasses import dataclass
from typing import Iterator, AsyncIterator, Generic, TypeVar, Optional, Coroutine, Any
from abc import ABC, abstractmethod

from alphora.server.stream_responser import DataStreamer


T = TypeVar('T')


@dataclass
class GeneratorOutput:
    """流式输出生成器 数据结构"""
    content: str
    content_type: str = 'char'


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

