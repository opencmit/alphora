# Alphora Postprocess

**流式输出后处理器组件**

Postprocess 是 Alphora 框架的流式输出后处理模块，专门用于对 Prompter 和 Agent 的流式输出进行实时处理。它提供了一系列可组合的后处理器，支持内容过滤、字符替换、模式匹配、JSON 提取等常见操作，完美配合流式输出场景。

## 特性

-  **链式组合** - 使用 `>>` 运算符串联多个后处理器
-  **流式处理** - 逐字符/逐块处理，保持流式输出特性
-  **模式匹配** - 基于状态机的精确标记匹配
-  **JSON 提取** - 从流式 JSON 中实时提取指定字段
- ️ **类型感知** - 支持按 content_type 差异化处理
-  **异步支持** - 同时支持同步和异步生成器

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.prompter import BasePrompt
from alphora.postprocess import ReplacePP, FilterPP

# 创建 Prompter
translator = BasePrompt(
    system="你是一个翻译助手",
    user="翻译：{{ text }}"
)

# 添加后处理器
translator = translator >> ReplacePP({"【": "[", "】": "]"}) >> FilterPP(filter_chars="*")

# 调用时自动应用后处理
async for chunk in translator.acall(text="Hello World"):
    print(chunk.content, end="")
```

## 目录

- [与 Prompter 集成](#与-prompter-集成)
- [后处理器链](#后处理器链)
- [内置后处理器](#内置后处理器)
    - [ReplacePP - 字符替换](#replacepp---字符替换)
    - [FilterPP - 内容过滤](#filterpp---内容过滤)
    - [PatternMatcherPP - 模式匹配](#patternmatcherpp---模式匹配)
    - [JsonKeyExtractorPP - JSON 提取](#jsonkeyextractorpp---json-提取)
    - [DynamicTypePP - 动态类型](#dynamictypepp---动态类型)
    - [TypeMapperPP - 类型映射](#typemapperpp---类型映射)
    - [SplitterPP - 字符拆分](#splitterpp---字符拆分)
- [自定义后处理器](#自定义后处理器)
- [API 参考](#api-参考)

---

## 与 Prompter 集成

Postprocess 模块与 Prompter 紧密集成，通过 `>>` 运算符可以将后处理器附加到任何 Prompter 上。

### 基础集成

```python
from alphora.prompter import BasePrompt
from alphora.postprocess import ReplacePP

# 创建 Prompter
prompt = BasePrompt(
    system="你是一个助手",
    user="{{ question }}"
)

# 附加后处理器
prompt_with_pp = prompt >> ReplacePP({"旧词": "新词"})

# 调用时自动应用后处理
result = await prompt_with_pp.acall(question="你好")
print(result.response)
```

### 流式输出处理

后处理器在流式输出时逐块处理，不会阻塞流式传输：

```python
from alphora.prompter import BasePrompt
from alphora.postprocess import FilterPP

prompt = BasePrompt(user="写一首诗")
prompt = prompt >> FilterPP(filter_chars="*#")  # 过滤 markdown 符号

# 流式输出
async for chunk in prompt.acall():
    print(chunk.content, end="", flush=True)  # 实时输出，已过滤
```

### 与 Agent 集成

后处理器同样适用于 Agent：

```python
from alphora.agent import BaseAgent
from alphora.postprocess import PatternMatcherPP

# 创建 Agent
agent = BaseAgent(system="你是一个助手")

# 添加后处理器，提取思考过程
agent = agent >> PatternMatcherPP(
    bos="<think>",
    eos="</think>",
    matched_type="thinking",
    output_mode="only_matched"
)
```

---

## 后处理器链

### 链式组合

使用 `>>` 运算符可以将多个后处理器串联：

```python
from alphora.postprocess import ReplacePP, FilterPP, PatternMatcherPP

