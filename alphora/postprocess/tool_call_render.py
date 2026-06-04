"""把流式工具调用转换成「便于前端渲染」的内容流（v2 协议）。

============================================================================
一、它解决什么问题
============================================================================

大模型在 ``stream_tool_calls=True`` 下会吐出两类原始 chunk：

- ``tool_call``       —— 一个 JSON：``{"index", "id", "name"}``，宣告开始调用某工具；
- ``tool_call_args``  —— 工具 ``arguments`` JSON 的「逐字增量片段」。

这两类是框架保留类型，前端无法直接渲染。``ToolCallStreamRenderPP`` 把它们改写成
**声明式、带结构化 meta 的内容流**，让前端能：

1. 在主对话区生成一个「工具胶囊」入口（图标 + 工具名 + 描述）；
2. 把工具的关键入参（代码 / SQL 等）以指定 ``content_type`` 流式送进右侧工作区；
3. 通过 ``meta.tool_call_id`` 把同一次调用的入口、描述、各参数、结果归到一组。

============================================================================
二、配置三件套：name / label / args
============================================================================

每个工具用一个 :class:`ToolRender` 描述「要输出什么」：

- ``name`` —— **工具入口槽**。决定主对话区那颗胶囊。
    * ``True``（默认）：等价 ``{"content": Ref.name(), "content_type": "tool"}``，
      即 ``content`` = 工具名、``content_type`` = ``"tool"``；
    * ``False``：**不发入口**（没有胶囊），只把 ``args`` 当普通正文/右侧内容输出。
      think / finish 这类「只要内容、不要工具按钮」的工具用它；
    * :class:`StreamSlot` 或 dict：自定义 ``content`` / ``content_type`` / ``meta``。

- ``label`` —— **写入入口的 ``meta.label``**，即胶囊上的描述文字。三种取值：
    * ``Ref.args("desc")`` / ``":args.desc"``：从工具 ``arguments`` 里的 ``desc`` 字段
      **流式**抽取，随生成过程不断更新 ``meta.label``（边写边变）；
    * 固定字符串（如 ``"正在编写代码"``）：入口创建时一次性写入；
    * ``None`` / 不填：默认用 **工具名**（``Ref.name()``）。

- ``args`` —— ``{参数名: 槽位}``，声明**要向前端输出**的入参；**未列出的参数一律拦截**。
    * 简写：``{"code": "python"}`` 等价
      ``{"code": {"content": Ref.args("code"), "content_type": "python"}}``；
    * 完整：``{"code": {"content": Ref.args("code"), "content_type": "python",
      "meta": {...}}}``。

- ``meta`` —— 业务扩展字段（如 ``{"icon": "code"}``），会合并进入口与 label 补丁的
  ``meta``。

绑定语法（配置期没有真实 ``tool`` 对象，用字符串/``Ref`` 表达）::

    tool.name        ->  ":name"        或 Ref.name()
    tool.args.desc   ->  ":args.desc"   或 Ref.args("desc")
    固定文案          ->  普通 str

============================================================================
三、自动注入的 meta（开发者不要手写这些键）
============================================================================

============  ========================================================
场景            框架自动写入的 meta 键
============  ========================================================
入口(start)    tool_call_id, name, status="start", label
label 补丁      tool_call_id, label
参数(running)  tool_call_id, name, status="running", arg=<参数名>
结束(end)      tool_call_id, name, status="end"
============  ========================================================

用户 ``meta`` 与上表 **浅合并**，键冲突时 **框架保留键优先**（``tool_call_id`` 不可被覆盖）。

============================================================================
四、输出 chunk 形状（以 write_python，label=:args.desc 为例）
============================================================================

::

    {"content":"write_python","content_type":"tool",
     "meta":{"tool_call_id":"call_123","name":"write_python","status":"start","label":"","xx":"xx"}}
    {"content":"write_python","content_type":"tool",
     "meta":{"tool_call_id":"call_123","label":"根据xx生成代码"}}        # label 流式补丁
    {"content":"import xx","content_type":"python",
     "meta":{"tool_call_id":"call_123","name":"write_python","status":"running","arg":"code"}}
    {"content":"write_python","content_type":"tool",
     "meta":{"tool_call_id":"call_123","name":"write_python","status":"end"}}

注意：

- 入口/label 补丁/结束三种 chunk 的 ``content`` 始终是 **工具名**（``content_type="tool"``）。
  前端按相同 ``(content_type="tool", tool_call_id)`` upsert 同一段，``meta.label`` 取最新值。
- 当 ``label`` 绑定了某个参数（如 ``desc``），该参数 **只驱动 ``meta.label``**，
  **不会**再作为独立 ``content_type`` 段输出（避免主区重复）。若确实想让 ``desc`` 同时进
  右侧详情，在 ``args`` 里再显式声明它。

============================================================================
五、顶层开关
============================================================================

- ``unmatched``：未在 ``tools`` 中登记的工具。``"pass"`` 原样透传框架
  ``tool_call`` / ``tool_call_args``；``"drop"`` 全部丢弃（主对话区更干净）。
- ``emit_start`` / ``emit_end``：是否发入口(start) / 结束(end) chunk。

============================================================================
六、约束
============================================================================

- 任何 ``content_type`` **不能包含子串 ``tool_call``**：``tool_call`` /
  ``tool_call_args`` 是框架保留类型，``acall`` 消费循环与 SSE 层会把这类 content 当作
  JSON ``json.loads`` 解析，纯文本会失败。构造期会校验报错。
- 必须配合 ``stream_tool_calls=True``，否则流中不会出现 ``tool_call`` chunk。

============================================================================
七、典型用法
============================================================================

标准编码工具（工具名入口 + 流式描述 + 代码进右侧）::

    from alphora.postprocess import ToolCallStreamRenderPP, ToolRender, Ref

    pp = ToolCallStreamRenderPP(
        tools={
            "write_python": ToolRender(
                name={"content": Ref.name(), "content_type": "tool", "meta": {"icon": "code"}},
                label=Ref.args("desc"),
                args={"code": {"content": Ref.args("code"), "content_type": "python"}},
            ),
        },
        unmatched="drop",
    )
    gen = await prompt.acall(
        query="...", tools=tools, is_stream=True,
        stream_tool_calls=True, postprocessor=pp, return_generator=True,
    )
    async for ck in gen:
        ...  # ck.content / ck.content_type / ck.meta -> SSE delta

更多形态::

    # 固定描述
    ToolRender(label="执行 SQL", args={"sql": "sql"})
    # 描述即工具名（不填 label）
    ToolRender(args={"code": "python"})
    # 纯状态提示（无参数）
    ToolRender(label="正在召唤专家智能体")
    # 不要主区入口，只要正文（思考 / 交付总结）
    ToolRender(name=False, args={"thought": "think"})
    ToolRender(name=False, args={"delivery_summary": "char"})
    # dict 简写（省 import）
    {"label": "执行命令", "args": {"command": "terminal"}}

============================================================================
八、向后兼容（legacy）
============================================================================

旧字段 ``label_start`` / ``label_end`` / ``label_content_type`` 仍可用：此时把
**文案放在 ``content`` 里**发 start/end（不是写 ``meta.label``）。仅为平滑迁移保留，
新代码请用上面的 v2 写法。``ToolRender(label_start=..., label_end=...)`` 会进入 legacy 分支。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, AsyncIterator, Dict, Iterator, List, Mapping, Optional, Union

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess._tool_call_json import extract_arg_value
from alphora.postprocess.base_pp import BasePostProcessor

TOOL_CALL_ID_KEY = "tool_call_id"
STATUS_KEY = "status"
ARG_KEY = "arg"
NAME_KEY = "name"
LABEL_KEY = "label"
STATUS_START = "start"
STATUS_RUNNING = "running"
STATUS_END = "end"

_BIND_NAME = ":name"
_BIND_ARG_PREFIX = ":args."

# v2 字段 + legacy 字段（coerce 时识别）
_TOOL_RENDER_V2_FIELDS = {"name", "label", "args", "meta"}
_TOOL_RENDER_LEGACY_FIELDS = {"label_start", "label_end", "label_content_type"}
_TOOL_RENDER_FIELDS = _TOOL_RENDER_V2_FIELDS | _TOOL_RENDER_LEGACY_FIELDS | {"label"}


class BindingKind(Enum):
    NAME = auto()
    ARG = auto()
    LITERAL = auto()


@dataclass(frozen=True)
class ContentBinding:
    """运行期内容绑定（配置期的 ``:name`` / ``:args.xxx``）。"""

    kind: BindingKind
    arg_name: str = ""

    @classmethod
    def parse(cls, value: Union[str, "ContentBinding", "Ref"]) -> "ContentBinding":
        if isinstance(value, ContentBinding):
            return value
        if isinstance(value, Ref):
            return value._binding
        if not isinstance(value, str):
            raise TypeError(f"content 绑定必须是 str、ContentBinding 或 Ref，收到 {type(value).__name__}")
        if value == _BIND_NAME:
            return cls(BindingKind.NAME)
        if value.startswith(_BIND_ARG_PREFIX):
            arg = value[len(_BIND_ARG_PREFIX) :]
            if not arg:
                raise ValueError(f"无效的参数绑定: {value!r}")
            return cls(BindingKind.ARG, arg_name=arg)
        return cls(BindingKind.LITERAL, arg_name=value)


class Ref:
    """绑定辅助：``Ref.name()`` / ``Ref.args('desc')``。"""

    @staticmethod
    def name() -> ContentBinding:
        return ContentBinding(BindingKind.NAME)

    @staticmethod
    def args(field: str) -> ContentBinding:
        if not field or not isinstance(field, str):
            raise ValueError("Ref.args(field) 需要非空字符串字段名")
        return ContentBinding(BindingKind.ARG, arg_name=field)

    def __init__(self, binding: ContentBinding):
        self._binding = binding


@dataclass
class StreamSlot:
    """单个输出槽位（工具入口或参数流）。"""

    content: Union[str, ContentBinding]
    content_type: str
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def coerce(
        cls,
        value: Union["StreamSlot", Mapping, bool, None],
        *,
        default_for_true: bool = True,
    ) -> Optional["StreamSlot"]:
        if value is False or value is None:
            return None
        if value is True:
            if not default_for_true:
                return None
            return cls(content=ContentBinding(BindingKind.NAME), content_type="tool")
        if isinstance(value, StreamSlot):
            binding = ContentBinding.parse(value.content)
            cls._validate_content_type(value.content_type, where="StreamSlot.content_type")
            return StreamSlot(content=binding, content_type=value.content_type, meta=dict(value.meta or {}))
        if isinstance(value, Mapping):
            if "content" not in value or "content_type" not in value:
                raise ValueError("StreamSlot dict 必须包含 content 与 content_type")
            binding = ContentBinding.parse(value["content"])
            ctype = value["content_type"]
            cls._validate_content_type(ctype, where="StreamSlot.content_type")
            return StreamSlot(
                content=binding,
                content_type=ctype,
                meta=dict(value.get("meta") or {}),
            )
        raise TypeError(f"无法解析为 StreamSlot: {type(value).__name__}")

    @staticmethod
    def _validate_content_type(ctype: str, where: str) -> None:
        if "tool_call" in ctype:
            raise ValueError(
                f"{where}={ctype!r} 不可包含 'tool_call' 子串："
                f"'tool_call' / 'tool_call_args' 是框架保留类型。"
            )


@dataclass(init=False)
class ToolRender:
    """单个工具的渲染配置（v2 归一化后的内部表示）。"""

    name_slot: Optional[StreamSlot]
    label_binding: Optional[ContentBinding]
    label_static: Optional[str]
    arg_slots: Dict[str, StreamSlot]
    tool_meta: Dict[str, Any]
    legacy_mode: bool
    legacy_start_text: str
    legacy_end_text: str
    legacy_label_content_type: str
    legacy_args: Dict[str, str]

    def __init__(
        self,
        *,
        name: Union[bool, StreamSlot, Mapping[str, Any]] = True,
        label: Union[str, ContentBinding, Ref, None] = None,
        args: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
        label_start: str = "",
        label_end: str = "",
        label_content_type: str = "tool",
    ):
        if label_start or label_end:
            cfg: Dict[str, Any] = {
                "label_start": label_start,
                "label_end": label_end,
                "args": args or {},
                "label_content_type": label_content_type,
            }
            if label:
                cfg["label"] = label
        else:
            cfg = {
                "name": name,
                "label": label,
                "args": args or {},
            }
            if meta:
                cfg["meta"] = meta
            if label_content_type != "tool":
                cfg["label_content_type"] = label_content_type
        normalized = ToolRender._coerce_mapping(cfg)
        self.name_slot = normalized.name_slot
        self.label_binding = normalized.label_binding
        self.label_static = normalized.label_static
        self.arg_slots = normalized.arg_slots
        self.tool_meta = normalized.tool_meta
        self.legacy_mode = normalized.legacy_mode
        self.legacy_start_text = normalized.legacy_start_text
        self.legacy_end_text = normalized.legacy_end_text
        self.legacy_label_content_type = normalized.legacy_label_content_type
        self.legacy_args = normalized.legacy_args

    @property
    def has_tool_entry(self) -> bool:
        return self.name_slot is not None

    @property
    def label_arg_name(self) -> Optional[str]:
        if self.legacy_mode:
            return None
        if self.label_binding is not None and self.label_binding.kind == BindingKind.ARG:
            return self.label_binding.arg_name
        return None

    @classmethod
    def coerce(cls, value: Union["ToolRender", Mapping]) -> "ToolRender":
        if isinstance(value, ToolRender):
            return value
        if isinstance(value, Mapping):
            return cls._coerce_mapping(value)
        raise TypeError(f"tools 的值必须是 ToolRender 或 dict，收到 {type(value).__name__}")

    @classmethod
    def _from_normalized(
        cls,
        *,
        name_slot: Optional[StreamSlot] = None,
        label_binding: Optional[ContentBinding] = None,
        label_static: Optional[str] = None,
        arg_slots: Optional[Dict[str, StreamSlot]] = None,
        tool_meta: Optional[Dict[str, Any]] = None,
        legacy_mode: bool = False,
        legacy_start_text: str = "",
        legacy_end_text: str = "",
        legacy_label_content_type: str = "tool",
        legacy_args: Optional[Dict[str, str]] = None,
    ) -> "ToolRender":
        inst = object.__new__(cls)
        inst.name_slot = name_slot
        inst.label_binding = label_binding
        inst.label_static = label_static
        inst.arg_slots = arg_slots or {}
        inst.tool_meta = tool_meta or {}
        inst.legacy_mode = legacy_mode
        inst.legacy_start_text = legacy_start_text
        inst.legacy_end_text = legacy_end_text
        inst.legacy_label_content_type = legacy_label_content_type
        inst.legacy_args = legacy_args or {}
        return inst

    @classmethod
    def _coerce_mapping(cls, value: Mapping) -> "ToolRender":
        keys = set(value.keys())
        unknown = keys - _TOOL_RENDER_FIELDS
        if unknown:
            raise ValueError(
                f"ToolRender 配置包含未知字段: {sorted(unknown)}；"
                f"支持 {sorted(_TOOL_RENDER_FIELDS)}"
            )
        if cls._looks_like_legacy(value):
            return cls._coerce_legacy(value)
        return cls._coerce_v2(value)

    @staticmethod
    def _looks_like_legacy(value: Mapping) -> bool:
        if "label_start" in value or "label_end" in value:
            return True
        if "name" in value or "meta" in value:
            return False
        label = value.get("label")
        if isinstance(label, str) and (
            label.startswith(_BIND_ARG_PREFIX) or label == _BIND_NAME
        ):
            return False
        if isinstance(label, (ContentBinding, Ref)):
            return False
        if label is None and "label" in value:
            return False
        args = value.get("args") or {}
        for v in args.values():
            if isinstance(v, Mapping) and "content" in v:
                return False
        if "label_content_type" in value:
            lct = value.get("label_content_type")
            if lct and lct != "tool":
                return True
        if label:
            return True
        if "name" not in value and args and all(isinstance(v, str) for v in args.values()):
            return True
        return False

    @classmethod
    def _coerce_legacy(cls, value: Mapping) -> "ToolRender":
        args = dict(value.get("args") or {})
        for k, v in args.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(f"legacy args 必须是 {{str: str}}，收到 {k!r}: {v!r}")
            StreamSlot._validate_content_type(v, where=f"args[{k!r}]")
        ctype = value.get("label_content_type") or "tool"
        StreamSlot._validate_content_type(ctype, where="label_content_type")
        label = value.get("label", "") or ""
        return cls._from_normalized(
            name_slot=None,
            legacy_mode=True,
            legacy_start_text=value.get("label_start", "") or label,
            legacy_end_text=value.get("label_end", "") or label,
            legacy_label_content_type=ctype,
            legacy_args=args,
        )

    @classmethod
    def _coerce_v2(cls, value: Mapping) -> "ToolRender":
        name_raw = value.get("name", True)
        name_slot = StreamSlot.coerce(name_raw, default_for_true=True)

        label_raw = value.get("label", None)
        label_binding, label_static = cls._parse_label(label_raw)

        arg_slots: Dict[str, StreamSlot] = {}
        for arg_name, arg_cfg in (value.get("args") or {}).items():
            if isinstance(arg_cfg, str):
                slot = StreamSlot(
                    content=ContentBinding(BindingKind.ARG, arg_name=arg_name),
                    content_type=arg_cfg,
                )
            else:
                slot = StreamSlot.coerce(arg_cfg, default_for_true=False)
            if slot is None:
                raise ValueError(f"args[{arg_name!r}] 无效")
            arg_slots[arg_name] = slot
            StreamSlot._validate_content_type(slot.content_type, where=f"args[{arg_name!r}]")

        return cls._from_normalized(
            name_slot=name_slot,
            label_binding=label_binding,
            label_static=label_static,
            arg_slots=arg_slots,
            tool_meta=dict(value.get("meta") or {}),
            legacy_mode=False,
        )

    @classmethod
    def _parse_label(
        cls, label_raw: Any,
    ) -> tuple[Optional[ContentBinding], Optional[str]]:
        if label_raw is None:
            return ContentBinding(BindingKind.NAME), None
        if isinstance(label_raw, (ContentBinding, Ref)):
            binding = ContentBinding.parse(label_raw)
            if binding.kind == BindingKind.LITERAL:
                return None, binding.arg_name
            return binding, None
        if isinstance(label_raw, str):
            binding = ContentBinding.parse(label_raw)
            if binding.kind == BindingKind.LITERAL:
                return None, label_raw
            return binding, None
        raise TypeError(f"label 必须是 str、None、ContentBinding 或 Ref，收到 {type(label_raw).__name__}")


def _merge_meta(framework: Dict[str, Any], *user_dicts: Mapping[str, Any]) -> Dict[str, Any]:
    """用户 meta 先合并，框架保留键覆盖（tool_call_id 等不可被覆盖）。"""
    merged: Dict[str, Any] = {}
    for d in user_dicts:
        if d:
            merged.update(dict(d))
    merged.update(framework)
    return merged


class ToolCallStreamRenderPP(BasePostProcessor):
    """流式工具调用渲染后处理器（v2，见模块 docstring）。"""

    def __init__(
        self,
        tools: Mapping[str, Union[ToolRender, Mapping]],
        unmatched: str = "pass",
        emit_end: bool = True,
        emit_start: bool = True,
    ):
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

    @staticmethod
    def _new_state() -> dict:
        return {
            "current_index": None,
            "index_name": {},
            "index_id": {},
            "arg_buffers": {},
            "emitted": {},
            "label_emitted": {},
            "started": set(),
            "ended": set(),
            "order": [],
        }

    def _handle(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        ctype = output.content_type
        if ctype == "tool_call":
            return self._handle_tool_call(output, state)
        if ctype == "tool_call_args":
            return self._handle_tool_call_args(output, state)
        return [output]

    def _handle_tool_call(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        info = self._safe_json(output.content)
        if info is None:
            return [output] if self.unmatched == "pass" else []

        idx = info.get("index", 0)
        name = info.get("name", "") or ""
        raw_id = info.get("id")
        tcid = raw_id if raw_id else f"call_{idx}"

        outputs: List[GeneratorOutput] = []
        if state["current_index"] is not None and state["current_index"] != idx:
            outputs.extend(self._emit_end(state["current_index"], state))

        state["current_index"] = idx
        if idx not in state["index_name"]:
            state["order"].append(idx)
        state["index_name"][idx] = name
        state["index_id"][idx] = tcid
        state["arg_buffers"].setdefault(idx, "")
        state["emitted"].setdefault(idx, {})
        state["label_emitted"].setdefault(idx, "")

        if name not in self.tools:
            if self.unmatched == "pass":
                outputs.append(output)
            return outputs

        render = self.tools[name]
        if render.legacy_mode:
            outputs.extend(self._legacy_emit_start(idx, name, tcid, render, state))
            return outputs

        if self.emit_start and render.has_tool_entry and idx not in state["started"]:
            outputs.extend(self._v2_emit_entry(idx, name, tcid, render, state))
        return outputs

    def _handle_tool_call_args(self, output: GeneratorOutput, state: dict) -> List[GeneratorOutput]:
        idx = state["current_index"]
        if idx is None:
            return [output] if self.unmatched == "pass" else []

        name = state["index_name"].get(idx, "")
        state["arg_buffers"][idx] += output.content or ""

        if name not in self.tools:
            return [output] if self.unmatched == "pass" else []

        render = self.tools[name]
        tcid = state["index_id"].get(idx, f"call_{idx}")

        if render.legacy_mode:
            return self._legacy_emit_args(idx, name, tcid, render, state)

        outputs: List[GeneratorOutput] = []
        outputs.extend(self._v2_emit_label_patch(idx, name, tcid, render, state))
        outputs.extend(self._v2_emit_arg_slots(idx, name, tcid, render, state))
        return outputs

    def _finalize(self, state: dict) -> List[GeneratorOutput]:
        outputs: List[GeneratorOutput] = []
        for idx in state["order"]:
            outputs.extend(self._emit_end(idx, state))
        return outputs

    # ------------------------------------------------------------------ #
    # v2
    # ------------------------------------------------------------------ #
    def _v2_emit_entry(
        self, idx: int, name: str, tcid: str, render: ToolRender, state: dict,
    ) -> List[GeneratorOutput]:
        slot = render.name_slot
        assert slot is not None
        state["started"].add(idx)
        content = self._resolve_slot_content(slot.content, idx, state) or name
        initial_label = self._resolve_label_value(idx, render, state)
        state["label_emitted"][idx] = initial_label
        meta = _merge_meta(
            {
                TOOL_CALL_ID_KEY: tcid,
                NAME_KEY: name,
                STATUS_KEY: STATUS_START,
                LABEL_KEY: initial_label,
            },
            render.tool_meta,
            slot.meta,
        )
        return [
            GeneratorOutput(content=content, content_type=slot.content_type, meta=meta),
        ]

    def _v2_emit_label_patch(
        self, idx: int, name: str, tcid: str, render: ToolRender, state: dict,
    ) -> List[GeneratorOutput]:
        if not render.has_tool_entry:
            return []
        label_arg = render.label_arg_name
        if label_arg is None:
            if render.label_static is not None:
                return []
            if render.label_binding and render.label_binding.kind == BindingKind.NAME:
                return []
            return []

        full = self._extract_full_arg(idx, label_arg, state)
        if full is None:
            return []
        last = state["label_emitted"].get(idx, "")
        if full == last:
            return []
        state["label_emitted"][idx] = full

        slot = render.name_slot
        assert slot is not None
        content = self._resolve_slot_content(slot.content, idx, state) or name
        meta = _merge_meta(
            {TOOL_CALL_ID_KEY: tcid, LABEL_KEY: full},
            render.tool_meta,
        )
        return [GeneratorOutput(content=content, content_type=slot.content_type, meta=meta)]

    def _v2_emit_arg_slots(
        self, idx: int, name: str, tcid: str, render: ToolRender, state: dict,
    ) -> List[GeneratorOutput]:
        emit_meta = render.has_tool_entry
        label_arg = render.label_arg_name
        outputs: List[GeneratorOutput] = []

        for arg_name, slot in render.arg_slots.items():
            if label_arg and arg_name == label_arg:
                continue
            binding = ContentBinding.parse(slot.content)
            if binding.kind != BindingKind.ARG or binding.arg_name != arg_name:
                source_arg = binding.arg_name if binding.kind == BindingKind.ARG else arg_name
            else:
                source_arg = arg_name
            delta = self._extract_incremental(idx, source_arg, state)
            if not delta:
                continue
            meta = None
            if emit_meta:
                meta = _merge_meta(
                    {
                        TOOL_CALL_ID_KEY: tcid,
                        NAME_KEY: name,
                        STATUS_KEY: STATUS_RUNNING,
                        ARG_KEY: arg_name,
                    },
                    slot.meta,
                )
            outputs.append(
                GeneratorOutput(content=delta, content_type=slot.content_type, meta=meta),
            )
        return outputs

    def _emit_end(self, idx: int, state: dict) -> List[GeneratorOutput]:
        if not self.emit_end or idx not in state["started"] or idx in state["ended"]:
            return []
        state["ended"].add(idx)
        name = state["index_name"].get(idx, "")
        render = self.tools.get(name)
        if render is None:
            return []
        tcid = state["index_id"].get(idx, f"call_{idx}")

        if render.legacy_mode:
            if not render.legacy_end_text:
                return []
            return [
                GeneratorOutput(
                    content=render.legacy_end_text,
                    content_type=render.legacy_label_content_type,
                    meta=_merge_meta(
                        {TOOL_CALL_ID_KEY: tcid, NAME_KEY: name, STATUS_KEY: STATUS_END},
                    ),
                ),
            ]

        if not render.has_tool_entry:
            return []
        slot = render.name_slot
        assert slot is not None
        content = self._resolve_slot_content(slot.content, idx, state) or name
        return [
            GeneratorOutput(
                content=content,
                content_type=slot.content_type,
                meta=_merge_meta(
                    {TOOL_CALL_ID_KEY: tcid, NAME_KEY: name, STATUS_KEY: STATUS_END},
                    render.tool_meta,
                ),
            ),
        ]

    # ------------------------------------------------------------------ #
    # legacy
    # ------------------------------------------------------------------ #
    def _legacy_emit_start(
        self, idx: int, name: str, tcid: str, render: ToolRender, state: dict,
    ) -> List[GeneratorOutput]:
        if not self.emit_start or not render.legacy_start_text or idx in state["started"]:
            return []
        state["started"].add(idx)
        return [
            GeneratorOutput(
                content=render.legacy_start_text,
                content_type=render.legacy_label_content_type,
                meta=_merge_meta(
                    {TOOL_CALL_ID_KEY: tcid, NAME_KEY: name, STATUS_KEY: STATUS_START},
                ),
            ),
        ]

    def _legacy_emit_args(
        self, idx: int, name: str, tcid: str, render: ToolRender, state: dict,
    ) -> List[GeneratorOutput]:
        emit_meta = bool(render.legacy_start_text)
        outputs: List[GeneratorOutput] = []
        for arg_name, out_ctype in render.legacy_args.items():
            delta = self._extract_incremental(idx, arg_name, state)
            if not delta:
                continue
            meta = (
                _merge_meta(
                    {
                        TOOL_CALL_ID_KEY: tcid,
                        NAME_KEY: name,
                        STATUS_KEY: STATUS_RUNNING,
                        ARG_KEY: arg_name,
                    },
                )
                if emit_meta
                else None
            )
            outputs.append(GeneratorOutput(content=delta, content_type=out_ctype, meta=meta))
        return outputs

    # ------------------------------------------------------------------ #
    # 解析 / 增量
    # ------------------------------------------------------------------ #
    def _resolve_label_value(self, idx: int, render: ToolRender, state: dict) -> str:
        if render.label_static is not None:
            return render.label_static
        if render.label_binding is None:
            return state["index_name"].get(idx, "")
        if render.label_binding.kind == BindingKind.NAME:
            return state["index_name"].get(idx, "")
        if render.label_binding.kind == BindingKind.ARG:
            return self._extract_full_arg(idx, render.label_binding.arg_name, state) or ""
        return ""

    @staticmethod
    def _resolve_slot_content(binding: Union[str, ContentBinding], idx: int, state: dict) -> str:
        b = ContentBinding.parse(binding)
        if b.kind == BindingKind.NAME:
            return state["index_name"].get(idx, "")
        if b.kind == BindingKind.ARG:
            return extract_arg_value(state["arg_buffers"][idx], b.arg_name) or ""
        return b.arg_name

    @staticmethod
    def _extract_full_arg(idx: int, arg_name: str, state: dict) -> Optional[str]:
        return extract_arg_value(state["arg_buffers"][idx], arg_name)

    @staticmethod
    def _extract_incremental(idx: int, arg_name: str, state: dict) -> Optional[str]:
        buffer = state["arg_buffers"][idx]
        value = extract_arg_value(buffer, arg_name)
        if value is None:
            return None

        emitted = state["emitted"][idx]
        last = emitted.get(arg_name, "")
        if value.startswith(last):
            delta = value[len(last) :]
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
