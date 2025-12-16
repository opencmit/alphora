from abc import ABC, abstractmethod
from typing import Optional, Iterator
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor
from typing import List, Tuple


class DynamicTypePP(BasePostProcessor):
    """
    根据内容中是否包含特定字符来更改内容类型的后处理器
    """

    def __init__(self, char_to_content_type: dict, default_content_type: Optional[str] = None):
        """
        初始化内容类型检测器
        char_to_content_type: 字符到内容类型的映射字典，例如 {"?": "question", "!": "exclamation"}
        default_content_type: 如果没有匹配任何规则，是否使用默认内容类型
        """
        self.char_to_content_type = char_to_content_type
        self.default_content_type = default_content_type

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        # 创建一个包装生成器的新生成器
        class ContentTypeDetectedGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator: BaseGenerator[GeneratorOutput],
                         char_to_content_type: dict,
                         default_content_type: Optional[str]):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.char_to_content_type = char_to_content_type
                self.default_content_type = default_content_type

            def generate(self) -> Iterator[GeneratorOutput]:
                # 逐个处理原始生成器的输出
                for output in self.original_generator:
                    # 检查是否包含检测字符
                    new_content_type = None

                    # 遍历所有需要检测的字符
                    for detect_char, content_type in self.char_to_content_type.items():
                        # 如果内容中包含该字符，则设置新的内容类型
                        if detect_char in output.content:
                            new_content_type = content_type
                            break

                    # 如果没有匹配到规则，并且设置了默认内容类型，则使用默认类型
                    if new_content_type is None and self.default_content_type is not None:
                        new_content_type = self.default_content_type

                    # 如果内容类型发生了变化，则创建新的输出对象
                    if new_content_type is not None and new_content_type != output.content_type:
                        yield GeneratorOutput(
                            content=output.content,
                            content_type=new_content_type
                        )
                    else:
                        # 否则保持原始输出不变
                        yield output

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                # 逐个处理原始生成器的输出
                async for output in self.original_generator:
                    # 检查是否包含检测字符
                    new_content_type = None

                    # 遍历所有需要检测的字符
                    for detect_char, content_type in self.char_to_content_type.items():
                        # 如果内容中包含该字符，则设置新的内容类型
                        if detect_char in output.content:
                            new_content_type = content_type
                            break

                    # 如果没有匹配到规则，并且设置了默认内容类型，则使用默认类型
                    if new_content_type is None and self.default_content_type is not None:
                        new_content_type = self.default_content_type

                    # 如果内容类型发生了变化，则创建新的输出对象
                    if new_content_type is not None and new_content_type != output.content_type:
                        yield GeneratorOutput(
                            content=output.content,
                            content_type=new_content_type
                        )
                    else:
                        # 否则保持原始输出不变
                        yield output

        return ContentTypeDetectedGenerator(generator, self.char_to_content_type, self.default_content_type)
