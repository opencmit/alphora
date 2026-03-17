"""
LLM 消息检视器。

通过 Hook 机制自动捕获每次 LLM 调用的完整输入消息与输出结果，
生成自包含的可视化 HTML 文件，便于开发者逐步展开、审查整个推理流程。

HTML 采用左右分栏布局：
- 左侧：调用时间线（时间戳 + 消息角色序列预览）
- 右侧：选中调用的完整详情（消息列表、工具定义、响应结果）

基本用法::

    from alphora.hooks.builtins import MessageInspector

    inspector = MessageInspector("debug.html")

    prompt = self.create_prompt(
        system_prompt="...",
        hooks=inspector.hooks,
    )

    for step in range(max_iterations):
        response = await prompt.acall(
            query=query, tools=tools,
            is_stream=True, history=memory.build_history(),
        )

    inspector.save()   # 写入 HTML

自动保存模式（每次 LLM 调用结束后自动写入）::

    inspector = MessageInspector("debug.html", auto_save=True)
"""

import html
import json
import os
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from alphora.hooks.context import HookContext


@dataclass
class _CallRecord:
    """单次 LLM 调用的完整记录。"""
    call_index: int
    timestamp: datetime
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tools: Optional[List[Dict[str, Any]]] = None
    response: Any = None
    agent_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class MessageInspector:
    """
    LLM 消息检视器，记录每次调用的输入消息与输出，保存为可视化 HTML。

    实现为一对 hook 函数（``before_llm`` + ``after_llm``），通过
    ``hooks`` property 返回 short_map 兼容的 dict，可直接传给
    ``BasePrompt`` 或 ``create_prompt``::

        inspector = MessageInspector("debug.html")
        prompt = BasePrompt(system_prompt="...", hooks=inspector.hooks)
    """

    def __init__(
        self,
        output_path: str = "messages_inspector.html",
        auto_save: bool = False,
        title: str = "Message Inspector",
    ) -> None:
        self._output_path = output_path
        self._resolved_path: Optional[str] = None
        self._auto_save = auto_save
        self._title = title
        self._calls: List[_CallRecord] = []
        self._lock = threading.Lock()
        self._counter = 0

    @property
    def hooks(self) -> Dict[str, Any]:
        """返回 ``{"before_llm": ..., "after_llm": ...}`` dict，
        与 ``build_manager`` 的 short_map 直接兼容。"""
        return {
            "before_llm": self._on_before_call,
            "after_llm": self._on_after_call,
        }

    def _on_before_call(self, ctx: HookContext) -> None:
        with self._lock:
            self._counter += 1
            record = _CallRecord(
                call_index=self._counter,
                timestamp=ctx.timestamp,
                messages=deepcopy(ctx.data.get("messages", [])),
                tools=deepcopy(ctx.data.get("tools")),
                agent_id=ctx.data.get("agent_id"),
                meta={
                    "is_stream": ctx.data.get("is_stream"),
                    "force_json": ctx.data.get("force_json"),
                    "long_response": ctx.data.get("long_response"),
                },
            )
            self._calls.append(record)

    def _on_after_call(self, ctx: HookContext) -> None:
        response = ctx.data.get("response")
        with self._lock:
            if self._calls:
                self._calls[-1].response = deepcopy(response)
        if self._auto_save:
            self.save()

    @property
    def calls(self) -> List[_CallRecord]:
        with self._lock:
            return list(self._calls)

    @property
    def call_count(self) -> int:
        with self._lock:
            return len(self._calls)

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._counter = 0

    def save(self, path: Optional[str] = None) -> str:
        """将当前记录渲染为 HTML 并写入文件，返回文件路径。

        首次保存时，若目标路径已存在同名文件（来自上一次运行），
        自动追加序号避免覆盖，例如 ``debug.html`` -> ``debug(1).html``。
        后续保存始终覆盖同一文件（同一会话的增量更新）。
        """
        if path is not None:
            target = path
        elif self._resolved_path is not None:
            target = self._resolved_path
        else:
            target = _unique_path(self._output_path)
            self._resolved_path = target

        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        content = self._render_html()
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return os.path.abspath(target)

    # ------------------------------------------------------------------
    # Training data export
    # ------------------------------------------------------------------

    def export_training_data(
        self,
        path: str = "training_data.jsonl",
        fmt: str = "openai",
        scope: str = "per_call",
    ) -> str:
        """导出训练数据为 JSONL 文件。

        Args:
            path: 输出文件路径。
            fmt: ``"openai"`` (OpenAI fine-tuning) 或 ``"sharegpt"``。
            scope: ``"per_call"`` (每次 LLM 调用一条) 或
                   ``"conversation"`` (整段对话合并为一条)。

        Returns:
            写入文件的绝对路径。
        """
        with self._lock:
            calls = list(self._calls)

        if scope == "conversation":
            samples = [self._to_conversation(calls, fmt)]
        else:
            samples = [self._call_to_sample(c, fmt) for c in calls]

        samples = [s for s in samples if s]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        path = _unique_path(path)
        with open(path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        return os.path.abspath(path)

    @staticmethod
    def _build_response_msg(response) -> Optional[Dict[str, Any]]:
        """从 response 对象构建 assistant 消息。"""
        if response is None:
            return None
        if hasattr(response, "tool_calls") and getattr(response, "tool_calls", None):
            tc_list = []
            for tc in response.tool_calls:
                if hasattr(tc, "function"):
                    func = tc.function
                    tc_list.append({
                        "id": getattr(tc, "id", ""),
                        "type": "function",
                        "function": {
                            "name": getattr(func, "name", ""),
                            "arguments": getattr(func, "arguments", ""),
                        },
                    })
                elif isinstance(tc, dict):
                    tc_list.append(tc)
            msg: Dict[str, Any] = {"role": "assistant", "content": None, "tool_calls": tc_list}
            text = getattr(response, "content", "") or ""
            if text:
                msg["content"] = text
            return msg
        content = str(response)
        return {"role": "assistant", "content": content} if content else None

    def _call_to_sample(self, record: _CallRecord, fmt: str) -> Optional[Dict]:
        resp_msg = self._build_response_msg(record.response)
        messages = list(record.messages)
        if resp_msg:
            messages.append(resp_msg)
        if not messages:
            return None
        if fmt == "sharegpt":
            convs: List[Dict[str, Any]] = []
            for m in messages:
                convs.extend(_to_sharegpt_turns(m))
            sample: Dict[str, Any] = {"conversations": convs}
            if record.tools:
                sample["tools"] = json.dumps(record.tools, ensure_ascii=False)
            return sample
        sample = {"messages": messages}
        if record.tools:
            sample["tools"] = record.tools
        return sample

    def _to_conversation(self, calls: List[_CallRecord], fmt: str) -> Optional[Dict]:
        """将所有调用合并为一段多轮对话。"""
        seen_system = set()
        merged: List[Dict[str, Any]] = []
        all_tools: Optional[List[Dict]] = None
        for c in calls:
            if c.tools:
                all_tools = c.tools
            for m in c.messages:
                if m.get("role") == "system":
                    key = m.get("content", "")
                    if key in seen_system:
                        continue
                    seen_system.add(key)
                merged.append(m)
            resp_msg = self._build_response_msg(c.response)
            if resp_msg:
                merged.append(resp_msg)
        if not merged:
            return None
        if fmt == "sharegpt":
            convs: List[Dict[str, Any]] = []
            for m in merged:
                convs.extend(_to_sharegpt_turns(m))
            sample: Dict[str, Any] = {"conversations": convs}
            if all_tools:
                sample["tools"] = json.dumps(all_tools, ensure_ascii=False)
            return sample
        sample: Dict[str, Any] = {"messages": merged}
        if all_tools:
            sample["tools"] = all_tools
        return sample

    @staticmethod
    def _serialize_call(record: _CallRecord) -> Dict[str, Any]:
        """将 _CallRecord 序列化为可 JSON 化的 dict（供 HTML 嵌入）。"""
        resp = record.response
        resp_data: Any = None
        if resp is not None:
            resp_msg = MessageInspector._build_response_msg(resp)
            if resp_msg:
                resp_data = resp_msg
            else:
                resp_data = str(resp)
        return {
            "call_index": record.call_index,
            "messages": record.messages,
            "tools": record.tools,
            "response": resp_data,
        }

    # ------------------------------------------------------------------
    # HTML 渲染
    # ------------------------------------------------------------------

    def _render_html(self) -> str:
        with self._lock:
            calls = list(self._calls)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sidebar_items = "\n".join(
            self._render_sidebar_item(c) for c in calls
        )
        detail_panels = "\n".join(
            self._render_detail_panel(c) for c in calls
        )

        raw_data = json.dumps(
            [self._serialize_call(c) for c in calls],
            ensure_ascii=False, default=str,
        )

        return _HTML_TEMPLATE.format(
            title=html.escape(self._title),
            generated_at=now_str,
            total_calls=len(calls),
            sidebar_items=sidebar_items,
            detail_panels=detail_panels,
            raw_data=raw_data,
            first_call_index=calls[0].call_index if calls else 0,
        )

    def _render_sidebar_item(self, record: _CallRecord) -> str:
        ts_time = record.timestamp.strftime("%H:%M:%S.%f")[:-3]
        ts_date = record.timestamp.strftime("%Y-%m-%d")
        msg_count = len(record.messages)

        role_dots = ""
        for m in record.messages:
            role = _safe_role(m.get("role", "unknown"))
            label = m.get("role", "?")[0].upper()
            role_dots += f'<span class="dot dot-{role}" title="{html.escape(m.get("role", ""))}">{label}</span>'

        has_tools = "yes" if record.tools else "no"
        resp_type = ""
        if record.response is not None:
            if hasattr(record.response, "tool_calls") and getattr(record.response, "tool_calls", None):
                resp_type = "tool_call"
            else:
                resp_type = "text"

        return f"""
<div class="sidebar-item" data-call="{record.call_index}" onclick="selectCall({record.call_index})">
  <div class="si-top">
    <span class="si-index">#{record.call_index}</span>
    <span class="si-time">{ts_time}</span>
  </div>
  <div class="si-date">{ts_date}</div>
  <div class="si-dots">{role_dots}</div>
  <div class="si-bottom">
    <span class="si-count">{msg_count} msgs</span>
    <span class="si-tools" data-has="{has_tools}">{"tools" if record.tools else ""}</span>
  </div>
</div>"""

    def _render_detail_panel(self, record: _CallRecord) -> str:
        ts = record.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        msg_count = len(record.messages)

        role_flow_items = []
        for i, m in enumerate(record.messages):
            role = m.get("role", "unknown")
            safe = _safe_role(role)
            arrow = '<span class="flow-arrow"></span>' if i > 0 else ""
            role_flow_items.append(
                f'{arrow}<span class="flow-tag ft-{safe}">{html.escape(role)}</span>'
            )
        role_flow = "".join(role_flow_items)

        meta_html = self._render_meta(record)

        messages_html = "\n".join(
            self._render_message_item(record.call_index, i, m)
            for i, m in enumerate(record.messages)
        )

        tools_modal = self._render_tools_modal(record)
        tools_count = len(record.tools) if record.tools else 0
        tools_btn = ""
        if tools_count > 0:
            modal_id = f"tools-modal-{record.call_index}"
            tools_btn = (
                f'<button class="tools-btn" onclick="openModal(\'{modal_id}\')">'
                f'Available Tools ({tools_count})</button>'
            )

        response_html = self._render_response_item(record)
        ci = record.call_index

        return f"""
<div class="detail-panel" id="detail-{ci}" style="display:none;">
  <div class="detail-top">
    <div class="detail-header">
      <h2>Call #{ci}</h2>
      <span class="dh-time">{ts}</span>
      <span class="dh-count">{msg_count} messages</span>
      {tools_btn}
    </div>
    {meta_html}
    <div class="flow-bar">{role_flow}</div>
  </div>
  <div class="detail-columns">
    <div class="col-messages" id="msglist-{ci}">
      {messages_html}
      {response_html}
    </div>
    <div class="col-inspector" id="inspector-{ci}">
      <div class="inspector-empty">Select a message to inspect</div>
    </div>
  </div>
  {tools_modal}
</div>"""

    def _render_message_item(self, call_idx: int, idx: int, msg: Dict[str, Any]) -> str:
        role = msg.get("role", "unknown")
        safe_role = _safe_role(role)
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")
        tool_call_id = msg.get("tool_call_id")
        name = msg.get("name")

        badge_parts = []
        if tool_call_id:
            badge_parts.append(f'<span class="msg-badge">call_id: {html.escape(str(tool_call_id))}</span>')
        if name:
            badge_parts.append(f'<span class="msg-badge">name: {html.escape(str(name))}</span>')
        badges = "".join(badge_parts)

        content_preview = _truncate(str(content), 80) if content else "empty"

        tool_calls_html = ""
        if tool_calls:
            tc_items = []
            for tc in tool_calls:
                tc_items.append(self._render_tool_call_item(tc))
            tool_calls_html = "\n".join(tc_items)

        content_escaped = _format_content(str(content), role) if content else ""

        msg_id = f"msg-{call_idx}-{idx}"

        detail_html = f'<pre class="msg-pre">{content_escaped}</pre>' if content_escaped else ""
        if tool_calls_html:
            detail_html += f'\n<div class="tc-block">{tool_calls_html}</div>'

        return f"""
<div class="msg-item msg-{safe_role}" id="{msg_id}"
     onclick="selectMsg('{msg_id}', {call_idx})"
     data-detail="{html.escape(detail_html, quote=True)}"
     data-role="{html.escape(role)}"
     data-idx="{idx}">
  <div class="msg-row">
    <span class="msg-idx">{idx}</span>
    <span class="msg-role mr-{safe_role}">{html.escape(role)}</span>
    {badges}
    <span class="msg-preview">{content_preview}</span>
  </div>
</div>"""

    def _render_tool_call_item(self, tc: Dict[str, Any]) -> str:
        tc_id = html.escape(str(tc.get("id", "")))
        tc_type = html.escape(str(tc.get("type", "function")))
        func = tc.get("function", {})
        func_name = html.escape(str(func.get("name", "unknown")))

        raw_args = func.get("arguments", "")
        try:
            parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            args_display = html.escape(json.dumps(parsed, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError):
            args_display = html.escape(str(raw_args))

        return f"""
<div class="tc-item">
  <div class="tc-head">
    <span class="tc-label">function</span>
    <span class="tc-fn">{func_name}</span>
    <span class="tc-id">{tc_id}</span>
  </div>
  <pre class="tc-args">{args_display}</pre>
</div>"""

    def _render_tools_modal(self, record: _CallRecord) -> str:
        tools = record.tools
        if not tools:
            return ""

        modal_id = f"tools-modal-{record.call_index}"

        tool_items = []
        for t in tools:
            func = t.get("function", {})
            name = html.escape(str(func.get("name", "unknown")))
            desc = html.escape(str(func.get("description", "")))
            params = func.get("parameters", {})
            try:
                params_str = html.escape(json.dumps(params, indent=2, ensure_ascii=False))
            except (TypeError, ValueError):
                params_str = html.escape(str(params))

            tool_items.append(f"""
<div class="tool-def">
  <div class="td-name">{name}</div>
  <div class="td-desc">{desc}</div>
  <details class="td-params"><summary>parameters</summary><pre>{params_str}</pre></details>
</div>""")

        return f"""
<div class="modal-overlay" id="{modal_id}" onclick="closeModalOutside(event, '{modal_id}')">
  <div class="modal-box">
    <div class="modal-header">
      <span class="modal-title">Available Tools ({len(tools)})</span>
      <button class="modal-close" onclick="closeModal('{modal_id}')">&times;</button>
    </div>
    <div class="modal-body">{"".join(tool_items)}</div>
  </div>
</div>"""

    def _render_response_item(self, record: _CallRecord) -> str:
        """Render response as a message-like item at the end of the list."""
        response = record.response
        ci = record.call_index
        msg_id = f"msg-{ci}-resp"

        if response is None:
            return f"""
<div class="msg-item msg-resp" id="{msg_id}"
     onclick="selectMsg('{msg_id}', {ci})"
     data-detail="N/A" data-role="response" data-idx="resp">
  <div class="msg-row">
    <span class="msg-role mr-resp">response</span>
    <span class="msg-preview">N/A</span>
  </div>
</div>"""

        resp_type = type(response).__name__

        if hasattr(response, "tool_calls") and getattr(response, "tool_calls", None):
            tc_list = response.tool_calls
            tc_items = []
            for tc in tc_list:
                if hasattr(tc, "function"):
                    func = tc.function
                    fname = html.escape(str(getattr(func, "name", "unknown")))
                    raw_args = getattr(func, "arguments", "")
                    try:
                        parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        args_str = html.escape(json.dumps(parsed, indent=2, ensure_ascii=False))
                    except (json.JSONDecodeError, TypeError):
                        args_str = html.escape(str(raw_args))
                    tc_items.append(
                        f'<div class="tc-item">'
                        f'<div class="tc-head"><span class="tc-label">function</span>'
                        f'<span class="tc-fn">{fname}</span></div>'
                        f'<pre class="tc-args">{args_str}</pre></div>'
                    )
                elif isinstance(tc, dict):
                    tc_items.append(self._render_tool_call_item(tc))

            text_content = getattr(response, "content", "") or ""
            text_html = f'<pre class="msg-pre">{html.escape(str(text_content))}</pre>' if text_content else ""
            detail_html = text_html + '\n<div class="tc-block">' + "\n".join(tc_items) + "</div>"

            preview = f"{resp_type} / {len(tc_list)} tool call(s)"
        else:
            content_str = str(response)
            detail_html = f'<pre class="msg-pre">{html.escape(content_str)}</pre>'
            preview = _truncate(content_str, 80)

        return f"""
<div class="msg-item msg-resp" id="{msg_id}"
     onclick="selectMsg('{msg_id}', {ci})"
     data-detail="{html.escape(detail_html, quote=True)}"
     data-role="response" data-idx="resp">
  <div class="msg-row">
    <span class="msg-role mr-resp">response</span>
    <span class="msg-badge">{html.escape(resp_type)}</span>
    <span class="msg-preview">{preview}</span>
  </div>
</div>"""

    def _render_meta(self, record: _CallRecord) -> str:
        parts = []
        if record.agent_id:
            parts.append(f"agent: {html.escape(str(record.agent_id))}")
        for k, v in record.meta.items():
            if v is not None:
                parts.append(f"{k}: {html.escape(str(v))}")
        if not parts:
            return ""
        return '<div class="detail-meta">' + " &middot; ".join(parts) + "</div>"

    def __repr__(self) -> str:
        return f"MessageInspector(calls={self.call_count}, path={self._output_path!r})"


# ======================================================================
# Helpers
# ======================================================================

def _unique_path(path: str) -> str:
    """若 path 已存在，追加 (1), (2), ... 直到找到可用文件名。"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{base}({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _to_sharegpt_turns(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将一条 OpenAI 格式消息转换为 LLaMA-Factory ShareGPT 格式的 turn 列表。

    assistant 含 tool_calls 时拆分为多条：
      - 若有 content → gpt turn
      - 每个 tool_call → function_call turn
    tool 结果消息 → observation turn
    """
    role = msg.get("role", "user")
    tool_calls = msg.get("tool_calls")

    if role == "assistant" and tool_calls:
        turns: List[Dict[str, Any]] = []
        text = msg.get("content") or ""
        if text:
            turns.append({"from": "gpt", "value": text})
        for tc in tool_calls:
            func = tc.get("function", {})
            call_obj = {"name": func.get("name", "")}
            raw_args = func.get("arguments", "")
            try:
                call_obj["arguments"] = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except (json.JSONDecodeError, TypeError):
                call_obj["arguments"] = raw_args
            turns.append({"from": "function_call", "value": json.dumps(call_obj, ensure_ascii=False)})
        return turns

    if role == "tool":
        return [{"from": "observation", "value": msg.get("content") or ""}]

    role_map = {"system": "system", "user": "human", "assistant": "gpt"}
    return [{"from": role_map.get(role, role), "value": msg.get("content") or ""}]


def _format_content(text: str, role: str) -> str:
    """对 tool 消息内容尝试 JSON 格式化，其他角色原样转义。"""
    if role == "tool":
        try:
            parsed = json.loads(text)
            return html.escape(json.dumps(parsed, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError):
            pass
    return html.escape(text)


def _safe_role(role: str) -> str:
    return role.replace(" ", "_").lower() if role else "unknown"


def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ")
    if len(text) > max_len:
        return html.escape(text[:max_len]) + "&hellip;"
    return html.escape(text)


# ======================================================================
# HTML Template
# ======================================================================

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
*,*::before,*::after {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ overflow-x: hidden; }}

:root {{
  --white: #ffffff;
  --bg: #f7f8fa;
  --surface: #ffffff;
  --surface2: #f2f3f5;
  --border: #e5e7eb;
  --border-light: #f0f0f0;
  --text: #1a1a2e;
  --text2: #6b7280;
  --text3: #9ca3af;
  --accent: #2563eb;
  --accent-light: #eff4ff;

  --c-sys: #3b82f6;
  --c-sys-bg: #eff6ff;
  --c-sys-border: #bfdbfe;
  --c-user: #059669;
  --c-user-bg: #ecfdf5;
  --c-user-border: #a7f3d0;
  --c-asst: #7c3aed;
  --c-asst-bg: #f5f3ff;
  --c-asst-border: #ddd6fe;
  --c-tool: #b45309;
  --c-tool-bg: #fffbeb;
  --c-tool-border: #fde68a;

  --mono: 'SF Mono', 'Cascadia Code', 'Fira Code', Consolas, monospace;
  --sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  --radius: 6px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}}

body {{
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  font-size: 14px;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  width: 100vw;
  max-width: 100vw;
}}

/* ---- Header ---- */
.topbar {{
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 14px 24px;
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-shrink: 0;
}}
.topbar h1 {{
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.3px;
}}
.topbar .t-meta {{
  font-size: 12px;
  color: var(--text3);
}}
.export-btn {{
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-light);
  border: 1px solid var(--accent);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
}}
.export-btn:hover {{
  background: var(--accent);
  color: #fff;
}}
.export-group {{
  margin-bottom: 16px;
}}
.export-label {{
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}}
.export-option {{
  display: block;
  font-size: 13px;
  color: var(--text2);
  padding: 4px 0;
  cursor: pointer;
}}
.export-option input {{
  margin-right: 6px;
}}
.export-action {{
  width: 100%;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: opacity 0.12s;
}}
.export-action:hover {{ opacity: 0.85; }}

/* ---- Layout ---- */
.layout {{
  display: flex;
  flex: 1;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
}}

/* ---- Sidebar ---- */
.sidebar {{
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--border);
  background: var(--white);
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
}}
.sidebar-label {{
  font-size: 11px;
  font-weight: 600;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  padding: 16px 16px 8px;
}}

