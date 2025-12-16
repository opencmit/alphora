import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Callable, Any

from jinja2 import Environment, Template, BaseLoader, meta

from alphora.models.message import Message
from alphora.prompter.postprocess.base import BasePostProcessor
from alphora.server.stream_responser import DataStreamer

from json_repair import repair_json

from alphora.models.llms.base import BaseLLM
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PrompterOutput(str):
    def __new__(cls, content: str, reasoning: str = "", finish_reason: str = ""):
        instance = super().__new__(cls, content)
        instance._reasoning = reasoning
        instance._finish_reason = finish_reason
        return instance

    @property
    def reasoning(self):
        return self._reasoning

    @property
    def finish_reason(self):
        return self._finish_reason

    def __repr__(self):
        return f'PrompterOutput({super().__repr__()}, reasoning={self._reasoning!r}, finish_reason={self._finish_reason!r})'


class BasePrompt:

    def __init__(self,
                 template_path: str = None,
                 template_desc: str = "",
                 verbose: bool = False,
                 callback: Optional[DataStreamer] = None,
                 **kwargs):

        """
        Args:
            verbose: 是否打印大模型的中间过程
            memory: 记忆棒
            **kwargs: 占位符
        """

        self.template_path = template_path
        self.template_desc = template_desc

        self.is_stream: bool = False

        self.llm: BaseLLM | None = None
        self.callback: Optional[DataStreamer] = callback
        self.verbose: bool = verbose

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

        pass

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
             content_type: str = 'text',
             postprocessor: 'BasePostProcessor' | Callable[[BaseGenerator], BaseGenerator] |
                            List['BasePostProcessor'] | List[Callable[[BaseGenerator], BaseGenerator]] | None = None,
             enable_thinking: bool = False,
             force_json: bool = False
             ) -> BaseGenerator | str | Any:
        """
        调用大模型对Prompt进行推理
        Args:
            content_type:
            query: 用户问题（Prompt中的query占位符）
            is_stream: 是否输出流式
            multimodal_message: # 包含图片、视频、语音等多模态数据
            return_generator: 是否返回生成器，默认返回字符串，并做流式输出，如果此项为True，则仅返回生成器
            postprocessor: 后处理器
            enable_thinking: 是否开启思考
            force_json: 强制Json
        Returns:
        """

        if not self.llm:
            raise ValueError("LLM not initialized")

        system_prompt = None

        if force_json:
            system_prompt = "必须输出Json格式"

        instruction = self.render()

        msg = multimodal_message or Message()

        if query:
            instruction = Template(instruction)
            instruction = instruction.render(query=query)

        msg.add_text(content=instruction)

        if is_stream:
            try:
                generator_with_content_type: BaseGenerator = self.llm.get_streaming_response(message=msg,
                                                                                             content_type=content_type,
                                                                                             enable_thinking=enable_thinking,
                                                                                             system_prompt=system_prompt)

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

                for ck in generator_with_content_type:

                    content = ck.content
                    content_type = ck.content_type

                    if self.callback:

                        if content_type == 'think' and enable_thinking:
                            self.callback.send_data(content_type=content_type, content=content)
                            reasoning_content += content
                            continue

                        if content:
                            self.callback.send_data(content_type=content_type, content=content)
                            output_str += content
                    else:
                        if content_type == 'think' and enable_thinking:
                            reasoning_content += content
                            print(content, end='', flush=True)
                            continue

                        if content:
                            output_str += content
                            print(content, end='', flush=True)

                if force_json:
                    try:
                        output_str = repair_json(json_str=output_str)
                    except Exception as e:
                        raise Exception(e)

                finish_reason = generator_with_content_type.finish_reason

                if self.verbose:
                    logger.info(msg=f'\n\nInstruction:\n{instruction}\n\n\nResponse:\n{output_str}')

                if enable_thinking:
                    return PrompterOutput(content=output_str, reasoning=reasoning_content, finish_reason=finish_reason)
                else:
                    return PrompterOutput(content=output_str, reasoning="", finish_reason=finish_reason)

            except Exception as e:
                raise f"流式响应时发生错误: {e}"

        else:
            """
            NonStream
            """

            try:
                resp = self.llm.invoke(message=msg)

                return PrompterOutput(content=resp, reasoning="", finish_reason="")

            except Exception as e:
                raise e

    async def acall(self,
                    query: str = None,
                    is_stream: bool = False,
                    multimodal_message: Message = None,  # 多模态数据
                    return_generator: bool = False,
                    content_type: str = 'text',
                    postprocessor: 'BasePostProcessor' | Callable[[BaseGenerator], BaseGenerator] |
                                   List['BasePostProcessor'] | List[
                                       Callable[[BaseGenerator], BaseGenerator]] | None = None,
                    enable_thinking: bool = False,
                    force_json: bool = False
                    ) -> BaseGenerator | str | Any:
        """
        调用大模型对Prompt进行推理
        Args:
            content_type:
            query: 用户问题（Prompt中的query占位符）
            is_stream: 是否输出流式
            multimodal_message: # 包含图片、视频、语音等多模态数据
            return_generator: 是否返回生成器，默认返回字符串，并做流式输出，如果此项为True，则仅返回生成器
            postprocessor: 后处理器
            enable_thinking: 是否开启思考
            force_json: 强制Json
        Returns:
        """

        if not self.llm:
            raise ValueError("LLM not initialized")

        system_prompt = None

        if force_json:
            system_prompt = "必须输出Json格式"

        instruction = self.render()

        msg = multimodal_message or Message()

        if query:
            instruction = Template(instruction)
            instruction = instruction.render(query=query)

        msg.add_text(content=instruction)

        if is_stream:
            try:

                generator_with_content_type: BaseGenerator = await self.llm.aget_streaming_response(message=msg,
                                                                                                    content_type=content_type,
                                                                                                    enable_thinking=enable_thinking,
                                                                                                    system_prompt=system_prompt)

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

                async for ck in generator_with_content_type:

                    content = ck.content
                    content_type = ck.content_type

                    if self.callback:

                        if content_type == 'think' and enable_thinking:
                            await self.callback.send_data(content_type=content_type, content=content)
                            reasoning_content += content
                            continue

                        if content:
                            await self.callback.send_data(content_type=content_type, content=content)
                            output_str += content

                    else:
                        if content_type == 'think' and enable_thinking:
                            reasoning_content += content
                            print(content, end='', flush=True)
                            continue

                        if content:
                            output_str += content
                            print(content, end='', flush=True)

                if force_json:
                    try:
                        output_str = json.dumps(json.loads(repair_json(json_str=output_str)), ensure_ascii=False)
                    except Exception as e:
                        raise Exception(e)

                finish_reason = generator_with_content_type.finish_reason

                if self.verbose:
                    logger.info(msg=f'\n\nInstruction:\n{instruction}\n\n\nResponse:\n{output_str}')

                if enable_thinking:
                    return PrompterOutput(content=output_str, reasoning=reasoning_content, finish_reason=finish_reason)
                else:
                    return PrompterOutput(content=output_str, reasoning="", finish_reason=finish_reason)

            except Exception as e:
                raise f"流式响应时发生错误: {e}"

        else:
            """
            NonStream
            """

            try:
                resp = await self.llm.ainvoke(message=msg)

                return PrompterOutput(content=resp, reasoning="", finish_reason="")

            except Exception as e:
                raise e

    def update_placeholder(self, **kwargs):
        """更新占位符值"""
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

        return self

    def __str__(self) -> str:
        try:
            rendered = self.render()
            if not rendered.strip():
                return f"BasePrompt (ID: {self.prompt_id}) - 模板未渲染或内容为空"

            return rendered

        except Exception as e:
            return f"BasePrompt (ID: {self.prompt_id}) - 渲染错误: {str(e)}"
