"""
Tutorial 21: ToolCallStreamRenderPP -- 把流式工具调用渲染成前端友好的内容流。

v2 协议（推荐）::

    入口:   content=工具名, content_type=tool, meta={tool_call_id, name, status:start, label:...}
    描述:   同槽位补丁 meta.label（来自 :args.desc 或静态 label）
    参数:   content=增量, content_type=配置, meta={tool_call_id, status:running, arg}
    结束:   content=工具名, content_type=tool, meta={status:end}

仍支持 legacy 配置（静态 label 文案 + args 简写），见 Demo 1–6。

Run:
  python tutorials/21_tool_call_render.py
"""

import asyncio
import json
from typing import AsyncIterator, Iterator, List

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess import ToolCallStreamRenderPP, ToolRender, Ref


# ---------------------------------------------------------------------------
# 辅助：模拟 LLM 在 stream_tool_calls=True 时的流式工具调用输出
# ---------------------------------------------------------------------------

class MockToolCallGenerator(BaseGenerator[GeneratorOutput]):
    """按以下顺序 yield chunk：
      1. tool_call        (JSON: index, id, name)
      2. tool_call_args   (逐片拼成完整 arguments JSON)
    可选地在最前面插入一段普通正文，演示透传。
    """

    def __init__(self, tool_calls: List[dict], chunk_size: int = 6, prefix_text: str = ""):
        super().__init__(content_type="char")
        self._tool_calls = tool_calls
        self._chunk_size = chunk_size
        self._prefix_text = prefix_text

    def generate(self) -> Iterator[GeneratorOutput]:
        if self._prefix_text:
            yield GeneratorOutput(content=self._prefix_text, content_type="char")
        for idx, tc in enumerate(self._tool_calls):
            yield GeneratorOutput(
                content=json.dumps(
                    {"index": idx, "id": tc.get("id", f"call_{idx:03d}"), "name": tc["name"]},
                    ensure_ascii=False),
                content_type="tool_call",
            )
            args_json = json.dumps(tc.get("arguments", {}), ensure_ascii=False)
            for i in range(0, len(args_json), self._chunk_size):
                yield GeneratorOutput(content=args_json[i:i + self._chunk_size],
                                      content_type="tool_call_args")

    async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
        for out in self.generate():
            yield out


def _show(out: GeneratorOutput) -> None:
    print(f"  content_type={out.content_type!r:14s} "
          f"content={out.content!r:28s} meta={out.meta}")


# ---------------------------------------------------------------------------
# Demo 0: v2 -- 工具名入口 + meta.label(desc) + code→python
# ---------------------------------------------------------------------------

def demo_v2_write_python():
    print("=" * 70)
    print("Demo 0 (v2): write_python — 入口工具名, meta.label=desc, code→python")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            "write_python": ToolRender(
                name={"content": Ref.name(), "content_type": "tool", "meta": {"xx": "xx"}},
                label=Ref.args("desc"),
                args={"code": {"content": Ref.args("code"), "content_type": "python"}},
            ),
        },
        unmatched="drop",
    )

    gen = MockToolCallGenerator([
        {
            "name": "write_python",
            "id": "call_123",
            "arguments": {"desc": "根据xx生成代码", "code": "import xx"},
        },
    ], chunk_size=4)

    chunks = list(pp(gen))
    print("\n输出 chunks:")
    for out in chunks:
        _show(out)

    assert any(
        c.content_type == "tool"
        and c.content == "write_python"
        and c.meta.get("status") == "start"
        and c.meta.get("xx") == "xx"
        for c in chunks
    ), "应有 tool 入口 chunk"
    assert any(
        c.content_type == "tool" and c.meta.get("label") == "根据xx生成代码"
        for c in chunks
    ), "应有 meta.label 补丁"
    python_chunks = [c for c in chunks if c.content_type == "python"]
    assert python_chunks, "应有 python 参数增量"
    assert all(c.meta.get("arg") == "code" for c in python_chunks)
    assert "import xx" == "".join(c.content for c in python_chunks)
    assert not any(c.content_type == "python_desc" for c in chunks), "desc 不应单独成段"
    assert any(c.meta and c.meta.get("status") == "end" for c in chunks), "应有 end"
    print("\n断言通过: v2 协议符合预期。")


