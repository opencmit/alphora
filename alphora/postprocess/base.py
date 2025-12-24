"""
用于接在 BaseAgent 后面 (BaseAgent > Subprocess )

这样，Agent输出的内容就能被后处理一道了

例如
Translator = Translator >> BadResponseFilter(bad_words=['xx'])
Translator = Translator >> StreamPatternMatch(pattern='<a>.*?</a>')
"""

from abc import ABC, abstractmethod
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput


class BasePostProcessor(ABC):
    """后处理器基类，定义了后处理器的基本接口"""

    @abstractmethod
    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        """
        处理单个GeneratorOutput对象
        返回处理后的对象，如果返回None则表示过滤掉该输出
        """
        pass

    def __call__(self, generator: BaseGenerator) -> BaseGenerator:
        """使后处理器实例可以作为函数调用，用于流式处理生成器"""
        return self.process(generator)

    def __rshift__(self, other: "BasePostProcessor") -> "BasePostProcessor":
        if not isinstance(other, BasePostProcessor):
            raise TypeError(f"Can only chain with another BasePostProcessor, got {type(other)}")

        left = self
        right = other

        class ChainedPostProcessor(BasePostProcessor):
            def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
                # 先用 left 处理，再用 right 处理结果
                intermediate = left.process(generator)
                return right.process(intermediate)

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
