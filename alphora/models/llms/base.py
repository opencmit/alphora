from abc import ABC, abstractmethod
from typing import Union, Optional, List, Dict, Any, Mapping
from alphora.models.message import Message
from alphora.models.llms.stream_helper import BaseGenerator
from alphora.server.stream_responser import DataStreamer


class BaseLLM(ABC):
    def __init__(
            self,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            system_prompt: Optional[str] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            is_multimodal: bool = False
    ):

        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.header = header
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.is_multimodal = is_multimodal

        self.post_processors = {}

    @abstractmethod
    def get_non_stream_response(self,
                                message: Union[str, Message, List[Dict[str, Any]]],
                                enable_thinking: bool = False,
                                system_prompt: Optional[str] = None,
                                prompt_id: Optional[str] = None) -> str:
        """Synchronous non-streaming response."""
        raise NotImplementedError

    @abstractmethod
    async def aget_non_stream_response(self,
                                       message: Union[str, Message, List[Dict[str, Any]]],
                                       enable_thinking: bool = False,
                                       system_prompt: Optional[str] = None,
                                       prompt_id: Optional[str] = None) -> str:
        """Asynchronous non-streaming response."""
        raise NotImplementedError

    @abstractmethod
    def get_streaming_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None
    ) -> BaseGenerator:
        """Synchronous streaming response."""
        raise NotImplementedError

    @abstractmethod
    async def aget_streaming_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None
    ) -> BaseGenerator:
        """Asynchronous streaming response (placeholder; actual impl may use async generator)."""
        raise NotImplementedError

    def invoke(self, message: Union[str, Message, List[Dict[str, Any]]]) -> str:
        return self.get_non_stream_response(message)

    async def ainvoke(self, message: Union[str, Message, List[Dict[str, Any]]]) -> str:
        return await self.aget_non_stream_response(message)

    def stream(self, *args, **kwargs) -> BaseGenerator:
        return self.get_streaming_response(*args, **kwargs)

    async def astream(self, *args, **kwargs) -> BaseGenerator:
        return await self.aget_streaming_response(*args, **kwargs)