.sidebar-item {{
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-light);
  transition: background 0.12s;
  position: relative;
}}
.sidebar-item:hover {{
  background: var(--surface2);
}}
.sidebar-item.active {{
  background: var(--accent-light);
}}
.sidebar-item.active::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--accent);
}}

.si-top {{
  display: flex;
  align-items: center;
  gap: 8px;
}}
.si-index {{
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}}
.si-time {{
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text2);
}}
.si-date {{
  font-size: 11px;
  color: var(--text3);
  margin-top: 2px;
}}

.si-dots {{
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 6px;
}}
.dot {{
  width: 18px; height: 18px;
  border-radius: 3px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0;
}}
.dot-system    {{ background: var(--c-sys-bg); color: var(--c-sys); border: 1px solid var(--c-sys-border); }}
.dot-user      {{ background: var(--c-user-bg); color: var(--c-user); border: 1px solid var(--c-user-border); }}
.dot-assistant {{ background: var(--c-asst-bg); color: var(--c-asst); border: 1px solid var(--c-asst-border); }}
.dot-tool      {{ background: var(--c-tool-bg); color: var(--c-tool); border: 1px solid var(--c-tool-border); }}

.si-bottom {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}}
.si-count {{
  font-size: 11px;
  color: var(--text3);
}}
.si-tools[data-has="yes"] {{
  font-size: 10px;
  color: var(--c-tool);
  background: var(--c-tool-bg);
  border: 1px solid var(--c-tool-border);
  padding: 0 5px;
  border-radius: 3px;
  font-weight: 600;
}}