# ---------------------------------------------------------------------------
# Demo 1: legacy -- write_python 只输出 desc，拦截 code
# ---------------------------------------------------------------------------

def demo_basic():
    print("=" * 70)
    print("Demo 1 (legacy): write_python(desc, code) -> 输出 desc, 拦截 code")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            "write_python": ToolRender(
                label="正在编写 Python 代码",
                args={"desc": "python_desc"},   # 只输出 desc
            ),
        },
        unmatched="pass",
    )

    gen = MockToolCallGenerator([
        {"name": "write_python", "id": "call_py01",
         "arguments": {"desc": "计算斐波那契数列", "code": "def fib(n): ..."}},
    ], chunk_size=5)

    print("\n输出 chunks:")
    for out in pp(gen):
        _show(out)
    print("\n说明: start 标签 + desc 增量(content_type=python_desc) + end 标签；")
    print("      code 参数未在 args 中配置，被完全拦截。")


# ---------------------------------------------------------------------------
# Demo 2: 多工具 + 未匹配工具透传 (unmatched="pass")
# ---------------------------------------------------------------------------

def demo_multi_pass():
    print("\n" + "=" * 70)
    print("Demo 2: 多工具映射 + 未匹配工具透传 (unmatched='pass')")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            "write_python": ToolRender(label="正在编写代码", args={"code": "python"}),
            # dict 简写，等价于 ToolRender，省去 import
            "run_bash": {"label": "正在执行命令", "args": {"command": "terminal"}},
        },
        unmatched="pass",
    )

    gen = MockToolCallGenerator([
        {"name": "run_bash", "id": "c1", "arguments": {"command": "ls -la /tmp"}},
        {"name": "write_python", "id": "c2", "arguments": {"code": "print('hi')"}},
        {"name": "search", "id": "c3", "arguments": {"query": "python"}},  # 未配置 -> 透传
    ], chunk_size=8)

    print("\n输出 chunks:")
    for out in pp(gen):
        _show(out)
    print("\n说明: run_bash / write_python 被转换；search 未配置，原样透传 tool_call/args。")


# ---------------------------------------------------------------------------
# Demo 3: 未匹配工具直接丢弃 (unmatched="drop")
# ---------------------------------------------------------------------------

def demo_drop():
    print("\n" + "=" * 70)
    print("Demo 3: 未匹配工具直接丢弃 (unmatched='drop')")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={"write_python": ToolRender(label="正在编写代码", args={"code": "python"})},
        unmatched="drop",
    )

    gen = MockToolCallGenerator([
        {"name": "debug_dump", "id": "d0", "arguments": {"verbose": True}},  # 丢弃
        {"name": "write_python", "id": "d1", "arguments": {"code": "x = 1"}},
    ], chunk_size=4)

    print("\n输出 chunks:")
    for out in pp(gen):
        _show(out)
    print("\n说明: debug_dump 未配置且 unmatched='drop'，整段不输出。")


# ---------------------------------------------------------------------------
# Demo 4: 异步消费（acall 的真实场景）
# ---------------------------------------------------------------------------

def demo_async():
    print("\n" + "=" * 70)
    print("Demo 4: 异步消费 (对应 acall + return_generator=True)")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={"write_python": ToolRender(label="正在编写 Python 代码",
                                          args={"desc": "python_desc"})},
        unmatched="pass",
    )
    gen = MockToolCallGenerator([
        {"name": "write_python", "id": "a1",
         "arguments": {"desc": "排序算法", "code": "sorted(x)"}},
    ], chunk_size=3, prefix_text="让我来帮你写一段代码。")

    async def run():
        print("\n输出 chunks:")
        async for out in pp(gen):
            _show(out)

    asyncio.run(run())
    print("\n真实用法:")
    print("  gen = await prompt.acall(query=..., tools=tools, is_stream=True,")
    print("                           stream_tool_calls=True, postprocessor=pp,")
    print("                           return_generator=True)")
    print("  async for ck in gen: ...")


