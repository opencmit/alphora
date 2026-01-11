"""
记忆管理器
"""

from typing import List, Optional, Dict, Any, Union, Literal
import time
import asyncio
import logging
from pathlib import Path

from alphora.memory.memory_unit import (
    MemoryUnit,
    MemoryType,
    create_memory,
    extract_keywords
)
from alphora.memory.decay import (
    DecayStrategy,
    get_decay_strategy,
    LogarithmicDecay
)
from alphora.memory.retrieval import (
    RetrievalStrategy,
    RetrievalResult,
    get_retrieval_strategy,
    search_memories
)
from alphora.memory.reflection import (
    MemoryReflector,
    AutoReflector,
    ReflectionResult
)
from alphora.storage import (
    StorageBackend,
    JSONStorage,
    SQLiteStorage,
    InMemoryStorage,
    create_storage
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器
    
    统一管理各类记忆，提供简洁的API接口。
    
    使用示例:
    ```python
    # 基本使用（内存存储）
    memory = MemoryManager()
    
    # 使用文件存储
    memory = MemoryManager(storage_path="./data/memory.json")
    
    # 使用SQLite存储
    memory = MemoryManager(
        storage_path="./data/memory.db",
        storage_type="sqlite"
    )
    
    # 启用LLM反思
    from alphora.models import OpenAILike
    llm = OpenAILike(...)
    memory = MemoryManager(llm=llm, auto_reflect=True)
    
    # 添加记忆（兼容旧接口）
    memory.add_memory(
        role="user",
        content="你好，我想了解Python",
        memory_id="chat_001"
    )
    
    # 构建历史（兼容旧接口）
    history = memory.build_history(
        memory_id="chat_001",
        max_round=5
    )

    # 搜索记忆
    results = memory.search("Python", memory_id="chat_001")
    
    # 获取反思
    reflection = await memory.reflect(memory_id="chat_001")
    ```
    """
    
    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        storage_path: Optional[str] = None,
        storage_type: str = "json",
        llm: Optional[Any] = None,
        decay_strategy: Union[str, DecayStrategy] = "log",
        retrieval_strategy: Union[str, RetrievalStrategy] = "hybrid",
        auto_reflect: bool = False,
        reflect_threshold: int = 20,
        auto_save: bool = True,
        auto_extract_tags: bool = True
    ):
        """
        Args:
            storage: 存储后端实例（优先使用）
            storage_path: 存储路径（如果storage为None则创建）
            storage_type: 存储类型 (json/sqlite/memory)
            llm: LLM实例，用于反思功能
            decay_strategy: 衰减策略名称或实例
            retrieval_strategy: 检索策略名称或实例
            auto_reflect: 是否自动反思
            reflect_threshold: 反思阈值
            auto_save: 是否自动保存
            auto_extract_tags: 是否自动提取标签
        """

        if storage is not None:
            self._storage = storage
        elif storage_path:
            self._storage = create_storage(storage_type, storage_path)
        else:
            self._storage = InMemoryStorage()

        if isinstance(decay_strategy, str):
            self._decay_strategy = get_decay_strategy(decay_strategy)
        else:
            self._decay_strategy = decay_strategy
        
        if isinstance(retrieval_strategy, str):
            self._retrieval_strategy = get_retrieval_strategy(retrieval_strategy)
        else:
            self._retrieval_strategy = retrieval_strategy
        
        # LLM和反思
        self._llm = llm
        self._reflector = MemoryReflector(llm) if llm else None
        self._auto_reflector = AutoReflector(
            self._reflector,
            threshold=reflect_threshold
        ) if llm and auto_reflect else None
        
        # 配置
        self._auto_save = auto_save
        self._auto_extract_tags = auto_extract_tags
        
        # 内存缓存（用于快速访问）
        self._cache: Dict[str, List[MemoryUnit]] = {}
        self._turn_counter: Dict[str, int] = {}
        
        # 从存储加载
        self._load_from_storage()

        self.agent = None
    
    # ==================== 存储 ====================
    
    def _get_storage_key(self, memory_id: str) -> str:
        """获取存储键"""
        return f"memories:{memory_id}"
    
    def _get_turn_key(self, memory_id: str) -> str:
        """获取轮数计数键"""
        return f"turns:{memory_id}"
    
    def _load_from_storage(self):
        """从存储加载数据"""
        # 获取所有记忆键
        keys = self._storage.keys("memories:*")
        
        for key in keys:
            memory_id = key.replace("memories:", "")
            memories_data = self._storage.lrange(key, 0, -1)
            
            self._cache[memory_id] = [
                MemoryUnit.from_dict(data) if isinstance(data, dict) else data
                for data in memories_data
            ]
            
            # 加载轮数
            turn = self._storage.get(self._get_turn_key(memory_id), 0)
            self._turn_counter[memory_id] = turn
    
    def _save_memory(self, memory_id: str, memory: MemoryUnit):
        """保存单条记忆到存储"""
        key = self._get_storage_key(memory_id)
        self._storage.rpush(key, memory.to_dict())
        
        if self._auto_save:
            self._storage.save()
    
    def _save_all(self, memory_id: str):
        """保存所有记忆到存储"""
        if memory_id not in self._cache:
            return
        
        key = self._get_storage_key(memory_id)
        
        # 清空并重新写入
        self._storage.delete(key)
        for memory in self._cache[memory_id]:
            self._storage.rpush(key, memory.to_dict())
        
        # 保存轮数
        self._storage.set(
            self._get_turn_key(memory_id),
            self._turn_counter.get(memory_id, 0)
        )
        
        if self._auto_save:
            self._storage.save()
    
    # ==================== 核心接口 ====================
    
    def add_memory(
        self,
        role: str,
        content: str,
        memory_id: str = 'default',
        decay_factor: float = 0.9,
        increment: float = 0.1,
        # 新增可选参数
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        memory_type: MemoryType = MemoryType.SHORT_TERM
    ) -> str:
        """
        添加记忆
        
        Args:
            role: 角色 (user/assistant/system)
            content: 内容
            memory_id: 记忆ID，用于区分不同的对话/Prompt
            decay_factor: 衰减因子（兼容旧接口，但会被decay_strategy覆盖）
            increment: 增强值
            importance: 重要性（可选，否则使用默认值）
            tags: 标签列表（可选，否则自动提取）
            metadata: 元数据
            memory_type: 记忆类型
            
        Returns:
            记忆单元的唯一ID
        """
        # 初始化
        if memory_id not in self._cache:
            self._cache[memory_id] = []
            self._turn_counter[memory_id] = 0
        
        # 更新轮数
        self._turn_counter[memory_id] += 1
        current_turn = self._turn_counter[memory_id]
        
        # 对现有记忆应用衰减
        for idx, memory in enumerate(self._cache[memory_id]):
            # 使用配置的衰减策略，而非简单的decay_factor
            memory_turn = idx + 1  # 假设按顺序添加
            self._decay_strategy.apply(memory, current_turn, memory_turn)
        
        # 创建新记忆
        new_memory = create_memory(
            role=role,
            content=content,
            importance=importance or 0.5,
            tags=tags,
            metadata=metadata,
            memory_type=memory_type,
            auto_extract_tags=self._auto_extract_tags and tags is None
        )
        
        # 增强新记忆
        new_memory.reinforce(increment)
        
        # 添加到缓存
        self._cache[memory_id].append(new_memory)
        
        # 保存到存储
        self._save_memory(memory_id, new_memory)
        
        # 触发自动反思（异步）
        if self._auto_reflector:
            asyncio.create_task(
                self._auto_reflector.maybe_reflect(
                    self._cache[memory_id],
                    memory_id
                )
            )
        
        return new_memory.unique_id
    
    def build_history(
        self,
        memory_id: str = "default",
        max_length: Optional[int] = None,
        max_round: int = 5,
        include_timestamp: bool = True,
        # 新增可选参数
        include_reflections: bool = True,
        query: Optional[str] = None,
        format: Literal["text", "messages"] = "text",
        min_score: float = 0.0
    ) -> Union[str, List[Dict[str, str]]]:
        """
        构建历史对话
        
        Args:
            memory_id: 记忆ID
            max_length: 最大字符长度
            max_round: 最大轮数
            include_timestamp: 是否包含时间戳
            include_reflections: 是否包含反思记忆
            query: 如果提供，则按相关性检索
            format: 输出格式 (text/messages)
            min_score: 最小分数阈值
            
        Returns:
            格式化的历史字符串或消息列表
        """
        memories = self.get_memories(memory_id)
        
        if not memories:
            return "" if format == "text" else []
        
        # 过滤低分记忆
        if min_score > 0:
            memories = [m for m in memories if m.score >= min_score]
        
        # 如果有查询，按相关性检索
        if query:
            results = self._retrieval_strategy.search(
                query, memories, top_k=max_round * 2
            )
            memories = [r.memory for r in results]
        else:
            # 否则按分数排序取top
            memories = self.get_top_memories(memory_id, top_n=max_round * 2)
        
        # 按时间排序
        memories = sorted(memories, key=lambda m: m.timestamp)
        
        # 过滤反思记忆（如果不需要）
        if not include_reflections:
            memories = [
                m for m in memories
                if m.memory_type != MemoryType.REFLECTION
            ]
        
        # 限制数量
        if len(memories) > max_round * 2:
            memories = memories[-max_round * 2:]
        
        # 构建输出
        if format == "messages":
            return self._build_messages(memories)
        else:
            return self._build_text(
                memories,
                max_length=max_length,
                include_timestamp=include_timestamp
            )
    
    def _build_text(
        self,
        memories: List[MemoryUnit],
        max_length: Optional[int],
        include_timestamp: bool
    ) -> str:
        """构建文本格式的历史"""
        context = []
        total_length = 0
        max_length = max_length or float('inf')
        
        for memory in memories:
            role = memory.get_role()
            content = memory.get_content_text()
            
            if include_timestamp:
                timestamp = memory.formatted_timestamp(include_second=False)
                line = f"[{timestamp}] % {role}: {content}\n"
            else:
                line = f"{role}: {content}\n"
            
            if total_length + len(line) > max_length:
                break
            
            context.append(line)
            total_length += len(line)
        
        return "".join(context)
    
    def _build_messages(
        self,
        memories: List[MemoryUnit]
    ) -> List[Dict[str, str]]:
        """构建消息列表格式"""
        return [memory.to_message_format() for memory in memories]
    
    def get_memories(self, memory_id: str) -> List[MemoryUnit]:
        """获取指定ID的所有记忆"""
        return self._cache.get(memory_id, [])
    
    def get_top_memories(
        self,
        memory_id: str,
        top_n: int = 10,
        sort_by: Literal["score", "importance", "composite", "time"] = "composite"
    ) -> List[MemoryUnit]:
        """
        获取评分最高的记忆
        
        Args:
            memory_id: 记忆ID
            top_n: 返回数量
            sort_by: 排序方式
        """
        memories = self.get_memories(memory_id)
        
        if sort_by == "score":
            key_func = lambda m: m.score
        elif sort_by == "importance":
            key_func = lambda m: m.importance
        elif sort_by == "time":
            key_func = lambda m: m.timestamp
        else:  # composite
            key_func = lambda m: m.get_composite_score()
        
        return sorted(memories, key=key_func, reverse=True)[:top_n]
    
    def search(
        self,
        query: str,
        memory_id: str = "default",
        top_k: int = 10,
        strategy: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        搜索记忆
        
        Args:
            query: 查询字符串
            memory_id: 记忆ID
            top_k: 返回数量
            strategy: 检索策略（可选，否则使用默认策略）
        """
        memories = self.get_memories(memory_id)
        
        if not memories:
            return []
        
        if strategy:
            retriever = get_retrieval_strategy(strategy)
        else:
            retriever = self._retrieval_strategy
        
        results = retriever.search(query, memories, top_k)
        
        # 记录访问
        for result in results:
            result.memory.access()
        
        return results
    
    def clear_memory(self, memory_id: str):
        """清空指定ID的记忆"""
        if memory_id in self._cache:
            del self._cache[memory_id]
        
        if memory_id in self._turn_counter:
            del self._turn_counter[memory_id]
        
        self._storage.delete(self._get_storage_key(memory_id))
        self._storage.delete(self._get_turn_key(memory_id))
        
        if self._auto_save:
            self._storage.save()
    
    def forget(
        self,
        memory_id: str,
        threshold: float = 0.1,
        keep_important: bool = True,
        importance_threshold: float = 0.7
    ) -> int:
        """
        遗忘低分记忆
        
        Args:
            memory_id: 记忆ID
            threshold: 分数阈值
            keep_important: 是否保留重要记忆
            importance_threshold: 重要性阈值
            
        Returns:
            遗忘的记忆数量
        """
        if memory_id not in self._cache:
            return 0
        
        original_count = len(self._cache[memory_id])
        
        def should_keep(m: MemoryUnit) -> bool:
            if m.score >= threshold:
                return True
            if keep_important and m.importance >= importance_threshold:
                return True
            return False
        
        self._cache[memory_id] = [
            m for m in self._cache[memory_id] if should_keep(m)
        ]
        
        forgotten = original_count - len(self._cache[memory_id])
        
        if forgotten > 0:
            self._save_all(memory_id)
        
        return forgotten
    
    def is_empty(self, memory_id: str) -> bool:
        """判断记忆是否为空"""
        return len(self.get_memories(memory_id)) == 0
    
    # ==================== 反思、总结 ====================
    
    async def reflect(
        self,
        memory_id: str = "default",
        force: bool = False
    ) -> Optional[ReflectionResult]:
        """
        触发反思
        
        Args:
            memory_id: 记忆ID
            force: 是否强制反思
            
        Returns:
            反思结果
        """
        if not self._reflector:
            logger.warning("No LLM configured for reflection")
            return None
        
        memories = self.get_memories(memory_id)
        
        if not memories:
            return None
        
        return await self._reflector.reflect(memories)
    
    async def summarize(
        self,
        memory_id: str = "default",
        style: str = "brief"
    ) -> str:
        """
        生成摘要
        
        Args:
            memory_id: 记忆ID
            style: 摘要风格
            
        Returns:
            摘要文本
        """
        if not self._reflector:
            logger.warning("No LLM configured for summarization")
            return ""
        
        memories = self.get_memories(memory_id)
        return await self._reflector.summarize(memories, style)
    
    async def extract_key_info(
        self,
        memory_id: str = "default"
    ) -> Dict[str, List[str]]:
        """提取关键信息"""
        if not self._reflector:
            return {}
        
        memories = self.get_memories(memory_id)
        return await self._reflector.extract_key_info(memories)
    
    # ==================== 持久化 ====================
    
    def save(self, path: Optional[str] = None):
        """保存到存储"""
        for memory_id in self._cache:
            self._save_all(memory_id)
        
        self._storage.save()
    
    def load(self, path: Optional[str] = None):
        """从存储加载"""
        self._load_from_storage()
    
    def dump(self, dump_path: str):
        """
        导出到文件（兼容旧接口）
        
        Args:
            dump_path: 导出路径
        """
        import dill
        
        with open(dump_path, 'wb') as f:
            dill.dump(self, f)
    
    @classmethod
    def load_from_dump(cls, dump_path: str) -> 'MemoryManager':
        """从dump文件加载"""
        import dill
        
        with open(dump_path, 'rb') as f:
            return dill.load(f)
    
    # ==================== 统计信息 ====================
    
    def stats(self, memory_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            memory_id: 记忆ID（可选，不提供则返回全局统计）
        """
        if memory_id:
            memories = self.get_memories(memory_id)
            return {
                "memory_id": memory_id,
                "count": len(memories),
                "turns": self._turn_counter.get(memory_id, 0),
                "avg_score": sum(m.score for m in memories) / len(memories) if memories else 0,
                "avg_importance": sum(m.importance for m in memories) / len(memories) if memories else 0,
                "types": {
                    t.value: len([m for m in memories if m.memory_type == t])
                    for t in MemoryType
                },
                "oldest": min(m.timestamp for m in memories) if memories else None,
                "newest": max(m.timestamp for m in memories) if memories else None,
            }
        else:
            return {
                "total_memories": sum(len(m) for m in self._cache.values()),
                "memory_ids": list(self._cache.keys()),
                "storage_info": self._storage.info() if hasattr(self._storage, 'info') else {},
                "decay_strategy": self._decay_strategy.name,
                "retrieval_strategy": self._retrieval_strategy.name,
                "has_llm": self._llm is not None,
                "auto_reflect": self._auto_reflector is not None,
            }
    
    def __repr__(self) -> str:
        total = sum(len(m) for m in self._cache.values())
        return f"MemoryManager(memories={total}, ids={len(self._cache)})"

    def __del__(self):
        """实例被销毁时调用"""
        total_memories = sum(len(m) for m in self._cache.values())
        logger.info(f"[MemoryManager销毁] 总记忆数:{total_memories} 对话ID数:{len(self._cache)}")


# ==================== 兼容旧接口 ====================

class BaseMemory(MemoryManager):
    """
    兼容旧版本的BaseMemory
    
    直接继承MemoryManager，保持API兼容
    """
    pass
