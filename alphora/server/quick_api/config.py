from dataclasses import dataclass
from typing import Optional, Type


@dataclass
class APIPublisherConfig:
    """API发布器配置类"""
    path: str = "/alphadata"
    memory_ttl: int = 3600          # 记忆过期时间（秒）
    max_memory_items: int = 1000        # 记忆池最大容量
    auto_clean_interval: int = 600          # 自动清理间隔（秒）
    sandbox_workspace: Optional[str] = None  # 沙箱宿主机工作目录，设置后自动启用文件服务
    api_title: Optional[str] = None
    api_description: Optional[str] = None

    def __post_init__(self):
        if self.api_title is None:
            self.api_title = "Alphaora Agent API Service"
        if self.api_description is None:
            self.api_description = "Auto-generated API for Alphaora Agent (per-request new instance)"

