"""
实现content_type的映射转换
"""
from typing import Optional, Iterator, Dict
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor


class TypeMapperPP(BasePostProcessor):
    """
    将内容类型根据映射表进行转换的后处理器
    """

    def __init__(self, mapping: Dict[str, str]):
        """
        初始化内容类型映射器
        mapping: 内容类型映射表，键为原始类型，值为目标类型
        """
        self.mapping = mapping

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        """
        处理生成器，根据映射表转换内容类型
        """
        class ContentTypeMappedGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self,
                         original_generator: BaseGenerator[GeneratorOutput],
                         mapping: dict,):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.mapping = mapping

            def generate(self) -> Iterator[GeneratorOutput]:
                """生成处理后的输出"""
                for output in self.original_generator:
                    original_type = output.content_type
                    if original_type in self.mapping:
                        new_type = self.mapping[original_type]
                    else:
                        new_type = original_type

                    if new_type != original_type:
                        yield GeneratorOutput(
                            content=output.content,
                            content_type=new_type
                        )
                    else:
                        yield output

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                """生成处理后的输出"""
                async for output in self.original_generator:
                    original_type = output.content_type
                    if original_type in self.mapping:
                        new_type = self.mapping[original_type]
                    else:
                        new_type = original_type

                    if new_type != original_type:
                        yield GeneratorOutput(
                            content=output.content,
                            content_type=new_type
                        )
                    else:
                        yield output

        return ContentTypeMappedGenerator(generator, self.mapping)
