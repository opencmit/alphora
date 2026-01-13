"""
记忆单元模块

定义记忆的基本数据结构，支持：
- 记忆强度和衰减
- 重要性评分
- 标签和元数据
- 访问统计
"""

from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field, asdict
import time
import uuid
import json
import re
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"
    EPISODIC = "episodic"
    REFLECTION = "reflection"  # 反思/摘要记忆


@dataclass
class MemoryUnit:
    """
    记忆单元
    
    存储单条记忆的所有相关信息。
    
    属性:
        content: 记忆内容，格式为 {"role": "...", "content": "..."}
        unique_id: 唯一标识符
        timestamp: 创建时间戳
        score: 记忆强度 (0-1)，会随时间衰减
        importance: 重要性 (0-1)，由LLM或规则评估
        tags: 标签列表，用于关键词检索
        metadata: 额外元数据
        memory_type: 记忆类型
        access_count: 访问次数
        last_accessed: 最后访问时间
        parent_id: 父记忆ID（用于关联）
        summary_of: 如果是摘要，记录源记忆ID列表
    """
    
    # 核心属性
    content: Dict[str, str]
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    # 强度和重要性
    score: float = 1.0
    importance: float = 0.5
    
    # 检索相关
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 类型和状态
    memory_type: MemoryType = MemoryType.SHORT_TERM
    
    # 访问统计
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    # 关联
    parent_id: Optional[str] = None
    summary_of: List[str] = field(default_factory=list)
    
    def decay(self, decay_factor: float) -> float:
        """
        衰减记忆强度
        
        Args:
            decay_factor: 衰减系数，范围 (0, 1)，越接近 0，衰减越快
            
        Returns:
            衰减后的分数
        """
        self.score *= decay_factor
        self.score = max(self.score, 0.0)
        return self.score
    
    def reinforce(self, increment: float = 0.1) -> float:
        """
        增强记忆强度
        
        Args:
            increment: 增加的分值
            
        Returns:
            增强后的分数
        """
        self.score = min(self.score + increment, 1.0)
        return self.score
    
    def access(self) -> None:
        """记录一次访问"""
        self.access_count += 1
        self.last_accessed = time.time()
        # 访问会略微增强记忆
        self.reinforce(0.02)
    
    def add_tag(self, tag: str) -> None:
        """添加标签"""
        tag = tag.lower().strip()
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def add_tags(self, tags: List[str]) -> None:
        """批量添加标签"""
        for tag in tags:
            self.add_tag(tag)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        return tag.lower().strip() in self.tags
    
    def get_role(self) -> str:
        """获取角色"""
        return self.content.get("role", "unknown")
    
    def get_content_text(self) -> str:
        """获取内容文本"""
        return self.content.get("content", "")
    
    def get_age(self) -> float:
        """获取记忆年龄（秒）"""
        return time.time() - self.timestamp
    
    def get_recency_score(self, half_life: float = 86400) -> float:
        """
        获取新近度分数
        
        Args:
            half_life: 半衰期（秒），默认1天
            
        Returns:
            新近度分数 (0-1)
        """
        age = self.get_age()
        return 0.5 ** (age / half_life)
    
    def get_composite_score(
        self,
        score_weight: float = 0.4,
        importance_weight: float = 0.3,
        recency_weight: float = 0.3
    ) -> float:
        """
        获取综合评分
        
        Args:
            score_weight: 强度权重
            importance_weight: 重要性权重
            recency_weight: 新近度权重
            
        Returns:
            综合评分 (0-1)
        """
        recency = self.get_recency_score()
        return (
            score_weight * self.score +
            importance_weight * self.importance +
            recency_weight * recency
        )
    
    def formatted_timestamp(self, include_second: bool = True) -> str:
        """
        返回格式化后的时间字符串
        
        Args:
            include_second: 是否包含秒
            
        Returns:
            格式化的时间，例如 '2025-01-24 15:30:45'
        """
        fmt = '%Y-%m-%d %H:%M:%S' if include_second else '%Y-%m-%d %H:%M'
        return time.strftime(fmt, time.localtime(self.timestamp))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['memory_type'] = self.memory_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryUnit':
        """从字典创建"""
        if 'memory_type' in data and isinstance(data['memory_type'], str):
            data['memory_type'] = MemoryType(data['memory_type'])
        return cls(**data)
    
    def to_message_format(self) -> Dict[str, str]:
        """转换为LLM消息格式"""
        return {
            "role": self.get_role(),
            "content": self.get_content_text()
        }
    
    def __repr__(self) -> str:
        return (
            f"MemoryUnit(id={self.unique_id[:8]}..., "
            f"role={self.get_role()}, "
            f"score={self.score:.2f}, "
            f"importance={self.importance:.2f})"
        )
    
    def __str__(self) -> str:
        content_preview = self.get_content_text()[:50]
        if len(self.get_content_text()) > 50:
            content_preview += "..."
        return (
            f"MemoryUnit:\n"
            f"  ID: {self.unique_id}\n"
            f"  Role: {self.get_role()}\n"
            f"  Content: {content_preview}\n"
            f"  Score: {self.score:.2f}\n"
            f"  Importance: {self.importance:.2f}\n"
            f"  Tags: {self.tags}\n"
            f"  Timestamp: {self.formatted_timestamp()}\n"
        )


# ==================== 工具函数 ====================

def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    从文本提取关键词（简单实现）
    
    Args:
        text: 输入文本
        top_n: 返回的关键词数量
        
    Returns:
        关键词列表
    """
    # 简单的关键词提取：分词 + 去停用词 + 词频统计
    # 如需更精准，可接入 jieba
    
    # 停用词列表
    stop_words = {
        # 中文
        '的', '了', '是', '我', '你', '他', '她', '它', '们', '这', '那',
        '有', '在', '不', '和', '与', '或', '但', '如果', '因为', '所以',
        '什么', '怎么', '为什么', '哪', '哪里', '哪个', '谁', '多少',
        '就', '都', '也', '还', '又', '再', '很', '太', '非常', '可以',
        '能', '会', '要', '想', '让', '给', '把', '被', '从', '到', '对',
        # 英文
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when',
        'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 's', 't', 'just', 'don',
        'now', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'you',
        'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they',
        'them', 'their', 'what', 'which', 'who', 'whom', 'this', 'that',
        'these', 'those', 'am', 'and', 'but', 'if', 'or', 'because',
    }
    
    # 分词（简单按空格和标点分割）
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text.lower())
    
    # 过滤停用词和短词
    words = [w for w in words if w not in stop_words and len(w) > 1]
    
    # 词频统计
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # 按频率排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    return [word for word, _ in sorted_words[:top_n]]


def create_memory(
    role: str,
    content: str,
    importance: float = 0.5,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    memory_type: MemoryType = MemoryType.SHORT_TERM,
    auto_extract_tags: bool = True
) -> MemoryUnit:
    """
    创建记忆单元的便捷函数
    
    Args:
        role: 角色 (user/assistant/system)
        content: 内容
        importance: 重要性
        tags: 标签列表
        metadata: 元数据
        memory_type: 记忆类型
        auto_extract_tags: 是否自动提取关键词作为标签
        
    Returns:
        MemoryUnit实例
    """
    try:
        content = str(content)
    except UnicodeEncodeError:
        raise ValueError(f'记忆的内容无法变成文字')

    memory = MemoryUnit(
        content={"role": role, "content": content},
        importance=importance,
        tags=tags or [],
        metadata=metadata or {},
        memory_type=memory_type
    )
    
    if auto_extract_tags:
        keywords = extract_keywords(content, top_n=5)
        memory.add_tags(keywords)
    
    return memory
