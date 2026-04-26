# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


"""
OpenAI-Like LLM 客户端

本模块提供一个对 OpenAI 兼容 SDK（`openai` Python 包）做统一封装的基类
:class:`OpenAILike`，所有 "OpenAI API 兼容" 的厂商（OpenAI / DeepSeek /
Qwen / 火山方舟 / 其他自建兼容服务）均可通过继承并覆盖若干扩展钩子来接入。

## 扩展钩子（子类可按需重写）

**客户端构造**

- :meth:`OpenAILike._make_sync_client`
- :meth:`OpenAILike._make_async_client`

**消息 / 请求参数构建**

- :meth:`OpenAILike._transform_messages`
- :meth:`OpenAILike._build_completion_kwargs` —— 全量覆盖
- :meth:`OpenAILike._apply_thinking` —— 窄口钩子，可同时改 top-level 与 ``extra_body``
- :meth:`OpenAILike._get_extra_body` —— 窄口钩子，仅改 ``extra_body``

**响应解析**

- :meth:`OpenAILike._parse_non_stream_completion`
- :meth:`OpenAILike._parse_stream_delta`
- :meth:`OpenAILike._parse_stream_usage`

**能力声明 / 参数校验**

- :attr:`OpenAILike.CAPABILITIES`
- :meth:`OpenAILike._validate_temperature`
- :meth:`OpenAILike._validate_top_p`

以上钩子均带有默认实现，未覆盖任何钩子的子类依然可以正常工作。
"""

import os
import time
import json
import logging
from typing import (
    List, Dict, Union, Optional, Iterator, Mapping, Any, AsyncIterator, Tuple,
)

from openai import AsyncOpenAI, OpenAI

from alphora.models.message import Message
from alphora.models.llms.base import BaseLLM
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.models.llms.balancer import _LLMLoadBalancer
from alphora.models.llms.types import ToolCall
from alphora.hooks import HookEvent, HookContext

logger = logging.getLogger(__name__)


# 内部辅助类
class _LLMCallContext:
    """封装一次 LLM 调用的计时与 ``LLM_AFTER_CALL`` hook 触发。

    仅管理本地可观测性，所有关于调用本身（client / messages / kwargs）的
    状态仍放在主方法里，以保持数据流清晰。
    """

    __slots__ = ("model_name", "start_time")

    def __init__(self, model_name: Optional[str]):
        self.model_name = model_name
        self.start_time = time.time()

    def _build_ctx(self, usage: Optional[Dict[str, int]]) -> HookContext:
        return HookContext(
            event=HookEvent.LLM_AFTER_CALL,
            component="llm",
            data={
                "model_name": self.model_name,
                "usage": usage or {},
                "elapsed": round(time.time() - self.start_time, 2),
            },
        )

    def end_sync(self, hooks, usage: Optional[Dict[str, int]] = None) -> None:
        if hooks is None:
            return
        hooks.emit_sync(HookEvent.LLM_AFTER_CALL, self._build_ctx(usage))

    async def end_async(self, hooks, usage: Optional[Dict[str, int]] = None) -> None:
        if hooks is None:
            return
        await hooks.emit(HookEvent.LLM_AFTER_CALL, self._build_ctx(usage))


class _StreamToolCallBuffer:
    """流式 ``delta.tool_calls`` 的累积器。

    OpenAI 兼容的流式协议里，tool_calls 会按 ``index`` 切片分多个 chunk
    推送。本类负责合并分片、去重公告，并在 ``stream_tool_calls=True`` 时
    返回需要对外 yield 的事件。
    """

    def __init__(self) -> None:
        self._tool_calls: Dict[int, Dict[str, Any]] = {}
        self._announced: set = set()

    def consume(self, tool_calls_delta) -> List[Tuple[str, Any]]:
        """消费一次 delta 中的 ``tool_calls`` 列表。

        Returns:
            事件列表，每个元素是 ``(kind, payload)``：
            - ``("announce", {index, id, name})``：工具调用首次出现时的公告
            - ``("args", str)``:参数增量
        """
        events: List[Tuple[str, Any]] = []
        for tc in tool_calls_delta:
            idx = tc.index
            if idx not in self._tool_calls:
                self._tool_calls[idx] = {
                    "index": idx,
                    "id": tc.id or "",
                    "type": "function",
                    "function": {
                        "name": (tc.function.name if tc.function else "") or "",
                        "arguments": "",
                    },
                }
            else:
                if tc.id:
                    self._tool_calls[idx]["id"] += tc.id
                if tc.function and tc.function.name:
                    self._tool_calls[idx]["function"]["name"] += tc.function.name

            args_delta = tc.function.arguments if tc.function else None
            if args_delta:
                self._tool_calls[idx]["function"]["arguments"] += args_delta

            current_name = self._tool_calls[idx]["function"]["name"]
            if idx not in self._announced and current_name:
                self._announced.add(idx)
                events.append((
                    "announce",
                    {
                        "index": idx,
                        "id": self._tool_calls[idx]["id"],
                        "name": current_name,
                    },
                ))

            if args_delta:
                events.append(("args", args_delta))

        return events

    def collected(self) -> List[Dict[str, Any]]:
        return [v for _, v in sorted(self._tool_calls.items())]


