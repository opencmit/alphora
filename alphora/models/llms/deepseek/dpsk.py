from typing import Optional, Mapping, Literal
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer


class DeepSeek(OpenAILike):
    """
    专为Dpsk系列模型设计的 LLM 封装类
    兼容 DashScope 的 OpenAI 兼容 API
    """

    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(
            self,
            model_name: str = "qwen-max",
            api_key: Optional[str] = None,
            header: Optional[Mapping[str, str]] = None,
            temperature: float = 0.0,
            max_tokens: int = 1024,
            top_p: float = 1.0,
    ):
        """
        初始化 Qwen 模型客户端。

        Args:
            model_name: 模型名称，如 'qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen3-32b' 等。
            api_key: DashScope API 密钥。若未提供，将尝试从环境变量 LLM_API_KEY 读取。
            header: 额外请求头。
            temperature: 采样温度（0.0 ~ 1.0）。
            max_tokens: 最大生成 token 数。
            top_p: 核采样参数。

        """
        super().__init__(
            model_name=model_name,
            api_key=api_key,
            base_url=self.DASHSCOPE_BASE_URL,
            header=header,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p
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

    def __repr__(self):
        return (
            f"DeepSeek(model='{self.model_name}', "
            f"temp={self.temperature}, max_tokens={self.max_tokens})"
        )

