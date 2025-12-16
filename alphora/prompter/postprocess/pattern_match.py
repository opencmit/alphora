from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor
import random
from enum import Enum, auto
from typing import Iterator, Optional, List, Union, Callable, Literal


class PatternMatcherPP(BasePostProcessor):
    """
    在流式内容中匹配特定模式，并根据配置处理匹配内容的后处理器
    """

    class State(Enum):
        """状态机"""
        NOT_MATCHING = auto()          # 不匹配状态
        PARTIAL_START_MATCH = auto()   # start_marker部分匹配
        FULL_START_MATCH = auto()      # start_marker完全匹配
        MATCHING_CONTENT = auto()      # 匹配内容中
        PARTIAL_END_MATCH = auto()     # end_marker部分匹配
        FULL_END_MATCH = auto()        # end_marker完全匹配

    def __init__(self,
                 bos: str,
                 eos: str,
                 matched_type: str = 'match',
                 buffer_size: int = 3,
                 min_buffer_size: int = 2,
                 max_buffer_size: int = 4,
                 include_bos: bool = True,
                 include_eos: bool = True,
                 output_mode: Literal['all', 'only_matched', 'exclude_matched'] = 'all',
                 unmatched_type: Optional[str] = None):
        """
        初始化模式匹配器
        bos: Beginning of Start，开始标记
        eos: End of Start，结束标记
        matched_type: 匹配内容的内容类型
        buffer_size: 缓冲区基础大小
        min_buffer_size: 缓冲区最小大小
        max_buffer_size: 缓冲区最大大小
        include_bos: 是否包含开始标记在匹配内容中
        include_eos: 是否包含结束标记在匹配内容中
        output_mode: 输出模式，可选值:
            - 'all': 输出所有内容（默认）
            - 'only_matched': 只输出匹配的内容
            - 'exclude_matched': 只输出不匹配的内容
        unmatched_type: 不匹配内容的内容类型，如果为None则保持原始类型
        """
        self.matched_type = matched_type
        self.buffer_size = buffer_size
        self.min_buffer_size = min_buffer_size
        self.max_buffer_size = max_buffer_size
        self.start_marker = bos
        self.end_marker = eos
        self.include_bos = include_bos
        self.include_eos = include_eos

        # 验证输出模式
        if output_mode not in ('all', 'only_matched', 'exclude_matched'):
            raise ValueError(f"无效的输出模式: {output_mode}。可用选项: 'all', 'only_matched', 'exclude_matched'")
        self.output_mode = output_mode

        self.unmatched_type = unmatched_type

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:

        class PatternMatchingGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self,
                         original_generator: BaseGenerator[GeneratorOutput],
                         start_marker: str,
                         end_marker: str,
                         matched_type: str,
                         buffer_size: int,
                         min_buffer_size: int,
                         max_buffer_size: int,
                         include_bos: bool,
                         include_eos: bool,
                         output_mode: str,
                         unmatched_type: Optional[str]):

                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.start_marker = start_marker
                self.end_marker = end_marker
                self.matched_type = matched_type
                self.buffer_size = buffer_size
                self.min_buffer_size = min_buffer_size
                self.max_buffer_size = max_buffer_size
                self.include_bos = include_bos
                self.include_eos = include_eos
                self.output_mode = output_mode
                self.unmatched_type = unmatched_type

                # 初始化状态和缓冲区
                self.state = PatternMatcherPP.State.NOT_MATCHING
                self.start_buffer = ""          # 开始标记缓冲区
                self.end_buffer = ""            # 结束标记缓冲区
                self.text_buffer = ""           # 不匹配状态的小文本缓冲区
                self.match_buffer = ""          # 匹配内容中的小文本缓冲区
                self.bos_buffer = ""            # 存储开始标记，用于include_bos=False的情况
                self.eos_buffer = ""            # 存储结束标记，用于include_eos=False的情况

                # 当前缓冲区大小，初始为buffer_size
                self.current_text_buffer_size = buffer_size
                self.current_match_buffer_size = buffer_size

            @staticmethod
            def get_random_buffer_size(base_size, min_size, max_size):
                """生成随机缓冲区大小"""
                return max(min_size, min(max_size, base_size + random.randint(-1, 1)))

            def generate(self) -> Iterator[GeneratorOutput]:
                """生成处理后的输出"""
                content_type: str = 'text'

                for item in self.original_generator:
                    if not isinstance(item, GeneratorOutput):
                        continue

                    content = item.content
                    content_type = item.content_type

                    for char in content:
                        if self.state == PatternMatcherPP.State.NOT_MATCHING:
                            # 不匹配状态：使用小缓冲区收集字符
                            if char == self.start_marker[0]:
                                # 当前字符与开头标识的第一个字符匹配
                                # 输出缓冲区中的内容
                                if self.text_buffer and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""

                                # 开始匹配开头标识
                                self.start_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识，添加到小缓冲区
                                self.text_buffer += char

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.PARTIAL_START_MATCH:
                            # start_marker部分匹配状态：继续检查是否匹配开头标识
                            buf_len = len(self.start_buffer)

                            if char == self.start_marker[buf_len]:
                                # 当前字符与开头标识的下一个字符匹配
                                self.start_buffer += char

                                # 检查是否完全匹配开头标识
                                if buf_len + 1 == len(self.start_marker):
                                    # 完全匹配开头标识
                                    self.bos_buffer = self.start_buffer
                                    self.start_buffer = ""  # 清空开始标记缓冲区

                                    if self.include_bos and self.output_mode != 'exclude_matched':
                                        # 输出整个开头标识
                                        yield GeneratorOutput(content=self.bos_buffer, content_type=self.matched_type)

                                    self.state = PatternMatcherPP.State.FULL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识的下一个字符
                                # 将缓冲区中的部分匹配内容添加到文本缓冲区
                                self.text_buffer += self.start_buffer + char
                                self.start_buffer = ""
                                self.state = PatternMatcherPP.State.NOT_MATCHING

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.FULL_START_MATCH:
                            # start_marker完全匹配状态：已匹配开头标识，开始收集内容
                            self.state = PatternMatcherPP.State.MATCHING_CONTENT

                            # 处理当前字符
                            if char == self.end_marker[0]:
                                # 当前字符与结束标识的第一个字符匹配
                                self.end_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识，添加到匹配缓冲区
                                self.match_buffer += char

                                # 匹配缓冲区达到指定大小，输出内容
                                if len(self.match_buffer) >= self.current_match_buffer_size and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.MATCHING_CONTENT:
                            # 匹配内容状态：继续收集内容
                            if char == self.end_marker[0]:
                                # 当前字符与结束标识的第一个字符匹配
                                # 输出匹配缓冲区中的内容
                                if self.match_buffer and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                                # 开始匹配结束标识
                                self.end_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识，添加到匹配缓冲区
                                self.match_buffer += char

                                # 匹配缓冲区达到指定大小，输出内容
                                if len(self.match_buffer) >= self.current_match_buffer_size and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.PARTIAL_END_MATCH:
                            # end_marker部分匹配状态：继续检查是否匹配结束标识
                            buf_len = len(self.end_buffer)

                            if char == self.end_marker[buf_len]:
                                # 当前字符与结束标识的下一个字符匹配
                                self.end_buffer += char

                                # 检查是否完全匹配结束标识
                                if buf_len + 1 == len(self.end_marker):
                                    # 完全匹配结束标识
                                    self.eos_buffer = self.end_buffer
                                    self.end_buffer = ""  # 清空结束标记缓冲区

                                    if self.include_eos and self.output_mode != 'exclude_matched':
                                        # 输出整个结束标识
                                        yield GeneratorOutput(content=self.eos_buffer, content_type=self.matched_type)

                                    self.state = PatternMatcherPP.State.FULL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识的下一个字符
                                # 将缓冲区中的部分匹配内容添加到匹配内容中
                                if self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.end_buffer + char, content_type=self.matched_type)

                                self.end_buffer = ""
                                self.state = PatternMatcherPP.State.MATCHING_CONTENT

                        elif self.state == PatternMatcherPP.State.FULL_END_MATCH:
                            # end_marker完全匹配状态：重置状态，继续处理
                            self.state = PatternMatcherPP.State.NOT_MATCHING

                            # 处理当前字符
                            if char == self.start_marker[0]:
                                # 当前字符与开头标识的第一个字符匹配
                                self.start_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识，添加到小缓冲区
                                self.text_buffer += char

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                # 处理可能剩余的缓冲区内容
                if self.text_buffer and self.output_mode != 'only_matched':
                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)

                if self.match_buffer and self.output_mode != 'exclude_matched':
                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)

                # 处理可能未完成的匹配
                if self.start_buffer:
                    # 将未完成的开始标记添加到文本缓冲区并输出
                    self.text_buffer += self.start_buffer
                    if self.text_buffer and self.output_mode != 'only_matched':
                        output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                        yield GeneratorOutput(content=self.text_buffer, content_type=output_type)

                if self.end_buffer:
                    # 将未完成的结束标记添加到匹配缓冲区并输出
                    self.match_buffer += self.end_buffer
                    if self.match_buffer and self.output_mode != 'exclude_matched':
                        yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                """生成处理后的输出"""
                content_type: str = 'text'

                async for item in self.original_generator:
                    if not isinstance(item, GeneratorOutput):
                        continue

                    content = item.content
                    content_type = item.content_type

                    for char in content:
                        if self.state == PatternMatcherPP.State.NOT_MATCHING:
                            # 不匹配状态：使用小缓冲区收集字符
                            if char == self.start_marker[0]:
                                # 当前字符与开头标识的第一个字符匹配
                                # 输出缓冲区中的内容
                                if self.text_buffer and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""

                                # 开始匹配开头标识
                                self.start_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识，添加到小缓冲区
                                self.text_buffer += char

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.PARTIAL_START_MATCH:
                            # start_marker部分匹配状态：继续检查是否匹配开头标识
                            buf_len = len(self.start_buffer)

                            if char == self.start_marker[buf_len]:
                                # 当前字符与开头标识的下一个字符匹配
                                self.start_buffer += char

                                # 检查是否完全匹配开头标识
                                if buf_len + 1 == len(self.start_marker):
                                    # 完全匹配开头标识
                                    self.bos_buffer = self.start_buffer
                                    self.start_buffer = ""  # 清空开始标记缓冲区

                                    if self.include_bos and self.output_mode != 'exclude_matched':
                                        # 输出整个开头标识
                                        yield GeneratorOutput(content=self.bos_buffer, content_type=self.matched_type)

                                    self.state = PatternMatcherPP.State.FULL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识的下一个字符
                                # 将缓冲区中的部分匹配内容添加到文本缓冲区
                                self.text_buffer += self.start_buffer + char
                                self.start_buffer = ""
                                self.state = PatternMatcherPP.State.NOT_MATCHING

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.FULL_START_MATCH:
                            # start_marker完全匹配状态：已匹配开头标识，开始收集内容
                            self.state = PatternMatcherPP.State.MATCHING_CONTENT

                            # 处理当前字符
                            if char == self.end_marker[0]:
                                # 当前字符与结束标识的第一个字符匹配
                                self.end_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识，添加到匹配缓冲区
                                self.match_buffer += char

                                # 匹配缓冲区达到指定大小，输出内容
                                if len(self.match_buffer) >= self.current_match_buffer_size and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.MATCHING_CONTENT:
                            # 匹配内容状态：继续收集内容
                            if char == self.end_marker[0]:
                                # 当前字符与结束标识的第一个字符匹配
                                # 输出匹配缓冲区中的内容
                                if self.match_buffer and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                                # 开始匹配结束标识
                                self.end_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识，添加到匹配缓冲区
                                self.match_buffer += char

                                # 匹配缓冲区达到指定大小，输出内容
                                if len(self.match_buffer) >= self.current_match_buffer_size and self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)
                                    self.match_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_match_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                        elif self.state == PatternMatcherPP.State.PARTIAL_END_MATCH:
                            # end_marker部分匹配状态：继续检查是否匹配结束标识
                            buf_len = len(self.end_buffer)

                            if char == self.end_marker[buf_len]:
                                # 当前字符与结束标识的下一个字符匹配
                                self.end_buffer += char

                                # 检查是否完全匹配结束标识
                                if buf_len + 1 == len(self.end_marker):
                                    # 完全匹配结束标识
                                    self.eos_buffer = self.end_buffer
                                    self.end_buffer = ""  # 清空结束标记缓冲区

                                    if self.include_eos and self.output_mode != 'exclude_matched':
                                        # 输出整个结束标识
                                        yield GeneratorOutput(content=self.eos_buffer, content_type=self.matched_type)

                                    self.state = PatternMatcherPP.State.FULL_END_MATCH
                            else:
                                # 当前字符不匹配结束标识的下一个字符
                                # 将缓冲区中的部分匹配内容添加到匹配内容中
                                if self.output_mode != 'exclude_matched':
                                    yield GeneratorOutput(content=self.end_buffer + char, content_type=self.matched_type)

                                self.end_buffer = ""
                                self.state = PatternMatcherPP.State.MATCHING_CONTENT

                        elif self.state == PatternMatcherPP.State.FULL_END_MATCH:
                            # end_marker完全匹配状态：重置状态，继续处理
                            self.state = PatternMatcherPP.State.NOT_MATCHING

                            # 处理当前字符
                            if char == self.start_marker[0]:
                                # 当前字符与开头标识的第一个字符匹配
                                self.start_buffer = char
                                self.state = PatternMatcherPP.State.PARTIAL_START_MATCH
                            else:
                                # 当前字符不匹配开头标识，添加到小缓冲区
                                self.text_buffer += char

                                # 缓冲区达到指定大小，输出内容
                                if len(self.text_buffer) >= self.current_text_buffer_size and self.output_mode != 'only_matched':
                                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)
                                    self.text_buffer = ""
                                    # 随机化下一次缓冲区大小
                                    self.current_text_buffer_size = self.get_random_buffer_size(
                                        self.buffer_size, self.min_buffer_size, self.max_buffer_size
                                    )

                # 处理可能剩余的缓冲区内容
                if self.text_buffer and self.output_mode != 'only_matched':
                    output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                    yield GeneratorOutput(content=self.text_buffer, content_type=output_type)

                if self.match_buffer and self.output_mode != 'exclude_matched':
                    yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)

                # 处理可能未完成的匹配
                if self.start_buffer:
                    # 将未完成的开始标记添加到文本缓冲区并输出
                    self.text_buffer += self.start_buffer
                    if self.text_buffer and self.output_mode != 'only_matched':
                        output_type = self.unmatched_type if self.unmatched_type is not None else content_type
                        yield GeneratorOutput(content=self.text_buffer, content_type=output_type)

                if self.end_buffer:
                    # 将未完成的结束标记添加到匹配缓冲区并输出
                    self.match_buffer += self.end_buffer
                    if self.match_buffer and self.output_mode != 'exclude_matched':
                        yield GeneratorOutput(content=self.match_buffer, content_type=self.matched_type)

        return PatternMatchingGenerator(
            generator,
            self.start_marker,
            self.end_marker,
            self.matched_type,
            self.buffer_size,
            self.min_buffer_size,
            self.max_buffer_size,
            self.include_bos,
            self.include_eos,
            self.output_mode,
            self.unmatched_type
        )
