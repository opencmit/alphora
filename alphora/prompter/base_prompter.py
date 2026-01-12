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

if TYPE_CHECKING:
    from alphora.memory import MemoryManager

from alphora.debugger import tracer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PrompterOutput(str):

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

    def __repr__(self):
        return (f'PrompterOutput({super().__repr__()}, reasoning={self._reasoning!r}, '
                f'finish_reason={self._finish_reason!r}, continuations={self._continuation_count})')


class BasePrompt:

    def __init__(self,
                 template_path: str = None,
                 template_desc: str = "",
                 verbose: bool = False,
                 callback: Optional[DataStreamer] = None,
                 content_type: Optional[str] = None,
                 system_prompt: Optional[str] = None,
                 enable_memory: bool = False,
                 memory: Optional['MemoryManager'] = None,
                 memory_id: Optional[str] = None,
                 max_history_rounds: int = 10,
                 auto_save_memory: bool = True,
                 agent_id: str | None = None,
                 **kwargs):

        """
        Args:
            template_path: 模板文件路径（传统模式）
            template_desc: 模板描述
            verbose: 是否打印大模型的中间过程
            callback: 流式回调
            content_type: 内容类型
            system_prompt: 系统提示词（新模式，支持占位符）
            enable_memory: 是否启用记忆（仅新模式可用）
            memory: MemoryManager 实例
            memory_id: 记忆ID，用于区分不同会话
            max_history_rounds: 最大历史轮数
            auto_save_memory: 是否自动保存对话到记忆
            **kwargs: 占位符
        """

        self.agent_id = agent_id
        self.prompt_id = str(uuid.uuid4())[:8]

        self.template_path = template_path
        self.template_desc = template_desc

        self.is_stream: bool = False

        self.llm: BaseLLM | None = None
        self.callback: Optional[DataStreamer] = callback
        self.verbose: bool = verbose
        self.content_type = content_type or 'char'
        self.context = kwargs

        self._resolved_prompt = None
        self.parser = []

        self.prompt: Optional[Template] = None
        self.content: Optional[str] = None  # 原始的tmpl文件的内容，字符串，包含了占位符

        self.prompt, self.content = self.load_template()  # 将文件路径读取，并加载为Template和content

        self.env: Optional[Environment] = None

        if self.prompt:
            self.env = self.prompt.environment
            self.placeholders = self._get_template_variables()
        else:
            self.placeholders = []

        self._system_prompt_raw = system_prompt  # 原始 system_prompt（可能含占位符）
        self._system_prompt_template: Optional[Template] = None
        self.enable_memory = enable_memory
        self._memory = memory
        self._memory_id = memory_id or f"prompt_{uuid.uuid4().hex[:8]}"
        self.max_history_rounds = max_history_rounds
        self.auto_save_memory = auto_save_memory

        # 判断使用哪种模式
        self._use_new_mode = system_prompt is not None
        self._use_legacy_mode = self.prompt is not None or self.content

        # 互斥检查
        self._validate_mode()

        # 如果有 system_prompt，初始化其模板
        if self._system_prompt_raw:
            if self.env is None:
                self.env = Environment(loader=BaseLoader())
            self._system_prompt_template = self.env.from_string(self._system_prompt_raw)
            # 解析 system_prompt 中的占位符
            self._update_placeholders_from_system_prompt()

        # 如果启用记忆但没有传入 memory，自动创建内存存储的
        if self.enable_memory and self._memory is None:
            from alphora.memory import MemoryManager
            self._memory = MemoryManager()

    def _validate_mode(self):
        """验证模式互斥性"""
        # 情况1：prompt + enable_memory
        if self._use_legacy_mode and self.enable_memory:
            raise ValueError(
                "\n" + "=" * 60 + "\n"
                                  "❌ 配置错误：传统模式不支持 Memory 功能\n"
                                  "=" * 60 + "\n\n"
                                             "您同时使用了 `prompt`/`template_path` 和 `enable_memory=True`，\n"
                                             "这两种模式不能混用。\n\n"
                                             "【传统模式】使用 prompt 参数：\n"
                                             "  - 所有内容（包括历史记录）渲染后放入 role='user' 的 content\n"
                                             "  - 不支持自动记忆管理\n"
                                             "  - 适合需要完全自定义提示词结构的场景\n\n"
                                             "  示例：\n"
                                             "    prompt = create_prompt(\n"
                                             "        prompt='历史记录：{{history}}\\n请回答：{{query}}'\n"
                                             "    )\n"
                                             "    history = memory.build_history(max_round=5)\n"
                                             "    prompt.update_placeholder(history=history)\n"
                                             "    await prompt.acall(query='你好')\n\n"
                                             "【新模式】使用 system_prompt 参数：\n"
                                             "  - 支持规范的 messages 结构（system/user/assistant 分离）\n"
                                             "  - 支持自动记忆管理\n"
                                             "  - 适合需要多轮对话记忆的场景\n\n"
                                             "  示例：\n"
                                             "    prompt = create_prompt(\n"
                                             "        system_prompt='你是一个{{personality}}的助手',\n"
                                             "        enable_memory=True,\n"
                                             "        memory=memory\n"
                                             "    )\n"
                                             "    prompt.update_placeholder(personality='友好')\n"
                                             "    await prompt.acall(query='你好')  # 自动管理历史\n\n"
                                             "请选择其中一种模式使用。"
                                             "\n" + "=" * 60
            )

        # 情况2：prompt + system_prompt
        if self._use_legacy_mode and self._use_new_mode:
            raise ValueError(
                "\n" + "=" * 60 + "\n"
                                  "❌ 配置错误：不能同时使用 prompt 和 system_prompt\n"
                                  "=" * 60 + "\n\n"
                                             "您同时使用了 `prompt`/`template_path` 和 `system_prompt`，\n"
                                             "这两种模式不能混用。\n\n"
                                             "【传统模式】使用 prompt 参数：\n"
                                             "  prompt = create_prompt(\n"
                                             "      prompt='你是助手。历史：{{history}}\\n问题：{{query}}'\n"
                                             "  )\n\n"
                                             "【新模式】使用 system_prompt 参数：\n"
                                             "  prompt = create_prompt(\n"
                                             "      system_prompt='你是一个友好的助手',\n"
                                             "      enable_memory=True\n"
                                             "  )\n\n"
                                             "请选择其中一种模式使用。"
                                             "\n" + "=" * 60
            )

    def _update_placeholders_from_system_prompt(self):
        """从 system_prompt 中提取占位符并合并"""
        if self._system_prompt_raw and self.env:
            parsed = self.env.parse(self._system_prompt_raw)
            variables = meta.find_undeclared_variables(parsed)
            new_vars = [var for var in variables if var != 'query']
            # 合并到 placeholders
            for var in new_vars:
                if var not in self.placeholders:
                    self.placeholders.append(var)

    def _render_system_prompt(self) -> Optional[str]:
        """渲染 system_prompt（应用占位符）"""
        if not self._system_prompt_template:
            return None

        try:
            return self._system_prompt_template.render(self.context)
        except Exception as e:
            logger.error(f"渲染 system_prompt 错误: {e}")
            return self._system_prompt_raw

    @property
    def memory(self) -> Optional['MemoryManager']:
        """获取记忆管理器"""
        return self._memory

    @memory.setter
    def memory(self, value: 'MemoryManager'):
        """设置记忆管理器"""
        self._memory = value
        if value is not None:
            self.enable_memory = True

    @property
    def memory_id(self) -> str:
        """获取记忆ID"""
        return self._memory_id

    @memory_id.setter
    def memory_id(self, value: str):
        """设置记忆ID"""
        self._memory_id = value

    def get_memory(self) -> Optional['MemoryManager']:
        """
        获取记忆管理器实例

        可用于：
        - 共享给其他 Prompt
        - 手动操作记忆（添加、搜索等）
        - 获取历史记录

        Returns:
            MemoryManager 实例
        """
        return self._memory

    def set_memory(
            self,
            memory: 'MemoryManager',
            memory_id: Optional[str] = None
    ) -> 'BasePrompt':
        """
        设置记忆管理器

        Args:
            memory: MemoryManager 实例
            memory_id: 记忆ID（可选）

        Returns:
            self（支持链式调用）
        """
        self._memory = memory
        if memory_id:
            self._memory_id = memory_id
        self.enable_memory = True
        return self

    def clear_memory(self) -> 'BasePrompt':
        """
        清空当前 memory_id 的记忆

        Returns:
            self（支持链式调用）
        """
        if self._memory:
            self._memory.clear_memory(self._memory_id)
        return self

    def get_history(
            self,
            format: Literal["text", "messages"] = "messages",
            max_round: Optional[int] = None
    ) -> Union[str, List[Dict[str, str]]]:
        """
        获取对话历史

        Args:
            format: 输出格式
                - "messages": List[Dict]，可直接用于 LLM
                - "text": 字符串格式
            max_round: 最大轮数（不传则使用 max_history_rounds）

        Returns:
            对话历史
        """
        if not self._memory:
            return [] if format == "messages" else ""

        return self._memory.build_history(
            memory_id=self._memory_id,
            max_round=max_round or self.max_history_rounds,
            format=format,
            include_timestamp=False
        )

    def _build_messages_for_new_mode(
            self,
            query: str,
            force_json: bool = False
    ) -> List[Dict[str, str]]:
        """
        构建新模式下的 messages 列表
        
        结构：
        1. [可选] force_json 的 system message
        2. system_prompt（渲染后）
        3. 历史对话（从 memory 获取）
        4. 当前用户输入（query 原文）
        """
        messages = []

        # 1. force_json 提示
        if force_json:
            messages.append({
                "role": "system",
                "content": "请严格使用 JSON 格式输出"
            })

        # 2. system_prompt
        rendered_system = self._render_system_prompt()
        if rendered_system:
            messages.append({
                "role": "system",
                "content": rendered_system
            })

        # 3. 历史对话
        if self.enable_memory and self._memory:
            history = self._memory.build_history(
                memory_id=self._memory_id,
                max_round=self.max_history_rounds,
                format="messages",
                include_timestamp=False
            )
            if history:
                messages.extend(history)

        # 4. 当前用户输入
        messages.append({
            "role": "user",
            "content": query
        })

        return messages

    def _save_to_memory(self, query: str, response: str):
        """保存对话到记忆（query 原文 + LLM 响应原文）"""
        if self.enable_memory and self._memory and self.auto_save_memory:
            self._memory.add_memory("user", query, memory_id=self._memory_id)
            self._memory.add_memory("assistant", response, memory_id=self._memory_id)

    @staticmethod
    def _get_base_path():
        """
        自动获取包的绝对路径
        Returns:
        """

        current_file = os.path.abspath(__file__)

        base_path = os.path.dirname(current_file)
        base_path = os.path.dirname(base_path)
        base_path = os.path.dirname(base_path)

        return base_path

    def load_template(self) -> [Optional[Template], str]:
        """
        加载 template_path 为
        Returns:
        """
        content = None

        # 尝试使用传入路径加载模板
        if self.template_path:
            template_file = Path(self.template_path)

            if template_file.is_file():
                try:
                    content = template_file.read_text(encoding='utf-8')
                except Exception as e:
                    raise Exception(f"Error reading template file: {e}")

            else:
                # 尝试使用项目的绝对位置来拼接
                template_path = os.path.join(self._get_base_path(), self.template_path)
                template_file = Path(template_path)
                if template_file.is_file():
                    try:
                        content = template_file.read_text(encoding='utf-8')
                    except Exception as e:
                        raise Exception(f"Error reading template file: {e}")
                print(f"Template file not found at path: {self.template_path}")

            # 加载模板内容到 self.prompt
            if content:
                try:
                    self.prompt = Template(content)
                    return self.prompt, content
                except Exception as e:
                    raise Exception(f"Error initializing template: {e}")

            raise Exception(f"Template file is not loaded: {self.template_path}")

        else:
            # 当template_path为None时，直接返回None
            return None, ""

    def _get_template_variables(self):
        """使用AST分析获取所有变量"""
        if not self.prompt:
            raise ValueError("Prompt is not initialized")

        parsed_content = self.env.parse(self.content)
        variables = meta.find_undeclared_variables(parsed_content)
        return [var for var in variables if var != 'query']

    def __or__(self, other: "BasePrompt") -> "ParallelPrompt":
        from alphora.prompter.parallel import ParallelPrompt
        if not isinstance(other, BasePrompt):
            return NotImplemented

        if isinstance(self, ParallelPrompt):
            new_prompts = self.prompts + [other]
        else:
            new_prompts = [self, other]

        return ParallelPrompt(new_prompts)

    def render(self) -> str:
        """渲染 Prompt 包含了占位符的渲染！"""
        # 确保 context 是字典类型
        if not isinstance(self.context, dict):
            self.context = {}

        # 添加 query 占位符
        render_context = self.context.copy()
        render_context["query"] = "{{query}}"

        try:
            # 渲染模板
            rendered = self.prompt.render(render_context)
            # 清理多余的空行，但保留基本格式
            rendered = re.sub(r'\n{3,}', '\n\n', rendered.strip())
            return rendered
        except Exception as e:
            logger.error(msg=f"渲染错误: {str(e)}\n 上下文变量: {render_context}")
            return ""

    def load_from_string(self, prompt: str) -> None:
        """
        从传入的Prompt String加载提示词
        Args:
            prompt: String
        Returns: None
        """
        if self.env is None:
            self.env = Environment(loader=BaseLoader())

        self.prompt = self.env.from_string(prompt)
        self.content = prompt

        self.placeholders = self._get_template_variables()  # 更新占位符列表

        self._use_legacy_mode = True
        # 重新验证模式
        if self.enable_memory or self._system_prompt_raw:
            self._validate_mode()

    def add_llm(self, model=None) -> "BasePrompt":
        """
        241025修改，支持解耦调用
        -241127更新，增加支持混合流式

        add_llm(model=qwen')

        Args:
            model:BaseLLM
        Returns: BasePrompt
        """
        self.llm = model
        return self

    def call(self,
             query: str = None,
             is_stream: bool = False,
             multimodal_message: Message = None,  # 多模态数据
             return_generator: bool = False,
             content_type: str = None,
             postprocessor: 'BasePostProcessor' | Callable[[BaseGenerator], BaseGenerator] |
                            List['BasePostProcessor'] | List[Callable[[BaseGenerator], BaseGenerator]] | None = None,
             enable_thinking: bool = False,
             force_json: bool = False,
             long_response: bool = False,
             system_prompt: str = None,
             save_to_memory: Optional[bool] = None,
             ) -> BaseGenerator | str | Any:
        """
        调用大模型对Prompt进行推理
        Args:
            content_type:
            query: 用户问题（传统模式下是 Prompt 中的 query 占位符，新模式下是用户输入原文）
            is_stream: 是否输出流式
            multimodal_message: # 包含图片、视频、语音等多模态数据
            return_generator: 是否返回生成器，默认返回字符串，并做流式输出，如果此项为True，则仅返回生成器
            postprocessor: 后处理器
            enable_thinking: 是否开启思考
            force_json: 强制Json
            long_response: 是否启用长响应模式（自动续写）
            system_prompt: 系统提示词（传统模式下使用）
            save_to_memory: 是否保存到记忆（新模式下有效，默认使用 auto_save_memory）
        Returns:
        """

        if not self.llm:
            raise ValueError("LLM not initialized")

        use_new_mode = self._use_new_mode and not multimodal_message  # 新模式，但多模态暂不支持

        if use_new_mode:
            # 构建规范的 messages 列表
            messages = self._build_messages_for_new_mode(query=query, force_json=force_json)
            msg = None  # 不使用 Message 对象
            instruction = None
        else:
            messages = None
            system_prompt = system_prompt
            if force_json:
                system_prompt = "必须输出Json格式"

            instruction = self.render()
            msg = multimodal_message or Message()

            if query:
                instruction = Template(instruction)
                instruction = instruction.render(query=query)

            msg.add_text(content=instruction)

        if is_stream:
            logger.warning(
                f"\n当前Prompter{self.__class__.__name__}使用同步方法 `call`，无法向客户端发送流式响应；"
                "请改用异步方法 `acall`。"
                " [Synchronous `call` does not support client streaming; use `acall` for API streaming.]\n"
            )

            try:
                # 根据是否启用长响应模式选择不同的生成器
                if long_response:
                    from alphora.prompter.long_response import LongResponseGenerator

                    generator_with_content_type = LongResponseGenerator(
                        llm=self.llm,
                        original_message=msg,
                        content_type=content_type or self.content_type,
                        system_prompt=system_prompt,
                        enable_thinking=enable_thinking
                    )
                else:
                    if use_new_mode:
                        generator_with_content_type: BaseGenerator = self.llm.get_streaming_response(
                            message=messages,
                            content_type=content_type,
                            enable_thinking=enable_thinking,
                        )
                    else:
                        generator_with_content_type: BaseGenerator = self.llm.get_streaming_response(
                            message=msg,
                            content_type=content_type,
                            enable_thinking=enable_thinking,
                            system_prompt=system_prompt
                        )

                # 后处理咯
                if postprocessor:
                    if isinstance(postprocessor, List):
                        processed_generator = generator_with_content_type

                        for processor in postprocessor:
                            processed_generator = processor(processed_generator)

                        generator_with_content_type = processed_generator

                    else:
                        generator_with_content_type = postprocessor(generator_with_content_type)

                # 在流式模式下，有流式输出器的情况下，如果要求输出生成器，则直接返回
                if return_generator:
                    return generator_with_content_type

                # 如果llm具备callback，那么返回一个str
                output_str = ''
                reasoning_content = ''
                continuation_count = 0

                for ck in generator_with_content_type:

                    content = ck.content
                    content_type = ck.content_type

                    if content_type == 'think' and enable_thinking:
                        reasoning_content += content
                        print(content, end='', flush=True)
                        continue

                    if content and content_type == '[STREAM_IGNORE]':
                        output_str += content
                        continue

                    if content and content_type == '[RESPONSE_IGNORE]':
                        # 只流式输出，不拼接到返回里面
                        print(content, end='', flush=True)
                        continue

                    if content_type == '[BOTH_IGNORE]':
                        # 不流式输出，也不拼接到返回里
                        continue

                    if content and content_type not in ['[STREAM_IGNORE]', '[RESPONSE_IGNORE]']:
                        # 又流式输出，又拼接到返回
                        print(content, end='', flush=True)
                        output_str += content
                        continue

                if force_json:
                    try:
                        output_str = repair_json(json_str=output_str)
                    except Exception as e:
                        logger.warning(f"无法将输出解析为Json，可能的原因：1、使用了 JsonKeyExtractorPP 并且output_mode='target_only'，如是，请将output_mode设置为'both' 2、该提示词下无法生成Json格式")

                finish_reason = generator_with_content_type.finish_reason

                # 获取续写次数（如果是长响应模式）
                if long_response and hasattr(generator_with_content_type, 'continuation_count'):
                    continuation_count = generator_with_content_type.continuation_count

                if self.verbose:
                    if use_new_mode:
                        logger.info(msg=f'\n\nMessages:\n{messages}\n\n\nResponse:\n{output_str}')
                    else:
                        logger.info(msg=f'\n\nInstruction:\n{instruction}\n\n\nResponse:\n{output_str}')

                should_save = save_to_memory if save_to_memory is not None else self.auto_save_memory
                if should_save and use_new_mode:
                    self._save_to_memory(query, output_str)

                if enable_thinking:
                    return PrompterOutput(content=output_str, reasoning=reasoning_content,
                                          finish_reason=finish_reason, continuation_count=continuation_count)
                else:
                    return PrompterOutput(content=output_str, reasoning="",
                                          finish_reason=finish_reason, continuation_count=continuation_count)

            except Exception as e:
                raise RuntimeError(f"流式响应时发生错误: {e}")

        else:
            """
            NonStream
            """

            try:
                if use_new_mode:
                    resp = self.llm.invoke(message=messages)
                else:
                    resp = self.llm.invoke(message=msg)

                should_save = save_to_memory if save_to_memory is not None else self.auto_save_memory
                if should_save and use_new_mode:
                    self._save_to_memory(query, resp)

                return PrompterOutput(content=resp, reasoning="", finish_reason="")

            except Exception as e:
                raise RuntimeError(f"非流式响应时发生错误: {e}")

    async def acall(self,
                    query: str = None,
                    is_stream: bool = False,
                    multimodal_message: Message = None,  # 多模态数据
                    return_generator: bool = False,
                    content_type: Optional[str] = None,
                    postprocessor: 'BasePostProcessor' | Callable[[BaseGenerator], BaseGenerator] |
                                   List['BasePostProcessor'] | List[
                                       Callable[[BaseGenerator], BaseGenerator]] | None = None,
                    enable_thinking: bool = False,
                    force_json: bool = False,
                    long_response: bool = False,
                    system_prompt: str = None,
                    save_to_memory: Optional[bool] = None,
                    ) -> BaseGenerator | str | Any:
        """
        调用大模型对Prompt进行推理
        Args:
            content_type:
            query: 用户问题（传统模式下是 Prompt 中的 query 占位符，新模式下是用户输入原文）
            is_stream: 是否输出流式
            multimodal_message: # 包含图片、视频、语音等多模态数据
            return_generator: 是否返回生成器，默认返回字符串，并做流式输出，如果此项为True，则仅返回生成器
            postprocessor: 后处理器
            enable_thinking: 是否开启思考
            force_json: 强制Json
            long_response: 是否启用长响应模式（自动续写）
            system_prompt: 系统提示词（传统模式下使用）
            save_to_memory: 是否保存到记忆（新模式下有效）
        Returns:
        """

        if not self.llm:
            raise ValueError("LLM not initialized")

        if not content_type:
            content_type = self.content_type or 'char'

        _debug_agent_id = getattr(self, '_debug_agent_id', 'unknown')

        # 追踪Prompt调用开始
        _prompt_call_id = tracer.track_prompt_call_start(
            agent_id=_debug_agent_id,
            prompt_id=self.prompt_id,
            query=query or "",
            is_stream=is_stream
        )

        start_time = time.time()

        use_new_mode = self._use_new_mode and not multimodal_message

        if use_new_mode:
            messages = self._build_messages_for_new_mode(query=query, force_json=force_json)
            msg = None
            instruction = None
        else:
            # 传统模式
            messages = None
            system_prompt = system_prompt

            if force_json:
                system_prompt = "必须输出Json格式"

            instruction = self.render()
            msg = multimodal_message or Message()

            if query:
                instruction = Template(instruction)
                instruction = instruction.render(query=query)

            msg.add_text(content=instruction)

        if is_stream:
            # 追踪LLM调用开始
            _debug_call_id = tracer.track_llm_start(
                agent_id=_debug_agent_id,
                model_name=getattr(self.llm, 'model_name', 'unknown'),
                messages=messages if use_new_mode else None,
                input_text=str(query) if not use_new_mode else "",
                is_streaming=True,
                prompt_id=self.prompt_id
            )
            try:
                # 根据是否启用长响应模式选择不同的生成器
                if long_response:
                    from alphora.prompter.long_response import LongResponseGenerator

                    generator_with_content_type = LongResponseGenerator(
                        llm=self.llm,
                        original_message=msg,
                        content_type=content_type,
                        system_prompt=system_prompt,
                        enable_thinking=enable_thinking
                    )
                else:
                    if use_new_mode:
                        generator_with_content_type: BaseGenerator = await self.llm.aget_streaming_response(
                            message=messages,
                            content_type=content_type,
                            enable_thinking=enable_thinking,
                        )
                    else:
                        generator_with_content_type: BaseGenerator = await self.llm.aget_streaming_response(
                            message=msg,
                            content_type=content_type,
                            enable_thinking=enable_thinking,
                            system_prompt=system_prompt
                        )

                # 后处理
                if postprocessor:
                    if isinstance(postprocessor, List):
                        processed_generator = generator_with_content_type

                        for processor in postprocessor:
                            processed_generator = processor(processed_generator)

                        generator_with_content_type = processed_generator

                    else:
                        generator_with_content_type = postprocessor(generator_with_content_type)

                # 在流式模式下，有流式输出器的情况下，如果要求输出生成器，则直接返回
                if return_generator:
                    return generator_with_content_type

                # 如果llm具备callback，那么返回一个str
                output_str = ''
                reasoning_content = ''
                continuation_count = 0

                async for ck in generator_with_content_type:

                    content = ck.content
                    content_type = ck.content_type

                    # 追踪每个流式chunk
                    tracer.track_llm_stream_chunk(
                        call_id=_debug_call_id,
                        content=content,
                        content_type=content_type,
                        is_reasoning=(content_type == 'think')
                    )

                    if self.callback:

                        if content_type == 'think' and enable_thinking:
                            await self.callback.send_data(content_type=content_type, content=content)
                            reasoning_content += content
                            continue

                        if content and content_type == '[STREAM_IGNORE]':
                            output_str += content
                            continue

                        if content and content_type == '[RESPONSE_IGNORE]':
                            # 只流式输出，不拼接到返回里面
                            await self.callback.send_data(content_type=content_type, content=content)
                            continue

                        if content_type == '[BOTH_IGNORE]':
                            # 不流式输出，也不拼接到返回里
                            continue

                        if content and content_type not in ['[STREAM_IGNORE]', '[RESPONSE_IGNORE]']:
                            # 又流式输出，又拼接到返回
                            await self.callback.send_data(content_type=content_type, content=content)
                            output_str += content
                            continue

                    else:
                        if content_type == 'think' and enable_thinking:
                            reasoning_content += content
                            print(content, end='', flush=True)
                            continue

                        if content and content_type == '[STREAM_IGNORE]':
                            output_str += content
                            continue

                        if content and content_type == '[RESPONSE_IGNORE]':
                            # 只流式输出，不拼接到返回里面
                            print(content, end='', flush=True)
                            continue

                        if content_type == '[BOTH_IGNORE]':
                            # 不流式输出，也不拼接到返回里
                            continue

                        if content and content_type not in ['[STREAM_IGNORE]', '[RESPONSE_IGNORE]']:
                            # 又流式输出，又拼接到返回
                            print(content, end='', flush=True)
                            output_str += content
                            continue

                if force_json:
                    try:
                        output_str = json.dumps(json.loads(repair_json(json_str=output_str)), ensure_ascii=False)
                    except Exception as e:
                        logger.warning(f"无法将输出解析为Json，可能的原因：1、使用了 JsonKeyExtractorPP 并且output_mode='target_only'，如是，请将output_mode设置为'both' 2、该提示词下无法生成Json格式")
                        pass
                        # raise RuntimeError(f"该提示词下无法将输出解析为Json，请修改提示词或将 `force_json` 设为 False 再尝试")

                finish_reason = generator_with_content_type.finish_reason

                # 获取续写次数（如果是长响应模式）
                if long_response and hasattr(generator_with_content_type, 'continuation_count'):
                    continuation_count = generator_with_content_type.continuation_count

                if self.verbose:
                    if use_new_mode:
                        logger.info(msg=f'\n\nMessages:\n{messages}\n\n\nResponse:\n{output_str}')
                    else:
                        logger.info(msg=f'\n\nInstruction:\n{instruction}\n\n\nResponse:\n{output_str}')

                should_save = save_to_memory if save_to_memory is not None else self.auto_save_memory
                if should_save and use_new_mode:
                    self._save_to_memory(query, output_str)

                if enable_thinking:
                    return PrompterOutput(content=output_str, reasoning=reasoning_content,
                                          finish_reason=finish_reason, continuation_count=continuation_count)
                else:
                    return PrompterOutput(content=output_str, reasoning="",
                                          finish_reason=finish_reason, continuation_count=continuation_count)

            except Exception as e:
                # tracer.track_llm_error(_debug_call_id, str(e))
                if self.callback:
                    await self.callback.stop(stop_reason=str(e))
                raise RuntimeError(f"流式响应时发生错误: {e}")

        else:
            """
            NonStream
            """

            try:
                if use_new_mode:
                    resp = await self.llm.ainvoke(message=messages)
                else:
                    resp = await self.llm.ainvoke(message=msg)

                should_save = save_to_memory if save_to_memory is not None else self.auto_save_memory
                if should_save and use_new_mode:
                    self._save_to_memory(query, resp)

                # tracer.track_llm_end(
                #     call_id=_debug_call_id,
                #     output_text=resp
                # )

                return PrompterOutput(content=resp, reasoning="", finish_reason="")

            except Exception as e:
                raise RuntimeError(f"非流式响应时发生错误: {e}")

    def update_placeholder(self, **kwargs):
        """更新占位符值（同时支持 prompt 和 system_prompt 中的占位符）"""
        invalid_placeholders = [k for k in kwargs if k not in self.placeholders]
        missing_placeholders = [p for p in self.placeholders if p not in kwargs and p not in self.context]

        if invalid_placeholders:
            logger.info(
                msg=f"以下占位符不存在: <{', '.join(invalid_placeholders)}>\n"
                    f"可用的占位符: {', '.join(self.placeholders)}。\n"
                    f"提示词模板:{self.__class__.__name__};\n"
                    f"路径:{self.template_path}"
            )

        if missing_placeholders:
            logger.info(
                msg=f"以下占位符未提供值: <{', '.join(missing_placeholders)}>\n"
                    f"提示词模板:{self.__class__.__name__};\n"
                    f"路径:{self.template_path}"
            )

        # 更新上下文，仅使用有效的占位符
        valid_kwargs = {k: v for k, v in kwargs.items() if k in self.placeholders}

        self.context.update(valid_kwargs)

        if self._use_new_mode:
            tracer.track_prompt_render(agent_id=self.agent_id, prompt_id=self.prompt_id, rendered_prompt=self._render_system_prompt(), placeholders=valid_kwargs)
        else:
            tracer.track_prompt_render(agent_id=self.agent_id, prompt_id=self.prompt_id, rendered_prompt=self.render(), placeholders=valid_kwargs)
        return self

    def __str__(self) -> str:
        try:
            if self._use_new_mode:
                rendered = self._render_system_prompt()
                if rendered:
                    return f"[新模式] system_prompt: {rendered}"
                return "BasePrompt - system_prompt 未渲染或内容为空"

            rendered = self.render()
            if not rendered.strip():
                return f"BasePrompt - 模板未渲染或内容为空"

            return rendered

        except Exception as e:
            return f"BasePrompt (渲染错误: {str(e)})"
