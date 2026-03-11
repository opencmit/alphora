# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
CLI parallel output renderer.

Provides a ``DataStreamer``-compatible interface that renders multiple
parallel agent outputs to the terminal without interleaving.

* When **rich** is installed, uses ``rich.live.Live`` + ``rich.layout.Layout``
  to create a tmux-like full-screen split-pane view.
* Otherwise falls back to ANSI-coloured, line-buffered atomic printing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sys
from typing import List, Optional


# ---------------------------------------------------------------------------
#  Lightweight ANSI CLI print (no external deps, usable for single-agent too)
# ---------------------------------------------------------------------------

def cli_print(content: str, ctype: str = "char", *, end: str = "", flush: bool = True):
    """Styled terminal print: dim for thinking, bold cyan for tool calls, normal otherwise."""
    if ctype == "think":
        sys.stdout.write(f"\033[2m\033[3m{content}\033[0m")
    elif ctype == "tool_call":
        sys.stdout.write(f"\033[1m\033[36m{content}\033[0m")
    elif ctype == "tool_call_args":
        sys.stdout.write(f"\033[36m{content}\033[0m")
    else:
        sys.stdout.write(content)
    if flush:
        sys.stdout.flush()


try:
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


# ---------------------------------------------------------------------------
#  Shared helpers
# ---------------------------------------------------------------------------

def _parse_prefixed_content_type(content_type: str):
    """Split ``"parallel_0:char"`` into ``(0, "char")``.

    Returns ``(None, content_type)`` when no parallel prefix is found.
    """
    if ":" in content_type:
        prefix, ctype = content_type.split(":", 1)
        if prefix.startswith("parallel_"):
            try:
                idx = int(prefix[len("parallel_"):])
                return idx, ctype
            except ValueError:
                pass
    return None, content_type


# ---------------------------------------------------------------------------
#  Rich-based implementation  —  tmux-style full-screen split panes
# ---------------------------------------------------------------------------

_PANE_BORDER_COLORS = ["blue", "green", "magenta", "yellow", "red", "cyan"]


