import asyncio
from types import SimpleNamespace

from alphora.models.llms.openai_like import (
    OpenAILike,
    _AsyncStreamGenerator,
    _SyncStreamGenerator,
)
from alphora.models.llms.repetition_guard import (
    DEFAULT_LOOP_FALLBACK_MESSAGE,
    RepetitionGuard,
    RepetitionGuardConfig,
)
from alphora.prompter import BasePrompt


def _chunk(
    content: str = "",
    *,
    reasoning: str = "",
    finish_reason=None,
    tool_calls=None,
):
    return SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                delta=SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning,
                    tool_calls=tool_calls,
                ),
            )
        ],
    )


class _AsyncChunks:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.closed = False

    def __aiter__(self):
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        self.closed = True


class _PromptLoopLLM(OpenAILike):
    async def aget_streaming_response(self, *args, **kwargs):
        phrase = "这是一个用于测试循环检测的较长句子，包含足够多不同字符，并且长度超过三十二。"
        stream = _AsyncChunks([_chunk(phrase), _chunk(phrase), _chunk(phrase), _chunk("不应输出")])
        return _AsyncStreamGenerator(
            llm=self,
            stream_iter=stream,
            content_type=kwargs.get("content_type") or "char",
            stream_tool_calls=False,
        )


def test_repetition_guard_detects_long_repeated_paragraph():
    guard = RepetitionGuard()
    phrase = "这是一个用于测试循环检测的较长句子，包含足够多不同字符，并且长度超过三十二。"

    assert guard.observe(phrase, "char") is None
    assert guard.observe(phrase, "char") is None
    match = guard.observe(phrase, "char")

    assert match is not None
    assert match.repeats == 3


def test_repetition_guard_ignores_normal_text_and_enumeration():
    guard = RepetitionGuard()
    text = (
        "第一步，读取文件并分析字段。第二步，清洗数据并构造指标。"
        "第三步，按月份和分层汇总。第四步，输出表格并解释口径。"
    )

    assert guard.observe(text, "char") is None


def test_repetition_guard_detects_across_chunk_boundaries():
    guard = RepetitionGuard()
    phrase = "跨 chunk 的循环检测也应该可以工作，这句话长度超过三十二个字符。"
    stream_text = phrase * 3

    match = None
    for index in range(0, len(stream_text), 11):
        match = guard.observe(stream_text[index:index + 11], "char")

    assert match is not None


def test_repetition_guard_skips_tool_call_args():
    guard = RepetitionGuard()
    phrase = "arguments should not be inspected even when this chunk repeats. "

    assert guard.observe(phrase * 3, "tool_call_args") is None


def test_sync_generator_aborts_with_fallback_on_loop():
    llm = OpenAILike(model_name="test", api_key="test")
    phrase = "这是一个用于测试同步生成器打断的较长句子，包含足够多不同字符，并且长度超过三十二。"
    chunks = [_chunk(phrase), _chunk(phrase), _chunk(phrase), _chunk("不应输出")]
    generator = _SyncStreamGenerator(
        llm=llm,
        stream_iter=iter(chunks),
        content_type="char",
        stream_tool_calls=False,
    )

    outputs = list(generator)

    assert [out.content for out in outputs] == [phrase, phrase, DEFAULT_LOOP_FALLBACK_MESSAGE]
    assert generator.get_finish_reason() == "loop_detected"


def test_async_generator_aborts_with_fallback_on_loop():
    llm = OpenAILike(model_name="test", api_key="test")
    phrase = "这是一个用于测试异步生成器打断的较长句子，包含足够多不同字符，并且长度超过三十二。"
    stream = _AsyncChunks([_chunk(phrase), _chunk(phrase), _chunk(phrase), _chunk("不应输出")])
    generator = _AsyncStreamGenerator(
        llm=llm,
        stream_iter=stream,
        content_type="char",
        stream_tool_calls=False,
    )

    async def collect():
        outputs = []
        async for out in generator:
            outputs.append(out.content)
        return outputs

    outputs = asyncio.run(collect())

    assert outputs == [phrase, phrase, DEFAULT_LOOP_FALLBACK_MESSAGE]
    assert generator.get_finish_reason() == "loop_detected"
    assert stream.closed is True


def test_prompt_acall_stream_receives_loop_fallback():
    llm = _PromptLoopLLM(model_name="test", api_key="test")
    prompt = BasePrompt(system_prompt="你是测试助手。", user_prompt="{{query}}")
    prompt.add_llm(llm)

    result = asyncio.run(prompt.acall(query="触发循环", is_stream=True))

    assert result.endswith(DEFAULT_LOOP_FALLBACK_MESSAGE)
    assert "不应输出" not in result
    assert result.finish_reason == "loop_detected"


def test_custom_config_can_disable_false_positive_by_content_type():
    config = RepetitionGuardConfig(text_content_types=frozenset({"text"}))
    guard = RepetitionGuard(config)
    phrase = "这个 char 类型内容即使重复三次，也会因为配置跳过检测。"

    assert guard.observe(phrase * 3, "char") is None
