import time
import logging
from dataclasses import dataclass
from typing import Dict, Type, Optional, TypeVar
from uuid import uuid4

from alphora.memory import MemoryManager

T = TypeVar('T', bound='BaseMemory')

logger = logging.getLogger(__name__)


@dataclass
class MemoryPoolItem:
    """记忆池项模型"""
    memory: MemoryManager
    create_time: float
    last_access_time: float
    session_id: str


class MemoryPool:
    """会话记忆池管理器"""

    def __init__(self, ttl: int, max_items: int):
        self._pool: Dict[str, MemoryPoolItem] = {}
        self._ttl = ttl
        self._max_items = max_items

    def get_or_create(
            self,
            session_id: Optional[str],
            memory_cls: Type[MemoryManager] = MemoryManager
    ) -> tuple[str, MemoryManager]:
        """
        获取或创建会话记忆
        :param session_id: 会话ID
        :param memory_cls: 记忆类
        :return: (session_id, 记忆实例)
        """
        # 生成会话ID
        session_id = session_id or str(uuid4())

        # 复用已有记忆
        if session_id in self._pool:
            item = self._pool[session_id]
            item.last_access_time = time.time()
            logger.debug(f"复用会话记忆: session_id={session_id}")
            return session_id, item.memory

        # 创建新记忆
        new_memory = memory_cls()
        self._pool[session_id] = MemoryPoolItem(
            memory=new_memory,
            create_time=time.time(),
            last_access_time=time.time(),
            session_id=session_id
        )
        logger.debug(
            f"创建新会话记忆: session_id={session_id}（当前容量: {len(self._pool)}/{self._max_items}）"
        )
        return session_id, new_memory

    def clean_expired(self) -> int:
        """
        清理过期/超出容量的记忆
        :return: 清理的数量
        """
        current_time = time.time()
        expired_keys = []

        # 收集过期项
        for session_id, item in self._pool.items():
            if current_time - item.last_access_time > self._ttl:
                expired_keys.append(session_id)

        # LRU清理超出容量的项
        if len(self._pool) > self._max_items:
            sorted_items = sorted(
                self._pool.items(),
                key=lambda x: x[1].last_access_time
            )
            need_remove = len(self._pool) - self._max_items
            expired_keys.extend([k for k, _ in sorted_items[:need_remove]])

        # 执行删除（去重）
        removed = 0
        for key in set(expired_keys):
            if key in self._pool:
                del self._pool[key]
                removed += 1
                logger.debug(f"清理会话记忆: session_id={key}")

        return removed

    @property
    def size(self) -> int:
        """获取当前记忆池大小"""
        return len(self._pool)