# 创建处理链
pp_chain = (
    ReplacePP({"【": "[", "】": "]"})      # 第一步：替换括号
    >> FilterPP(filter_chars="*_")          # 第二步：过滤符号
    >> PatternMatcherPP(                    # 第三步：提取标签内容
        bos="<answer>",
        eos="</answer>",
        output_mode="only_matched"
    )
)

# 应用到 Prompter
prompt = BasePrompt(user="问题") >> pp_chain
```

### 执行顺序

后处理器按从左到右的顺序执行：

```python
# 执行顺序：A → B → C
prompt >> A >> B >> C

# 等价于
C(B(A(prompt_output)))
```

### 独立使用后处理器

后处理器也可以独立于 Prompter 使用：

```python
from alphora.postprocess import ReplacePP
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput

# 创建后处理器
replacer = ReplacePP({"old": "new"})

# 处理任意生成器
processed_generator = replacer.process(some_generator)

for output in processed_generator:
    print(output.content)
```

---

## 内置后处理器

### ReplacePP - 字符替换

替换输出中的字符或字符串。

```python
from alphora.postprocess import ReplacePP

# 字典方式：键为待替换内容，值为替换内容
replacer = ReplacePP(replace_map={
    "【": "[",
    "】": "]",
    "旧文本": "新文本"
})

# 元组列表方式
replacer = ReplacePP(replace_map=[
    ("old", "new"),
    ("foo", "bar")
])

# 按内容类型差异化替换
replacer = ReplacePP(
    replace_map={"通用替换": "通用结果"},
    type_specific_replace={
        "code": {"print": "console.log"},     # 仅对 code 类型
        "text": {"Hello": "你好"}              # 仅对 text 类型
    }
)
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `replace_map` | `Dict[str, str]` 或 `List[tuple]` | 通用替换规则 |
| `type_specific_replace` | `Dict[str, Dict/List]` | 按内容类型的特定替换规则 |

---

### FilterPP - 内容过滤

过滤特定字符或按内容类型过滤。

```python
from alphora.postprocess import FilterPP

# 过滤特定字符
filter_pp = FilterPP(filter_chars="*#_~")  # 过滤 markdown 符号

# 字符列表方式
filter_pp = FilterPP(filter_chars=["*", "#", "\n"])

# 只保留特定内容类型
filter_pp = FilterPP(include_content_types="text")  # 只保留 text 类型
filter_pp = FilterPP(include_content_types=["text", "code"])

# 排除特定内容类型
filter_pp = FilterPP(exclude_content_types="thinking")  # 排除 thinking 类型

# 组合使用
filter_pp = FilterPP(
    filter_chars="*#",
    include_content_types=["text", "answer"]
)
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `filter_chars` | `str` 或 `List[str]` | 需要过滤的字符 |
| `include_content_types` | `str` 或 `List[str]` | 只保留的内容类型（与 exclude 互斥） |
| `exclude_content_types` | `str` 或 `List[str]` | 需要排除的内容类型 |

---

### PatternMatcherPP - 模式匹配

基于状态机的模式匹配，用于提取或处理特定标记之间的内容。

```python
from alphora.postprocess import PatternMatcherPP

# 基础用法：提取 <think>...</think> 之间的内容
matcher = PatternMatcherPP(
    bos="<think>",           # Beginning of Start，开始标记
    eos="</think>",          # End of Start，结束标记
    matched_type="thinking"  # 匹配内容的类型
)

# 只输出匹配的内容
matcher = PatternMatcherPP(
    bos="<answer>",
    eos="</answer>",
    matched_type="answer",
    output_mode="only_matched"  # 只输出标记内的内容
)

# 排除匹配的内容（输出标记外的内容）
matcher = PatternMatcherPP(
    bos="<internal>",
    eos="</internal>",
    matched_type="internal",
    output_mode="exclude_matched"
)

# 不包含标记本身
matcher = PatternMatcherPP(
    bos="```",
    eos="```",
    matched_type="code",
    include_bos=False,  # 不输出开始标记
    include_eos=False   # 不输出结束标记
)

