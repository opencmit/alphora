# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


from uuid import uuid4
from typing import TypeVar, List, Dict, Optional, Any, Type, Union, TYPE_CHECKING, AsyncIterator, Callable
import logging
import time
import re

from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
from alphora.prompter import BasePrompt
from alphora.agent.stream import Stream
from pydantic import BaseModel

from alphora.memory import MemoryManager
from alphora.hooks import HookManager, build_manager

from alphora.debugger import tracer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

T = TypeVar('T', bound='BaseAgent')


class MemoryPoolItem(BaseModel):
    """记忆池项模型，包含记忆实例和元数据"""
    memory: MemoryManager
    create_time: float
    last_access_time: float
    agent_id: str
    session_id: str

    class Config:
        arbitrary_types_allowed = True


class BaseAgent(object):
    agent_type: str = "BaseAgent"

    def __init__(self,
                 llm: Optional[OpenAILike] = None,
                 verbose: bool = False,
                 agent_id: Optional[str] = None,
                 callback: Optional[DataStreamer] = None,
                 debugger: bool = False,
                 debugger_port: int = 9527,
                 config: Optional[Dict[str, Any]] = None,
                 memory: Optional[MemoryManager] = None,
                 hooks: Optional[HookManager] = None,
                 **kwargs):

        self.callback = callback
        self.agent_id = agent_id or str(uuid4())

        self.verbose = verbose

        # 记忆存储（作为共享存储池）
        self.memory = memory or MemoryManager()

        self.llm = llm

        # Agent配置字典，会继承给派生智能体
        # self.config: Dict[str, Any] = {}
        self.config: Dict[str, Any] = config if config is not None else {}

        self.stream = Stream(callback=self.callback)
        self._hooks = build_manager(hooks)

        self.init_params = {
            "llm": self.llm,
            "memory": self.memory,
            "config": self.config,
            **kwargs
        }

        self._log = []

        # ========== 会话追踪（用于提示） ==========
        self._active_sessions: Dict[str, float] = {}  # session_id -> last_access_time
        self._session_prompt_count: Dict[str, int] = {}  # 用于检测短时间内重复创建
        self._memory_source_logged: bool = False  # 避免重复日志

        if debugger:
            tracer.enable(start_server=True, port=debugger_port)
        tracer.track_agent_created(self)

    def update_config(self, key: str, value: Any = None) -> None:
        """更新单个配置项"""
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")
        self.config[key] = value

    def get_config(self, key: str) -> Any:
        """获取指定配置项的值"""
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")

        if key not in self.config:
            from difflib import get_close_matches
            similar = get_close_matches(key, self.config.keys(), n=1, cutoff=0.6)
            if similar:
                raise KeyError(
                    f"Config '{key}' not found. Did you mean '{similar[0]}'?"
                )
            else:
                available = list(self.config.keys())
                raise KeyError(
                    f"Config '{key}' not found. Available: {available}"
                )
        return self.config.get(key)

    def _reinitialize(self, **new_kwargs) -> None:
        merged_params = {**self.init_params, **new_kwargs}
        self.__init__(**merged_params)

    def derive(self, agent_cls_or_instance: Union[Type[T], T], **kwargs) -> T:
        """
        从当前 agent 派生出一个新的 agent 实例。

        支持两种用法：
        1. 传入类：derive(SomeAgentClass) - 用当前 agent 的参数创建新实例
        2. 传入实例：derive(some_agent_instance) - 继承共享状态，保留实例特有属性

        Args:
            agent_cls_or_instance: Agent 类或实例
            **kwargs: 额外的覆盖参数

        Returns:
            派生后的 agent 实例

        示例：
            # 方式1：传入类
            sub_agent = self.derive(SubAgentClass)

            # 方式2：传入实例（推荐用于有特殊初始化参数的子类）
            view_agent = FileViewerAgent(base_dir="/path/to/files")
            view_agent = self.derive(view_agent)  # base_dir 会被保留
        """

        if isinstance(agent_cls_or_instance, type) and issubclass(agent_cls_or_instance, BaseAgent):
            # 传入的是类，创建新实例
            override_params = {**self.init_params, 'config': self.config, **kwargs}
            derived_agent = agent_cls_or_instance(**override_params, callback=self.callback)

            tracer.track_agent_derived(self, derived_agent)

            return derived_agent

        elif isinstance(agent_cls_or_instance, BaseAgent):
            # 传入的是实例，直接替换共享属性，不重新初始化
            instance = agent_cls_or_instance

            # 只替换需要从父 agent 继承的共享属性
            instance.llm = self.llm
            instance.memory = self.memory
            instance.config = self.config
            instance.callback = self.callback
            instance.verbose = self.verbose

            # 重建依赖 callback 的 stream
            instance.stream = Stream(callback=instance.callback)

            # 同步 init_params 中的共享部分（用于后续可能的再派生）
            instance.init_params.update({
                'llm': self.llm,
                'memory': self.memory,
                'config': self.config,
                'verbose': self.verbose,
            })

            # 应用额外的覆盖参数
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
                instance.init_params[key] = value

            tracer.track_agent_derived(self, instance)

            return instance
        else:
            raise TypeError(
                f"Unsupported type: {type(agent_cls_or_instance)}. "
                f"Expected a subclass or instance of BaseAgent."
            )

    def create_prompt(
            self,
            prompt: str = None,
            user_prompt: str = None,
            template_path: str = None,
            template_desc: str = "",
            content_type: Optional[str] = None,
            system_prompt: Optional[str] = None,
    ) -> BasePrompt:
        """
        快速创建提示词模板

        支持两种模式：

        【传统模式】使用 prompt/template_path 参数：
            - 所有内容渲染后放入 role='user' 的 content
            - 不支持自动记忆管理
            - 适合需要完全自定义提示词结构的场景

            示例：
                prompt = self.create_prompt(
                    prompt='历史记录：{{history}}\\n请回答：{{query}}'
                )
                prompt.update_placeholder(history=history)
                await prompt.acall(query='你好')

        【新模式】使用 system_prompt 参数：
            - 支持规范的 messages 结构（system/user/assistant 分离）
            - 支持自动记忆管理
            - 适合需要多轮对话记忆的场景

            示例：
                prompt = self.create_prompt(
                    system_prompt='你是一个{{personality}}的助手',
                )
                prompt.update_placeholder(personality='友好')
                await prompt.acall(query='你好')  # 自动管理历史

        Args:
            user_prompt: role=user 的提示词
            prompt: 提示词字符串（传统模式）
            template_path: 提示词模板文件路径（传统模式）
            template_desc: 提示词描述
            content_type: 当调用 acall 方法时，输出的流的 content_type
            system_prompt: 系统提示词（新模式，支持占位符）

        Returns:
            BasePrompt 实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        prompt_instance = BasePrompt(
            user_prompt=user_prompt or prompt,
            template_path=template_path,
            template_desc=template_desc,
            callback=self.callback,
            content_type=content_type,
            system_prompt=system_prompt,
            agent_id=self.agent_id,
        )

        try:
            prompt_instance.add_llm(model=self.llm)

            # if prompt:
            #     prompt_instance.load_from_string(prompt=prompt)

            prompt_instance.verbose = self.verbose

            tracer.track_prompt_created(
                agent_id=self.agent_id,
                prompt_id=prompt_instance.prompt_id,
                system_prompt=system_prompt,
                prompt=prompt_instance.prompt,
                placeholders=prompt_instance.content,
            )
            prompt_instance._debug_agent_id = self.agent_id

            return prompt_instance

        except Exception as e:
            error_msg = f'Failed to create prompt: {str(e)}'
            logging.error(error_msg)
            raise ValueError(error_msg)

    def _track_session(self, session_id: str):
        """追踪会话使用情况，检测潜在误用"""
        now = time.time()

        # 检测短时间内重复创建（可能是误用）
        if session_id in self._active_sessions:
            last_time = self._active_sessions[session_id]
            count = self._session_prompt_count.get(session_id, 0) + 1
            self._session_prompt_count[session_id] = count

            # 1秒内创建超过5次，给警告
            if now - last_time < 1 and count > 5:
                logger.warning(
                    f"[Memory] 检测到短时间内多次创建 Prompt 使用同一 session_id='{session_id}'，"
                    f" 如果这是循环调用请忽略，"
                    f" 否则建议复用 Prompt 实例以提高性能"
                )
                self._session_prompt_count[session_id] = 0  # 重置，避免重复警告
        else:
            self._session_prompt_count[session_id] = 1

        self._active_sessions[session_id] = now

    def __or__(self, other):
        # TODO
        pass

    async def afetch_stream(self,
                            url: str,
                            payload: Dict[str, Any],
                            parser_func: Optional[Callable[[bytes], str]] = None,
                            method: str = "POST",
                            headers: Optional[Dict[str, str]] = None,
                            content_type: str = "char") -> str:
        """
        调用第三方的接口，并透传至流式输出，函数返回完整输出字符串。

        Args:
            url: 目标 URL
            payload: 请求体 JSON
            parser_func: 自定义解析函数。
                         - 如果为 None (默认): 使用标准 OpenAI SSE 解析逻辑 (处理 data: {...})
                         - 如果传入函数: 接收 raw bytes，返回解析后的 string
            method: 请求方法
            headers: 请求头
            content_type: 输出的ct
        """
        import json
        import httpx
        from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput

        req_headers = headers or {}
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"

        if "Accept" not in req_headers:
            req_headers["Accept"] = "text/event-stream"

        # 定义标准 OpenAI 解析器 (适配器)
        class StandardOpenAIAdapter(BaseGenerator[GeneratorOutput]):
            def __init__(self, response_lines_iter, default_content_type):
                super().__init__(content_type=default_content_type)
                self.lines_iter = response_lines_iter

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                async for line in self.lines_iter:

                    if not line.startswith("data: "):
                        continue

                    data_str = line.replace("data: ", "").strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})

                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")

                        if reasoning:
                            yield GeneratorOutput(content=reasoning, content_type="think")
                        elif content:
                            yield GeneratorOutput(content=content, content_type=self.content_type)

                    except Exception:
                        continue

        class CustomRawAdapter(BaseGenerator[GeneratorOutput]):
            def __init__(self, response_bytes_iter, parser, default_content_type):
                super().__init__(content_type=default_content_type)
                self.bytes_iter = response_bytes_iter
                self.parser = parser

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                async for chunk in self.bytes_iter:
                    try:
                        decoded = self.parser(chunk)
                        if decoded:
                            yield GeneratorOutput(content=decoded, content_type=self.content_type)
                    except Exception as e:
                        logger.error(f"Custom parse error: {e}")

        # 发起请求
        full_content = ""
        client = httpx.AsyncClient(timeout=60.0)

        try:
            async with client.stream(method, url, json=payload, headers=req_headers) as response:
                if response.status_code != 200:
                    error_msg = f"API Error: {response.status_code} - {await response.aread()}"
                    logger.error(error_msg)
                    return error_msg

                # 根据是否传入 parser_func 决定处理策略
                if parser_func is None:

                    generator = StandardOpenAIAdapter(
                        response_lines_iter=response.aiter_lines(),
                        default_content_type=content_type
                    )
                else:
                    generator = CustomRawAdapter(
                        response_bytes_iter=response.aiter_bytes(),
                        parser=parser_func,
                        default_content_type=content_type
                    )

                full_content = await self.stream.astream_to_response(generator)

        except Exception as e:
            logger.error(f"Stream request failed: {e}")
            raise e
        finally:
            await client.aclose()

        return full_content
