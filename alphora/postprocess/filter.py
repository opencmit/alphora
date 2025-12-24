from typing import Optional, Iterator, Union, List
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.base import BasePostProcessor


class FilterPP(BasePostProcessor):
    """过滤特定字符或内容类型的后处理器"""

    def __init__(self,
                 filter_chars: Union[str, List[str]] = "",
                 include_content_types: Union[str, List[str], None] = None,
                 exclude_content_types: Union[str, List[str], None] = None):
        """
        初始化过滤器
        filter_chars: 需要过滤的字符，可以是字符串或字符列表
        include_content_types: 只保留的内容类型（与exclude互斥）
        exclude_content_types: 需要排除的内容类型
        """
        self.filter_chars = self._parse_filter_chars(filter_chars)

        # 处理内容类型过滤参数
        self.include_content_types = self._parse_content_types(include_content_types)
        self.exclude_content_types = self._parse_content_types(exclude_content_types)

        # 检查include和exclude是否同时存在
        if self.include_content_types and self.exclude_content_types:
            raise ValueError("include_content_types和exclude_content_types不能同时使用")

    @staticmethod
    def _parse_filter_chars(chars: Union[str, List[str]]) -> List[str]:
        """解析过滤字符参数，统一转换为字符列表"""
        if isinstance(chars, str):
            return list(chars)
        if isinstance(chars, list):
            return chars
        raise TypeError("filter_chars必须是字符串或字符列表")

    @staticmethod
    def _parse_content_types(types: Union[str, List[str], None]) -> Optional[List[str]]:
        """解析内容类型参数"""
        if types is None:
            return None
        if isinstance(types, str):
            return [types]
        if isinstance(types, list):
            return types
        raise TypeError("content_types必须是字符串、字符串列表或None")

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:

        class FilteredGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self,
                         original_generator: BaseGenerator[GeneratorOutput],
                         filter_chars: List[str],
                         include_content_types: Optional[List[str]],
                         exclude_content_types: Optional[List[str]]):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.filter_chars = filter_chars
                self.include_content_types = include_content_types
                self.exclude_content_types = exclude_content_types

            def generate(self) -> Iterator[GeneratorOutput]:
                for output in self.original_generator:
                    # 内容类型过滤
                    if self.include_content_types and output.content_type not in self.include_content_types:
                        continue
                    if self.exclude_content_types and output.content_type in self.exclude_content_types:
                        continue

                    # 字符过滤
                    filtered_content = ''.join(c for c in output.content if c not in self.filter_chars)

                    if filtered_content:
                        yield GeneratorOutput(
                            content=filtered_content,
                            content_type=output.content_type
                        )

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                async for output in self.original_generator:
                    # 内容类型过滤
                    if self.include_content_types and output.content_type not in self.include_content_types:
                        continue
                    if self.exclude_content_types and output.content_type in self.exclude_content_types:
                        continue

                    # 字符过滤
                    filtered_content = ''.join(c for c in output.content if c not in self.filter_chars)

                    if filtered_content:
                        yield GeneratorOutput(
                            content=filtered_content,
                            content_type=output.content_type
                        )

        return FilteredGenerator(
            generator,
            self.filter_chars,
            self.include_content_types,
            self.exclude_content_types
        )