# 设置未匹配内容的类型
matcher = PatternMatcherPP(
    bos="<code>",
    eos="</code>",
    matched_type="code",
    unmatched_type="text"  # 标记外的内容类型
)
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `bos` | `str` | - | 开始标记（Beginning of Start） |
| `eos` | `str` | - | 结束标记（End of Start） |
| `matched_type` | `str` | `"match"` | 匹配内容的 content_type |
| `include_bos` | `bool` | `True` | 是否包含开始标记 |
| `include_eos` | `bool` | `True` | 是否包含结束标记 |
| `output_mode` | `str` | `"all"` | 输出模式：`all`/`only_matched`/`exclude_matched` |
| `unmatched_type` | `str` | `None` | 未匹配内容的类型，None 保持原类型 |
| `buffer_size` | `int` | `3` | 缓冲区基础大小 |

**输出模式**：

| 模式 | 说明 |
|------|------|
| `all` | 输出所有内容（默认） |
| `only_matched` | 只输出匹配的内容（标记之间的内容） |
| `exclude_matched` | 只输出不匹配的内容（标记之外的内容） |

**使用场景示例**：

```python
# 场景 1：提取 AI 的思考过程
thinking_extractor = PatternMatcherPP(
    bos="<think>",
    eos="</think>",
    matched_type="thinking",
    output_mode="only_matched",
    include_bos=False,
    include_eos=False
)

# 场景 2：隐藏内部推理，只显示最终答案
answer_only = PatternMatcherPP(
    bos="<reasoning>",
    eos="</reasoning>",
    matched_type="reasoning",
    output_mode="exclude_matched"
)

# 场景 3：代码块高亮
code_highlighter = PatternMatcherPP(
    bos="```python",
    eos="```",
    matched_type="python_code",
    include_bos=False,
    include_eos=False
)
```

---

### JsonKeyExtractorPP - JSON 提取

从流式 JSON 输出中实时提取指定字段的值。

```python
from alphora.postprocess import JsonKeyExtractorPP

# 提取单个 key
extractor = JsonKeyExtractorPP(target_key="content")

# 嵌套路径
extractor = JsonKeyExtractorPP(target_key="data.result.text")

# 数组索引
extractor = JsonKeyExtractorPP(target_key="items[0].name")

# 提取多个 key
extractor = JsonKeyExtractorPP(
    target_keys=["title", "content", "summary"],
    separator="\n---\n"  # 多个值之间的分隔符
)
```

**输出模式**：

```python
# target_only：只输出提取的值（流式+响应都是目标值）
extractor = JsonKeyExtractorPP(
    target_key="analysis",
    output_mode="target_only"
)

# raw_only：透传原始 JSON
extractor = JsonKeyExtractorPP(
    target_key="content",
    output_mode="raw_only"
)

# both：流式显示提取值，响应返回原始 JSON
extractor = JsonKeyExtractorPP(
    target_key="content",
    output_mode="both"
)
```

**参数说明**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_key` | `str` | - | 单个目标 key（支持嵌套路径） |
| `target_keys` | `List[str]` | - | 多个目标 key 列表 |
| `separator` | `str` | `"\n"` | 多 key 时的分隔符 |
| `content_type` | `str` | `"text"` | 输出的 content_type |
| `output_mode` | `str` | `"both"` | 输出模式 |

**实际应用示例**：

```python
from alphora.prompter import BasePrompt
from alphora.postprocess import JsonKeyExtractorPP

# AI 输出结构化 JSON
analyzer = BasePrompt(
    system="分析文本，以 JSON 格式输出：{\"sentiment\": \"...\", \"keywords\": [...], \"summary\": \"...\"}",
    user="分析：{{ text }}"
)

# 只提取 summary 字段流式显示
analyzer = analyzer >> JsonKeyExtractorPP(
    target_key="summary",
    output_mode="both"  # 流式显示 summary，响应保留完整 JSON
)

result = await analyzer.acall(text="这是一段需要分析的文本...")
# 流式输出：只显示 summary 内容
# result.response：完整的 JSON 字符串
```

