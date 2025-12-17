from typing import Optional, List, Dict, Any
import time
import uuid


class MemoryUnit:
    def __init__(self,
                 content: Dict,
                 score: float = 1.0,
                 timestamp: float = None,
                 metadata: Optional[Dict] = None,
                 unique_id: Optional[str] = None):
        """
        Args:
            content (dict): 记忆内容，例如 {"input": "hello", "output": "i am fine"}
            score (float): 记忆的强度，初始值为 1.0
            timestamp()
            metadata (Optional[Dict]): 额外的元数据
        """
        self.content: dict = content
        self.score = score
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.metadata = metadata or {}

        self.unique_id = unique_id or str(uuid.uuid4())  # 自动生成唯一标识符

    def decay(self, decay_factor: float):
        """
        衰减记忆强度。
        Args:
            decay_factor (float): 衰减系数，范围 (0, 1)，越接近 0，衰减越快。
        """
        self.score *= decay_factor
        self.score = max(self.score, 0.0)  # 确保不低于 0

    def reinforce(self, increment: float):
        """
        增强记忆强度。
        Args:
            increment (float): 增加的分值，范围 [0, 1]。
        """
        self.score = min(self.score + increment, 1.0)  # 确保不超过 1.0

    def formatted_timestamp(self, include_second: bool = True) -> str:
        """
        返回格式化后的时间字符串。
        Returns:
            str: 格式化的时间，例如 '2025-01-24 15:30:45'。
        """
        if include_second:
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))
        else:
            return time.strftime('%Y-%m-%d %H:%M', time.localtime(self.timestamp))

    def __repr__(self) -> str:
        return (f"MemoryUnit(id={self.unique_id}, content={self.content}, score={self.score:.2f}, "
                f"timestamp={self.formatted_timestamp()}, metadata={self.metadata})")

    def __str__(self) -> str:
        """
        返回易读的字符串表示。
        """
        return (f"MemoryUnit:\n"
                f"  ID: {self.unique_id}\n"
                f"  Content: {self.content}\n"
                f"  Score: {self.score:.2f}\n"
                f"  Timestamp: {self.formatted_timestamp()}\n"
                f"  Metadata: {self.metadata}\n")
