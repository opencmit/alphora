"""把流式工具调用转换成「便于前端渲染」的内容流。

1. **哪些工具需要被解析？**  -- ``tools`` 里列出的工具名才会被转换。
2. **没匹配到的工具怎么办？** -- 一个开关 ``unmatched``：``"pass"`` 原样放行 /
   ``"drop"`` 直接不输出。
3. **匹配到的工具能配什么？** -- 提示文案 ``label``（或分别 ``label_start`` /
   ``label_end``）+ ``args``（要输出哪些参数、各自的 content_type；没列出的参数
   一律不输出）。

提示文案可省略：``start_text = label_start or label``、``end_text = label_end or label``。
若开始文案为空，则 **不发 start/end 标签**，且参数内容作为「普通正文」输出 —— 此时
**不附带任何 tool_call_id/status/arg 等 meta**（适合 think / finish 这种「只要内容、
不要工具入口」的工具，内容会直接落在主对话区，而非右侧工作区）；若只配开始文案则只发 start。

输出约定（固定，便于前端对接）::

    开始(仅当 start_text 非空):  content=start_text,  content_type=label_content_type(默认 tool_status),
                  meta={"tool_call_id": id, "name": 工具名, "status": "start"}
    参数增量(有 label 的工具): content=增量值, content_type=配置的 type,
                  meta={"tool_call_id": id, "name": 工具名, "status": "running", "arg": 参数名}
    参数增量(无 label 的工具): content=增量值, content_type=配置的 type, meta=None（当普通正文）
    结束(仅当 end_text 非空):  content=end_text,  content_type=label_content_type,
                  meta={"tool_call_id": id, "name": 工具名, "status": "end"}
    未配置参数:   不输出
    其它普通内容: 原样透传

需要配合 ``stream_tool_calls=True`` 使用，否则流中不会出现 ``tool_call`` /
``tool_call_args`` 类型的 chunk。

重要：``tool_call`` / ``tool_call_args`` 是框架保留类型，``acall`` 消费循环与
``alphora/server/stream_responser.py`` 的 SSE 层都会把这类 content 当作 JSON
``json.loads``。因此本后处理器产出的标签/参数 content_type **不能包含 ``tool_call``
子串**（构造时会校验报错），默认标签类型用 ``"tool_status"``，参数用各自的自定义
类型，content 均为纯文本，安全地走通用转发分支。

示例::

    from alphora.postprocess import ToolCallStreamRenderPP, ToolRender

    pp = ToolCallStreamRenderPP(
        tools={
            "write_python": ToolRender(
                label="正在编写 Python 代码",
                args={"desc": "python_desc"},   # 只输出 desc，code 等被拦截
            ),
            # 也支持等价的 dict 简写，省去 import：
            "run_bash": {"label": "执行命令", "args": {"command": "terminal"}},
        },
        unmatched="pass",   # "pass"=透传未配置工具；"drop"=不输出
        emit_end=True,      # 是否发结束信号（默认 start + end）
    )

    gen = await prompt.acall(
        query="...", tools=tools, is_stream=True,
        stream_tool_calls=True, postprocessor=pp, return_generator=True,
    )
    async for ck in gen:
        ...  # ck.content_type / ck.content / ck.meta
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Iterator, List, Mapping, Optional, Union

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess._tool_call_json import extract_arg_value
from alphora.postprocess.base_pp import BasePostProcessor

# meta 中携带工具调用 id 的固定键名
TOOL_CALL_ID_KEY = "tool_call_id"
STATUS_KEY = "status"
ARG_KEY = "arg"
NAME_KEY = "name"
STATUS_START = "start"
STATUS_RUNNING = "running"
STATUS_END = "end"

_TOOL_RENDER_FIELDS = {"label", "label_start", "label_end", "args", "label_content_type"}


@dataclass
class ToolRender:
    """单个工具的渲染配置。

    Attributes:
        label: 开始/结束统一的提示文案简写。当未单独指定 ``label_start`` /
            ``label_end`` 时，start 与 end 都用它。
        label_start: 工具开始时的提示文案（优先于 ``label``）。
        label_end: 工具结束时的提示文案（优先于 ``label``）。
        args: ``{参数名: content_type}``。只有列出的参数会增量输出，其余参数一律拦截。
        label_content_type: start/end 标签的 content_type，默认 ``"tool_status"``。
            **不能包含 ``"tool_call"`` 子串**：``tool_call`` / ``tool_call_args`` 是框架
            保留类型，``acall`` 消费循环与 SSE 层会把这类 content 当作 JSON 解析，
            用纯文本标签会导致解析失败。

    label 可省略规则（按 ``label_start or label`` / ``label_end or label`` 解析）：
        - 都留空           -> 不发 start/end，只输出参数内容；
        - 只有开始文案      -> 只发 start，不发 end；
        - 只有结束文案      -> 因为没有 start，end 也不会发（块以 start 开启）。
    """

    label: str = ""
    label_start: str = ""
    label_end: str = ""
    args: Dict[str, str] = field(default_factory=dict)
    label_content_type: str = "tool"

    @property
    def start_text(self) -> str:
        return self.label_start or self.label

    @property
    def end_text(self) -> str:
        return self.label_end or self.label

    @classmethod
    def coerce(cls, value: Union["ToolRender", Mapping]) -> "ToolRender":
        """把 ToolRender 或等价 dict 归一化为 ToolRender。"""
        if isinstance(value, ToolRender):
            args = dict(value.args or {})
            ctype = value.label_content_type or "tool_status"
            cls._validate_content_type(ctype, where="label_content_type")
            cls._validate_args(args)
            return ToolRender(
                label=value.label,
                label_start=value.label_start,
                label_end=value.label_end,
                args=args,
                label_content_type=ctype,
            )
        if isinstance(value, Mapping):
            unknown = set(value.keys()) - _TOOL_RENDER_FIELDS
            if unknown:
                raise ValueError(
                    f"ToolRender 配置包含未知字段: {sorted(unknown)}；"
                    f"仅支持 {sorted(_TOOL_RENDER_FIELDS)}"
                )
            args = dict(value.get("args") or {})
            ctype = value.get("label_content_type") or "tool_status"
            cls._validate_content_type(ctype, where="label_content_type")
            cls._validate_args(args)
            return ToolRender(
                label=value.get("label", "") or "",
                label_start=value.get("label_start", "") or "",
                label_end=value.get("label_end", "") or "",
                args=args,
                label_content_type=ctype,
            )
        raise TypeError(
            f"tools 的值必须是 ToolRender 或 dict，收到 {type(value).__name__}"
        )

    @staticmethod
    def _validate_content_type(ctype: str, where: str) -> None:
        """拒绝含 ``tool_call`` 子串的 content_type（框架保留类型）。"""
        if "tool_call" in ctype:
            raise ValueError(
                f"{where}={ctype!r} 不可包含 'tool_call' 子串："
                f"'tool_call' / 'tool_call_args' 是框架保留类型，"
                f"acall 消费循环与 SSE 层会将其 content 当作 JSON 解析，"
                f"纯文本会解析失败。请改用如 'tool_status' 等自定义类型。"
            )

    @classmethod
    def _validate_args(cls, args: Dict[str, str]) -> None:
        for k, v in args.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(
                    f"args 必须是 {{参数名(str): content_type(str)}}，收到 {k!r}: {v!r}"
                )
            cls._validate_content_type(v, where=f"args[{k!r}] 的 content_type")


class ToolCallStreamRenderPP(BasePostProcessor):
    """流式工具调用渲染后处理器（见模块 docstring）。"""

    def __init__(
        self,
        tools: Mapping[str, Union[ToolRender, Mapping]],
        unmatched: str = "pass",
        emit_end: bool = True,
        emit_start: bool = True,
    ):
        """
        Args:
            tools: ``{工具名: ToolRender | dict}``。只有这里列出的工具会被解析转换。
            unmatched: 未匹配工具的处理方式：``"pass"`` 原样透传 ``tool_call`` /
                ``tool_call_args``；``"drop"`` 全部不输出。
            emit_end: 是否在工具参数流结束（切换到下个工具 / 整个流结束）时
                发出 ``status="end"`` 的结束信号。
            emit_start: 是否在工具开始时发出 ``status="start"`` 的标签。
        """
        if unmatched not in ("pass", "drop"):
            raise ValueError(f"unmatched 必须是 'pass' 或 'drop'，收到 {unmatched!r}")
        if not isinstance(tools, Mapping):
            raise TypeError("tools 必须是 {工具名: ToolRender|dict} 的映射")

        self.tools: Dict[str, ToolRender] = {
            name: ToolRender.coerce(cfg) for name, cfg in tools.items()
        }
        self.unmatched = unmatched
        self.emit_end = emit_end
        self.emit_start = emit_start

    # ------------------------------------------------------------------ #
    # BasePostProcessor 接口
    # ------------------------------------------------------------------ #
    def process(self, generator: BaseGenerator[GeneratorOutput]) -> BaseGenerator[GeneratorOutput]:
        pp = self

        class RenderGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, original_generator):
                super().__init__(getattr(original_generator, "content_type", "text"))
                self.original_generator = original_generator

            def generate(self) -> Iterator[GeneratorOutput]:
                state = pp._new_state()
                for output in self.original_generator:
                    for out in pp._handle(output, state):
                        yield out
                for out in pp._finalize(state):
                    yield out

            async def agenerate(self) -> AsyncIterator[GeneratorOutput]:
                state = pp._new_state()
                async for output in self.original_generator:
                    for out in pp._handle(output, state):
                        yield out
                for out in pp._finalize(state):
                    yield out

        return RenderGenerator(generator)

    # ------------------------------------------------------------------ #
    # 状态机
    # ------------------------------------------------------------------ #
    @staticmethod
    def _new_state() -> dict:
        return {
            "current_index": None,        # 当前正在累积参数的 tool index
            "index_name": {},             # idx -> 工具名（所有工具，含未匹配）
            "index_id": {},               # idx -> tool_call_id（解析或回退生成）
            "arg_buffers": {},            # idx -> 累积的 arguments JSON 片段
            "emitted": {},                # idx -> {arg_name -> 已发出的完整值}
            "started": set(),             # 已发出 start 的 idx（仅匹配工具）
            "ended": set(),               # 已发出 end 的 idx（仅匹配工具）
            "order": [],                  # 按出现顺序记录的 idx（用于 finalize）
        }

    def _handle(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        ctype = output.content_type
        if ctype == "tool_call":
            return self._handle_tool_call(output, state)
        if ctype == "tool_call_args":
            return self._handle_tool_call_args(output, state)
        # 其它内容（正文/think/等）原样透传
        return [output]

    def _handle_tool_call(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        info = self._safe_json(output.content)
        if info is None:
            # 无法解析的 tool_call：按 unmatched 兜底，避免吞掉信息
            return [output] if self.unmatched == "pass" else []

        idx = info.get("index", 0)
        name = info.get("name", "") or ""
        raw_id = info.get("id")
        tcid = raw_id if raw_id else f"call_{idx}"

        outputs: List[GeneratorOutput] = []
        # 切换到新的 tool index：先收尾上一个工具
        if state["current_index"] is not None and state["current_index"] != idx:
            outputs.extend(self._emit_end(state["current_index"], state))

        state["current_index"] = idx
        if idx not in state["index_name"]:
            state["order"].append(idx)
        state["index_name"][idx] = name
        state["index_id"][idx] = tcid
        state["arg_buffers"].setdefault(idx, "")
        state["emitted"].setdefault(idx, {})

        if name in self.tools:
            # 匹配工具：仅当配置了开始文案时才发 start 标签（同一 idx 只发一次），
            # 不再透传原始 JSON。开始文案为空表示「只输出参数、不带工具名」，
            # 此时不记入 started，end 也随之不发。
            render = self.tools[name]
            if self.emit_start and render.start_text and idx not in state["started"]:
                state["started"].add(idx)
                outputs.append(GeneratorOutput(
                    content=render.start_text,
                    content_type=render.label_content_type,
                    meta={TOOL_CALL_ID_KEY: tcid, NAME_KEY: name, STATUS_KEY: STATUS_START},
                ))
            return outputs

        # 未匹配工具
        if self.unmatched == "pass":
            outputs.append(output)
        return outputs

    def _handle_tool_call_args(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        idx = state["current_index"]
        if idx is None:
            # 还没见到任何 tool_call 就来了 args：当作未知工具处理
            return [output] if self.unmatched == "pass" else []

        name = state["index_name"].get(idx, "")
        state["arg_buffers"][idx] += output.content or ""

        if name in self.tools:
            tcid = state["index_id"].get(idx, f"call_{idx}")
            render = self.tools[name]
            # 无开始标签的工具（如 think / finish）= 没有「工具入口」概念，参数内容直接作为
            # 普通正文输出，**不附带 tool_call_id/status/arg 等 meta**，避免前端误判为工具调用
            # 而把内容塞进右侧工作区。只有带 label 的工具才发结构化 meta 供前端归组到右侧详情。
            emit_meta = bool(render.start_text)
            outputs: List[GeneratorOutput] = []
            for arg_name, out_ctype in render.args.items():
                delta = self._extract_incremental(idx, arg_name, state)
                if delta:
                    meta = (
                        {
                            TOOL_CALL_ID_KEY: tcid,
                            NAME_KEY: name,
                            STATUS_KEY: STATUS_RUNNING,
                            ARG_KEY: arg_name,
                        }
                        if emit_meta
                        else None
                    )
                    outputs.append(GeneratorOutput(
                        content=delta,
                        content_type=out_ctype,
                        meta=meta,
                    ))
            # 未配置参数：不输出（已被忽略）
            return outputs

        # 未匹配工具
        return [output] if self.unmatched == "pass" else []

    def _finalize(self, state: dict) -> List[GeneratorOutput]:
        """流结束时，对仍未收尾的匹配工具补发 end。"""
        outputs: List[GeneratorOutput] = []
        for idx in state["order"]:
            outputs.extend(self._emit_end(idx, state))
        return outputs

    def _emit_end(self, idx: int, state: dict) -> List[GeneratorOutput]:
        if not self.emit_end:
            return []
        if idx not in state["started"] or idx in state["ended"]:
            return []
        state["ended"].add(idx)
        name = state["index_name"].get(idx, "")
        render = self.tools.get(name)
        if render is None or not render.end_text:
            return []
        tcid = state["index_id"].get(idx, f"call_{idx}")
        return [GeneratorOutput(
            content=render.end_text,
            content_type=render.label_content_type,
            meta={TOOL_CALL_ID_KEY: tcid, NAME_KEY: name, STATUS_KEY: STATUS_END},
        )]

    # ------------------------------------------------------------------ #
    # 增量提取
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_incremental(idx: int, arg_name: str, state: dict) -> Optional[str]:
        buffer = state["arg_buffers"][idx]
        value = extract_arg_value(buffer, arg_name)
        if value is None:
            return None

        emitted = state["emitted"][idx]
        last = emitted.get(arg_name, "")
        if value.startswith(last):
            delta = value[len(last):]
            if delta:
                emitted[arg_name] = value
                return delta
        elif not last:
            emitted[arg_name] = value
            return value
        return None

    @staticmethod
    def _safe_json(content: str) -> Optional[dict]:
        try:
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
