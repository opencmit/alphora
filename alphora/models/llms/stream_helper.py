from dataclasses import dataclass
from typing import Iterator, Generic, TypeVar
from abc import ABC, abstractmethod


T = TypeVar('T')


@dataclass
class GeneratorOutput:
    """流式输出生成器 数据结构"""
    content: str
    content_type: str = 'text'


class BaseGenerator(ABC, Generic[T]):
    def __init__(self, content_type: str = 'text'):
        self.content_type = content_type
        self.instruction: str | None = None

        self.finish_reason: str | None = None

    @abstractmethod
    def generate(self) -> Iterator[T]:
        raise NotImplementedError

    def __iter__(self) -> Iterator[T]:
        return self.generate()

