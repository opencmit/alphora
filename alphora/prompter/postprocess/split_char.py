from abc import ABC, abstractmethod
from typing import Optional, Iterator
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor


class SplitterPP(BasePostProcessor):
    """
    将文本块拆分成单个字符输出的后处理器
    """

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        class CharacterSplitGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator: BaseGenerator[GeneratorOutput]):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator

            def generate(self) -> Iterator[GeneratorOutput]:
                # 逐个处理原始生成器的输出
                for output in self.original_generator:
                    # 如果内容为空，则直接传递
                    if not output.content:
                        yield output
                        continue

                    # 将内容拆分成单个字符并逐个输出
                    for char in output.content:
                        yield GeneratorOutput(
                            content=char,
                            content_type=output.content_type
                        )

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                # 逐个处理原始生成器的输出
                async for output in self.original_generator:
                    # 如果内容为空，则直接传递
                    if not output.content:
                        yield output
                        continue

                    # 将内容拆分成单个字符并逐个输出
                    for char in output.content:
                        yield GeneratorOutput(
                            content=char,
                            content_type=output.content_type
                        )

        return CharacterSplitGenerator(generator)
