"""
Tutorial 19: Tool call postprocessors (stream extraction, filtering, arg extraction).

Demonstrates three types of tool-call post-processing:

1) ToolCallArgStreamPP  -- 流式提取工具调用参数（process 层）
2) ToolCallFilterPP     -- 按工具名过滤最终 ToolCall 结果（process_tool_call 层）
3) ToolCallArgExtractorPP -- 从最终 ToolCall 中提取特定参数（process_tool_call 层）
4) 链式组合             -- 多个后处理器串联

Run:
  python tutorials/19_tool_call_postprocess.py
"""

import json
from typing import Iterator, AsyncIterator, List

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.models.llms.types import ToolCall
from alphora.postprocess import (
    ToolCallArgStreamPP,
    ToolCallFilterPP,
    ToolCallArgExtractorPP,
)


# ---------------------------------------------------------------------------
# 辅助：模拟 LLM 的流式工具调用输出
# ---------------------------------------------------------------------------

class MockToolCallGenerator(BaseGenerator[GeneratorOutput]):
    """模拟 LLM 在 stream_tool_calls=True 时的输出。

    按以下顺序 yield chunk:
      1. tool_call   (JSON: index, id, name)
      2. tool_call_args 片段 (逐步拼成完整的 arguments JSON)
    """

    def __init__(self, tool_calls: List[dict], chunk_size: int = 8):
        """
        Args:
            tool_calls: 模拟的工具调用列表，每个元素格式:
                {"name": "run_bash", "id": "call_001", "arguments": {"command": "ls -la"}}
            chunk_size: 每个 args chunk 的大小
        """
        super().__init__(content_type="char")
        self._tool_calls = tool_calls
        self._chunk_size = chunk_size

    def generate(self) -> Iterator[GeneratorOutput]:
        for idx, tc in enumerate(self._tool_calls):
            yield GeneratorOutput(
                content=json.dumps({
                    "index": idx,
                    "id": tc.get("id", f"call_{idx:03d}"),
                    "name": tc["name"],
                }, ensure_ascii=False),
                content_type="tool_call",
            )

            args_json = json.dumps(tc.get("arguments", {}), ensure_ascii=False)
            for i in range(0, len(args_json), self._chunk_size):
                yield GeneratorOutput(
                    content=args_json[i:i + self._chunk_size],
                    content_type="tool_call_args",
                )

    async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
        for out in self.generate():
            yield out


# ---------------------------------------------------------------------------
# Demo 1: ToolCallArgStreamPP -- 流式提取工具调用参数
# ---------------------------------------------------------------------------

def demo_stream_extraction():
    print("=" * 60)
    print("Demo 1: ToolCallArgStreamPP (流式参数提取)")
    print("=" * 60)

    gen = MockToolCallGenerator(
        tool_calls=[
            {"name": "run_bash", "id": "call_001", "arguments": {"command": "ls -la /tmp"}},
            {"name": "read_file", "id": "call_002", "arguments": {"path": "/etc/hosts", "encoding": "utf-8"}},
        ],
        chunk_size=6,
    )

    pp = ToolCallArgStreamPP(
        tool_name="run_bash",
        arg_name="command",
        content_type="terminal",
    )

    processed = pp(gen)
    print("\n输出 chunks:")
    for out in processed:
        print(f"  content_type={out.content_type!r:20s} content={out.content!r}")

    print("\n说明: run_bash 的 command 被提取并标记为 'terminal'，")
    print("      read_file 的 tool_call/tool_call_args 原样透传。")


# ---------------------------------------------------------------------------
# Demo 2: ToolCallArgStreamPP -- 多工具映射
# ---------------------------------------------------------------------------

