from uuid import uuid4
from typing import TypeVar, List, Dict, Optional, Any, Type, Union, TYPE_CHECKING
import logging
import time
import re

from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
from alphora.prompter import BasePrompt
from alphora.agent.stream import Stream
from pydantic import BaseModel

from alphora.memory import MemoryManager

from alphora.debugger import tracer


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
                 debugger: bool = False,
                 debugger_port: int = 9527,
                 **kwargs):

        self.callback = callback
        self.agent_id = agent_id or str(uuid4())

        self.verbose = verbose

        # 记忆存储（作为共享存储池）
        self.memory = memory if memory is not None else MemoryManager(llm=llm)

        self.llm = llm

        # Agent配置字典，会继承给派生智能体
        self.config: Dict[str, Any] = {}

        self.stream = Stream(callback=self.callback)

        self.init_params = {
            "llm": self.llm,
            **kwargs
        }

        self._log = []

        # ========== 会话追踪（用于提示） ==========
        self._active_sessions: Dict[str, float] = {}  # session_id -> last_access_time
        self._session_prompt_count: Dict[str, int] = {}  # 用于检测短时间内重复创建
        self._memory_source_logged: bool = False  # 避免重复日志

        if debugger:
            tracer.enable(start_server=True, port=debugger_port)
        tracer.track_agent_created(self)

    def update_config(self, key: str, value: Any = None) -> None:
        """更新单个配置项"""
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")
        self.config[key] = value

    def get_config(self, key: str) -> Any:
        """获取指定配置项的值"""
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")
        if key not in self.config:
            raise ValueError(f'{key} does not exist.')
        return self.config.get(key)

    def _reinitialize(self, **new_kwargs) -> None:
        merged_params = {**self.init_params, **new_kwargs}
        self.__init__(**merged_params)

    def set_input_ports(self) -> None:
        """设置Agent的输入"""
        self.input_ports = self.input_ports
        if not self.input_ports:
            logging.warning("No input ports defined")

    def set_output_ports(self) -> None:
        """设置Agent的输出"""
        self.output_ports = self.output_ports
        if not self.output_ports:
            logging.warning("No output ports defined")

    def list_input_ports(self) -> dict:
        """列出该智能体的输入端口要求"""
        pass

    def derive(self, agent_cls_or_instance: Union[Type[T], T], **kwargs) -> T:
        """从当前 agent 派生出一个新的 agent 实例"""
        override_params = {**self.init_params, **kwargs}

        if isinstance(agent_cls_or_instance, type) and issubclass(agent_cls_or_instance, BaseAgent):
            derived_agent = agent_cls_or_instance(**override_params, callback=self.callback)

            tracer.track_agent_derived(self, derived_agent)

            return derived_agent
        elif isinstance(agent_cls_or_instance, BaseAgent):
            agent_cls_or_instance._reinitialize(**override_params)
            agent_cls_or_instance.callback = self.callback

            tracer.track_agent_derived(self, agent_cls_or_instance)

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
                    memory_id='user_001'
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
            memory: MemoryManager 实例（默认使用 Agent 的 memory）
            memory_id: 会话ID（默认 'default'，用于区分不同会话）
            max_history_rounds: 最大历史轮数（新模式）
            auto_save_memory: 是否自动保存对话到记忆（新模式）

        Returns:
            BasePrompt 实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        # ========== 记忆相关的验证和提示 ==========
        if enable_memory:
            # memory_id 处理
            if memory_id is None:
                memory_id = "default"
                if self.verbose:
                    logger.info(
                        f"[Memory] 使用默认会话 session_id='default'，如需区分多用户/多会话，请显式传入 memory_id 参数"
                    )
            else:
                # 验证 memory_id 格式
                self._validate_memory_id(memory_id)

            # memory 处理
            if memory is None:
                memory = self.memory
                # 首次使用时提示存储类型
                if not self._memory_source_logged and self.verbose:
                    self._memory_source_logged = True
                    storage_type = getattr(memory, '_storage_type', 'memory')
                    if storage_type == 'memory':
                        logger.info(
                            f"[Memory] 使用 Agent 默认记忆存储（内存模式，重启后丢失），"
                            f" 如需持久化，请在创建 Agent 时传入（示例）:"
                            f" memory=MemoryManager(storage_path='chat.db', storage_type='sqlite')"
                        )
                    else:
                        logger.info(f"[Memory] 使用 {storage_type} 存储模式")

            # 检查会话历史
            self._check_session_status(memory, memory_id, max_history_rounds)

            # 记录活跃会话（用于检测误用）
            self._track_session(memory_id)
        else:
            # 未启用记忆时的默认值
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
            agent_id=self.agent_id,
        )

        try:
            prompt_instance.add_llm(model=self.llm)

            if prompt:
                prompt_instance.load_from_string(prompt=prompt)

            prompt_instance.verbose = self.verbose

            tracer.track_prompt_created(
                agent_id=self.agent_id,
                prompt_id=prompt_instance.prompt_id,
                system_prompt=system_prompt,
                prompt=prompt_instance.prompt,
                placeholders=prompt_instance.content,
                enable_memory=enable_memory,
                memory_id=memory_id
            )
            prompt_instance._debug_agent_id = self.agent_id

            return prompt_instance

        except Exception as e:
            error_msg = f'Failed to create prompt: {str(e)}'
            logging.error(error_msg)
            raise ValueError(error_msg)

    def _validate_memory_id(self, memory_id: str):
        """
        验证 memory_id 格式

        规则：仅允许字母、数字、下划线、连字符
        """
        if not re.match(r'^[\w\-]+$', memory_id):
            raise ValueError(
                f"memory_id='{memory_id}' 格式无效\n"
                f"仅允许字母、数字、下划线、连字符\n"
                f"有效示例: 'user_001', 'session-abc', 'chat123'"
            )

        if len(memory_id) > 128:
            raise ValueError(
                f"memory_id='{memory_id[:20]}...' 过长（{len(memory_id)}字符）\n"
                f"最大长度: 128 字符"
            )

    def _check_session_status(self, memory: 'MemoryManager', session_id: str, max_rounds: int):
        """检查会话状态并给出提示"""
        try:
            # 获取会话摘要
            summary = memory.get_session_summary(session_id)

            if summary.get('exists', False):
                total_rounds = summary.get('rounds', 0)

                if self.verbose and total_rounds > 0:
                    logger.info(f"[Memory] 会话 '{session_id}' 已有 {total_rounds} 轮历史对话")

                # 警告：历史过长
                if total_rounds > max_rounds:
                    logger.warning(
                        f"[Memory] ⚠️ 会话 '{session_id}' 历史记录 ({total_rounds}轮) 超过 max_history_rounds={max_rounds}，"
                        f"仅最近 {max_rounds} 轮会发送给模型，旧消息将被忽略，"
                        f"如需调整，请设置 max_history_rounds 参数"
                    )
        except Exception:
            pass

    def _track_session(self, session_id: str):
        """追踪会话使用情况，检测潜在误用"""
        now = time.time()

        # 检测短时间内重复创建（可能是误用）
        if session_id in self._active_sessions:
            last_time = self._active_sessions[session_id]
            count = self._session_prompt_count.get(session_id, 0) + 1
            self._session_prompt_count[session_id] = count

            # 1秒内创建超过5次，给警告
            if now - last_time < 1 and count > 5:
                logger.warning(
                    f"[Memory] 检测到短时间内多次创建 Prompt 使用同一 session_id='{session_id}'，"
                    f" 如果这是循环调用请忽略，"
                    f" 否则建议复用 Prompt 实例以提高性能"
                )
                self._session_prompt_count[session_id] = 0  # 重置，避免重复警告
        else:
            self._session_prompt_count[session_id] = 1

        self._active_sessions[session_id] = now

    def list_sessions(self) -> List[str]:
        """
        列出所有会话ID

        Returns:
            会话ID列表

        示例:
            sessions = agent.list_sessions()
            # ['default', 'user_001', 'user_002']
        """
        if self.memory:
            return self.memory.list_memory_ids()
        return []

    def get_session_info(self, session_id: str = "default") -> Dict[str, Any]:
        """
        获取会话详细信息

        Args:
            session_id: 会话ID

        Returns:
            会话信息字典，包含:
            - session_id: 会话ID
            - exists: 是否存在
            - rounds: 对话轮数
            - total_messages: 总消息数
            - user_messages: 用户消息数
            - assistant_messages: 助手消息数
            - created_at: 创建时间戳
            - last_active: 最后活跃时间戳
            - storage_type: 存储类型

        示例:
            info = agent.get_session_info('user_001')
            print(f"对话轮数: {info['rounds']}")
        """
        if not self.memory:
            return {
                "session_id": session_id,
                "exists": False,
                "error": "No memory configured"
            }

        summary = self.memory.get_session_summary(session_id)
        summary['storage_type'] = getattr(self.memory, '_storage_type', 'unknown')
        return summary

    def get_session_history(
            self,
            session_id: str = "default",
            format: str = "messages",
            max_rounds: Optional[int] = None
    ) -> Union[str, List[Dict[str, str]]]:
        """
        获取会话历史记录

        Args:
            session_id: 会话ID
            format: 输出格式 ('messages' 或 'text')
            max_rounds: 最大轮数（可选）

        Returns:
            历史记录（messages 格式或 text 格式）

        示例:
            # 获取 messages 格式
            history = agent.get_session_history('user_001')
            # [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]

            # 获取 text 格式
            history_text = agent.get_session_history('user_001', format='text')
            # "用户: 你好\\n助手: 你好！"
        """
        if not self.memory:
            return [] if format == "messages" else ""

        return self.memory.build_history(
            memory_id=session_id,
            max_round=max_rounds or 100,
            format=format,
            include_timestamp=False
        )

    def clear_session(self, session_id: str = "default") -> bool:
        """
        清空指定会话的记忆

        Args:
            session_id: 会话ID

        Returns:
            是否成功

        示例:
            agent.clear_session('user_001')
            # [Memory] 已清空会话 'user_001' 的记忆
        """
        if self.memory:
            # 先检查是否存在
            if self.memory.has_memory(session_id):
                self.memory.clear_memory(session_id)
                logger.info(f"[Memory] 已清空会话 '{session_id}' 的记忆")
                tracer.track_memory_clear(memory_id=session_id, agent_id=self.agent_id)
                return True
            else:
                logger.info(f"[Memory] 会话 '{session_id}' 不存在或已为空")
                return False
        return False

    def clear_all_sessions(self, confirm: bool = False) -> int:
        """
        清空所有会话的记忆（危险操作，需要确认）

        Args:
            confirm: 必须显式传入 True 才会执行

        Returns:
            清空的会话数量

        示例:
            # 错误用法（会抛出异常）
            agent.clear_all_sessions()

            # 正确用法
            agent.clear_all_sessions(confirm=True)
            # [Memory] ⚠️ 已清空所有会话（共 3 个）
        """
        if not confirm:
            raise ValueError(
                "清空所有会话是危险操作！\n"
                "如果确定要执行，请显式传入 confirm=True\n"
                "示例: agent.clear_all_sessions(confirm=True)"
            )

        if self.memory:
            sessions = self.list_sessions()
            count = len(sessions)
            for sid in sessions:
                self.memory.clear_memory(sid)

            if count > 0:
                logger.warning(f"[Memory] ⚠️ 已清空所有会话（共 {count} 个）")
            else:
                logger.info("[Memory] 没有需要清空的会话")

            return count
        return 0

    def add_to_session(
            self,
            role: str,
            content: str,
            session_id: str = "default"
    ):
        """
        手动向会话添加记忆

        Args:
            role: 角色 ('user' 或 'assistant')
            content: 内容
            session_id: 会话ID

        示例:
            # 手动添加用户消息
            agent.add_to_session('user', '你好', session_id='user_001')

            # 手动添加助手消息
            agent.add_to_session('assistant', '你好！有什么可以帮你的？', session_id='user_001')
        """
        if self.memory:
            self.memory.add_memory(role, content, memory_id=session_id)
            if self.verbose:
                logger.info(f"[Memory] 已添加 {role} 消息到会话 '{session_id}'")

            tracer.track_memory_add(
                memory_id=session_id,
                role=role,
                content=content,
                agent_id=self.agent_id
            )

    def create_memory(
            self,
            storage_path: Optional[str] = None,
            storage_type: str = "memory",
            **kwargs
    ) -> 'MemoryManager':
        """
        创建 MemoryManager 实例

        Args:
            storage_path: 存储路径（如果需要持久化）
            storage_type: 存储类型
                - "memory": 内存存储（默认，程序重启后丢失）
                - "json": JSON 文件存储
                - "sqlite": SQLite 数据库存储（推荐用于生产）
            **kwargs: 传递给 MemoryManager 的其他参数

        Returns:
            MemoryManager 实例

        示例:
            # 内存存储（默认）
            memory = agent.create_memory()

            # SQLite 持久化（推荐）
            memory = agent.create_memory(
                storage_path="./data/chat.db",
                storage_type="sqlite"
            )

            # JSON 持久化
            memory = agent.create_memory(
                storage_path="./data/chat.json",
                storage_type="json"
            )
        """
        from alphora.memory import MemoryManager
        return MemoryManager(
            storage_path=storage_path,
            storage_type=storage_type,
            llm=self.llm,
            **kwargs
        )

    def memory_status(self) -> str:
        """
        获取记忆系统状态的可读描述

        Returns:
            状态描述字符串

        示例:
            print(agent.memory_status())
        """
        if not self.memory:
            return "记忆系统未配置"

        sessions = self.list_sessions()
        storage_type = getattr(self.memory, '_storage_type', 'unknown')

        lines = [
            "=" * 50,
            "记忆系统状态",
            "=" * 50,
            f"存储类型: {storage_type}",
            f"会话数量: {len(sessions)}",
            "-" * 50,
            ]

        if sessions:
            lines.append("会话列表:")
            for sid in sessions[:10]:  # 最多显示10个
                info = self.get_session_info(sid)
                rounds = info.get('rounds', 0)
                lines.append(f"  - {sid}: {rounds} 轮对话")

            if len(sessions) > 10:
                lines.append(f"  ... 还有 {len(sessions) - 10} 个会话")
        else:
            lines.append("暂无会话")

        lines.append("=" * 50)
        return "\n".join(lines)

    def __or__(self, other):
        # TODO
        pass