class _BaseStreamGenerator(BaseGenerator[GeneratorOutput]):
    """同步 / 异步流生成器的公共基础。

    持有 ``llm`` 引用，以便在迭代过程中调用 :meth:`OpenAILike._parse_stream_delta`
    等扩展钩子，允许子类通过覆盖钩子来定制流式解析。
    """

    def __init__(
        self,
        llm: "OpenAILike",
        stream_iter: Any,
        content_type: str,
        stream_tool_calls: bool,
    ) -> None:
        super().__init__(content_type=content_type)
        self._llm = llm
        self._stream = stream_iter
        self._stream_tool_calls = stream_tool_calls

        self._full_content = ""
        self._full_reasoning = ""
        self.token_usage: Optional[Dict[str, int]] = None

        self._ctx = _LLMCallContext(model_name=llm.model_name)
        self._buffer = _StreamToolCallBuffer()

    @property
    def collected_tool_calls(self) -> List[Dict[str, Any]]:
        return self._buffer.collected()

    def _handle_chunk(self, chunk) -> List[GeneratorOutput]:
        """解析单个 chunk，返回若干需要 yield 的输出。

        汇总到一个列表里返回是为了同 / 异步两条路径共用这段逻辑。
        """
        outputs: List[GeneratorOutput] = []

        usage = self._llm._parse_stream_usage(chunk)
        if usage is not None:
            self.token_usage = usage

        if not chunk.choices:
            return outputs

        delta = chunk.choices[0].delta
        finish_reason = chunk.choices[0].finish_reason
        if finish_reason:
            self.finish_reason = finish_reason

        parsed = self._llm._parse_stream_delta(delta)

        tool_calls_delta = parsed.get("tool_calls_delta") or []
        if tool_calls_delta:
            events = self._buffer.consume(tool_calls_delta)
            if self._stream_tool_calls:
                for kind, payload in events:
                    if kind == "announce":
                        outputs.append(GeneratorOutput(
                            content=json.dumps(payload, ensure_ascii=False),
                            content_type="tool_call",
                        ))
                    else:
                        outputs.append(GeneratorOutput(
                            content=payload,
                            content_type="tool_call_args",
                        ))
            return outputs

        reasoning = parsed.get("reasoning") or ""
        content = parsed.get("content") or ""

        if reasoning:
            self._full_reasoning += reasoning
            outputs.append(GeneratorOutput(content=reasoning, content_type="think"))
        elif content:
            self._full_content += content
            outputs.append(GeneratorOutput(content=content, content_type=self.content_type))

        return outputs


class _SyncStreamGenerator(_BaseStreamGenerator):
    def generate(self) -> Iterator[GeneratorOutput]:
        for chunk in self._stream:
            for out in self._handle_chunk(chunk):
                yield out
        self._ctx.end_sync(self._llm._hooks, usage=self.token_usage)


class _AsyncStreamGenerator(_BaseStreamGenerator):
    async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
        async for chunk in self._stream:
            for out in self._handle_chunk(chunk):
                yield out
        await self._ctx.end_async(self._llm._hooks, usage=self.token_usage)


