"""
Alphora PostProcessor Component - 后处理器示例

本文件演示各种后处理器的使用：
1. FilterPP - 字符/类型过滤
2. ReplacePP - 内容替换
3. JsonKeyExtractorPP - JSON键值提取
4. PatternMatcherPP - 模式匹配
5. DynamicTypePP - 动态类型转换
6. SplitterPP - 字符拆分
7. TypeMapperPP - 类型映射
8. 后处理器链式组合

后处理器用于对 LLM 流式输出进行实时处理和转换
"""

import asyncio
import os
from typing import Iterator, AsyncIterator

# 后处理器
from alphora.postprocess import FilterPP, ReplacePP, JsonKeyExtractorPP
from alphora.postprocess.pattern_match import PatternMatcherPP
from alphora.postprocess.dynamic_type import DynamicTypePP
from alphora.postprocess.split_char import SplitterPP
from alphora.postprocess.type_mapper import TypeMapperPP
from alphora.postprocess.base_pp import BasePostProcessor

# 流式输出相关
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput


# ============================================================
# 辅助函数：创建模拟生成器
# ============================================================
def create_mock_generator(content: str, content_type: str = "char") -> BaseGenerator:
    """
    创建模拟的流式生成器
    用于演示后处理器的效果
    """
    class MockGenerator(BaseGenerator[GeneratorOutput]):
        def __init__(self, text: str, ct: str):
            super().__init__(content_type=ct)
            self.text = text

        def generate(self) -> Iterator[GeneratorOutput]:
            # 模拟流式输出，每次输出几个字符
            for i in range(0, len(self.text), 3):
                chunk = self.text[i:i+3]
                yield GeneratorOutput(content=chunk, content_type=self.content_type)

        async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
            for i in range(0, len(self.text), 3):
                chunk = self.text[i:i+3]
                yield GeneratorOutput(content=chunk, content_type=self.content_type)

    return MockGenerator(content, content_type)


def consume_generator(generator: BaseGenerator) -> str:
    """消费生成器并返回完整内容"""
    result = ""
    for output in generator:
        result += output.content
        print(output.content, end="", flush=True)
    print()  # 换行
    return result


# ============================================================
# 示例 1: FilterPP - 字符过滤
# ============================================================
def example_1_filter_pp():
    """
    FilterPP: 过滤特定字符或内容类型

    用途：
    - 过滤敏感字符
    - 移除特殊符号
    - 按内容类型筛选
    """
    print("=" * 60)
    print("示例 1: FilterPP - 字符过滤")
    print("=" * 60)

    # 示例1：过滤特定字符
    print("\n1. 过滤换行符和空格：")
    text = "Hello\n World!\n How are you?"
    generator = create_mock_generator(text)

    # 创建过滤器
    filter_pp = FilterPP(filter_chars="\n ")  # 过滤换行和空格
    filtered_gen = filter_pp(generator)

    print("  原文: ", repr(text))
    print("  过滤后: ", end="")
    consume_generator(filtered_gen)

    # 示例2：过滤特殊符号
    print("\n2. 过滤特殊符号：")
    text = "Hello! @World# $Python%"
    generator = create_mock_generator(text)

    filter_pp = FilterPP(filter_chars=["!", "@", "#", "$", "%"])
    filtered_gen = filter_pp(generator)

    print("  原文: ", text)
    print("  过滤后: ", end="")
    consume_generator(filtered_gen)

    # 示例3：按内容类型筛选
    print("\n3. 按内容类型筛选（只保留 'text' 类型）：")

    class MixedGenerator(BaseGenerator):
        def generate(self):
            yield GeneratorOutput("思考中...", "think")
            yield GeneratorOutput("这是回答", "text")
            yield GeneratorOutput("继续思考", "think")
            yield GeneratorOutput("最终结果", "text")

    mixed_gen = MixedGenerator("text")
    filter_pp = FilterPP(include_content_types=["text"])  # 只保留text类型
    filtered_gen = filter_pp(mixed_gen)

    print("  筛选后: ", end="")
    consume_generator(filtered_gen)

    # 示例4：排除特定类型
    print("\n4. 排除 'think' 类型：")
    mixed_gen = MixedGenerator("text")
    filter_pp = FilterPP(exclude_content_types=["think"])
    filtered_gen = filter_pp(mixed_gen)

    print("  排除后: ", end="")
    consume_generator(filtered_gen)