/* ---- Detail ---- */
.detail {{
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}}

.detail-panel {{
  display: none;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}}

.detail-header {{
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}}
.detail-header h2 {{
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.3px;
}}
.dh-time {{
  font-family: var(--mono);
  font-size: 13px;
  color: var(--text2);
}}
.dh-count {{
  font-size: 12px;
  color: var(--text3);
  background: var(--surface2);
  padding: 2px 8px;
  border-radius: 4px;
}}

.tools-btn {{
  font-size: 12px;
  font-weight: 600;
  color: var(--c-tool);
  background: var(--c-tool-bg);
  border: 1px solid var(--c-tool-border);
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s, box-shadow 0.12s;
  margin-left: auto;
  white-space: nowrap;
}}
.tools-btn:hover {{
  background: var(--c-tool-border);
  color: #fff;
  box-shadow: var(--shadow);
}}

.detail-meta {{
  font-size: 12px;
  color: var(--text2);
  margin-bottom: 12px;
}}

/* Modal */
.modal-overlay {{
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.25);
  z-index: 1000;
  justify-content: center;
  align-items: center;
}}
.modal-overlay.visible {{
  display: flex;
}}
.modal-box {{
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.modal-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}}
.modal-title {{
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}}
.modal-close {{
  background: none;
  border: none;
  font-size: 20px;
  color: var(--text3);
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  transition: color 0.1s;
}}
.modal-close:hover {{
  color: var(--text);
}}
.modal-body {{
  padding: 16px 18px;
  overflow-y: auto;
  flex: 1;
}}