class OpenAILike(BaseLLM):
    """OpenAI-兼容厂商的通用封装基类。
    继承并覆盖扩展钩子即可快速适配新厂商；参见模块文档。
    """
    #: 子类可声明自身支持的能力，框架层在必要时可据此做前置校验。
    #: 常见值：``"reasoning"``, ``"json_mode"``, ``"tools"``, ``"vision"``,
    #: ``"audio"``, ``"video"``。
    CAPABILITIES: set = set()

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
            hooks=None,
    ):
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            header=header,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            is_multimodal=is_multimodal,
            hooks=hooks,
        )

        self.model_name = model_name or os.getenv("DEFAULT_LLM")
        self.api_key = api_key or os.getenv("LLM_API_KEY") or "empty"
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.header = header

        self.completion_params: Dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "model": self.model_name,
        }

        # Agent ID 由上层 Agent 设置，保留为 attribute 兼容历史代码
        self.agent_id: str = "default"

        self._sync_client = self._make_sync_client(
            api_key=self.api_key, base_url=self.base_url, header=self.header,
        )
        self._async_client = self._make_async_client(
            api_key=self.api_key, base_url=self.base_url, header=self.header,
        )

        self._balancer = _LLMLoadBalancer()
        self._balancer.add_client(
            sync_client=self._sync_client,
            async_client=self._async_client,
            completion_params=self.completion_params,
            is_multimodal=self.is_multimodal,
        )

    # 客户端构造钩子
    def _make_sync_client(
            self,
            *,
            api_key: str,
            base_url: Optional[str],
            header: Optional[Mapping[str, str]],
    ) -> OpenAI:
        """构造同步 ``OpenAI`` 客户端。

        子类如需走自定义 endpoint（例如 DeepSeek 的 ``/beta``）或注入自定义
        transport，可覆盖此钩子。
        """
        return OpenAI(api_key=api_key, base_url=base_url, default_headers=header)

    def _make_async_client(
            self,
            *,
            api_key: str,
            base_url: Optional[str],
            header: Optional[Mapping[str, str]],
    ) -> AsyncOpenAI:
        """构造异步 ``AsyncOpenAI`` 客户端，详见 :meth:`_make_sync_client`。"""
        return AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=header)

    # 消息预处理 / 改写
    def _prepare_messages(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """将入参快速组装为 OpenAI 兼容的 ``messages`` 列表。

        支持三种输入：

        - ``str``：纯文本，自动包装为 :class:`~alphora.models.message.Message`
        - :class:`~alphora.models.message.Message`：多模态消息对象
        - ``List[Dict]``：已组装好的 messages 列表（用于带记忆的多轮对话）
        """
        if isinstance(message, list):
            return message

        if isinstance(message, str):
            message = Message().add_text(message)
        elif not isinstance(message, Message):
            raise TypeError("message must be str or Message or List[Dict]")

        messages: List[Dict[str, Any]] = []
        sys_prompt = system_prompt or self.system_prompt
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        messages.append(message.to_openai_format(role="user"))
        return messages

    def _transform_messages(
            self, messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """在发送前对 ``messages`` 做最后一次改写（默认原样返回）。

        子类可用此钩子实现 prefix completion、role 归一化等厂商特定逻辑。
        """
        return messages

    def _needs_multimodal(
            self, message: Union[str, Message, List[Dict[str, Any]]],
    ) -> bool:
        if isinstance(message, Message):
            return message.has_images() or message.has_audios() or message.has_videos()
        return False

    # 请求参数构建钩子
    def _get_extra_body(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """返回要透传给 ``extra_body`` 的字典，默认返回 ``None`` 表示不附加。

        仅用于纯 ``extra_body`` 字段的注入；若还需同步改 top-level kwarg
        （例如 DeepSeek V4 的 ``reasoning_effort`` + ``extra_body.thinking``
        组合），请改用 :meth:`_apply_thinking` 或直接覆盖
        :meth:`_build_completion_kwargs`。
        """
        return None

    def _apply_thinking(
            self,
            kwargs: Dict[str, Any],
            *,
            enable_thinking: bool,
    ) -> None:
        """根据 ``enable_thinking`` 原地修改 ``kwargs``（窄口钩子）。

        允许一个方法里同时处理 top-level 参数与 ``extra_body``，适合
        "thinking 模式需要同时传 ``reasoning_effort`` 和 ``extra_body.thinking``"
        这类组合场景。默认为 no-op，子类按需实现。

        Example:
            class DeepSeekV4Pro(DeepSeek):
                def _apply_thinking(self, kwargs, *, enable_thinking):
                    if not enable_thinking:
                        return
                    kwargs["reasoning_effort"] = "high"
                    eb = dict(kwargs.get("extra_body") or {})
                    eb["thinking"] = {"type": "enabled"}
                    kwargs["extra_body"] = eb
        """
        return None

    def _build_completion_kwargs(
            self,
            *,
            params: Dict[str, Any],
            messages: List[Dict[str, Any]],
            tools: Optional[List] = None,
            stream: bool = False,
            enable_thinking: bool = False,
            response_format: Optional[Dict[str, Any]] = None,
            include_usage: bool = True,
            **extra: Any,
    ) -> Dict[str, Any]:
        """构造 ``client.chat.completions.create(**kwargs)`` 的关键字参数。

        扩展的三种方式（按侵入性从低到高）：

        1. **调用方 per-call 注入**：通过 ``**extra`` 传入的键会直接追加到
           最终 kwargs；若传入 ``extra_body``，会与 :meth:`_get_extra_body`
           返回的字典合并，调用方优先。
        2. **子类窄口钩子**：覆盖 :meth:`_get_extra_body` 或 :meth:`_apply_thinking`。
           前者只能改 ``extra_body``；后者可以同时改 top-level 与 ``extra_body``。
        3. **子类全量覆盖**：直接重写本方法，通过 ``super()._build_completion_kwargs(...)``
           拿到基础 kwargs 后自由修改。
        """
        kwargs: Dict[str, Any] = {**params, "messages": messages, "stream": stream}

        base_eb = self._get_extra_body(enable_thinking=enable_thinking)
        caller_eb = extra.pop("extra_body", None)
        merged_eb = self._merge_extra_body(base_eb, caller_eb)
        if merged_eb:
            kwargs["extra_body"] = merged_eb

        if tools:
            kwargs["tools"] = tools

        if response_format is not None:
            kwargs["response_format"] = response_format

        if stream and include_usage:
            kwargs["stream_options"] = {"include_usage": True}

        self._apply_thinking(kwargs, enable_thinking=enable_thinking)

        if extra:
            kwargs.update(extra)

        return kwargs

    @staticmethod
    def _merge_extra_body(
            base: Optional[Dict[str, Any]],
            override: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """合并两个 ``extra_body`` 字典；顶层键 ``override`` 优先。"""
        if not base and not override:
            return None
        if not base:
            return dict(override) if override else None
        if not override:
            return dict(base)
        merged = dict(base)
        merged.update(override)
        return merged

    # ------------------------------------------------------------------
    # 响应解析钩子
    # ------------------------------------------------------------------

    def _parse_non_stream_completion(self, completion) -> Dict[str, Any]:
        """解析非流式响应，返回统一的结构化字典。

        返回键：``content``（已 ``strip()``）、``reasoning``、``tool_calls``、
        ``finish_reason``、``usage``、``raw``（原始 completion 对象）。
        """
        if not completion.choices:
            raise RuntimeError("No choices returned from LLM.")

        msg = completion.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", "") or ""

        raw_tool_calls = msg.tool_calls or []
        tool_calls = [tc.model_dump() for tc in raw_tool_calls] if raw_tool_calls else []

        usage: Optional[Dict[str, int]] = None
        if completion.usage:
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens or 0,
                "completion_tokens": completion.usage.completion_tokens or 0,
                "total_tokens": completion.usage.total_tokens or 0,
            }

        return {
            "content": content.strip(),
            "reasoning": reasoning,
            "tool_calls": tool_calls,
            "finish_reason": completion.choices[0].finish_reason,
            "usage": usage,
            "raw": completion,
        }

    def _parse_stream_delta(self, delta) -> Dict[str, Any]:
        """解析单个流式 ``chunk.choices[0].delta``。

        返回键：``content``、``reasoning``、``tool_calls_delta``（原始对象列表）。
        """
        content = getattr(delta, "content", "") or ""
        reasoning = getattr(delta, "reasoning_content", "") or ""
        tool_calls_delta = getattr(delta, "tool_calls", None) or []
        return {
            "content": content,
            "reasoning": reasoning,
            "tool_calls_delta": tool_calls_delta,
        }

    def _parse_stream_usage(self, chunk) -> Optional[Dict[str, int]]:
        """从流式 chunk 中提取 usage（如果存在）。

        默认不要求 ``chunk.choices`` 为空才读 usage，以兼容那些 usage 会随
        非空 choices 一起下发的厂商。
        """
        usage = getattr(chunk, "usage", None)
        if not usage:
            return None
        return {
            "prompt_tokens": usage.prompt_tokens or 0,
            "completion_tokens": usage.completion_tokens or 0,
            "total_tokens": usage.total_tokens or 0,
        }

    # 参数校验钩子
    def _validate_temperature(self, v: float) -> None:
        if not (0.0 <= v <= 2.0):
            raise RuntimeError("temperature must be between 0.0 and 2.0")

    def _validate_top_p(self, v: float) -> None:
        if not (0.0 <= v <= 1.0):
            raise RuntimeError("top_p must be between 0.0 and 1.0")

    # Tool call 统一分支（同 / 异步对称）
    def _tool_call(
            self,
            client: OpenAI,
            params: Dict[str, Any],
            tools: List,
            messages: List[Dict[str, Any]],
    ) -> ToolCall:
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=tools, stream=False,
        )
        try:
            completion = client.chat.completions.create(**kwargs, timeout=9999)
        except Exception as e:
            raise RuntimeError(f"llm tool call error: {e}")
        return self._tool_call_result(completion)

    async def _atool_call(
            self,
            async_client: AsyncOpenAI,
            params: Dict[str, Any],
            tools: List,
            messages: List[Dict[str, Any]],
    ) -> ToolCall:
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=tools, stream=False,
        )
        try:
            completion = await async_client.chat.completions.create(**kwargs, timeout=9999)
        except Exception as e:
            raise RuntimeError(f"llm tool call error: {e}")
        return self._tool_call_result(completion)

    def _tool_call_result(self, completion) -> ToolCall:
        """把 tool_call 响应统一转成 :class:`ToolCall`。"""
        if not completion.choices:
            return ToolCall(tool_calls=[], content=None)

        finish_reason = completion.choices[0].finish_reason
        message = completion.choices[0].message

        if finish_reason == "stop":
            return ToolCall(tool_calls=[], content=message.content)

        raw_tool_calls = message.tool_calls or []
        tool_calls_list = [tc.model_dump() for tc in raw_tool_calls]
        return ToolCall(tool_calls=tool_calls_list, content=None)

    # 主方法：同步非流式
    def get_non_stream_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None,
            tools: Optional[List] = None,
            response_format: Optional[Dict[str, Any]] = None,
            **extra_kwargs: Any,
    ) -> Union[str, ToolCall]:
        """``**extra_kwargs`` 会直接透传给底层 ``chat.completions.create``，
        例如 ``reasoning_effort="high"`` 或 ``extra_body={"thinking": {"type": "enabled"}}``。
        """
        messages = self._prepare_messages(message, system_prompt)
        messages = self._transform_messages(messages)
        need_mm = self._needs_multimodal(message)

        client, params = self._balancer.get_next_sync_backend(need_multimodal=need_mm)

        if tools:
            return self._tool_call(client, params, tools, messages)

        ctx = _LLMCallContext(self.model_name)
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=None, stream=False,
            enable_thinking=enable_thinking, response_format=response_format,
            **extra_kwargs,
        )
        completion = client.chat.completions.create(**kwargs, timeout=9999)
        parsed = self._parse_non_stream_completion(completion)

        self._response_info = {
            "usage": parsed["usage"] or {},
            "model_name": self.model_name,
            "time_taken": round(time.time() - ctx.start_time, 2),
            "response": parsed["content"],
        }

        ctx.end_sync(self._hooks, usage=parsed["usage"])
        return parsed["content"]

    # 主方法：同步流式
    def get_streaming_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None,
            tools: Optional[List] = None,
            stream_tool_calls: bool = False,
            response_format: Optional[Dict[str, Any]] = None,
            **extra_kwargs: Any,
    ) -> BaseGenerator:
        """``**extra_kwargs`` 透传给底层 ``chat.completions.create``，详见
        :meth:`get_non_stream_response`。
        """
        messages = self._prepare_messages(message, system_prompt)
        messages = self._transform_messages(messages)
        need_mm = self._needs_multimodal(message)

        sync_client, params = self._balancer.get_next_sync_backend(need_multimodal=need_mm)
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=tools, stream=True,
            enable_thinking=enable_thinking, response_format=response_format,
            **extra_kwargs,
        )

        stream = sync_client.chat.completions.create(**kwargs)
        return _SyncStreamGenerator(
            llm=self,
            stream_iter=stream,
            content_type=content_type,
            stream_tool_calls=stream_tool_calls,
        )

    # 主方法：异步非流式
    async def aget_non_stream_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None,
            tools: Optional[List] = None,
            response_format: Optional[Dict[str, Any]] = None,
            **extra_kwargs: Any,
    ) -> Union[str, ToolCall]:
        """``**extra_kwargs`` 透传给底层 ``chat.completions.create``，详见
        :meth:`get_non_stream_response`。
        """
        messages = self._prepare_messages(message, system_prompt)
        messages = self._transform_messages(messages)
        need_mm = self._needs_multimodal(message)

        async_client, params = self._balancer.get_next_async_backend(need_multimodal=need_mm)

        if tools:
            return await self._atool_call(async_client, params, tools, messages)

        ctx = _LLMCallContext(self.model_name)
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=None, stream=False,
            enable_thinking=enable_thinking, response_format=response_format,
            **extra_kwargs,
        )
        completion = await async_client.chat.completions.create(**kwargs, timeout=9999)
        parsed = self._parse_non_stream_completion(completion)

        self._response_info = {
            "usage": parsed["usage"] or {},
            "model_name": self.model_name,
            "time_taken": round(time.time() - ctx.start_time, 2),
        }

        await ctx.end_async(self._hooks, usage=parsed["usage"])
        return parsed["content"]

    # 主方法：异步流式
    async def aget_streaming_response(
            self,
            message: Union[str, Message, List[Dict[str, Any]]],
            content_type: str = "char",
            enable_thinking: bool = False,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None,
            tools: Optional[List] = None,
            stream_tool_calls: bool = False,
            response_format: Optional[Dict[str, Any]] = None,
            **extra_kwargs: Any,
    ) -> BaseGenerator:
        """``**extra_kwargs`` 透传给底层 ``chat.completions.create``，详见
        :meth:`get_non_stream_response`。
        """
        messages = self._prepare_messages(message, system_prompt)
        messages = self._transform_messages(messages)
        need_mm = self._needs_multimodal(message)

        async_client, params = self._balancer.get_next_async_backend(need_multimodal=need_mm)
        kwargs = self._build_completion_kwargs(
            params=params, messages=messages, tools=tools, stream=True,
            enable_thinking=enable_thinking, response_format=response_format,
            **extra_kwargs,
        )

        stream = await async_client.chat.completions.create(**kwargs)
        return _AsyncStreamGenerator(
            llm=self,
            stream_iter=stream,
            content_type=content_type,
            stream_tool_calls=stream_tool_calls,
        )

    # 参数 setter / 其他
    def set_temperature(self, temp: float) -> None:
        self._validate_temperature(temp)
        self.temperature = temp
        self.completion_params["temperature"] = temp
        self._balancer.update_primary_param("temperature", temp)

    def set_max_tokens(self, tokens: int) -> None:
        if tokens <= 0:
            raise RuntimeError("max_tokens must be > 0")
        self.max_tokens = tokens
        self.completion_params["max_tokens"] = tokens
        self._balancer.update_primary_param("max_tokens", tokens)

    def set_top_p(self, p: float) -> None:
        self._validate_top_p(p)
        self.top_p = p
        self.completion_params["top_p"] = p
        self._balancer.update_primary_param("top_p", p)

    def set_model_name(self, name: str) -> None:
        self.model_name = name
        self.completion_params["model"] = name
        self._balancer.update_primary_param("model", name)

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

    def __repr__(self) -> str:
        return (
            f"LLM(model='{self.model_name}', base_url='{self.base_url}', "
            f"temp={self.temperature}, max_tokens={self.max_tokens})"
        )

    def __getstate__(self) -> Dict[str, Any]:
        state = self.__dict__.copy()
        state.pop("_sync_client", None)
        state.pop("_async_client", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._sync_client = self._make_sync_client(
            api_key=self.api_key, base_url=self.base_url, header=self.header,
        )
        self._async_client = self._make_async_client(
            api_key=self.api_key, base_url=self.base_url, header=self.header,
        )

    def __add__(self, other: "OpenAILike") -> "OpenAILike":
        if not isinstance(other, OpenAILike):
            return NotImplemented

        self._balancer.add_client(
            async_client=other._async_client,
            sync_client=other._sync_client,
            completion_params=other.completion_params,
            is_multimodal=other.is_multimodal,
        )
        return self
