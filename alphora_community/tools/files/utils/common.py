"""
通用工具函数
"""
import os
import datetime
from typing import Optional, Dict, Any


def find_file(base_dir: str, file_name: str) -> Optional[str]:
    """
    查找文件，支持多种匹配方式

    查找优先级：
    1. 精确路径匹配
    2. 完全文件名匹配
    3. 忽略大小写匹配
    4. 包含匹配（文件名包含搜索词）

    Args:
        base_dir: 基础目录
        file_name: 要查找的文件名

    Returns:
        找到的文件完整路径，未找到返回 None
    """
    # 1. 精确匹配
    exact_path = os.path.join(base_dir, file_name)
    if os.path.exists(exact_path):
        return exact_path

    # 2. 遍历目录查找
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            # 完全匹配文件名
            if f == file_name:
                return os.path.join(root, f)
            # 忽略大小写匹配
            if f.lower() == file_name.lower():
                return os.path.join(root, f)
            # 包含匹配（文件名包含搜索词）
            if file_name.lower() in f.lower():
                return os.path.join(root, f)

    return None


def list_available_files(base_dir: str, max_files: int = 30) -> str:
    """
    列出目录中的可用文件

    Args:
        base_dir: 基础目录
        max_files: 最大显示文件数

    Returns:
        格式化的文件列表字符串
    """
    files = []
    for root, dirs, filenames in os.walk(base_dir):
        for f in filenames:
            if not f.startswith('.'):
                rel_path = os.path.relpath(os.path.join(root, f), base_dir)
                # 获取文件大小
                full_path = os.path.join(root, f)
                size = format_file_size(os.path.getsize(full_path))
                files.append(f"  - {rel_path} ({size})")

    if not files:
        return "  （目录为空）"

    result = '\n'.join(files[:max_files])
    if len(files) > max_files:
        result += f"\n  ... 还有 {len(files) - max_files} 个文件未显示"
    return result


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    获取文件基本信息

    Args:
        file_path: 文件路径

    Returns:
        包含文件信息的字典
    """
    stat = os.stat(file_path)
    return {
        'name': os.path.basename(file_path),
        'path': file_path,
        'size': stat.st_size,
        'size_human': format_file_size(stat.st_size),
        'modified': datetime.datetime.fromtimestamp(stat.st_mtime),
        'modified_str': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'extension': os.path.splitext(file_path)[1].lower(),
    }


def format_file_size(size_bytes: int) -> str:
    """
    将字节数转换为人类可读的格式

    Args:
        size_bytes: 字节数

    Returns:
        格式化的大小字符串（如 "1.5 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if size_bytes != int(size_bytes) else f"{int(size_bytes)} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def clean_text(text: str) -> str:
    """
    清洗文本，去除多余空白字符

    Args:
        text: 原始文本

    Returns:
        清洗后的文本
    """
    if text is None:
        return ""
    text = str(text).strip()
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    text = " ".join(text.split())
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_datetime(val) -> str:
    """
    格式化日期时间值

    Args:
        val: datetime 对象或时间对象

    Returns:
        格式化的字符串
    """
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S") if val.hour or val.minute or val.second else val.strftime("%Y-%m-%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, datetime.time):
        return val.strftime("%H:%M:%S")
    return str(val) if val is not None else ""
