# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


"""
DeepSeek 模型封装。

本模块演示了三种对接 DeepSeek 的方式，覆盖其历史与当前的 API 形态：

- :class:`DeepSeek`：根据 ``enable_thinking`` 自动在 ``deepseek-chat`` /
  ``deepseek-reasoner`` 间切换模型（经典双模型形态）。
- :class:`DeepSeekV3`：单模型 + ``extra_body={"thinking": {"type": ...}}``
  开关（V3.1 混合推理模型形态）。
- :class:`DeepSeekV4Pro`：``reasoning_effort`` 顶层参数 + ``extra_body.thinking``
  组合（V4-Pro 形态）。

JSON mode 与 tool calls 均可直接复用父类默认实现：

- **JSON mode**：调用时传入 ``response_format={"type": "json_object"}`` 即可；
  prompt 中需显式包含 "json" 字样（DeepSeek 官方要求）。
- **Tool calls**：使用 ``deepseek-chat`` 模型，按 OpenAI 兼容格式传 ``tools`` 即可。
"""

from typing import Any, Dict, Mapping, Optional

from alphora.models.llms.openai_like import OpenAILike


class DeepSeek(OpenAILike):
    """DeepSeek 基础封装（双模型切换形态）。

    ``enable_thinking=True`` 时自动切换到 :attr:`REASONER_MODEL`；
    ``enable_thinking=False`` 时切回 :attr:`DEFAULT_CHAT_MODEL`。
    """

    BASE_URL: str = "https://api.deepseek.com"

    REASONER_MODEL: str = "deepseek-reasoner"
    DEFAULT_CHAT_MODEL: str = "deepseek-chat"

    CAPABILITIES = {"reasoning", "json_mode", "tools"}

    def __init__(
            self,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            is_multimodal: bool = False,
            hooks=None,
    ):
        """初始化 DeepSeek 客户端。

        各参数与 :class:`OpenAILike` 相同；仅作两处约定化默认值：

        - ``model_name`` 为 ``None`` 时使用 :attr:`DEFAULT_CHAT_MODEL`。
        - ``base_url`` 为 ``None`` 时使用 :attr:`BASE_URL`；其它行为与父类一致
          （例如 ``api_key``、空 ``base_url`` 时与环境变量 `LLM_*` 的组合）。
        """
        if model_name is None:
            model_name = type(self).DEFAULT_CHAT_MODEL
        if base_url is None:
            base_url = type(self).BASE_URL
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            header=header,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            is_multimodal=is_multimodal,
            hooks=hooks,
        )

    # ------------------------------------------------------------------
    # thinking：enable_thinking 切模型
    # ------------------------------------------------------------------

    def _resolve_model(self, current: Optional[str], enable_thinking: bool) -> str:
        """根据 ``enable_thinking`` 选择合适的 DeepSeek model 名称。

        规则：
        - ``enable_thinking=True`` 且当前 model 不是 reasoner → 切到 reasoner
        - ``enable_thinking=False`` 且当前 model 是 reasoner → 切到 chat
        - 否则保持当前 model 不变（允许用户显式指定特殊模型）
        """
        current = current or self.model_name
        if enable_thinking and current != self.REASONER_MODEL:
            return self.REASONER_MODEL
        if not enable_thinking and current == self.REASONER_MODEL:
            return self.DEFAULT_CHAT_MODEL
        return current

    def _apply_thinking(
            self,
            kwargs: Dict[str, Any],
            *,
            enable_thinking: bool,
    ) -> None:
        kwargs["model"] = self._resolve_model(kwargs.get("model"), enable_thinking)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"DeepSeek(model='{self.model_name}', "
            f"temp={self.temperature}, max_tokens={self.max_tokens})"
        )


class DeepSeekV3(DeepSeek):
    """DeepSeek V3.1 混合推理形态：单模型 + ``extra_body.thinking``。

    不做模型切换，仅通过 ``extra_body={"thinking": {"type": "enabled"/"disabled"}}``
    控制推理行为。
    """

    def __init__(
            self,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            is_multimodal: bool = False,
            hooks=None,
    ) -> None:
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            header=header,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            is_multimodal=is_multimodal,
            hooks=hooks,
        )

    def _apply_thinking(
            self,
            kwargs: Dict[str, Any],
            *,
            enable_thinking: bool,
    ) -> None:
        eb = dict(kwargs.get("extra_body") or {})
        eb["thinking"] = {"type": "enabled" if enable_thinking else "disabled"}
        kwargs["extra_body"] = eb


class DeepSeekV4Pro(DeepSeek):
    """DeepSeek V4-Pro 形态：``reasoning_effort`` + ``extra_body.thinking`` 组合。

    对应官方示例::

        client.chat.completions.create(
            model="deepseek-v4-pro",
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )

    默认 ``reasoning_effort="high"``，可通过构造函数或调用时 ``extra_kwargs``
    覆写。
    """

    DEFAULT_CHAT_MODEL = "deepseek-v4-pro"

    def __init__(
            self,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            is_multimodal: bool = False,
            reasoning_effort: str = "high",
            hooks=None,
    ) -> None:
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            header=header,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            is_multimodal=is_multimodal,
            hooks=hooks,
        )
        self.reasoning_effort = reasoning_effort

    def _apply_thinking(
            self,
            kwargs: Dict[str, Any],
            *,
            enable_thinking: bool,
    ) -> None:
        if not enable_thinking:
            return
        kwargs.setdefault("reasoning_effort", self.reasoning_effort)
        eb = dict(kwargs.get("extra_body") or {})
        eb["thinking"] = {"type": "enabled"}
        kwargs["extra_body"] = eb