# ============================================================
# 示例 2: ReplacePP - 内容替换
# ============================================================
def example_2_replace_pp():
    """
    ReplacePP: 替换特定内容

    用途：
    - 敏感词替换
    - 格式转换
    - 术语统一
    """
    print("\n" + "=" * 60)
    print("示例 2: ReplacePP - 内容替换")
    print("=" * 60)

    # 示例1：简单替换
    print("\n1. 简单文本替换：")
    text = "Python是最好的语言，Java也很不错"
    generator = create_mock_generator(text)

    # 使用字典定义替换规则
    replace_pp = ReplacePP(replace_map={
        "Python": "🐍Python",
        "Java": "☕Java"
    })
    replaced_gen = replace_pp(generator)

    print("  原文: ", text)
    print("  替换后: ", end="")
    consume_generator(replaced_gen)

    # 示例2：使用元组列表（保持顺序）
    print("\n2. 使用元组列表替换：")
    text = "价格：100元，折扣：20%"
    generator = create_mock_generator(text)

    replace_pp = ReplacePP(replace_map=[
        ("元", " CNY"),
        ("%", " percent"),
    ])
    replaced_gen = replace_pp(generator)

    print("  原文: ", text)
    print("  替换后: ", end="")
    consume_generator(replaced_gen)

    # 示例3：按内容类型替换
    print("\n3. 按内容类型进行不同替换：")

    class TypedGenerator(BaseGenerator):
        def generate(self):
            yield GeneratorOutput("Hello World", "english")
            yield GeneratorOutput("你好世界", "chinese")

    typed_gen = TypedGenerator("text")

    replace_pp = ReplacePP(
        type_specific_replace={
            "english": {"Hello": "Hi", "World": "Everyone"},
            "chinese": {"你好": "嗨", "世界": "大家"}
        }
    )
    replaced_gen = replace_pp(typed_gen)

    print("  替换后: ", end="")
    consume_generator(replaced_gen)


# ============================================================
# 示例 3: JsonKeyExtractorPP - JSON键值提取
# ============================================================
def example_3_json_extractor():
    """
    JsonKeyExtractorPP: 从JSON流中提取指定键的值

    用途：
    - 提取结构化输出中的特定字段
    - 处理LLM返回的JSON响应
    - 支持嵌套路径和数组索引
    """
    print("\n" + "=" * 60)
    print("示例 3: JsonKeyExtractorPP - JSON键值提取")
    print("=" * 60)

    # 示例1：提取单个键
    print("\n1. 提取单个键：")
    json_text = '{"name": "张三", "age": 25, "city": "北京"}'
    generator = create_mock_generator(json_text)

    extractor = JsonKeyExtractorPP(target_key="name", output_mode="target_only")
    extracted_gen = extractor(generator)

    print("  JSON: ", json_text)
    print("  提取 'name': ", end="")
    consume_generator(extracted_gen)

    # 示例2：提取嵌套键
    print("\n2. 提取嵌套键：")
    json_text = '{"user": {"profile": {"name": "李四", "email": "lisi@example.com"}}}'
    generator = create_mock_generator(json_text)

    extractor = JsonKeyExtractorPP(
        target_key="user.profile.name",  # 使用点号表示嵌套路径
        output_mode="target_only"
    )
    extracted_gen = extractor(generator)

    print("  JSON: ", json_text)
    print("  提取 'user.profile.name': ", end="")
    consume_generator(extracted_gen)

    # 示例3：提取数组元素
    print("\n3. 提取数组元素：")
    json_text = '{"items": [{"id": 1, "name": "苹果"}, {"id": 2, "name": "香蕉"}]}'
    generator = create_mock_generator(json_text)

    extractor = JsonKeyExtractorPP(
        target_key="items[0].name",  # 数组索引
        output_mode="target_only"
    )
    extracted_gen = extractor(generator)

    print("  JSON: ", json_text)
    print("  提取 'items[0].name': ", end="")
    consume_generator(extracted_gen)

    # 示例4：提取多个键
    print("\n4. 提取多个键：")
    json_text = '{"title": "学习Python", "content": "Python是一门优雅的语言", "author": "匿名"}'
    generator = create_mock_generator(json_text)

    extractor = JsonKeyExtractorPP(
        target_keys=["title", "content"],  # 多个键
        separator="\n---\n",               # 分隔符
        output_mode="target_only"
    )
    extracted_gen = extractor(generator)

    print("  JSON: ", json_text)
    print("  提取 'title' 和 'content':")
    consume_generator(extracted_gen)

    # 示例5：output_mode 选项
    print("\n5. output_mode 选项演示：")
    print("  - target_only: 只输出提取的值")
    print("  - raw_only: 只输出原始JSON")
    print("  - both: 流式输出提取值，响应返回原始JSON")