/* Flow bar */
.flow-bar {{
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 10px 12px;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 0;
  box-shadow: var(--shadow-sm);
}}
.flow-tag {{
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding: 2px 7px;
  border-radius: 3px;
}}
.ft-system    {{ background: var(--c-sys-bg); color: var(--c-sys); }}
.ft-user      {{ background: var(--c-user-bg); color: var(--c-user); }}
.ft-assistant {{ background: var(--c-asst-bg); color: var(--c-asst); }}
.ft-tool      {{ background: var(--c-tool-bg); color: var(--c-tool); }}
.flow-arrow {{
  display: inline-block;
  width: 12px;
  text-align: center;
  color: var(--text3);
  font-size: 10px;
}}
.flow-arrow::after {{ content: '\\203A'; font-size: 14px; }}

/* Detail layout */
.detail-top {{
  flex-shrink: 0;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--white);
}}

.detail-columns {{
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 0;
}}

.col-messages {{
  width: 380px;
  min-width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 1px solid var(--border);
  padding: 8px 0;
}}

.col-inspector {{
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
}}
.inspector-empty {{
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text3);
  font-size: 13px;
}}
.inspector-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}}
.inspector-header .msg-role {{
  font-size: 12px;
  padding: 2px 8px;
}}
.inspector-header .ih-idx {{
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text3);
}}

