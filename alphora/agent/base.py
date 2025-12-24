from uuid import uuid4
from typing import TypeVar, List, Dict, Optional, Any, Type, Union
import logging
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
from alphora.prompter import BasePrompt
from alphora.memory.base import BaseMemory
from alphora.memory.memories.short_term_memory import ShortTermMemory
from alphora.agent.stream import Stream
from pydantic import BaseModel


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


T = TypeVar('T', bound='BaseAgent')


class MemoryPoolItem(BaseModel):
    """记忆池项模型，包含记忆实例和元数据"""
    memory: BaseMemory
    create_time: float
    last_access_time: float
    agent_id: str
    session_id: str

    class Config:
        arbitrary_types_allowed = True


class BaseAgent(object):

    agent_type: str = "BaseAgent"

    def __init__(self,
                 llm: Optional[OpenAILike] = None,
                 verbose: bool = False,
                 memory: Optional[BaseMemory] = None,
                 agent_id: Optional[str] = None,
                 callback: Optional[DataStreamer] = None,
                 **kwargs):

        # if not callback:
        #     self.callback = DataStreamer(timeout=300)
        # else:
        #     self.callback = callback

        self.callback = callback
        self.agent_id = agent_id or str(uuid4())

        self.verbose = verbose
        self.memory = memory if memory is not None else ShortTermMemory()

        self.llm = llm

        # Agent配置字典，会继承给派生智能体
        self.config: Dict[str, Any] = {}

        self.stream = Stream(callback=self.callback)

        self.init_params = {
            "llm": self.llm,
            **kwargs}

        # self.metadata = AgentMetadata(name=self.agent_type)
        #
        # self.input_ports: List[AgentInputPort] = []
        # self.output_ports: List[AgentOutputPort] = []

        # self._status: AgentStatus = AgentStatus.PENDING
        # self._outputs: Dict[str, AgentOutput] = {}

        self._log = []

    def update_config(self,
                      key: str,
                      value: Any = None) -> None:
        """
        更新单个配置项。
        :param key: 配置项的键名（必须为字符串）
        :param value: 配置项的值。若为 None，可将该 key 设为 None（允许）。
        :return: None
        """
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")

        self.config[key] = value

    def get_config(self, key: str) -> Any:
        """
        获取指定配置项的值。

        :param key: 配置项的键名（必须为字符串）
        :return: 配置项的值，若不存在则返回 default
        """
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")

        if key not in self.config:
            raise ValueError(f'{key} dose not exist.')

        return self.config.get(key)

    def _reinitialize(self, **new_kwargs) -> None:
        merged_params = {**self.init_params, **new_kwargs}
        self.__init__(**merged_params)

    def set_input_ports(self) -> None:
        """设置Agent的输入"""
        self.input_ports = self.input_ports
        if not self.input_ports:
            logging.warning("No input ports defined")
        pass

    def set_output_ports(self) -> None:
        """设置Agent的输出"""
        self.output_ports = self.output_ports
        if not self.output_ports:
            logging.warning("No output ports defined")
        pass

    def list_input_ports(self) -> dict:
        """列出该智能体的输入端口要求"""

        pass

    def derive(self, agent_cls_or_instance: Union[Type[T], T], **kwargs) -> T:
        """
        从当前 agent 派生出一个新的 agent 实例。

        - 如果传入类：创建新实例，参数 = self.init_params + kwargs
        - 如果传入实例：用 self.init_params + kwargs 更新该实例
        """
        # 合并参数：kwargs 优先级最高，然后是 self.init_params
        override_params = {**self.init_params, **kwargs}

        # 情况1：传入的是类
        if isinstance(agent_cls_or_instance, type) and issubclass(agent_cls_or_instance, BaseAgent):
            derived_agent = agent_cls_or_instance(**override_params, callback=self.callback)
            return derived_agent

        # 情况2：传入的是实例
        elif isinstance(agent_cls_or_instance, BaseAgent):
            agent_cls_or_instance._reinitialize(**override_params)
            agent_cls_or_instance.callback = self.callback
            return agent_cls_or_instance

        else:
            raise TypeError(
                f"Unsupported type: {type(agent_cls_or_instance)}. "
                f"Expected a subclass or instance of BaseAgent."
            )

    def create_prompt(
            self,
            prompt: str = None,
            template_path: str = None,
            template_desc: str = "",
            content_type: Optional[str] = None) -> BasePrompt:
        """
        快速创建提示词模板
        Args:
            template_path: 提示词路径
            template_desc: 提示词描述
            content_type: 当调用 acall 方法时，输出的流的 content_type
            prompt: Optional

        Returns: BasePrompt实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        prompt_instance = BasePrompt(
            template_path=template_path,
            template_desc=template_desc,
            callback=self.callback,
            content_type=content_type
        )

        try:
            prompt_instance.add_llm(model=self.llm)

            if prompt:
                prompt_instance.load_from_string(prompt=prompt)

            prompt_instance.verbose = self.verbose

            return prompt_instance

        except Exception as e:
            error_msg = f'Failed to create prompt: {str(e)}'
            logging.error(error_msg)
            raise ValueError(error_msg)

    def __or__(self, other):
        # TODO
        pass



