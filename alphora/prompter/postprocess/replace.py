from abc import ABC
from typing import Optional, Iterator, Union, List, Dict
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor


class ReplacePP(BasePostProcessor):
    """替换特定字符、字符串或根据内容类型进行替换的后处理器"""

    def __init__(self,
                 replace_map: Union[Dict[str, str], List[tuple]] = None,
                 type_specific_replace: Optional[Dict[str, Union[Dict[str, str], List[tuple]]]] = None):
        """
        初始化替换处理器

        replace_map: 通用替换规则，可传入字典(键为待替换内容，值为替换内容)
                    或元组列表[(待替换内容, 替换内容), ...]

        type_specific_replace: 按内容类型的特定替换规则，键为内容类型，
                              值为该类型对应的替换规则(格式同replace_map)
                              例如: {"text": {"a": "b"}, "code": [("x", "y")]}
        """
        self.replace_map = self._parse_replace_map(replace_map or {})
        self.type_specific_replace = self._parse_type_specific_replace(type_specific_replace or {})

    @staticmethod
    def _parse_replace_map(replacements: Union[Dict[str, str], List[tuple]]) -> List[tuple]:
        """解析替换规则，统一转换为(原内容, 替换内容)元组列表"""
        if isinstance(replacements, dict):
            return [(k, v) for k, v in replacements.items()]
        if isinstance(replacements, list):
            for item in replacements:
                if not isinstance(item, tuple) or len(item) != 2:
                    raise ValueError("替换列表中的元素必须是长度为2的元组")
            return replacements
        raise TypeError("replace_map必须是字典或元组列表")

    def _parse_type_specific_replace(self, type_replacements: Dict[str, Union[Dict[str, str], List[tuple]]]) -> Dict[str, List[tuple]]:
        """解析按内容类型的替换规则"""
        parsed = {}
        for content_type, replacements in type_replacements.items():
            parsed[content_type] = self._parse_replace_map(replacements)
        return parsed

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:

        class ReplacedGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self,
                         original_generator: BaseGenerator[GeneratorOutput],
                         global_replace: List[tuple],
                         type_replace: Dict[str, List[tuple]]):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.global_replace = global_replace
                self.type_replace = type_replace

            def _apply_replacements(self, content: str, content_type: str) -> str:
                """应用所有替换规则到内容"""
                processed = content

                # 先应用全局替换规则
                for old, new in self.global_replace:
                    processed = processed.replace(old, new)

                # 再应用该内容类型的特定替换规则
                if content_type in self.type_replace:
                    for old, new in self.type_replace[content_type]:
                        processed = processed.replace(old, new)

                return processed

            def generate(self) -> Iterator[GeneratorOutput]:
                for output in self.original_generator:
                    # 应用替换规则
                    replaced_content = self._apply_replacements(
                        output.content,
                        output.content_type
                    )

                    # 生成替换后的输出
                    yield GeneratorOutput(
                        content=replaced_content,
                        content_type=output.content_type
                    )

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                async for output in self.original_generator:
                    # 应用替换规则
                    replaced_content = self._apply_replacements(
                        output.content,
                        output.content_type
                    )

                    # 生成替换后的输出
                    yield GeneratorOutput(
                        content=replaced_content,
                        content_type=output.content_type
                    )

        return ReplacedGenerator(
            generator,
            self.replace_map,
            self.type_specific_replace
        )