/* Messages */
.msg-item {{
  background: var(--white);
  margin: 0 8px 4px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
  cursor: pointer;
  transition: background 0.1s, box-shadow 0.1s;
}}
.msg-item:hover {{ background: var(--surface2); }}
.msg-item.selected {{
  background: var(--accent-light);
  border-color: var(--accent);
  box-shadow: var(--shadow);
}}
.msg-system    {{ border-left: 3px solid var(--c-sys); }}
.msg-user      {{ border-left: 3px solid var(--c-user); }}
.msg-assistant {{ border-left: 3px solid var(--c-asst); }}
.msg-tool      {{ border-left: 3px solid var(--c-tool); }}
.msg-resp      {{ border-left: 3px solid var(--accent); }}

.msg-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  user-select: none;
}}

.msg-idx {{
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text3);
  min-width: 16px;
  text-align: right;
}}
.msg-role {{
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}}
.mr-system    {{ background: var(--c-sys-bg); color: var(--c-sys); }}
.mr-user      {{ background: var(--c-user-bg); color: var(--c-user); }}
.mr-assistant {{ background: var(--c-asst-bg); color: var(--c-asst); }}
.mr-tool      {{ background: var(--c-tool-bg); color: var(--c-tool); }}
.mr-resp      {{ background: var(--accent-light); color: var(--accent); }}

