import os
import time
import json
from typing import (
    List, Dict, Union, Optional, Iterator, Mapping, Any, AsyncIterator
)
from functools import wraps

from openai import AsyncOpenAI, OpenAI

from alphora.models.message import Message
from alphora.models.llms.base import BaseLLM
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.server.stream_responser import DataStreamer

from alphora.models.llms.balancer import _LLMLoadBalancer

from alphora.utils.logger import get_logger
logger = get_logger("test", level="DEBUG")


class APIInvalidResponse(Exception):
    pass


class APIParameterError(ValueError):
    pass


class OpenAILike(BaseLLM):
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
            callback: Optional[DataStreamer] = None,
    ):
        super().__init__(callback=callback)
        self.model_name = model_name or os.getenv("DEFAULT_LLM")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.header = header

        self.completion_params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "model": model_name,
        }

        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.agent_id: str = "default"

        if not self.api_key:
            raise ValueError("API key is required (via arg or LLM_API_KEY env var).")

        # Clients
        self._sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)

        self._balancer = _LLMLoadBalancer()
        self._balancer.add_client(sync_client=self._sync_client,
                                  async_client=self._async_client,
                                  completion_params=self.completion_params)

    def _prepare_messages(self, message: Union[str, Message], system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        if isinstance(message, str):
            message = Message().add_text(message)
        elif not isinstance(message, Message):
            raise TypeError("message must be str or Message")

        messages = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append(message.to_openai_format(role="user"))
        return messages

    def get_non_stream_response(self, message: Union[str, Message]) -> str:
        """
        用同步的客户端，获取大模型的输出
        :param message:
        :return:
        """
        messages = self._prepare_messages(message)

        start = time.time()

        client, params = self._balancer.get_next_sync_backend()

        completion = client.chat.completions.create(
            **params,
            messages=messages,
            timeout=9999,
            stream=False,
            extra_body=self._get_extra_body(),
        )

        elapsed = round(time.time() - start, 2)

        if not completion.choices:
            raise APIInvalidResponse("No choices returned from LLM.")

        content = completion.choices[0].message.content or ""

        self._response_info = {
            "usage": dict(completion.usage) if completion.usage else {},
            "model_name": self.model_name,
            "time_taken": elapsed,
            "response": content,
        }

        return content.strip()

    def get_streaming_response(
            self,
            message: Union[str, Message],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:

        messages = self._prepare_messages(message, system_prompt)

        sync_client, params = self._balancer.get_next_sync_backend()

        stream = sync_client.chat.completions.create(
            **params,
            messages=messages,
            stream=True,
            extra_body=self._get_extra_body(enable_thinking),
        )

        class SyncStreamGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, stream_iter, content_type: str):
                super().__init__(content_type=content_type)
                self._stream = stream_iter

            def generate(self) -> Iterator[GeneratorOutput]:
                for chunk in self._stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason
                    if finish_reason:
                        self.finish_reason = finish_reason

                    content = getattr(delta, 'content', '') or ''
                    reasoning = getattr(delta, 'reasoning_content', '') or ''

                    if reasoning:
                        yield GeneratorOutput(content=reasoning, content_type='think')
                    elif content:
                        yield GeneratorOutput(content=content, content_type=content_type)

        gen = SyncStreamGenerator(stream, content_type)

        return gen

    async def aget_non_stream_response(self, message: Union[str, Message]) -> str:
        messages = self._prepare_messages(message)
        start = time.time()

        async_client, params = self._balancer.get_next_async_backend()

        completion = await async_client.chat.completions.create(
            **params,
            messages=messages,
            timeout=9999,
            extra_body=self._get_extra_body(),
        )
        elapsed = round(time.time() - start, 2)
        if not completion.choices:
            raise APIInvalidResponse("No choices returned from LLM.")

        content = completion.choices[0].message.content or ""

        self._response_info = {
            "usage": dict(completion.usage) if completion.usage else {},
            "model_name": self.model_name,
            "time_taken": elapsed,
        }
        return content.strip()

    async def aget_streaming_response(
            self,
            message: Union[str, Message],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:

        messages = self._prepare_messages(message, system_prompt)

        async_client, params = self._balancer.get_next_async_backend()

        stream = await async_client.chat.completions.create(
            **params,
            messages=messages,
            stream=True,
            extra_body=self._get_extra_body(enable_thinking),
        )

        class AsyncStreamGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, async_stream, content_type: str):
                super().__init__(content_type=content_type)
                self._stream = async_stream

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                async for chunk in self._stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    if finish_reason:
                        self.finish_reason = finish_reason

                    content = getattr(delta, 'content', '') or ''
                    reasoning = getattr(delta, 'reasoning_content', '') or ''

                    if reasoning:
                        yield GeneratorOutput(content=reasoning, content_type='think')
                    elif content:
                        yield GeneratorOutput(content=content, content_type=content_type)

        gen = AsyncStreamGenerator(stream, content_type)

        return gen

    def _get_extra_body(self, **kwargs) -> dict:
        """由子类重写"""
        return {}

    def set_temperature(self, temp: float):
        if not (0.0 <= temp <= 1.0):
            raise APIParameterError("temperature must be between 0.0 and 1.0")
        self.temperature = temp

    def set_max_tokens(self, tokens: int):
        if tokens <= 0:
            raise APIParameterError("max_tokens must be > 0")
        self.max_tokens = tokens

    def set_top_p(self, p: float):
        if not (0.0 <= p <= 1.0):
            raise APIParameterError("top_p must be between 0.0 and 1.0")
        self.top_p = p

    def set_model_name(self, name: str):
        self.model_name = name

    def ping(self) -> bool:
        try:
            self.invoke("你好")
            return True
        except Exception:
            return False

    async def aping(self) -> bool:
        try:
            await self.ainvoke("你好")
            return True
        except Exception:
            return False

    def __repr__(self):
        return (
            f"LLM(model='{self.model_name}', base_url='{self.base_url}', "
            f"temp={self.temperature}, max_tokens={self.max_tokens})"
        )

    # Serialization support
    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('_sync_client', None)
        state.pop('_async_client', None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)

    def __add__(self, other: "OpenAILike") -> "OpenAILike":
        if not isinstance(other, OpenAILike):
            return NotImplemented

        self._balancer.add_client(async_client=other._async_client,
                                  sync_client=other._sync_client,
                                  completion_params=other.completion_params)

        return self


