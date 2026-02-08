"""
Alphora Base Prompter Module

This module provides the core orchestration logic for prompt engineering within the Alphora framework.
It leverages Jinja2 for dynamic template rendering, manages variable interpolation, and handles the
lifecycle of LLM interactions.

Key Features:
- **Orchestration**: Manages the end-to-end flow from template loading to LLM execution.
- **Stateless Design**: Externalizes history management to ensure scalability and determinism.
- **Jinja2 Integration**: specialized environment for rendering dynamic system and user contexts.
- **Dual Mode**: Fully supports both synchronous (`call`) and asynchronous (`acall`) invocation patterns.
- **Metadata Encapsulation**: Returns enriched string objects containing reasoning traces and generation metadata.

"""

import json
import logging
import time
import os
import re
import uuid
from pathlib import Path
from typing import Optional, List, Callable, Any, Union, Dict, Literal, TYPE_CHECKING

from jinja2 import Environment, Template, BaseLoader, meta

from alphora.models.message import Message
from alphora.postprocess.base_pp import BasePostProcessor
from alphora.server.stream_responser import DataStreamer

from json_repair import repair_json

from alphora.models.llms.base import BaseLLM
from alphora.models.llms.stream_helper import BaseGenerator
from alphora.models.llms.types import ToolCall

from alphora.memory.history_payload import HistoryPayload, is_valid_history_payload

from alphora.debugger import tracer
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PrompterOutput(str):
    """
    A metadata-enriched string wrapper for LLM responses.

    Inherits directly from `str` to maintain backward compatibility with standard string
    operations while providing access to model-specific metadata such as reasoning chains
    and stop sequences.
    """

    def __new__(cls, content: str, reasoning: str = "", finish_reason: str = "",
                continuation_count: int = 0):
        instance = super().__new__(cls, content)
        instance._reasoning = reasoning
        instance._finish_reason = finish_reason
        instance._continuation_count = continuation_count
        return instance

    @property
    def reasoning(self):
        return self._reasoning

    @property
    def finish_reason(self):
        return self._finish_reason

    @property
    def continuation_count(self):
        """返回续写次数（long_response 模式）"""
        return self._continuation_count