.msg-badge {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text3);
  background: var(--surface2);
  padding: 1px 5px;
  border-radius: 3px;
}}
.msg-preview {{
  font-size: 12px;
  color: var(--text3);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.msg-pre {{
  white-space: pre-wrap;
  word-break: break-all;
  overflow-wrap: break-word;
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text);
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px 12px;
  max-height: 500px;
  overflow-y: auto;
  overflow-x: hidden;
}}

/* Tool calls inside messages */
.tc-block {{ margin-top: 10px; }}
.tc-item {{
  background: var(--white);
  border: 1px solid var(--c-tool-border);
  border-radius: var(--radius);
  margin-bottom: 6px;
  overflow: hidden;
}}
.tc-head {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--c-tool-bg);
  border-bottom: 1px solid var(--c-tool-border);
}}
.tc-label {{
  font-size: 10px;
  font-weight: 600;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}}
.tc-fn {{
  font-weight: 600;
  font-size: 13px;
  color: var(--c-tool);
}}
.tc-id {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text3);
  margin-left: auto;
}}
.tc-args {{
  white-space: pre-wrap;
  word-break: break-all;
  overflow-wrap: break-word;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.5;
  padding: 8px 10px;
  color: var(--text);
  max-height: 300px;
  overflow-y: auto;
  overflow-x: hidden;
}}


