"""
用于接在 BaseAgent 后面 (BaseAgent > Subprocess )

这样，Agent输出的内容就能被后处理一道了

例如
Translator = Translator >> BadResponseFilter(bad_words=['xx'])
Translator = Translator >> StreamPatternMatch(pattern='<a>.*?</a>')

也支持对 ToolCall 结果的后处理:
pp = ToolCallFilterPP(include_tools=["get_weather"])
result = prompt.call(query="...", tools=tools, postprocessor=pp)
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput

if TYPE_CHECKING:
    from alphora.models.llms.types import ToolCall


class BasePostProcessor(ABC):
    """后处理器基类，定义了后处理器的基本接口。

    子类可按需覆盖:
    - ``process``            处理流式 Generator 输出
    - ``process_tool_call``  处理 ToolCall 结果（工具调用场景）

    两者默认均为透传，子类只需覆盖自己关心的方法即可。
    """

    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        """处理流式 Generator 输出，默认透传。"""
        return generator

    def process_tool_call(self, tool_call: "ToolCall") -> "ToolCall":
        """处理 ToolCall 结果，默认透传。"""
        return tool_call

    def __call__(self, generator_or_tool_call):
        """使后处理器实例可以作为函数调用，自动识别输入类型。"""
        from alphora.models.llms.types import ToolCall
        if isinstance(generator_or_tool_call, ToolCall):
            return self.process_tool_call(generator_or_tool_call)
        return self.process(generator_or_tool_call)

    def __rshift__(self, other: "BasePostProcessor") -> "BasePostProcessor":
        if not isinstance(other, BasePostProcessor):
            raise TypeError(f"Can only chain with another BasePostProcessor, got {type(other)}")

        left = self
        right = other

        class ChainedPostProcessor(BasePostProcessor):
            def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
                intermediate = left.process(generator)
                return right.process(intermediate)

            def process_tool_call(self, tool_call: "ToolCall") -> "ToolCall":
                intermediate = left.process_tool_call(tool_call)
                return right.process_tool_call(intermediate)

        return ChainedPostProcessor()
    #
    # def __or__(self, other):
    #
    #     if not isinstance(other, BasePostProcessor):
    #         raise TypeError(f"unsupported operand type(s) for |: '{type(self).__name__}' and '{type(other).__name__}'")
    #
    #     def combined_process(generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
    #
    #         first_processed = self.process(generator)
    #
    #         second_processed = other.process(generator)
    #
    #         class CombinedGenerator(BaseGenerator[GeneratorOutput]):
    #             def __init__(self, first_gen, second_gen):
    #                 super().__init__(first_gen.content_type)
    #                 self.first_gen = first_gen
    #                 self.second_gen = second_gen
    #
    #             def generate(self):
    #                 first_outputs = list(self.first_gen)
    #                 second_outputs = list(self.second_gen)
    #
    #                 if len(first_outputs) != len(second_outputs):
    #                     for output in first_outputs:
    #                         yield output
    #                     return
    #
    #                 for i in range(len(first_outputs)):
    #                     first_output = first_outputs[i]
    #                     second_output = second_outputs[i]
    #                     if first_output.content == second_output.content:
    #                         yield first_output
    #                     else:
    #                         yield first_output
    #
    #         return CombinedGenerator(first_processed, second_processed)
    #
    #     return combined_process
    #
    #