---

### DynamicTypePP - 动态类型

根据内容中是否包含特定字符来动态更改 content_type。

```python
from alphora.postprocess import DynamicTypePP

# 根据字符判断类型
type_detector = DynamicTypePP(
    char_to_content_type={
        "?": "question",    # 包含 ? 则类型为 question
        "!": "exclamation", # 包含 ! 则类型为 exclamation
        "```": "code"       # 包含 ``` 则类型为 code
    }
)

# 设置默认类型
type_detector = DynamicTypePP(
    char_to_content_type={"?": "question"},
    default_content_type="statement"  # 不匹配时使用默认类型
)
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `char_to_content_type` | `Dict[str, str]` | 字符到内容类型的映射 |
| `default_content_type` | `str` | 默认内容类型（可选） |

---

### TypeMapperPP - 类型映射

将 content_type 根据映射表进行转换。

```python
from alphora.postprocess import TypeMapperPP

# 类型映射
mapper = TypeMapperPP(mapping={
    "thinking": "thought",      # thinking → thought
    "reasoning": "analysis",    # reasoning → analysis
    "code_block": "code"        # code_block → code
})
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `mapping` | `Dict[str, str]` | 类型映射表，键为原始类型，值为目标类型 |

---

### SplitterPP - 字符拆分

将文本块拆分成单个字符输出，用于实现打字机效果。

```python
from alphora.postprocess import SplitterPP

# 拆分为单字符
splitter = SplitterPP()

# 配合 Prompter 使用
prompt = BasePrompt(user="写一句话") >> SplitterPP()

# 每次输出一个字符
async for chunk in prompt.acall():
    print(chunk.content, end="", flush=True)
    await asyncio.sleep(0.05)  # 打字机效果
```

---

## 自定义后处理器

### 创建自定义后处理器

继承 `BasePostProcessor` 并实现 `process` 方法：

```python
from alphora.postprocess.base_pp import BasePostProcessor
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from typing import Iterator

class UpperCasePP(BasePostProcessor):
    """将内容转为大写的后处理器"""
    
    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        
        class UpperCaseGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
            
            def generate(self) -> Iterator[GeneratorOutput]:
                for output in self.original_generator:
                    yield GeneratorOutput(
                        content=output.content.upper(),
                        content_type=output.content_type
                    )
            
            async def agenerate(self) -> Iterator[GeneratorOutput]:
                async for output in self.original_generator:
                    yield GeneratorOutput(
                        content=output.content.upper(),
                        content_type=output.content_type
                    )
        
        return UpperCaseGenerator(generator)

# 使用自定义后处理器
prompt = BasePrompt(user="Say hello") >> UpperCasePP()
```

### 带状态的后处理器

```python
class WordCountPP(BasePostProcessor):
    """统计并在末尾追加字数的后处理器"""
    
    def __init__(self, append_count: bool = True):
        self.append_count = append_count
    
    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        pp = self
        
        class WordCountGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
                self.char_count = 0
            
            def generate(self) -> Iterator[GeneratorOutput]:
                for output in self.original_generator:
                    self.char_count += len(output.content)
                    yield output
                
                # 流结束后追加字数
                if pp.append_count:
                    yield GeneratorOutput(
                        content=f"\n\n[字数: {self.char_count}]",
                        content_type="meta"
                    )
            
            async def agenerate(self) -> Iterator[GeneratorOutput]:
                async for output in self.original_generator:
                    self.char_count += len(output.content)
                    yield output
                
                if pp.append_count:
                    yield GeneratorOutput(
                        content=f"\n\n[字数: {self.char_count}]",
                        content_type="meta"
                    )
        
        return WordCountGenerator(generator)