.tool-def {{
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}}
.tool-def:last-child {{ border-bottom: none; }}
.td-name {{
  font-weight: 600;
  font-size: 13px;
  color: var(--c-tool);
}}
.td-desc {{
  font-size: 12px;
  color: var(--text2);
  margin: 2px 0 4px;
}}
.td-params {{ font-size: 12px; color: var(--text2); }}
.td-params summary {{
  cursor: pointer;
  user-select: none;
  padding: 2px 0;
  font-weight: 500;
}}
.td-params pre {{
  white-space: pre-wrap;
  word-break: break-all;
  overflow-wrap: break-word;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.45;
  padding: 8px;
  margin-top: 4px;
  background: var(--surface2);
  border-radius: 4px;
  color: var(--text);
  max-height: 240px;
  overflow-y: auto;
  overflow-x: hidden;
}}


/* Empty state */
.empty-state {{
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text3);
  font-size: 14px;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text3); }}
</style>
</head>
<body>

<div class="topbar">
  <h1>{title}</h1>
  <span class="t-meta">{generated_at} &middot; {total_calls} calls</span>
  <button class="export-btn" onclick="openModal('export-modal')">Export Training Data</button>
</div>

<div class="modal-overlay" id="export-modal" onclick="closeModalOutside(event, 'export-modal')">
  <div class="modal-box" style="width:420px;">
    <div class="modal-header">
      <span class="modal-title">Export Training Data</span>
      <button class="modal-close" onclick="closeModal('export-modal')">&times;</button>
    </div>
    <div class="modal-body">
      <div class="export-group">
        <div class="export-label">Format</div>
        <label class="export-option"><input type="radio" name="exp-fmt" value="openai" checked> OpenAI fine-tuning JSONL</label>
        <label class="export-option"><input type="radio" name="exp-fmt" value="sharegpt"> ShareGPT JSONL</label>
      </div>
      <div class="export-group">
        <div class="export-label">Scope</div>
        <label class="export-option"><input type="radio" name="exp-scope" value="per_call" checked> Per-call (each LLM call = 1 sample)</label>
        <label class="export-option"><input type="radio" name="exp-scope" value="conversation"> Conversation (full session = 1 sample)</label>
      </div>
      <button class="export-action" onclick="doExport()">Download JSONL</button>
    </div>
  </div>
</div>

<script id="raw-call-data" type="application/json">{raw_data}</script>

<div class="layout">
  <div class="sidebar">
    <div class="sidebar-label">Calls</div>
    {sidebar_items}
  </div>
  <div class="detail" id="detail-container">
    {detail_panels}
    <div class="empty-state" id="empty-hint">Select a call from the sidebar</div>
  </div>
</div>

<script>
var currentCall = null;
var currentMsg = null;

function selectCall(idx) {{
  if (currentCall === idx) return;

  document.querySelectorAll('.sidebar-item').forEach(function(el) {{
    el.classList.toggle('active', parseInt(el.dataset.call) === idx);
  }});

  document.querySelectorAll('.detail-panel').forEach(function(el) {{
    el.style.display = 'none';
  }});

  var panel = document.getElementById('detail-' + idx);
  if (panel) {{
    panel.style.display = 'flex';
  }}

  var hint = document.getElementById('empty-hint');
  if (hint) hint.style.display = 'none';

  currentCall = idx;
  currentMsg = null;

  var first = panel ? panel.querySelector('.msg-item') : null;
  if (first) first.click();
}}

