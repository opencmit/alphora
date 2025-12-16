from abc import ABC, abstractmethod
from typing import Union, Optional, List, Dict, Any
from alphora.models.message import Message
from alphora.models.llms.stream_helper import BaseGenerator
from alphora.server.stream_responser import DataStreamer


class BaseLLM(ABC):
    def __init__(
            self,
            callback: Optional[DataStreamer] = None,
    ):

        self.callback: Optional[DataStreamer] = callback

    @abstractmethod
    def get_non_stream_response(self, message: Union[str, Message]) -> str:
        """Synchronous non-streaming response."""
        raise NotImplementedError

    @abstractmethod
    async def aget_non_stream_response(self, message: Union[str, Message]) -> str:
        """Asynchronous non-streaming response."""
        raise NotImplementedError

    @abstractmethod
    def get_streaming_response(
            self,
            message: Union[str, Message],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:
        """Synchronous streaming response."""
        raise NotImplementedError

    @abstractmethod
    async def aget_streaming_response(
            self,
            message: Union[str, Message],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:
        """Asynchronous streaming response (placeholder; actual impl may use async generator)."""
        raise NotImplementedError

    def invoke(self, message: Union[str, Message]) -> str:
        return self.get_non_stream_response(message)

    async def ainvoke(self, message: Union[str, Message]) -> str:
        return await self.aget_non_stream_response(message)

    def stream(self, *args, **kwargs) -> BaseGenerator:
        return self.get_streaming_response(*args, **kwargs)

    async def astream(self, *args, **kwargs) -> BaseGenerator:
        return await self.aget_streaming_response(*args, **kwargs)

    def __add__(self, other):
        from alphora.models.llms.balancer import LLMBalancer
        if isinstance(other, BaseLLM):
            return LLMBalancer([self, other])
        elif isinstance(other, LLMBalancer):
            other.add_llm(self)
            return other
        else:
            raise TypeError(f"Unsupported operand type(s) for +: '{type(self)}' and '{type(other)}'")

    def __radd__(self, other):
        return self.__add__(other)