# ============================================================
# 示例 4: PatternMatcherPP - 模式匹配
# ============================================================
def example_4_pattern_matcher():
    """
    PatternMatcherPP: 在流式内容中匹配特定模式

    用途：
    - 提取特定标签包裹的内容
    - 代码块识别
    - 结构化内容解析
    """
    print("\n" + "=" * 60)
    print("示例 4: PatternMatcherPP - 模式匹配")
    print("=" * 60)

    # 示例1：匹配XML标签
    print("\n1. 匹配XML标签内容：")
    text = "前言内容<answer>这是答案</answer>后续内容"
    generator = create_mock_generator(text)

    matcher = PatternMatcherPP(
        bos="<answer>",      # 开始标记
        eos="</answer>",     # 结束标记
        matched_type="answer",
        include_bos=False,   # 不包含开始标记
        include_eos=False,   # 不包含结束标记
        output_mode="only_matched"  # 只输出匹配内容
    )
    matched_gen = matcher(generator)

    print("  原文: ", text)
    print("  匹配内容: ", end="")
    consume_generator(matched_gen)

    # 示例2：匹配代码块
    print("\n2. 匹配代码块：")
    text = "这是说明```python\nprint('Hello')\n```这是后续"
    generator = create_mock_generator(text)

    matcher = PatternMatcherPP(
        bos="```python",
        eos="```",
        matched_type="code",
        include_bos=True,
        include_eos=True,
        output_mode="all"  # 输出所有内容
    )
    matched_gen = matcher(generator)

    print("  原文: ", text)
    print("  处理后: ", end="")
    for output in matched_gen:
        type_indicator = "[CODE]" if output.content_type == "code" else ""
        print(f"{type_indicator}{output.content}", end="")
    print()

    # 示例3：只输出匹配内容
    print("\n3. 只输出匹配的内容：")
    text = "无关内容<important>重要信息</important>更多无关内容"
    generator = create_mock_generator(text)

    matcher = PatternMatcherPP(
        bos="<important>",
        eos="</important>",
        matched_type="important",
        include_bos=False,
        include_eos=False,
        output_mode="only_matched"
    )
    matched_gen = matcher(generator)

    print("  原文: ", text)
    print("  只输出匹配: ", end="")
    consume_generator(matched_gen)

    # 示例4：排除匹配内容
    print("\n4. 排除匹配的内容：")
    text = "保留这部分<skip>跳过这部分</skip>也保留这部分"
    generator = create_mock_generator(text)

    matcher = PatternMatcherPP(
        bos="<skip>",
        eos="</skip>",
        matched_type="skip",
        output_mode="exclude_matched"
    )
    matched_gen = matcher(generator)

    print("  原文: ", text)
    print("  排除后: ", end="")
    consume_generator(matched_gen)


# ============================================================
# 示例 5: DynamicTypePP - 动态类型转换
# ============================================================
def example_5_dynamic_type():
    """
    DynamicTypePP: 根据内容特征动态改变内容类型

    用途：
    - 自动识别内容类型
    - 根据特定字符改变类型标记
    """
    print("\n" + "=" * 60)
    print("示例 5: DynamicTypePP - 动态类型转换")
    print("=" * 60)

    # 示例1：根据字符改变类型
    print("\n1. 根据特定字符改变类型：")

    class SimpleGenerator(BaseGenerator):
        def generate(self):
            yield GeneratorOutput("这是普通文本？", "text")
            yield GeneratorOutput("这是感叹句！", "text")
            yield GeneratorOutput("这也是普通文本。", "text")

    gen = SimpleGenerator("text")

    dynamic_pp = DynamicTypePP(
        char_to_content_type={
            "?": "question",   # 包含?的变为question类型
            "!": "exclamation" # 包含!的变为exclamation类型
        },
        default_content_type="statement"  # 默认类型
    )
    dynamic_gen = dynamic_pp(gen)

    print("  动态类型转换结果：")
    for output in dynamic_gen:
        print(f"    [{output.content_type}] {output.content}")


# ============================================================
# 示例 6: TypeMapperPP - 类型映射
# ============================================================
def example_6_type_mapper():
    """
    TypeMapperPP: 将内容类型映射为其他类型

    用途：
    - 类型标准化
    - 类型转换
    """
    print("\n" + "=" * 60)
    print("示例 6: TypeMapperPP - 类型映射")
    print("=" * 60)

    class TypedGenerator(BaseGenerator):
        def generate(self):
            yield GeneratorOutput("思考过程...", "think")
            yield GeneratorOutput("最终答案", "char")
            yield GeneratorOutput("补充说明", "note")

    gen = TypedGenerator("text")

    # 将类型映射为统一格式
    mapper = TypeMapperPP(mapping={
        "think": "reasoning",     # think -> reasoning
        "char": "content",        # char -> content
        "note": "supplementary"   # note -> supplementary
    })
    mapped_gen = mapper(gen)

    print("  类型映射结果：")
    for output in mapped_gen:
        print(f"    [{output.content_type}] {output.content}")


