# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

from abc import ABC, abstractmethod
from typing import Union, Optional, List, Dict, Any, Mapping
from alphora.models.message import Message
from alphora.models.llms.stream_helper import BaseGenerator
from alphora.server.stream_responser import DataStreamer
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager


class BaseLLM(ABC):

    _SHORT_MAP: Dict[str, HookEvent] = {
        "before_call": HookEvent.LLM_BEFORE_CALL,
        "after_call": HookEvent.LLM_AFTER_CALL,
    }

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
            is_multimodal: bool = False,
            hooks=None,
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

        self._hooks = build_manager(
            hooks,
            short_map=self._SHORT_MAP,
        )

    @property
    def hooks(self) -> HookManager:
        return self._hooks

    def _resolve_event(self, event):
        return self._SHORT_MAP.get(event, event) if isinstance(event, str) else event

    def add_hook(self, event, func, *, priority=0, when=None, timeout=None, error_policy=None):
        self._hooks.register(
            self._resolve_event(event), func,
            priority=priority, when=when,
            timeout=timeout, error_policy=error_policy,
        )
        return self

    def remove_hook(self, event, func):
        self._hooks.unregister(self._resolve_event(event), func)
        return self

    @abstractmethod
    def get_non_stream_response(self,
                                message: Union[str, Message, List[Dict[str, Any]]],
                                enable_thinking: bool = False,
                                system_prompt: Optional[str] = None,
                                prompt_id: Optional[str] = None,
                                tools: Optional[List] = None) -> str | List:
        """Synchronous non-streaming response."""
        raise NotImplementedError

    @abstractmethod
    async def aget_non_stream_response(self,
                                       message: Union[str, Message, List[Dict[str, Any]]],
                                       enable_thinking: bool = False,
                                       system_prompt: Optional[str] = None,
                                       prompt_id: Optional[str] = None,
                                       tools: Optional[List] = None) -> str | List:
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