function selectMsg(msgId, callIdx) {{
  if (currentMsg === msgId) return;

  var panel = document.getElementById('detail-' + callIdx);
  if (!panel) return;

  panel.querySelectorAll('.msg-item').forEach(function(el) {{
    el.classList.remove('selected');
  }});

  var item = document.getElementById(msgId);
  if (!item) return;
  item.classList.add('selected');

  var inspector = document.getElementById('inspector-' + callIdx);
  if (!inspector) return;

  var role = item.dataset.role || '';
  var idx = item.dataset.idx || '';
  var detailHtml = item.dataset.detail || '';

  var roleClass = 'mr-' + role.replace(/\s/g, '_').toLowerCase();

  inspector.innerHTML =
    '<div class="inspector-header">' +
      '<span class="ih-idx">#' + idx + '</span>' +
      '<span class="msg-role ' + roleClass + '">' + role + '</span>' +
    '</div>' +
    '<div class="inspector-content">' + detailHtml + '</div>';

  currentMsg = msgId;
}}

function openModal(id) {{
  var el = document.getElementById(id);
  if (el) el.classList.add('visible');
}}
function closeModal(id) {{
  var el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}}
function closeModalOutside(e, id) {{
  if (e.target.id === id) closeModal(id);
}}

/* ---- Export logic ---- */
var _rawCalls = JSON.parse(document.getElementById('raw-call-data').textContent);

function _toShareGPTTurns(msg) {{
  var role = msg.role || 'user';
  var tc = msg.tool_calls;
  if (role === 'assistant' && tc && tc.length) {{
    var turns = [];
    var text = msg.content || '';
    if (text) turns.push({{from:'gpt', value:text}});
    tc.forEach(function(t) {{
      var fn = t.function || {{}};
      var args = fn.arguments || '';
      try {{ args = JSON.parse(args); }} catch(e) {{}}
      var obj = {{name: fn.name || '', arguments: args}};
      turns.push({{from:'function_call', value:JSON.stringify(obj)}});
    }});
    return turns;
  }}
  if (role === 'tool') {{
    return [{{from:'observation', value:msg.content || ''}}];
  }}
  var rmap = {{system:'system', user:'human', assistant:'gpt'}};
  return [{{from: rmap[role] || role, value: msg.content || ''}}];
}}

function _buildRespMsg(resp) {{
  if (!resp) return null;
  if (typeof resp === 'string') return {{role:'assistant', content:resp}};
  if (resp.role) return resp;
  return null;
}}

function _perCallSamples(fmt) {{
  return _rawCalls.map(function(c) {{
    var msgs = (c.messages || []).slice();
    var rm = _buildRespMsg(c.response);
    if (rm) msgs.push(rm);
    if (!msgs.length) return null;
    if (fmt === 'sharegpt') {{
      var convs = [];
      msgs.forEach(function(m) {{ convs = convs.concat(_toShareGPTTurns(m)); }});
      var s = {{conversations: convs}};
      if (c.tools) s.tools = JSON.stringify(c.tools);
      return s;
    }}
    var s = {{messages: msgs}};
    if (c.tools) s.tools = c.tools;
    return s;
  }}).filter(Boolean);
}}

function _conversationSample(fmt) {{
  var seenSys = {{}};
  var merged = [];
  var allTools = null;
  _rawCalls.forEach(function(c) {{
    if (c.tools) allTools = c.tools;
    (c.messages || []).forEach(function(m) {{
      if (m.role === 'system') {{
        var k = m.content || '';
        if (seenSys[k]) return;
        seenSys[k] = true;
      }}
      merged.push(m);
    }});
    var rm = _buildRespMsg(c.response);
    if (rm) merged.push(rm);
  }});
  if (!merged.length) return [];
  if (fmt === 'sharegpt') {{
    var convs = [];
    merged.forEach(function(m) {{ convs = convs.concat(_toShareGPTTurns(m)); }});
    var s = {{conversations: convs}};
    if (allTools) s.tools = JSON.stringify(allTools);
    return [s];
  }}
  var s = {{messages: merged}};
  if (allTools) s.tools = allTools;
  return [s];
}}

function doExport() {{
  var fmt = document.querySelector('input[name="exp-fmt"]:checked').value;
  var scope = document.querySelector('input[name="exp-scope"]:checked').value;
  var samples = scope === 'conversation' ? _conversationSample(fmt) : _perCallSamples(fmt);
  var lines = samples.map(function(s) {{ return JSON.stringify(s); }});
  var blob = new Blob([lines.join('\\n') + '\\n'], {{type:'application/jsonl'}});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'training_data_' + fmt + '_' + scope + '.jsonl';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  closeModal('export-modal');
}}

(function() {{
  var first = {first_call_index};
  if (first > 0) selectCall(first);
}})();
</script>

</body>
</html>
"""
