from uuid import uuid4
from typing import TypeVar, List, Dict, Optional, Any, Type, Union, TYPE_CHECKING
import logging
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
from alphora.prompter import BasePrompt
from alphora.agent.stream import Stream
from pydantic import BaseModel

from alphora.memory import MemoryManager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


T = TypeVar('T', bound='BaseAgent')


class MemoryPoolItem(BaseModel):
    """记忆池项模型，包含记忆实例和元数据"""
    memory: MemoryManager
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
                 memory: Optional[MemoryManager] = None,
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
        self.memory = memory if memory is not None else MemoryManager(llm=llm)

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
            content_type: Optional[str] = None,

            system_prompt: Optional[str] = None,
            enable_memory: bool = False,
            memory: Optional['MemoryManager'] = None,
            memory_id: Optional[str] = None,
            max_history_rounds: int = 10,
            auto_save_memory: bool = True,

    ) -> BasePrompt:
        """
        快速创建提示词模板

        支持两种模式：

        【传统模式】使用 prompt/template_path 参数：
            - 所有内容渲染后放入 role='user' 的 content
            - 不支持自动记忆管理
            - 适合需要完全自定义提示词结构的场景

            示例：
                prompt = self.create_prompt(
                    prompt='历史记录：{{history}}\\n请回答：{{query}}'
                )
                prompt.update_placeholder(history=history)
                await prompt.acall(query='你好')

        【新模式】使用 system_prompt 参数：
            - 支持规范的 messages 结构（system/user/assistant 分离）
            - 支持自动记忆管理
            - 适合需要多轮对话记忆的场景

            示例：
                prompt = self.create_prompt(
                    system_prompt='你是一个{{personality}}的助手',
                    enable_memory=True,
                    memory=memory
                )
                prompt.update_placeholder(personality='友好')
                await prompt.acall(query='你好')  # 自动管理历史

        注意：两种模式不能混用！

        Args:
            prompt: 提示词字符串（传统模式）
            template_path: 提示词模板文件路径（传统模式）
            template_desc: 提示词描述
            content_type: 当调用 acall 方法时，输出的流的 content_type
            system_prompt: 系统提示词（新模式，支持占位符）
            enable_memory: 是否启用记忆（仅新模式）
            memory_id: 记忆ID，用于区分不同会话（新模式）
            max_history_rounds: 最大历史轮数（新模式）
            auto_save_memory: 是否自动保存对话到记忆（新模式）

        Returns:
            BasePrompt 实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        if memory is None:
            memory = self.memory

        if memory_id is None:
            memory_id = "default"

        prompt_instance = BasePrompt(
            template_path=template_path,
            template_desc=template_desc,
            callback=self.callback,
            content_type=content_type,

            system_prompt=system_prompt,
            enable_memory=enable_memory,
            memory=memory,
            memory_id=memory_id,
            max_history_rounds=max_history_rounds,
            auto_save_memory=auto_save_memory,

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

    def create_memory(
            self,
            storage_path: Optional[str] = None,
            storage_type: str = "memory",
            **kwargs
    ) -> 'MemoryManager':
        """
        创建 MemoryManager 实例（用于 Prompt 级别的记忆）

        Args:
            storage_path: 存储路径（如果需要持久化）
            storage_type: 存储类型
                - "memory": 内存存储（默认，程序结束后丢失）
                - "json": JSON 文件存储
                - "sqlite": SQLite 数据库存储（推荐用于生产）
            **kwargs: 传递给 MemoryManager 的其他参数

        Returns:
            MemoryManager 实例

        使用示例：
            # 内存存储
            memory = agent.create_memory()

            # SQLite 持久化
            memory = agent.create_memory(
                storage_path="./data/chat.db",
                storage_type="sqlite"
            )

            # JSON 持久化
            memory = agent.create_memory(
                storage_path="./data/chat.json",
                storage_type="json"
            )

            # 使用
            prompt = agent.create_prompt(
                system_prompt="你是助手",
                enable_memory=True,
                memory=memory
            )
        """
        from alphora.memory import MemoryManager
        return MemoryManager(
            storage_path=storage_path,
            storage_type=storage_type,
            **kwargs
        )

    def __or__(self, other):
        # TODO
        pass
