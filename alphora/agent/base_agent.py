# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


from uuid import uuid4
from typing import TypeVar, List, Dict, Optional, Any, Type, Union, Tuple, TYPE_CHECKING, AsyncIterator, Callable
import asyncio
import logging
import time
import re

from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer, StreamCallback
from alphora.prompter import BasePrompt
from alphora.agent.stream import Stream
from pydantic import BaseModel

from alphora.memory import MemoryManager
from alphora.hooks import HookManager, build_manager

from alphora.debugger import tracer

from alphora.agent._request_scope import RequestScoped

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

T = TypeVar('T', bound='BaseAgent')


class _PrefixedCallback:
    """DataStreamer 代理：给 content_type 加前缀以区分并行 agent 的输出，拦截 stop() 防止提前关闭共享流。"""

    def __init__(self, callback, prefix: str):
        self._callback = callback
        self._prefix = prefix

    async def send_data(self, content_type: str, content: str = None, meta: dict = None):
        if self._callback:
            await self._callback.send_data(
                content_type=f"{self._prefix}:{content_type}",
                content=content,
                meta=meta,
            )

    async def stop(self, stop_reason='stop'):
        pass


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
    _SHARED_KEYS: tuple = ("llm", "memory", "config", "verbose")

    # 请求级属性：通过描述符在并发请求间隔离。
    # 详见 alphora.agent._request_scope.RequestScoped。
    # 写入：激活请求作用域时只写入 per-task 覆盖字典；否则写到 instance.__dict__["_singleton_<name>"]
    # 读取：激活请求作用域且有覆盖时读覆盖；否则回落到单例默认值。
    config = RequestScoped("config")
    memory = RequestScoped("memory")
    callback = RequestScoped("callback")
    stream = RequestScoped("stream")
    llm = RequestScoped("llm")

    def __init__(self,
                 llm: Optional[OpenAILike] = None,
                 verbose: bool = False,
                 agent_id: Optional[str] = None,
                 callback: Optional[StreamCallback] = None,
                 debugger: bool = False,
                 debugger_port: int = 9527,
                 config: Optional[Dict[str, Any]] = None,
                 memory: Optional[MemoryManager] = None,
                 hooks: Optional[HookManager] = None,
                 **kwargs):

        self.callback = callback

        self.agent_id = agent_id or self.__class__.__name__

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
                logger.warning(f"Config '{key}' not found. Did you mean '{similar[0]}'?")
                return None

            else:
                available = list(self.config.keys())
                logger.warning(f"Config '{key}' not found. Available: {available}")
                return None
        return self.config.get(key)

    def _get_shared_params(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self._SHARED_KEYS}

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
            params = {**self._get_shared_params(), **kwargs}
            derived_agent = agent_cls_or_instance(**params, callback=self.callback)

            tracer.track_agent_derived(self, derived_agent)

            return derived_agent

        elif isinstance(agent_cls_or_instance, BaseAgent):
            instance = agent_cls_or_instance

            for k, v in self._get_shared_params().items():
                setattr(instance, k, v)
            instance.callback = self.callback
            instance.stream = Stream(callback=instance.callback)

            for key, value in kwargs.items():
                setattr(instance, key, value)

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
            hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
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
            hooks:钩子

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
            hooks=hooks,
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

    async def parallel_run(
            self,
            tasks: List[Tuple["BaseAgent", str]],
            timeout: Optional[float] = None,
            return_exceptions: bool = False,
    ) -> List[str]:
        """
        并行运行多个子 agent，返回有序结果列表。

        自动处理 memory 隔离（防止并发写入冲突），并把整段并发包进一个
        ``AgentCollabScope(kind="batch")``：发出 ``agent_collab_start/end`` 生命周期事件，
        各子 agent 输出经 ``TaggedCallback`` 自动带上 ``agent_id`` 与 ``collab_id``，
        前端据 ``collab_id`` + ``size`` 确定性渲染为多智能体面板（无需推断并发）。

        Args:
            tasks: ``(agent, query)`` 元组列表，每个元素是一个子 agent 及其对应的查询
            timeout: 可选的总超时时间（秒），超时抛出 ``asyncio.TimeoutError``
            return_exceptions: 为 True 时异常不抛出，对应位置结果为错误信息字符串；
                               为 False 时任一 agent 失败立即抛出

        Returns:
            与 tasks 顺序一一对应的结果字符串列表

        示例::

            sub_a = self.derive(ReActAgent, tools=[tool_1], system_prompt="研究员")
            sub_b = self.derive(ReActAgent, tools=[tool_2], system_prompt="分析师")
            results = await self.parallel_run([
                (sub_a, "搜索相关资料"),
                (sub_b, "分析现有数据"),
            ])
        """
        if not tasks:
            return []

        for i, (agent, _) in enumerate(tasks):
            if type(agent).run is BaseAgent.run:
                raise TypeError(
                    f"tasks[{i}] 的 agent ({type(agent).__name__}) 未覆写 run() 方法。"
                    f"parallel_run 通过 run() 驱动每个子 agent，"
                    f"请确保子类实现了 async def run(self, task: str) -> str。"
                )

        seen_memories = set()
        for agent, _ in tasks:
            mem_id = id(agent.memory)
            if mem_id in seen_memories:
                agent.memory = MemoryManager()
            seen_memories.add(mem_id)

        from alphora.agent.agent_collab import AgentCollabScope
        from alphora.agent.tagged_callback import TaggedCallback

        cli_streamer = None
        effective_callback = self.callback

        labels = [f"{type(agent).__name__}_{i}" for i, (agent, _) in enumerate(tasks)]

        if not effective_callback:
            from alphora.cli import create_cli_streamer
            cli_streamer = create_cli_streamer(agent_labels=labels)
            effective_callback = cli_streamer

        # 每个子 agent 包一层通用打标 callback：输出自动带 agent_id/agent_name，
        # 并在 AgentCollabScope 内自动带 collab_id（前端据此确定性归组，无需推断并发）。
        for i, (agent, _) in enumerate(tasks):
            wrapped = TaggedCallback(effective_callback, agent_id=labels[i], agent_name=labels[i])
            agent.callback = wrapped
            agent.stream = Stream(callback=wrapped)
            if hasattr(agent, '_prompt') and agent._prompt:
                agent._prompt.callback = wrapped

        if cli_streamer is not None:
            cli_streamer.start()

        members = [{"agent_id": labels[i], "agent_name": labels[i]} for i in range(len(tasks))]
        scope_stream = Stream(callback=effective_callback)

        try:
            async with AgentCollabScope(
                scope_stream,
                kind="batch",
                members=members,
                title=f"并行执行 {len(tasks)} 个子任务",
            ):
                coros = [agent.run(task=query) for agent, query in tasks]
                if timeout is not None:
                    raw_results = await asyncio.wait_for(
                        asyncio.gather(*coros, return_exceptions=return_exceptions),
                        timeout=timeout,
                    )
                else:
                    raw_results = await asyncio.gather(*coros, return_exceptions=return_exceptions)
        finally:
            if cli_streamer is not None:
                cli_streamer.stop_display()

        results: List[str] = []
        for r in raw_results:
            if isinstance(r, BaseException):
                results.append(f"[Error] {type(r).__name__}: {r}")
            else:
                results.append(r if r is not None else "")

        return results

    async def run(self, task: str) -> ...:
        raise NotImplementedError

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
