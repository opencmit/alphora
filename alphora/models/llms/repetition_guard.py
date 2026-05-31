# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


DEFAULT_LOOP_FALLBACK_MESSAGE = "抱歉，遇到了循环输出问题，请稍后再试"


@dataclass(frozen=True)
class RepetitionGuardConfig:
    """Configuration for streaming repetition detection."""

    window_chars: int = 4096
    min_pattern_chars: int = 32
    max_pattern_chars: int = 512
    min_repeats: int = 3
    min_distinct_chars: int = 4
    fallback_message: str = DEFAULT_LOOP_FALLBACK_MESSAGE
    text_content_types: FrozenSet[str] = frozenset({"char", "text", "think"})


@dataclass(frozen=True)
class RepetitionMatch:
    pattern: str
    pattern_chars: int
    repeats: int


class RepetitionGuard:
    """Detects obvious looped text in a streaming suffix window.

    The detector only checks whether the current output suffix is made of the
    same medium-sized pattern repeated several times. It intentionally ignores
    arbitrary duplicate substrings elsewhere in the text.
    """

    def __init__(self, config: Optional[RepetitionGuardConfig] = None) -> None:
        self.config = config or RepetitionGuardConfig()
        self._window = ""

    def observe(self, content: str, content_type: str) -> Optional[RepetitionMatch]:
        if not content or content_type not in self.config.text_content_types:
            return None

        normalized = self._normalize(content)
        if not normalized:
            return None

        self._window = (self._window + normalized)[-self.config.window_chars:]
        return self._detect_suffix_repeat()

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(text.split())

    def _detect_suffix_repeat(self) -> Optional[RepetitionMatch]:
        text = self._window
        cfg = self.config
        text_len = len(text)
        if text_len < cfg.min_pattern_chars * cfg.min_repeats:
            return None

        max_pattern = min(cfg.max_pattern_chars, text_len // cfg.min_repeats)
        for pattern_len in range(cfg.min_pattern_chars, max_pattern + 1):
            pattern = text[-pattern_len:]
            if len(set(pattern)) < cfg.min_distinct_chars:
                continue

            repeats = 1
            cursor = text_len - pattern_len
            while cursor >= pattern_len:
                start = cursor - pattern_len
                if text[start:cursor] != pattern:
                    break
                repeats += 1
                cursor = start
                if repeats >= cfg.min_repeats:
                    return RepetitionMatch(
                        pattern=pattern,
                        pattern_chars=pattern_len,
                        repeats=repeats,
                    )

        return None