def demo_multi_mapping():
    print("\n" + "=" * 60)
    print("Demo 2: ToolCallArgStreamPP (多工具映射)")
    print("=" * 60)

    gen = MockToolCallGenerator(
        tool_calls=[
            {"name": "run_bash", "id": "call_001", "arguments": {"command": "echo hello"}},
            {"name": "run_python", "id": "call_002", "arguments": {"code": "print('hi')"}},
        ],
        chunk_size=10,
    )

    pp = ToolCallArgStreamPP(mappings={
        "run_bash": ("command", "terminal"),
        "run_python": ("code", "python"),
    })

    processed = pp(gen)
    print("\n输出 chunks:")
    for out in processed:
        print(f"  content_type={out.content_type!r:20s} content={out.content!r}")


# ---------------------------------------------------------------------------
# Demo 3: ToolCallFilterPP -- 按工具名过滤 ToolCall 结果
# ---------------------------------------------------------------------------

def demo_tool_call_filter():
    print("\n" + "=" * 60)
    print("Demo 3: ToolCallFilterPP (按工具名过滤)")
    print("=" * 60)

    tc = ToolCall.create(
        ("get_weather", {"city": "北京"}),
        ("debug_info", {"verbose": True}),
        ("get_weather", {"city": "上海"}),
    )
    print(f"\n过滤前: {len(tc)} 个工具调用")
    for item in tc:
        print(f"  {item['function']['name']}({item['function']['arguments']})")

    pp = ToolCallFilterPP(include_tools=["get_weather"])
    filtered = pp.process_tool_call(tc)
    print(f"\n过滤后 (include_tools=['get_weather']): {len(filtered)} 个工具调用")
    for item in filtered:
        print(f"  {item['function']['name']}({item['function']['arguments']})")

    pp2 = ToolCallFilterPP(exclude_tools=["debug_info"])
    filtered2 = pp2.process_tool_call(tc)
    print(f"\n过滤后 (exclude_tools=['debug_info']): {len(filtered2)} 个工具调用")
    for item in filtered2:
        print(f"  {item['function']['name']}({item['function']['arguments']})")


# ---------------------------------------------------------------------------
# Demo 4: ToolCallArgExtractorPP -- 提取特定参数
# ---------------------------------------------------------------------------

def demo_arg_extractor():
    print("\n" + "=" * 60)
    print("Demo 4: ToolCallArgExtractorPP (提取特定参数)")
    print("=" * 60)

    tc = ToolCall.create(
        ("get_weather", {"city": "北京", "unit": "celsius", "detailed": True}),
        ("search", {"query": "python tutorial", "limit": 10, "lang": "zh"}),
    )
    print(f"\n提取前:")
    for item in tc:
        print(f"  {item['function']['name']}({item['function']['arguments']})")

    pp = ToolCallArgExtractorPP(
        extraction_map={
            "get_weather": ["city"],
            "search": ["query"],
        },
    )
    extracted = pp.process_tool_call(tc)
    print(f"\n提取后 (只保留指定参数):")
    for item in extracted:
        print(f"  {item['function']['name']}({item['function']['arguments']})")


# ---------------------------------------------------------------------------
# Demo 5: 链式组合
# ---------------------------------------------------------------------------

def demo_chained():
    print("\n" + "=" * 60)
    print("Demo 5: 链式组合 (FilterPP >> ArgExtractorPP)")
    print("=" * 60)

    tc = ToolCall.create(
        ("get_weather", {"city": "北京", "unit": "celsius"}),
        ("debug_info", {"verbose": True}),
        ("search", {"query": "hello", "limit": 5}),
    )
    print(f"\n原始: {len(tc)} 个工具调用")
    for item in tc:
        print(f"  {item['function']['name']}({item['function']['arguments']})")

    pipeline = (
        ToolCallFilterPP(exclude_tools=["debug_info"])
        >> ToolCallArgExtractorPP(
            extraction_map={"get_weather": ["city"], "search": ["query"]},
        )
    )
    result = pipeline.process_tool_call(tc)
    print(f"\n链式处理后: {len(result)} 个工具调用")
    for item in result:
        print(f"  {item['function']['name']}({item['function']['arguments']})")


def main():
    demo_stream_extraction()
    demo_multi_mapping()
    demo_tool_call_filter()
    demo_arg_extractor()
    demo_chained()


if __name__ == "__main__":
    main()