# ============================================================
# 示例 7: SplitterPP - 字符拆分
# ============================================================
def example_7_splitter():
    """
    SplitterPP: 将内容拆分为单个字符输出

    用途：
    - 打字机效果
    - 逐字输出
    """
    print("\n" + "=" * 60)
    print("示例 7: SplitterPP - 字符拆分")
    print("=" * 60)

    print("\n1. 将块状输出拆分为逐字输出：")

    class BlockGenerator(BaseGenerator):
        def generate(self):
            yield GeneratorOutput("Hello", "text")
            yield GeneratorOutput("World", "text")

    gen = BlockGenerator("text")
    splitter = SplitterPP()
    split_gen = splitter(gen)

    print("  逐字输出: ", end="")
    for output in split_gen:
        print(f"[{output.content}]", end="")
    print()


# ============================================================
# 示例 8: 后处理器链式组合
# ============================================================
def example_8_chained_processors():
    """
    链式组合多个后处理器

    使用 >> 运算符或手动组合
    """
    print("\n" + "=" * 60)
    print("示例 8: 后处理器链式组合")
    print("=" * 60)

    # 示例1：使用 >> 运算符
    print("\n1. 使用 >> 运算符链接：")
    text = "Hello! @World# Python是最好的语言！"
    generator = create_mock_generator(text)

    # 先过滤特殊字符，再替换文本
    chained = FilterPP(filter_chars="@#") >> ReplacePP(replace_map={"Python": "🐍"})
    result_gen = chained(generator)

    print("  原文: ", text)
    print("  链式处理后: ", end="")
    consume_generator(result_gen)

    # 示例2：多步骤链接
    print("\n2. 多步骤链接：")
    json_text = '{"analysis": "<think>思考中</think>最终答案是42"}'
    generator = create_mock_generator(json_text)

    # 1. 提取JSON键
    # 2. 过滤think标签内容
    # 这里为了演示，手动组合

    step1 = JsonKeyExtractorPP(target_key="analysis", output_mode="target_only")
    step2 = PatternMatcherPP(
        bos="<think>",
        eos="</think>",
        matched_type="think",
        output_mode="exclude_matched"
    )

    # 手动组合
    gen_step1 = step1(generator)
    gen_step2 = step2(gen_step1)

    print("  JSON: ", json_text)
    print("  处理后: ", end="")
    consume_generator(gen_step2)

    # 示例3：使用列表组合（在Prompt中）
    print("\n3. 在Prompt调用中使用列表组合：")
    print("   prompt.acall(")
    print("       query='...',")
    print("       postprocessor=[FilterPP(...), ReplacePP(...), ...]")
    print("   )")


# ============================================================
# 示例 9: 自定义后处理器
# ============================================================
def example_9_custom_processor():
    """
    创建自定义后处理器

    继承 BasePostProcessor 并实现 process 方法
    """
    print("\n" + "=" * 60)
    print("示例 9: 自定义后处理器")
    print("=" * 60)

    class UppercasePP(BasePostProcessor):
        """将内容转换为大写的后处理器"""

        def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
            class UppercaseGenerator(BaseGenerator[GeneratorOutput]):
                def __init__(self, original):
                    super().__init__(original.content_type)
                    self.original = original

                def generate(self):
                    for output in self.original:
                        yield GeneratorOutput(
                            content=output.content.upper(),
                            content_type=output.content_type
                        )

                async def agenerate(self):
                    async for output in self.original:
                        yield GeneratorOutput(
                            content=output.content.upper(),
                            content_type=output.content_type
                        )

            return UppercaseGenerator(generator)

    # 使用自定义后处理器
    text = "hello world, this is a test"
    generator = create_mock_generator(text)

    uppercase_pp = UppercasePP()
    upper_gen = uppercase_pp(generator)

    print("\n自定义大写后处理器：")
    print("  原文: ", text)
    print("  转换后: ", end="")
    consume_generator(upper_gen)

    # 与其他后处理器组合
    print("\n组合自定义后处理器：")
    generator = create_mock_generator("hello! world@")

    chained = FilterPP(filter_chars="!@") >> UppercasePP()
    result_gen = chained(generator)

    print("  原文: hello! world@")
    print("  处理后: ", end="")
    consume_generator(result_gen)


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora PostProcessor 后处理器示例")
    print("=" * 60)

    example_1_filter_pp()
    example_2_replace_pp()
    example_3_json_extractor()
    example_4_pattern_matcher()
    example_5_dynamic_type()
    example_6_type_mapper()
    example_7_splitter()
    example_8_chained_processors()
    example_9_custom_processor()

    print("\n" + "=" * 60)
    print("所有后处理器示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()