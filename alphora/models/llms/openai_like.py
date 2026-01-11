import os
import time
import json
from typing import (
    List, Dict, Union, Optional, Iterator, Mapping, Any, AsyncIterator
)
from openai import AsyncOpenAI, OpenAI
from alphora.models.message import Message
from alphora.models.llms.base import BaseLLM
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.models.llms.balancer import _LLMLoadBalancer

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OpenAILike(BaseLLM):
    def __init__(
            self,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            is_multimodal: bool = False,
    ):

        super().__init__(model_name=model_name,
                         api_key=api_key,
                         base_url=base_url,
                         header=header,
                         temperature=temperature,
                         max_tokens=max_tokens,
                         top_p=top_p,
                         is_multimodal=is_multimodal)

        self.model_name = model_name or os.getenv("DEFAULT_LLM")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.header = header

        self.completion_params = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "model": self.model_name,
        }

        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.agent_id: str = "default"

        if not self.api_key:
            self.api_key = "empty"

        # Clients
        self._sync_client = OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.header)

        self._balancer = _LLMLoadBalancer()
        self._balancer.add_client(sync_client=self._sync_client,
                                  async_client=self._async_client,
                                  completion_params=self.completion_params,
                                  is_multimodal=self.is_multimodal)

    def _prepare_messages(self,
                          message: Union[str, Message, List[Dict[str, Any]]],  # ← 新增 List[Dict[str, Any]]
                          system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        快速将字符串输出组装成传入oai模型的消息体
        
        支持三种输入：
        - str: 纯文本，自动包装为 Message
        - Message: 多模态消息对象
        - List[Dict]: 已组装好的 messages 列表（新增，用于带记忆的规范调用）
        
        :param message:
        :param system_prompt:
        :return:
        """
        # ========== 新增：支持直接传入 messages 列表 ==========
        if isinstance(message, list):
            return message
        # ========== 新增结束 ==========

        if isinstance(message, str):
            message = Message().add_text(message)
        elif not isinstance(message, Message):
            raise TypeError("message must be str or Message or List[Dict]")

        messages = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append(message.to_openai_format(role="user"))
        return messages

    def get_non_stream_response(self,
                                message: Union[str, Message, List[Dict[str, Any]]],  # ← 新增类型
                                enable_thinking: bool = False,
                                system_prompt: Optional[str] = None,) -> str:
        """
        同步-非流式
        :param message:
        :param enable_thinking:
        :param system_prompt:
        :return:
        """
        multi_model_msg = False

        if isinstance(message, Message):
            if message.has_images() or message.has_audios() or message.has_videos():
                multi_model_msg = True

        messages = self._prepare_messages(message=message, system_prompt=system_prompt)

        start = time.time()

        try:
            client, params = self._balancer.get_next_sync_backend(need_multimodal=multi_model_msg)
        except Exception as e:
            raise RuntimeError(f"llm error: {e}")

        completion = client.chat.completions.create(
            **params,
            messages=messages,
            timeout=9999,
            stream=False,
            extra_body=self._get_extra_body(enable_thinking=enable_thinking),
        )

        elapsed = round(time.time() - start, 2)

        if not completion.choices:
            raise RuntimeError("No choices returned from LLM.")

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
            message: Union[str, Message, List[Dict[str, Any]]],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:

        """
        同步-流式输出
        :param message:
        :param content_type:
        :param enable_thinking:
        :param system_prompt:
        :return:
        """
        multi_model_msg = False

        if isinstance(message, Message):
            if message.has_images() or message.has_audios() or message.has_videos():
                multi_model_msg = True

        messages = self._prepare_messages(message=message, system_prompt=system_prompt)

        try:
            sync_client, params = self._balancer.get_next_sync_backend(need_multimodal=multi_model_msg)
        except Exception as e:
            raise RuntimeError(f"llm error: {e}")

        stream = sync_client.chat.completions.create(
            **params,
            messages=messages,
            stream=True,
            extra_body=self._get_extra_body(enable_thinking=enable_thinking),
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

    async def aget_non_stream_response(self,
                                       message: Union[str, Message, List[Dict[str, Any]]],  # ← 新增类型
                                       enable_thinking: bool = False,
                                       system_prompt: Optional[str] = None,) -> str:
        """
        异步-非流式输出
        :param message:
        :param enable_thinking:
        :param system_prompt:
        :return:
        """
        multi_model_msg = False

        if isinstance(message, Message):
            if message.has_images() or message.has_audios() or message.has_videos():
                multi_model_msg = True

        messages = self._prepare_messages(message=message, system_prompt=system_prompt)
        start = time.time()

        try:
            async_client, params = self._balancer.get_next_async_backend(need_multimodal=multi_model_msg)
        except Exception as e:
            raise RuntimeError(f"llm error: {e}")

        completion = await async_client.chat.completions.create(
            **params,
            messages=messages,
            timeout=9999,
            extra_body=self._get_extra_body(),
        )
        elapsed = round(time.time() - start, 2)
        if not completion.choices:
            raise RuntimeError("No choices returned from LLM.")

        content = completion.choices[0].message.content or ""

        self._response_info = {
            "usage": dict(completion.usage) if completion.usage else {},
            "model_name": self.model_name,
            "time_taken": elapsed,
        }
        return content.strip()

    async def aget_streaming_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],  # ← 新增类型
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
    ) -> BaseGenerator:

        """
        异步 - 流式输出 (核心方法)
        :param message:
        :param content_type: 流式输出的content-type
        :param enable_thinking:
        :param system_prompt:
        :return:
        """

        multi_model_msg = False

        if isinstance(message, Message):
            if message.has_images() or message.has_audios() or message.has_videos():
                multi_model_msg = True

        messages = self._prepare_messages(message=message, system_prompt=system_prompt)

        try:
            async_client, params = self._balancer.get_next_async_backend(need_multimodal=multi_model_msg)
        except Exception as e:
            raise RuntimeError(f"llm error: {e}")

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

    def _get_extra_body(self, *args, **kwargs) -> dict:
        """由子类重写"""
        return {}

    def set_temperature(self, temp: float):
        if not (0.0 <= temp <= 1.0):
            raise RuntimeError("temperature must be between 0.0 and 1.0")
        self.temperature = temp

    def set_max_tokens(self, tokens: int):
        if tokens <= 0:
            raise RuntimeError("max_tokens must be > 0")
        self.max_tokens = tokens

    def set_top_p(self, p: float):
        if not (0.0 <= p <= 1.0):
            raise RuntimeError("top_p must be between 0.0 and 1.0")
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