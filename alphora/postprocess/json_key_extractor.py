import re
from typing import Iterator, AsyncIterator
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.base import BasePostProcessor


class JsonKeyExtractorPP(BasePostProcessor):
    """
    流式 JSON key 提取后处理器
    支持大段chunk处理，精准提取目标key的完整value
    """

    def __init__(
            self,
            target_key: str,
            stop_on_comma_or_brace: bool = True,
            content_type: str = "text"
    ):
        self.target_key = target_key
        self.stop_on_comma_or_brace = stop_on_comma_or_brace
        self.output_content_type = content_type

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        class JsonKeyExtractingGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator: BaseGenerator[GeneratorOutput], target_key: str, stop_flag: bool, out_type: str):
                super().__init__(out_type)
                self.original_generator = original_generator
                self.target_key = target_key
                self.stop_on_comma_or_brace = stop_flag

                # 核心状态变量
                self.buffer = ""  # 全量缓冲区
                self.in_target_value = False  # 是否进入目标value区域
                self.finished = False  # 是否提取完成
                self.value_start_pos = -1  # 目标value的起始位置（全局buffer中）

                # JSON解析状态（精细化）
                self.quote_open = False  # 是否在字符串引号内
                self.escape_next = False  # 是否下一个字符是转义
                self.nest_level = 0  # 当前value内的嵌套层级
                self.value_quote_type = None  # 目标value的引号类型（" / ' / None）
                self.value_is_string = False  # 是否是字符串类型value

            def _parse_value_state(self, text: str) -> tuple[int, bool]:
                """
                解析目标value文本，返回：
                - 有效内容的结束位置（终止符的前一个位置）
                - 是否已到达终止条件
                """
                end_pos = len(text)
                is_finished = False

                for idx, char in enumerate(text):
                    # 处理转义
                    if self.escape_next:
                        self.escape_next = False
                        continue
                    if char == "\\":
                        self.escape_next = True
                        continue

                    # 初始化value引号类型（仅第一个字符）
                    if idx == 0 and not self.value_is_string and char in ('"', "'"):
                        self.value_quote_type = char
                        self.value_is_string = True
                        self.quote_open = True
                        continue

                    # 处理字符串引号闭合
                    if self.value_is_string and char == self.value_quote_type and not self.escape_next:
                        self.quote_open = False
                        continue

                    # 处理嵌套层级（非引号内）
                    if not self.quote_open:
                        if char in "{[":
                            self.nest_level += 1
                        elif char in "}]":
                            self.nest_level = max(0, self.nest_level - 1)

                    # 判断是否到达终止条件
                    if self.stop_on_comma_or_brace:
                        # 字符串类型：引号闭合 + 嵌套0 + 终止符
                        if self.value_is_string:
                            if not self.quote_open and self.nest_level == 0 and char in (",", "}"):
                                end_pos = idx  # 终止符前的位置为有效结束位
                                is_finished = True
                                break
                        # 非字符串类型：嵌套0 + 终止符
                        else:
                            if self.nest_level == 0 and char in (",", "}"):
                                end_pos = idx
                                is_finished = True
                                break

                return end_pos, is_finished

            def _find_target_key_position(self) -> int:
                """
                在buffer中找到目标key的value起始位置（支持大chunk）
                返回：value起始位置（-1表示未找到）
                """
                # 强匹配顶层JSON字段：{/,, 后接key，支持空格和单/双引号
                pattern = re.compile(
                    rf'(?<=[{{,])\s*(?<!\\)["\']{re.escape(self.target_key)}(?<!\\)["\']\s*:\s*',
                    re.DOTALL
                )
                match = pattern.search(self.buffer)
                if match:
                    return match.end()
                return -1

            def generate(self) -> Iterator[GeneratorOutput]:
                """同步生成器：适配大chunk，完整提取value"""
                for output in self.original_generator:
                    if self.finished:
                        continue

                    self.buffer += output.content

                    if not self.in_target_value:
                        self.value_start_pos = self._find_target_key_position()
                        if self.value_start_pos == -1:
                            continue

                        self.in_target_value = True

                        value_text = self.buffer[self.value_start_pos:]

                        valid_end_pos, is_finished = self._parse_value_state(value_text)

                        if valid_end_pos > 0:
                            valid_content = value_text[:valid_end_pos]
                            if valid_content:
                                yield GeneratorOutput(
                                    content=valid_content,
                                    content_type=self.content_type
                                )

                        if is_finished:
                            self.finished = True
                            continue

                        self.buffer = self.buffer[self.value_start_pos + valid_end_pos:]
                        self.value_start_pos = 0  # 后续buffer从0开始

                    # 阶段2：已进入value提取，处理剩余buffer
                    else:
                        if not self.buffer:
                            continue

                        valid_end_pos, is_finished = self._parse_value_state(self.buffer)

                        valid_content = self.buffer[:valid_end_pos]
                        if valid_content:
                            yield GeneratorOutput(
                                content=valid_content,
                                content_type=self.content_type
                            )

                        if is_finished:
                            self.finished = True
                            continue

                        self.buffer = self.buffer[valid_end_pos:]

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                """异步生成器：适配大chunk，通过callback输出完整value"""
                async for output in self.original_generator:
                    if self.finished:
                        yield GeneratorOutput(content=output.content, content_type='[IGNORE]')
                        continue

                    yield GeneratorOutput(content=output.content, content_type='[IGNORE]')

                    self.buffer += output.content

                    # 阶段1：未找到目标key
                    if not self.in_target_value:
                        self.value_start_pos = self._find_target_key_position()
                        if self.value_start_pos == -1:
                            continue

                        self.in_target_value = True
                        value_text = self.buffer[self.value_start_pos:]

                        valid_end_pos, is_finished = self._parse_value_state(value_text)

                        if valid_end_pos > 0 and hasattr(self.original_generator, 'callback'):
                            valid_content = value_text[:valid_end_pos]
                            if valid_content:
                                try:
                                    if self.original_generator.callback:
                                        await self.original_generator.callback.send_data(
                                            content=valid_content,
                                            content_type=self.content_type
                                        )
                                    else:
                                        print(valid_content, end='', flush=True)
                                except Exception as e:
                                    print(f"Callback send failed: {e}")

                        if is_finished:
                            self.finished = True
                            continue
                        self.buffer = self.buffer[self.value_start_pos + valid_end_pos:]
                        self.value_start_pos = 0

                    else:
                        if not self.buffer:
                            continue

                        valid_end_pos, is_finished = self._parse_value_state(self.buffer)

                        # 输出有效内容
                        if valid_end_pos > 0 and hasattr(self.original_generator, 'callback'):
                            valid_content = self.buffer[:valid_end_pos]
                            if valid_content:
                                try:
                                    if self.original_generator.callback:
                                        await self.original_generator.callback.send_data(
                                            content=valid_content,
                                            content_type=self.content_type
                                        )
                                    else:
                                        print(valid_content, end='', flush=True)

                                except Exception as e:
                                    print(f"Callback send failed: {e}")

                        # 更新状态
                        if is_finished:
                            self.finished = True
                            continue
                        self.buffer = self.buffer[valid_end_pos:]

        return JsonKeyExtractingGenerator(
            generator,
            self.target_key,
            self.stop_on_comma_or_brace,
            self.output_content_type
        )