```

### 条件处理后处理器

```python
class ConditionalPP(BasePostProcessor):
    """根据条件应用不同处理的后处理器"""
    
    def __init__(self, condition_fn, true_pp: BasePostProcessor, false_pp: BasePostProcessor = None):
        self.condition_fn = condition_fn
        self.true_pp = true_pp
        self.false_pp = false_pp
    
    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        pp = self
        
        class ConditionalGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator):
                super().__init__(original_generator.content_type)
                self.original_generator = original_generator
            
            def generate(self) -> Iterator[GeneratorOutput]:
                for output in self.original_generator:
                    if pp.condition_fn(output):
                        # 条件为真，应用 true_pp
                        if pp.true_pp:
                            # 简化处理：直接修改内容
                            yield output
                    else:
                        # 条件为假，应用 false_pp 或透传
                        yield output
            
            async def agenerate(self) -> Iterator[GeneratorOutput]:
                async for output in self.original_generator:
                    if pp.condition_fn(output):
                        yield output
                    else:
                        yield output
        
        return ConditionalGenerator(generator)
```

---

## API 参考

### BasePostProcessor

所有后处理器的基类。

| 方法 | 说明 |
|------|------|
| `process(generator)` | 处理生成器，返回处理后的生成器（抽象方法） |
| `__call__(generator)` | 使后处理器可作为函数调用 |
| `__rshift__(other)` | 实现 `>>` 运算符，用于链式组合 |

### ReplacePP

| 参数 | 类型 | 说明 |
|------|------|------|
| `replace_map` | `Dict[str, str]` 或 `List[tuple]` | 通用替换规则 |
| `type_specific_replace` | `Dict[str, Dict/List]` | 按类型的替换规则 |

### FilterPP

| 参数 | 类型 | 说明 |
|------|------|------|
| `filter_chars` | `str` 或 `List[str]` | 过滤的字符 |
| `include_content_types` | `str` 或 `List[str]` | 只保留的类型 |
| `exclude_content_types` | `str` 或 `List[str]` | 排除的类型 |

### PatternMatcherPP

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `bos` | `str` | - | 开始标记 |
| `eos` | `str` | - | 结束标记 |
| `matched_type` | `str` | `"match"` | 匹配内容类型 |
| `include_bos` | `bool` | `True` | 包含开始标记 |
| `include_eos` | `bool` | `True` | 包含结束标记 |
| `output_mode` | `str` | `"all"` | 输出模式 |
| `unmatched_type` | `str` | `None` | 未匹配内容类型 |
| `buffer_size` | `int` | `3` | 缓冲区大小 |
| `min_buffer_size` | `int` | `2` | 最小缓冲区 |
| `max_buffer_size` | `int` | `4` | 最大缓冲区 |

### JsonKeyExtractorPP

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_key` | `str` | - | 单个目标 key |
| `target_keys` | `List[str]` | - | 多个目标 key |
| `separator` | `str` | `"\n"` | 分隔符 |
| `content_type` | `str` | `"text"` | 输出类型 |
| `output_mode` | `str` | `"both"` | 输出模式 |

### DynamicTypePP

| 参数 | 类型 | 说明 |
|------|------|------|
| `char_to_content_type` | `Dict[str, str]` | 字符到类型映射 |
| `default_content_type` | `str` | 默认类型 |

### TypeMapperPP

| 参数 | 类型 | 说明 |
|------|------|------|
| `mapping` | `Dict[str, str]` | 类型映射表 |

### SplitterPP

无参数，将文本块拆分为单字符输出。

### GeneratorOutput

后处理器处理的基本数据单元。

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 内容文本 |
| `content_type` | `str` | 内容类型标识 |

**特殊 content_type**：

| 类型 | 说明 |
|------|------|
| `[STREAM_IGNORE]` | 不流式输出，但加入响应 |
| `[RESPONSE_IGNORE]` | 流式输出，但不加入响应 |