# ---------------------------------------------------------------------------
# Demo 5: label 可选 -- 只输出参数、不带工具名 (think / finish)
# ---------------------------------------------------------------------------

def demo_label_optional():
    print("\n" + "=" * 70)
    print("Demo 5: legacy — think/finish 只出内容, call_specialist 只发提示")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            "think": ToolRender(args={"thought": "think"}),
            # 只有 label，没有 args：纯状态提示（无参数内容）
            "call_specialist": ToolRender(label="正在召唤专家智能体"),
            # 无 label：只把 delivery_summary 当 char 输出
            "finish": ToolRender(args={"delivery_summary": "char"}),
        },
        unmatched="drop",
        emit_end=True,
    )

    gen = MockToolCallGenerator([
        {"name": "think", "id": "t1", "arguments": {"thought": "先分析需求，再拆解任务"}},
        {"name": "call_specialist", "id": "t2", "arguments": {"agent": "researcher"}},
        {"name": "finish", "id": "t3", "arguments": {"delivery_summary": "已完成全部任务"}},
    ], chunk_size=6)

    print("\n输出 chunks:")
    for out in pp(gen):
        _show(out)
    print("\n说明: think/finish 无 label -> 无 tool_call 标签块，仅输出参数(带 tool_call_id)；")
    print("      call_specialist 有 label -> 发 start/end 提示，无参数内容。")


# ---------------------------------------------------------------------------
# Demo 6: label_start / label_end -- start 与 end 显示不同文案
# ---------------------------------------------------------------------------

def demo_label_start_end():
    print("\n" + "=" * 70)
    print("Demo 6: label_start / label_end (开始/结束不同文案)")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            # 开始/结束显示不同文案
            "call_specialist": ToolRender(
                label_start="正在召唤专家智能体…",
                label_end="专家智能体已就绪",
            ),
            # 只配 label_start -> 只发 start，不发 end
            "compile": ToolRender(label_start="正在编译"),
            # write_python: 参数 chunk 现在带 status='running' 和 arg 参数名
            "write_python": ToolRender(label="正在编写代码", args={"code": "python"}),
        },
        unmatched="drop",
    )

    gen = MockToolCallGenerator([
        {"name": "call_specialist", "id": "s1", "arguments": {"agent": "x"}},
        {"name": "compile", "id": "s2", "arguments": {"target": "main"}},
        {"name": "write_python", "id": "s3", "arguments": {"code": "print(42)"}},
    ], chunk_size=6)

    print("\n输出 chunks:")
    for out in pp(gen):
        _show(out)
    print("\n说明: call_specialist 的 start/end 文案不同；compile 只配 label_start 故只发 start；")
    print("      参数增量的 meta 现在带 status='running' 和 arg 参数名。")


def demo_v2_think_no_entry():
    print("\n" + "=" * 70)
    print("Demo 0b (v2): think — name=False，无主区工具入口")
    print("=" * 70)

    pp = ToolCallStreamRenderPP(
        tools={
            "think": ToolRender(name=False, args={"thought": "think"}),
        },
        unmatched="drop",
    )
    gen = MockToolCallGenerator([
        {"name": "think", "id": "t1", "arguments": {"thought": "分析中"}},
    ], chunk_size=8)
    chunks = list(pp(gen))
    for out in chunks:
        _show(out)
    assert not any(c.content_type == "tool" for c in chunks)
    assert any(c.content_type == "think" and c.meta is None for c in chunks)
    print("\n断言通过: 无 tool 入口，thought 作普通正文。")


def main():
    demo_v2_write_python()
    demo_v2_think_no_entry()
    demo_basic()
    demo_multi_pass()
    demo_drop()
    demo_async()
    demo_label_optional()
    demo_label_start_end()


if __name__ == "__main__":
    main()