class BasePrompt:
    """
    Core engine for constructing and executing LLM prompts.

    This class manages the lifecycle of a prompt, including template loading, placeholder
    interpolation, message assembly, and final LLM invocation. The message sequence follows
    a strict topological order:
    [System Context] -> [Runtime Injections] -> [History] -> [User Input].

    Attributes:
        agent_id (Optional[str]): Unique identifier for the associated agent for tracing.
        prompt_id (str): Ephemeral identifier for this specific prompt instance.
        placeholders (List[str]): List of detected variables within the Jinja2 templates.
        llm (Optional[BaseLLM]): The bound Language Model instance.
    """

    def __init__(self,
                 user_prompt: str = None,
                 template_path: str = None,
                 system_prompt: Union[str, List[str], None] = None,
                 verbose: bool = False,
                 callback: Optional[DataStreamer] = None,
                 content_type: Optional[str] = None,
                 agent_id: str | None = None,
                 hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
                 before_build_messages: Optional[Callable] = None,
                 after_build_messages: Optional[Callable] = None,
                 before_llm: Optional[Callable] = None,
                 after_llm: Optional[Callable] = None,
                 on_stream_chunk: Optional[Callable] = None,
                 **kwargs):

        """
        Initializes the Prompter with templates and initial context.

        Args:
            user_prompt: Raw Jinja2 string for the user message.
            template_path: File path to a template containing the user message.
            system_prompt: System-level instructions (string or list of strings).
            verbose: Enables detailed logging of the internal state.
            callback: Stream handler for real-time data transmission.
            content_type: MIME type or format hint for the output (default: 'char').
            agent_id: Traceable ID for the calling agent.
            **kwargs: Initial key-value pairs for template placeholders.
        """

        self.agent_id = agent_id
        self.prompt_id = str(uuid.uuid4())[:8]

        self.template_path = template_path

        self.is_stream: bool = False

        self.llm: BaseLLM | None = None
        self.callback: Optional[DataStreamer] = callback
        self.verbose: bool = verbose
        self.content_type = content_type or 'char'
        self.context = kwargs
        self._hooks = build_manager(
            hooks,
            short_map={
                "before_build_messages": HookEvent.PROMPTER_BEFORE_BUILD_MESSAGES,
                "after_build_messages": HookEvent.PROMPTER_AFTER_BUILD_MESSAGES,
                "before_llm": HookEvent.LLM_BEFORE_CALL,
                "after_llm": HookEvent.LLM_AFTER_CALL,
                "on_stream_chunk": HookEvent.LLM_ON_STREAM_CHUNK,
            },
            before_build_messages=before_build_messages,
            after_build_messages=after_build_messages,
            before_llm=before_llm,
            after_llm=after_llm,
            on_stream_chunk=on_stream_chunk,
        )

        self._resolved_prompt = None
        self.parser = []

        self.prompt: Optional[Template] = None
        self.content: Optional[str] = None

        self.prompt, self.content = self.load_template()

        # 1. 初始化 Jinja2 环境
        self.env = Environment(loader=BaseLoader())

        # 2. 处理 User 模板
        self.user_template: Optional[Template] = None
        self._user_prompt_raw: Optional[str] = None

        if user_prompt:
            self._user_prompt_raw = user_prompt
            self.user_template = self.env.from_string(user_prompt)
        elif template_path:
            self.template_path = template_path
            tmpl, content = self.load_template()
            self.user_template = tmpl
            self._user_prompt_raw = content

        # 3. 处理 System 模板
        self.system_templates: List[Template] = []
        self._raw_system_prompts = []

        if system_prompt:
            if isinstance(system_prompt, str):
                self._raw_system_prompts = [system_prompt]
            elif isinstance(system_prompt, list):
                self._raw_system_prompts = system_prompt

            for sp in self._raw_system_prompts:
                self.system_templates.append(self.env.from_string(sp))

        # 4. 扫描所有变量
        self.placeholders = self._scan_all_variables()

    def _scan_all_variables(self) -> List[str]:
        """
        Performs AST analysis on templates to identify undeclared variables.

        Returns:
            List[str]: A unique list of variable names found in user and system templates.
        """

        vars_set = set()

        if self._user_prompt_raw:
            try:
                parsed = self.env.parse(self._user_prompt_raw)
                vars_set.update(meta.find_undeclared_variables(parsed))
            except Exception:
                pass

        for sp in self._raw_system_prompts:
            try:
                parsed = self.env.parse(sp)
                vars_set.update(meta.find_undeclared_variables(parsed))
            except Exception:
                pass

        if 'query' in vars_set:
            vars_set.remove('query')

        return list(vars_set)

    def _render_user_content(self, query: str) -> str:
        """Interpolates variables into the user template."""
        render_context = self.context.copy()

        if query is not None:
            render_context['query'] = query

        if self.user_template:
            try:
                return self.user_template.render(render_context)
            except Exception as e:
                logger.error(f"User 模板渲染失败: {e}")
                return query or ""

        return query or ""

    def _render_system_prompts(self) -> List[str]:
        """Interpolates variables into all system templates."""
        return [tmpl.render(self.context) for tmpl in self.system_templates]

    def update_placeholder(self, **kwargs):
        """
        Updates the internal context with new values for template placeholders.

        Args:
            **kwargs: Key-value pairs matching template variables.

        Returns:
            BasePrompt: The current instance for method chaining.
        """
        invalid_placeholders = [k for k in kwargs if k not in self.placeholders]
        missing_placeholders = [p for p in self.placeholders if p not in kwargs and p not in self.context]

        if invalid_placeholders:
            logger.info(f"传入了未定义占位符: <{', '.join(invalid_placeholders)}> (可用: {self.placeholders})")

        if missing_placeholders:
            logger.info(f"存在未赋值占位符: <{', '.join(missing_placeholders)}>")

        valid_kwargs = {k: v for k, v in kwargs.items() if k in self.placeholders}
        self.context.update(valid_kwargs)

        # 调试追踪
        try:
            sys_rendered = self._render_system_prompts()
            sys_str = "\n".join([f"[System]: {s}" for s in sys_rendered if s.strip()])
            user_str = f"[User]: {self._render_user_content('{{query}}')}"
            combined_preview = f"{sys_str}\n\n{user_str}".strip()

            tracer.track_prompt_render(
                agent_id=self.agent_id,
                prompt_id=self.prompt_id,
                rendered_prompt=combined_preview,
                placeholders=valid_kwargs
            )
        except Exception:
            pass

        return self

    def build_messages(
            self,
            query: str = None,
            force_json: bool = False,
            runtime_system_prompt: Union[str, List[str], None] = None,
            history: Optional[HistoryPayload] = None,
    ) -> List[Dict[str, str]]:
        """
        Assembles the final message list for the LLM.

        Constructs the sequence of messages in the following order:
        1. JSON Constraint (if enforced)
        2. Pre-configured System Prompts
        3. Runtime System Prompts
        4. Historical Context (from MemoryManager)
        5. User Input

        Args:
            query: The current user input string.
            force_json: If True, injects a system instruction to strictly enforce JSON output.
            runtime_system_prompt: Additional system instructions appended dynamically.
            history: An external history payload object.

        Returns:
            List[Dict[str, str]]: A list of message dictionaries compliant with Chat Completion API.

        Raises:
            TypeError: If the provided `history` object is not a valid `HistoryPayload`.
        """

        before_ctx = HookContext(
            event=HookEvent.PROMPTER_BEFORE_BUILD_MESSAGES,
            component="prompter",
            data={
                "query": query,
                "force_json": force_json,
                "runtime_system_prompt": runtime_system_prompt,
                "history": history,
            },
        )
        before_ctx = self._hooks.emit_sync(HookEvent.PROMPTER_BEFORE_BUILD_MESSAGES, before_ctx)
        query = before_ctx.data.get("query", query)
        force_json = before_ctx.data.get("force_json", force_json)
        runtime_system_prompt = before_ctx.data.get("runtime_system_prompt", runtime_system_prompt)
        history = before_ctx.data.get("history", history)

        messages = []

        # 1. Force JSON 指令
        if force_json:
            messages.append({
                "role": "system",
                "content": "请严格使用 JSON 格式输出"
            })

        # 2. 预设 System Prompts
        rendered_sys = self._render_system_prompts()
        for content in rendered_sys:
            if content.strip():
                messages.append({"role": "system", "content": content})

        # 3. 运行时动态追加的 System Prompts
        if runtime_system_prompt:
            extras = [runtime_system_prompt] if isinstance(runtime_system_prompt, str) else runtime_system_prompt
            for content in extras:
                if content:
                    messages.append({"role": "system", "content": content})

        # 4. 插入历史记录 (来自 HistoryPayload)
        if history is not None:
            if not is_valid_history_payload(history):
                raise TypeError(
                    "history must be a valid HistoryPayload from MemoryManager.build_history(). "
                    "Got: {type(history).__name__}"
                )

            # 检查工具链完整性警告
            if history.has_tool_calls and not history.tool_chain_valid:
                logger.warning(
                    f"History contains incomplete tool chain (session={history.session_id}). "
                    "This may cause LLM errors."
                )

            # 合并历史消息
            messages.extend(history.to_list())

        # 5. User Content
        if query is not None:
            user_content = self._render_user_content(query)
            messages.append({"role": "user", "content": user_content})

        after_ctx = HookContext(
            event=HookEvent.PROMPTER_AFTER_BUILD_MESSAGES,
            component="prompter",
            data={
                "query": query,
                "messages": messages,
            },
        )
        after_ctx = self._hooks.emit_sync(HookEvent.PROMPTER_AFTER_BUILD_MESSAGES, after_ctx)
        return after_ctx.data.get("messages", messages)

    @staticmethod
    def _get_base_path():
        """Resolves the absolute path of the package root."""
        current_file = os.path.abspath(__file__)
        base_path = os.path.dirname(current_file)
        base_path = os.path.dirname(base_path)
        base_path = os.path.dirname(base_path)
        return base_path

    def load_template(self) -> [Optional[Template], str]:

        """
        Loads the template file from the configured path.

        Returns:
            Tuple[Optional[Template], str]: The compiled Jinja2 template and the raw string content.

        Raises:
            Exception: If the file cannot be read or the template cannot be compiled.
        """

        content = None

        if self.template_path:
            template_file = Path(self.template_path)

            if template_file.is_file():
                try:
                    content = template_file.read_text(encoding='utf-8')
                except Exception as e:
                    raise Exception(f"Error reading template file: {e}")

            else:
                template_path = os.path.join(self._get_base_path(), self.template_path)
                template_file = Path(template_path)
                if template_file.is_file():
                    try:
                        content = template_file.read_text(encoding='utf-8')
                    except Exception as e:
                        raise Exception(f"Error reading template file: {e}")
                print(f"Template file not found at path: {self.template_path}")

            if content:
                try:
                    self.prompt = Template(content)
                    return self.prompt, content
                except Exception as e:
                    raise Exception(f"Error initializing template: {e}")

            raise Exception(f"Template file is not loaded: {self.template_path}")

        else:
            return None, ""

    def _get_template_variables(self):
        """Analyzes the template AST to retrieve undeclared variables."""
        if not self.prompt:
            raise ValueError("Prompt is not initialized")

        parsed_content = self.env.parse(self.content)
        variables = meta.find_undeclared_variables(parsed_content)
        return [var for var in variables if var != 'query']

    def __or__(self, other: "BasePrompt") -> "ParallelPrompt":

        """Support parallel prompt execution."""

        from alphora.prompter.parallel import ParallelPrompt
        if not isinstance(other, BasePrompt):
            return NotImplemented

        if isinstance(self, ParallelPrompt):
            new_prompts = self.prompts + [other]
        else:
            new_prompts = [self, other]

        return ParallelPrompt(new_prompts)

    def load_from_string(self, prompt: str) -> None:
        """从字符串加载 User 提示词"""
        if self.env is None:
            self.env = Environment(loader=BaseLoader())

        self.prompt = self.env.from_string(prompt)
        self.content = prompt
        self.user_template = self.prompt
        self._user_prompt_raw = prompt
        self.placeholders = self._scan_all_variables()

    def render(self) -> str:
        """[兼容方法] 获取渲染后的 User 文本"""
        return self._render_user_content("{{query}}")

    def add_llm(self, model=None) -> "BasePrompt":

        """
        Binds a Language Model instance to this prompter.

        Args:
            model: The BaseLLM instance to bind.

        Returns:
            BasePrompt: The current instance for method chaining.
        """

        self.llm = model
        return self

    def call(self,
             query: str = None,
             is_stream: bool = False,
             tools: Optional[List] = None,
             multimodal_message: Message = None,
             return_generator: bool = False,
             content_type: str = None,
             postprocessor: BasePostProcessor | List[BasePostProcessor] | None = None,
             enable_thinking: bool = False,
             force_json: bool = False,
             long_response: bool = False,
             runtime_system_prompt: Union[str, List[str], None] = None,
             history: Optional[HistoryPayload] = None,
             ) -> BaseGenerator | str | Any | ToolCall:

        """
        Executes the LLM request synchronously.

        Supports standard generation, streaming, tool invocation, and long-context handling.

        Args:
            query: The user input (optional if continuing a tool chain).
            is_stream: If True, streams the response token by token.
            tools: A list of available tools/functions for the LLM.
            multimodal_message: A specialized message object for multimodal inputs.
            return_generator: If True, returns the raw generator instead of consuming it.
            content_type: MIME type override for the response.
            postprocessor: One or more processors to transform the stream output.
            enable_thinking: If True, captures reasoning traces (Chain of Thought).
            force_json: If True, attempts to repair and parse the output as JSON.
            long_response: If True, activates the LongResponseGenerator for extended outputs.
            runtime_system_prompt: System prompts injected specifically for this call.
            history: The conversation history payload.

        Returns:
            Union[PrompterOutput, ToolCall, BaseGenerator]: The generated response, tool call, or stream generator.

        Raises:
            ValueError: If the LLM has not been bound via `add_llm`.
            RuntimeError: If the execution fails during generation.
        """

        if not self.llm:
            raise ValueError("LLM not initialized. Call add_llm() first.")

        # 1. 构建消息
        messages = self.build_messages(
            query=query,
            force_json=force_json,
            runtime_system_prompt=runtime_system_prompt,
            history=history
        )

        msg_payload = messages if not multimodal_message else multimodal_message
        self._hooks.emit_sync(
            HookEvent.LLM_BEFORE_CALL,
            HookContext(
                event=HookEvent.LLM_BEFORE_CALL,
                component="llm",
                data={
                    "messages": msg_payload,
                    "tools": tools,
                    "is_stream": is_stream,
                    "force_json": force_json,
                    "long_response": long_response,
                },
            ),
        )

        # 2. 工具调用 (非流式优先)
        if tools and not is_stream:
            response = self.llm.get_non_stream_response(
                message=msg_payload, tools=tools, prompt_id=self.prompt_id
            )
            after_ctx = HookContext(
                event=HookEvent.LLM_AFTER_CALL,
                component="llm",
                data={
                    "response": response,
                    "messages": msg_payload,
                },
            )
            after_ctx = self._hooks.emit_sync(HookEvent.LLM_AFTER_CALL, after_ctx)
            return after_ctx.data.get("response", response)

        # 3. 流式调用
        if is_stream:
            try:
                gen_kwargs = {
                    "message": msg_payload,
                    "content_type": content_type or self.content_type,
                    "enable_thinking": enable_thinking,
                    "prompt_id": self.prompt_id,
                    "system_prompt": None
                }

                if tools:
                    gen_kwargs["tools"] = tools

                if long_response:
                    from alphora.prompter.long_response import LongResponseGenerator
                    generator = LongResponseGenerator(
                        llm=self.llm,
                        original_message=msg_payload,
                        **{k: v for k, v in gen_kwargs.items() if k != "message"}
                    )
                else:
                    generator = self.llm.get_streaming_response(**gen_kwargs)

                # 后处理
                if postprocessor:
                    if isinstance(postprocessor, List):
                        for p in postprocessor:
                            generator = p(generator)
                    else:
                        generator = postprocessor(generator)

                if return_generator:
                    return generator

                # 消费流
                output_str = ''
                reasoning_content = ''

                for ck in generator:
                    chunk_ctx = HookContext(
                        event=HookEvent.LLM_ON_STREAM_CHUNK,
                        component="llm",
                        data={"chunk": ck},
                    )
                    chunk_ctx = self._hooks.emit_sync(HookEvent.LLM_ON_STREAM_CHUNK, chunk_ctx)
                    ck = chunk_ctx.data.get("chunk", ck)

                    content = ck.content
                    ctype = ck.content_type

                    if ctype == 'think' and enable_thinking:
                        reasoning_content += content
                        print(content, end='', flush=True)
                        continue

                    if ctype == '[STREAM_IGNORE]':
                        output_str += content
                        continue
                    if ctype == '[RESPONSE_IGNORE]':
                        print(content, end='', flush=True)
                        continue
                    if ctype == '[BOTH_IGNORE]':
                        continue

                    if content:
                        print(content, end='', flush=True)
                        output_str += content

                # 流结束后，检查工具调用
                collected_tools = getattr(generator, 'collected_tool_calls', None)

                if tools:
                    response = ToolCall(tool_calls=collected_tools, content=output_str)
                    after_ctx = HookContext(
                        event=HookEvent.LLM_AFTER_CALL,
                        component="llm",
                        data={
                            "response": response,
                            "messages": msg_payload,
                        },
                    )
                    after_ctx = self._hooks.emit_sync(HookEvent.LLM_AFTER_CALL, after_ctx)
                    return after_ctx.data.get("response", response)

                # if collected_tools:
                #     return ToolCall(tool_calls=collected_tools, content=output_str)

                if force_json:
                    try:
                        output_str = repair_json(json_str=output_str)
                    except Exception:
                        pass

                response = PrompterOutput(
                    content=output_str,
                    reasoning=reasoning_content,
                    finish_reason=getattr(generator, 'finish_reason', ''),
                    continuation_count=getattr(generator, 'continuation_count', 0)
                )
                after_ctx = HookContext(
                    event=HookEvent.LLM_AFTER_CALL,
                    component="llm",
                    data={
                        "response": response,
                        "messages": msg_payload,
                    },
                )
                after_ctx = self._hooks.emit_sync(HookEvent.LLM_AFTER_CALL, after_ctx)
                return after_ctx.data.get("response", response)

            except Exception as e:
                raise RuntimeError(f"流式响应错误: {e}")

        else:
            # 4. 非流式
            try:
                resp = self.llm.invoke(message=msg_payload)
                response = PrompterOutput(content=resp, reasoning="", finish_reason="")
                after_ctx = HookContext(
                    event=HookEvent.LLM_AFTER_CALL,
                    component="llm",
                    data={
                        "response": response,
                        "messages": msg_payload,
                    },
                )
                after_ctx = self._hooks.emit_sync(HookEvent.LLM_AFTER_CALL, after_ctx)
                return after_ctx.data.get("response", response)
            except Exception as e:
                raise RuntimeError(f"非流式响应错误: {e}")

    async def acall(self,
                    query: str = None,
                    is_stream: bool = False,
                    tools: Optional[List] = None,
                    multimodal_message: Message = None,
                    return_generator: bool = False,
                    content_type: Optional[str] = None,
                    postprocessor: BasePostProcessor | List[BasePostProcessor] | None = None,
                    enable_thinking: bool = False,
                    force_json: bool = False,
                    long_response: bool = False,
                    runtime_system_prompt: Union[str, List[str], None] = None,
                    history: Optional[HistoryPayload] = None,
                    ) -> BaseGenerator | str | Any | ToolCall:
        """
        Asynchronously executes the LLM request.

        Mirror of `call` but optimized for async/await environments. Supports streaming, tools,
        and callback handling for real-time applications.

        Args:
            query: The user input (optional if continuing a tool chain).
            is_stream: If True, streams the response token by token.
            tools: A list of available tools/functions for the LLM.
            multimodal_message: A specialized message object for multimodal inputs.
            return_generator: If True, returns the async generator instead of consuming it.
            content_type: MIME type override for the response.
            postprocessor: One or more processors to transform the stream output.
            enable_thinking: If True, captures reasoning traces (Chain of Thought).
            force_json: If True, attempts to repair and parse the output as JSON.
            long_response: If True, activates the LongResponseGenerator for extended outputs.
            runtime_system_prompt: System prompts injected specifically for this call.
            history: The conversation history payload.

        Returns:
            Union[PrompterOutput, ToolCall, BaseGenerator]: The generated response, tool call, or stream generator.

        Example:
            prompt = BasePrompt(user_prompt="Hello, {{name}}")
            prompt.add_llm(model)
            prompt.update_placeholder(name="World")
            response = await prompt.acall(is_stream=True)
        """

        if not self.llm:
            raise ValueError("LLM not initialized. Call add_llm() first.")

        if not content_type:
            content_type = self.content_type or 'char'

        # 1. 构建消息
        messages = self.build_messages(
            query=query,
            force_json=force_json,
            runtime_system_prompt=runtime_system_prompt,
            history=history
        )
        msg_payload = messages if not multimodal_message else multimodal_message
        await self._hooks.emit(
            HookEvent.LLM_BEFORE_CALL,
            HookContext(
                event=HookEvent.LLM_BEFORE_CALL,
                component="llm",
                data={
                    "messages": msg_payload,
                    "tools": tools,
                    "is_stream": is_stream,
                    "force_json": force_json,
                    "long_response": long_response,
                },
            ),
        )

        # 2. 工具调用 (非流式优先)
        if tools and not is_stream:
            tool_resp = await self.llm.aget_non_stream_response(
                message=msg_payload, system_prompt=None, tools=tools, prompt_id=self.prompt_id
            )
            after_ctx = HookContext(
                event=HookEvent.LLM_AFTER_CALL,
                component="llm",
                data={
                    "response": tool_resp,
                    "messages": msg_payload,
                },
            )
            after_ctx = await self._hooks.emit(HookEvent.LLM_AFTER_CALL, after_ctx)
            return after_ctx.data.get("response", tool_resp)

        # 3. 流式调用
        if is_stream:
            try:
                gen_kwargs = {
                    "message": msg_payload,
                    "content_type": content_type,
                    "enable_thinking": enable_thinking,
                    "prompt_id": self.prompt_id,
                    "system_prompt": None
                }

                if tools:
                    gen_kwargs["tools"] = tools

                if long_response:
                    gen_kwargs.pop('prompt_id')
                    from alphora.prompter.long_response import LongResponseGenerator
                    generator = LongResponseGenerator(
                        llm=self.llm,
                        original_message=msg_payload,
                        **{k: v for k, v in gen_kwargs.items() if k != "message"}
                    )
                else:
                    generator = await self.llm.aget_streaming_response(**gen_kwargs)

                if postprocessor:
                    if isinstance(postprocessor, List):
                        for p in postprocessor:
                            generator = p(generator)
                    else:
                        generator = postprocessor(generator)

                if return_generator:
                    return generator

                output_str = ''
                reasoning_content = ''

                async for ck in generator:
                    chunk_ctx = HookContext(
                        event=HookEvent.LLM_ON_STREAM_CHUNK,
                        component="llm",
                        data={"chunk": ck},
                    )
                    chunk_ctx = await self._hooks.emit(HookEvent.LLM_ON_STREAM_CHUNK, chunk_ctx)
                    ck = chunk_ctx.data.get("chunk", ck)

                    content = ck.content
                    ctype = ck.content_type

                    if self.callback:
                        if ctype == 'think' and enable_thinking:
                            await self.callback.send_data(content_type=ctype, content=content)
                            reasoning_content += content
                            continue
                        if ctype == '[STREAM_IGNORE]':
                            output_str += content
                            continue
                        if ctype == '[RESPONSE_IGNORE]':
                            await self.callback.send_data(content_type=ctype, content=content)
                            continue
                        if ctype == '[BOTH_IGNORE]':
                            continue

                        await self.callback.send_data(content_type=ctype, content=content)
                        output_str += content
                    else:
                        if ctype == 'think' and enable_thinking:
                            reasoning_content += content
                            print(content, end='', flush=True)
                            continue
                        if content and ctype != '[STREAM_IGNORE]':
                            print(content, end='', flush=True)
                        if ctype != '[RESPONSE_IGNORE]':
                            output_str += content

                # 流结束后，检查工具调用
                collected_tools = getattr(generator, 'collected_tool_calls', None)

                if tools:
                    response = ToolCall(tool_calls=collected_tools, content=output_str)
                    after_ctx = HookContext(
                        event=HookEvent.LLM_AFTER_CALL,
                        component="llm",
                        data={
                            "response": response,
                            "messages": msg_payload,
                        },
                    )
                    after_ctx = await self._hooks.emit(HookEvent.LLM_AFTER_CALL, after_ctx)
                    return after_ctx.data.get("response", response)

                # 20260123 注释
                # if collected_tools:
                #     return ToolCall(tool_calls=collected_tools, content=output_str)

                if force_json:
                    try:
                        output_str = json.dumps(json.loads(repair_json(json_str=output_str)), ensure_ascii=False)
                    except:
                        pass

                response = PrompterOutput(
                    content=output_str,
                    reasoning=reasoning_content,
                    finish_reason=getattr(generator, 'finish_reason', ''),
                    continuation_count=getattr(generator, 'continuation_count', 0)
                )
                after_ctx = HookContext(
                    event=HookEvent.LLM_AFTER_CALL,
                    component="llm",
                    data={
                        "response": response,
                        "messages": msg_payload,
                    },
                )
                after_ctx = await self._hooks.emit(HookEvent.LLM_AFTER_CALL, after_ctx)
                return after_ctx.data.get("response", response)

            except Exception as e:
                if self.callback:
                    await self.callback.stop(stop_reason=str(e))
                raise RuntimeError(f"流式响应错误: {e}")

        else:
            # 4. 非流式
            try:
                resp = await self.llm.ainvoke(message=msg_payload)
                response = PrompterOutput(content=resp, reasoning="", finish_reason="")
                after_ctx = HookContext(
                    event=HookEvent.LLM_AFTER_CALL,
                    component="llm",
                    data={
                        "response": response,
                        "messages": msg_payload,
                    },
                )
                after_ctx = await self._hooks.emit(HookEvent.LLM_AFTER_CALL, after_ctx)
                return after_ctx.data.get("response", response)
            except Exception as e:
                raise RuntimeError(f"非流式响应错误: {e}")

    def __str__(self) -> str:
        try:
            sys_rendered = self._render_system_prompts()
            sys_str = ""
            if sys_rendered:
                sys_str = "[System Prompts]\n" + "\n".join([f" - {s}" for s in sys_rendered]) + "\n"
            user_str = "[User Prompt]\n" + self._render_user_content("{{query}}")
            return sys_str + "\n" + user_str
        except Exception as e:
            return f"BasePrompt (Render Error: {str(e)})"