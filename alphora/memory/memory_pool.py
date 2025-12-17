"""
pool:
source - memory (BaseMemory)
"""

import threading
from collections import OrderedDict
from typing import Optional, Any, Dict
from alphora.memory.base import BaseMemory


class MemoryPool:
    def __init__(self,
                 max_memories: int = 999):
        """
        初始化连接池
        """
        self.max_connections = max_memories
        self.pool: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.lock = threading.Lock()

    def get_memory(self, mid: str) -> Optional[Any]:
        """
        获取指定mid的Memory实例
        Args:
            mid:
        """
        with self.lock:
            entry = self.pool.get(mid)
            if entry:
                memory = entry['memory']
                if not memory:
                    print(f"连接 '{mid}' 不可用，正在移除")
                    del self.pool[mid]
                else:
                    return memory
            return None

    def add_memory(self,
                   mid: str,
                   memory: BaseMemory):
        """
        Args:
            mid:
            memory:
        Returns:
        """
        if mid in self.pool:
            raise ValueError(f'{mid} 已存在，请换个mid试试吧')

        if not isinstance(memory, BaseMemory):
            raise ValueError('memory must be BaseMemory')

        with self.lock:
            if len(self.pool) >= self.max_connections:
                removed_source, _ = self.pool.popitem(last=False)
                print(f"连接池已满，移除最久未使用的连接 '{removed_source}'")

            self.pool[mid] = {
                'memory': memory
            }