class _RichCLIStreamer:
    """Full-screen tmux-like split-pane display powered by *rich*.

    Uses ``rich.layout.Layout`` to divide the terminal into a grid of panes
    (one per agent) and ``rich.live.Live`` with ``screen=True`` (alternate
    screen buffer) so the pane view is completely isolated from log output.
    """

    _STYLE_MAP = {
        "think": "dim italic",
        "tool_call": "bold cyan",
        "tool_call_args": "cyan",
    }

    def __init__(
        self,
        agent_labels: List[str],
        refresh_per_second: int = 10,
    ):
        self._labels = agent_labels
        self._buffers: List[Text] = [Text() for _ in agent_labels]
        self._lock = asyncio.Lock()
        self._console = Console()
        self._layout = self._build_layout()
        self._update_panes()

        self._live = Live(
            self._layout,
            console=self._console,
            refresh_per_second=refresh_per_second,
            screen=True,
        )

        self._saved_log_levels: dict[int, int] = {}

    # -- layout construction -------------------------------------------------

    def _build_layout(self) -> "Layout":
        """Create a grid layout that splits the terminal like tmux.

        Grid sizing: cols = ceil(sqrt(n)), rows = ceil(n / cols).
        """
        n = len(self._labels)
        if n == 1:
            return Layout(name="pane_0")

        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

        root = Layout()
        row_layouts = [Layout(name=f"_row_{r}") for r in range(rows)]
        root.split_column(*row_layouts)

        idx = 0
        for r in range(rows):
            panes: list[Layout] = []
            for _ in range(cols):
                if idx < n:
                    panes.append(Layout(name=f"pane_{idx}"))
                    idx += 1
            row_layouts[r].split_row(*panes)

        return root

    def _update_panes(self):
        """Re-render each pane's Panel with the latest buffer content."""
        term_h = self._console.size.height
        n = len(self._labels)
        cols = math.ceil(math.sqrt(n)) if n > 1 else 1
        rows = math.ceil(n / cols) if n > 1 else 1
        max_lines = max(3, (term_h // rows) - 4)

        for i, label in enumerate(self._labels):
            color = _PANE_BORDER_COLORS[i % len(_PANE_BORDER_COLORS)]
            display = self._tail_text(self._buffers[i], max_lines)
            panel = Panel(
                display,
                title=f"[bold]{label}[/bold]",
                subtitle=f"[dim]{self._line_count(i)} lines[/dim]",
                border_style=color,
                expand=True,
            )
            self._layout[f"pane_{i}"].update(panel)

    def _line_count(self, idx: int) -> int:
        return self._buffers[idx].plain.count("\n") + 1

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        self._suppress_logging()
        self._live.start()

    def stop_display(self):
        """Exit the alternate screen and print final results normally."""
        try:
            self._live.stop()
        except Exception:
            pass
        self._restore_logging()
        self._print_final_summary()

    def _suppress_logging(self):
        """Temporarily raise all loggers to WARNING so they don't fight
        with the alternate-screen display."""
        root = logging.getLogger()
        for handler in root.handlers:
            hid = id(handler)
            self._saved_log_levels[hid] = handler.level
            handler.setLevel(logging.WARNING)

    def _restore_logging(self):
        root = logging.getLogger()
        for handler in root.handlers:
            hid = id(handler)
            if hid in self._saved_log_levels:
                handler.setLevel(self._saved_log_levels[hid])
        self._saved_log_levels.clear()

    # -- DataStreamer interface -----------------------------------------------

    async def send_data(self, content_type: str, content: str = None):
        if not content:
            return

        idx, ctype = _parse_prefixed_content_type(content_type)
        if idx is None or idx >= len(self._labels):
            idx = 0

        style = self._STYLE_MAP.get(ctype, "")

        async with self._lock:
            buf = self._buffers[idx]

            if ctype == "tool_call":
                try:
                    tc_info = json.loads(content)
                    name = tc_info.get("name", "unknown")
                except (json.JSONDecodeError, TypeError):
                    name = "unknown"
                buf.append(f"\n[Tool Call] {name}\n", style="bold cyan")
            elif ctype in ("[STREAM_IGNORE]", "[BOTH_IGNORE]"):
                return
            else:
                buf.append(content, style=style)

            self._update_panes()
            self._live.update(self._layout)

    async def stop(self, stop_reason: str = "stop"):
        pass

    # -- text helpers --------------------------------------------------------

    @staticmethod
    def _tail_text(text: "Text", max_lines: int) -> "Text":
        """Return at most the last *max_lines* lines of a Rich Text object."""
        plain = text.plain
        lines = plain.split("\n")
        if len(lines) <= max_lines:
            return text

        keep_from_char = 0
        for line in lines[:-max_lines]:
            keep_from_char += len(line) + 1

        tail = text[keep_from_char:]
        hint = Text("...\n", style="dim")
        return hint + tail

    def _print_final_summary(self):
        """Print full results after exiting the alternate screen."""
        self._console.print()
        for i, label in enumerate(self._labels):
            buf = self._buffers[i]
            color = _PANE_BORDER_COLORS[i % len(_PANE_BORDER_COLORS)]
            if buf.plain.strip():
                self._console.print(
                    Panel(
                        buf,
                        title=f"[bold {color}]{label}[/bold {color}]",
                        border_style=color,
                        expand=True,
                    )
                )
        self._console.print()


# ---------------------------------------------------------------------------
#  ANSI fallback implementation
# ---------------------------------------------------------------------------

_ANSI_COLORS = [
    "\033[36m",   # cyan
    "\033[33m",   # yellow
    "\033[35m",   # magenta
    "\033[32m",   # green
    "\033[34m",   # blue
    "\033[91m",   # bright red
    "\033[96m",   # bright cyan
    "\033[93m",   # bright yellow
]
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"


class _FallbackCLIStreamer:
    """Coloured-prefix, line-buffered atomic printer (no external deps)."""

    def __init__(self, agent_labels: List[str]):
        self._labels = agent_labels
        self._colors = [
            _ANSI_COLORS[i % len(_ANSI_COLORS)] for i in range(len(agent_labels))
        ]
        self._buffers: List[str] = [""] * len(agent_labels)
        self._lock = asyncio.Lock()

    def start(self):
        pass

    def stop_display(self):
        self._flush_all()
        print()

    async def send_data(self, content_type: str, content: str = None):
        if not content:
            return

        idx, ctype = _parse_prefixed_content_type(content_type)
        if idx is None or idx >= len(self._labels):
            idx = 0

        if ctype in ("[STREAM_IGNORE]", "[BOTH_IGNORE]"):
            return

        async with self._lock:
            if ctype == "tool_call":
                try:
                    tc_info = json.loads(content)
                    name = tc_info.get("name", "unknown")
                except (json.JSONDecodeError, TypeError):
                    name = "unknown"
                self._buffers[idx] += f"\n[Tool Call] {name}\n"
            else:
                self._buffers[idx] += content

            self._flush_complete_lines(idx)

    async def stop(self, stop_reason: str = "stop"):
        pass

    def _flush_complete_lines(self, idx: int):
        buf = self._buffers[idx]
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            self._print_line(idx, line)
        self._buffers[idx] = buf

    def _flush_all(self):
        for idx in range(len(self._labels)):
            remaining = self._buffers[idx]
            if remaining.strip():
                self._print_line(idx, remaining)
            self._buffers[idx] = ""

    def _print_line(self, idx: int, line: str):
        color = self._colors[idx]
        label = self._labels[idx]
        prefix = f"{color}{_ANSI_BOLD}[{label}]{_ANSI_RESET} "
        sys.stdout.write(f"{prefix}{line}\n")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
#  Factory
# ---------------------------------------------------------------------------

def create_cli_streamer(
    agent_labels: List[str],
) -> "_RichCLIStreamer | _FallbackCLIStreamer":
    """Create the best available CLI streamer for parallel output.

    Selection logic:

    1. **Real terminal** (``isatty() == True``) + *rich* installed
       → full-screen tmux-style split panes (``_RichCLIStreamer``).
    2. **Non-terminal** (PyCharm Run, piped output, etc.) or *rich* missing
       → coloured-prefix line-buffered printer (``_FallbackCLIStreamer``).
    """
    if _RICH_AVAILABLE and sys.stdout.isatty():
        return _RichCLIStreamer(agent_labels=agent_labels)
    return _FallbackCLIStreamer(agent_labels=agent_labels)
