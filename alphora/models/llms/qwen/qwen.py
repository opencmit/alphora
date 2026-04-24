from typing import Any, Dict, List, Mapping, Optional

from alphora.models.llms.openai_like import OpenAILike


class Qwen(OpenAILike):
    """
    专为通义千问（Qwen）系列模型设计的 LLM 封装类
    兼容 DashScope 的 OpenAI 兼容 API
    """

    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

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
        """
        各参数与 :class:`OpenAILike` 相同，调用习惯（关键字顺序、可省略项）可保持一致。

        与父类有别的默认约定：``model_name`` 为 ``None`` 时视为 ``"qwen-max"``；``base_url`` 为
        ``None`` 时使用 :attr:`DASHSCOPE_BASE_URL`；``api_key`` 仍按父类与环境变量
        ``LLM_API_KEY`` 解析。
        """
        if model_name is None:
            model_name = "qwen-max"
        if base_url is None:
            base_url = type(self).DASHSCOPE_BASE_URL
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

    def _get_extra_body(self, enable_thinking: bool = False) -> Optional[dict]:
        """
        为 Qwen3 系列模型启用推理模式（thinking）。
        只有特定模型（如 qwen3-32b）支持该功能。
        """
        if self.model_name and self.model_name.startswith("qwen3") and not self.model_name.endswith("jz"):
            return {
                "enable_thinking": enable_thinking,
                "chat_template_kwargs": {"enable_thinking": enable_thinking},
            }
        return None

    def _transform_messages(
            self, messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """DashScope 严格要求每条消息的 ``content`` 字段必须存在且为字符串类型。

        OpenAI / DeepSeek 允许 ``content: null``（如 assistant 仅带 ``tool_calls``
        的情况）或省略该字段（如部分 tool 结果消息），但 DashScope 会直接返回
        400 ``The content field is a required field``。

        这里做一次非破坏性归一化：仅当某条消息的 ``content`` 缺失 / 为 ``None``
        / 非字符串时，复制该条消息并把 ``content`` 置为空字符串；其余消息保持
        原对象引用不变。``tool_calls``、``tool_call_id``、``name`` 等字段保留。
        """
        normalized: List[Dict[str, Any]] = []
        for m in messages:
            if not isinstance(m, dict):
                normalized.append(m)
                continue
            c = m.get("content", None)
            if isinstance(c, str):
                normalized.append(m)
                continue
            fixed = dict(m)
            fixed["content"] = "" if c is None else c
            normalized.append(fixed)
        return normalized

    def __repr__(self):
        return (
            f"Qwen(model='{self.model_name}', "
            f"temp={self.temperature}, max_tokens={self.max_tokens})"
        )

