"""
2025年1月22日：修改为仅传入路径 删除了 template_root

路径: 绝对路径，相对路径

"""
from datetime import datetime
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any

from jinja2 import Environment, Template, BaseLoader, meta

from alphora.models.message import Message
from alphora.server.stream_responser import DataStreamer

from alphora.models.llms import LLM, BaseGenerator, GeneratorOutput

from typing import TYPE_CHECKING

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ResponseWithReasoning(str):
    def __new__(cls, answer: str, reasoning: str = None):
        instance = super().__new__(cls, answer)
        instance.reasoning_content = reasoning
        return instance


class BasePrompt:
    template_path: str = None  # tmpl文件的路径
    template_desc: str = ""  # tmpl文件的描述

    def __init__(self,
                 verbose: bool = False,
                 prompt_id: str = None,
                 **kwargs):

        """
        Args:
            verbose: 是否打印大模型的中间过程
            memory: 记忆棒
            **kwargs: 占位符
        """

        self.prompt_id = prompt_id or f"pmt{str(uuid.uuid4())[:8]}"  # 用于跟踪BasePrompt

        self.is_stream: bool = False
        self.llm: LLM | None = None

        self.verbose: bool = verbose

        if self.llm:
            self.llm.verbose = self.verbose

        self.llm_data_streamer = None  # self.llm 自带的 callback

        self.context = kwargs

        self._resolved_prompt = None
        self.parser = []
        self.next_prompt = None  # 存储下一个 BasePrompt 实例

        self.prompt: Optional[Template] = None
        self.content: Optional[str] = None  # 原始的tmpl文件的内容，字符串，包含了占位符

        self.prompt, self.content = self.load_template()  # 将文件路径读取，并加载为Template和content

        self.env: Optional[Environment] = None

        if self.prompt:
            # 使用 AST 分析获取所有变量
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

    def __or__(self, other):
        from chatbi.prompts.parallel import ParallelPrompts
        """允许在BasePrompt后面加入 | 实现并行"""
        if isinstance(other, BasePrompt):
            return ParallelPrompts([self, other])
        elif isinstance(other, ParallelPrompts):
            other.prompts.append(self)
            return other
        else:
            raise TypeError("The right-hand side of the 'or' must be an instance of BasePrompt or ParallelPrompts.")

    def run(self,
            query: str,
            multimodal_message: Message = None  # 多模态数据
            ):

        """执行模型调用并使用配置的解析器处理输出。"""
        response = self.call(query=query, multimodal_message=multimodal_message)
        for parser in self.parser:
            response = parser(response)
        return response

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
            printf(title='Render Error', color='red',
                   message=f"渲染错误: {str(e)}\n上下文变量: {render_context}")
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

        if self.llm:
            self.llm.verbose = self.verbose

        self.llm_data_streamer: Optional[DataStreamer] = self.llm.callback

        return self

    def _character_level_streaming(self, output_content: GeneratorOutput) -> str:
        """
        将llm.get_streaming_response(prompt=instruction)返回的chunk转换为DataStreamer的流式输出
        chunk: JSON字符串！！
        Returns:
        """
        data_streamer: Optional[DataStreamer] = self.llm.callback

        if data_streamer:
            try:
                content = output_content.content
                content_type = output_content.content_type

                if content:
                    ctype = 'char' if content_type == 'text' else content_type
                    data_streamer.send_data(content_type=ctype, content=content)
                    return content

            except Exception as e:
                logger.error(msg=f'Streaming Parsing Error: {e}')
                return ''
        return ''

    def call(self,
             query: str = None,
             is_stream: bool = False,
             multimodal_message: Message = None,  # 多模态数据
             return_generator: bool = False,
             content_type: str = 'text',
             postprocessor: 'BasePostProcessor' | Callable[[BaseGenerator], BaseGenerator] |
                            List['BasePostProcessor'] | List[Callable[[BaseGenerator], BaseGenerator]] | None = None,
             enable_thinking: bool = False,
             system_prompt: str = None,
             return_finish_reason: bool = False
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
            system_prompt: 系统提示词
            return_finish_reason: 是否返回终止原因，对流式输出
        Returns:
        """

        if not self.llm:
            raise ValueError("LLM not initialized")

        llm: LLM = self.llm

        instruction = self.render()

        msg = multimodal_message or Message()

        if is_stream:
            try:
                if query:
                    instruction = Template(instruction)
                    instruction = instruction.render(query=query)

                msg.add_text(content=instruction)

                # 调试的时候可能需要用到输出渲染后的Prompt，平时可以注释掉
                if llm.verbose:
                    logger.info(msg=instruction)

                generator_with_content_type: BaseGenerator = llm.get_streaming_response(message=msg,
                                                                                        content_type=content_type,
                                                                                        enable_thinking=enable_thinking,
                                                                                        system_prompt=system_prompt,
                                                                                        return_finish_reason=return_finish_reason)

                # 后处理咯
                if postprocessor:
                    if isinstance(postprocessor, List):
                        processed_generator = generator_with_content_type

                        for processor in postprocessor:
                            processed_generator = processor(processed_generator)

                        generator_with_content_type = processed_generator

                    else:
                        generator_with_content_type = postprocessor(generator_with_content_type)

                data_streamer: Optional[DataStreamer] = self.llm.callback

                # 在流式模式下，有流式输出器的情况下，如果要求输出生成器，则直接返回
                if return_generator:
                    return generator_with_content_type

                # 如果llm具备callback，那么返回一个str
                output_str = ''
                reasoning_content = ''

                # for ck in generator_with_content_type:
                #     output_str += self._character_level_streaming(output_content=ck)

                for ck in generator_with_content_type:

                    content = ck.content
                    content_type = ck.content_type

                    if content_type == 'think' and enable_thinking:
                        data_streamer.send_data(content_type=content_type, content=content)
                        reasoning_content += content
                        continue

                    if content:
                        data_streamer.send_data(content_type=content_type, content=content)
                        output_str += content

                finish_reason = generator_with_content_type.finish_reason

                if return_finish_reason:
                    if enable_thinking:
                        return ResponseWithReasoning(answer=output_str, reasoning=reasoning_content), finish_reason
                    else:
                        return ResponseWithReasoning(answer=output_str), finish_reason

                if enable_thinking:
                    return ResponseWithReasoning(answer=output_str, reasoning=reasoning_content)
                else:
                    return ResponseWithReasoning(answer=output_str)

            except Exception as e:
                raise f"流式响应时发生错误: {e}"

        else:
            """
            NonStream
            """
            if query:
                instruction = Template(instruction)
                instruction = instruction.render(query=query)

            msg.add_text(content=instruction)

            if llm.verbose:
                logger.info(msg=f'调试-渲染Prompt:\n{instruction}')

            try:
                resp = llm.invoke(message=msg)

                return resp

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

    @staticmethod
    def random_split(text):
        """用于随机拆分防火墙输出的标准答案，避免逐个字符输出"""
        import random
        result = []
        while text:
            split_point = random.randint(1, max(1, len(text)))
            result.append(text[:split_point])
            text = text[split_point:]
        return result

    def __str__(self) -> str:
        try:
            rendered = self.render()
            if not rendered.strip():
                return f"BasePrompt (ID: {self.prompt_id}) - 模板未渲染或内容为空"

            return rendered

        except Exception as e:
            return f"BasePrompt (ID: {self.prompt_id}) - 渲染错误: {str(e)}"
