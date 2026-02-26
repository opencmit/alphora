# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
内置钩子：运行检查点（Checkpoint）

在智能体每次迭代后自动保存检查点，支持：
- 断点续跑：从任意检查点恢复记忆，继续执行
- 中间结果调试：检查每一步的完整消息历史

使用 YAML 格式保存，自动将 JSON 工具返回值展开为原生 YAML 结构，
多行文本统一使用 literal block scalar（|），方便人工阅读。

注册到 AGENT_AFTER_ITERATION 事件，从 ctx.data 中获取 memory。

用法：
    # 保存检查点
    hooks = HookManager()
    hooks.register(
        HookEvent.AGENT_AFTER_ITERATION,
        make_checkpoint_saver(checkpoint_dir=".checkpoints"),
    )

    # 从检查点恢复并继续
    memory, meta = create_memory_from_checkpoint(
        ".checkpoints/checkpoint_iter_0005_20260226_143000.yaml"
    )
    agent = SkillAgent(llm=llm, memory=memory, ...)
    result = await agent.run("继续之前的任务")
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional, Tuple

import yaml

from alphora.hooks.context import HookContext
from alphora.memory import MemoryManager, Message

logger = logging.getLogger(__name__)

_JSON_CONTENT_TAG = "_content_was_json"


class _CheckpointDumper(yaml.Dumper):
    """Custom Dumper: multiline str -> literal block (|)"""
    pass


def _str_representer(dumper: yaml.Dumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style="|",
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_CheckpointDumper.add_representer(str, _str_representer)


def _expand_json_content(msg_dict: dict) -> dict:
    """
    若 content 是 JSON 字符串（dict / list），解析为原生结构并标记。
    这样 YAML 可以用块样式自然渲染嵌套字段中的多行文本。
    """
    content = msg_dict.get("content")
    if not content or not isinstance(content, str):
        return msg_dict

    stripped = content.strip()
    if not (stripped.startswith(("{", "["))):
        return msg_dict

    try:
        parsed = json.loads(content)
        if isinstance(parsed, (dict, list)):
            msg_dict["content"] = parsed
            msg_dict[_JSON_CONTENT_TAG] = True
    except (json.JSONDecodeError, ValueError):
        pass

    return msg_dict


def _collapse_json_content(msg_dict: dict) -> dict:
    """恢复时将原生结构重新编码为 JSON 字符串。"""
    if msg_dict.pop(_JSON_CONTENT_TAG, False):
        msg_dict["content"] = json.dumps(
            msg_dict["content"], ensure_ascii=False,
        )
    return msg_dict


def make_checkpoint_saver(
    checkpoint_dir: str = "checkpoints",
    every_n_iterations: int = 1,
    max_checkpoints: int = 0,
) -> Callable[[HookContext], None]:
    """
    创建检查点保存钩子，注册到 AGENT_AFTER_ITERATION。

    每隔 N 次迭代将完整的记忆状态保存为 YAML 文件，
    可用于断点续跑或中间调试。

    Args:
        checkpoint_dir: 检查点保存目录（相对路径或绝对路径）
        every_n_iterations: 每隔多少次迭代保存一次（默认每次都保存）
        max_checkpoints: 最多保留的检查点数量（0 表示不限制）

    Returns:
        hook 函数，注册到 AGENT_AFTER_ITERATION

    Example:
        hooks = HookManager()
        hooks.register(
            HookEvent.AGENT_AFTER_ITERATION,
            make_checkpoint_saver(
                checkpoint_dir=".checkpoints",
                every_n_iterations=1,
                max_checkpoints=20,
            ),
        )
    """
    dir_path = Path(checkpoint_dir).resolve()

    async def _hook(ctx: HookContext) -> None:
        memory: Optional[MemoryManager] = ctx.get("memory")
        iteration: int = ctx.get("iteration", 0)

        if not memory:
            return

        if every_n_iterations > 1 and iteration % every_n_iterations != 0:
            return

        dir_path.mkdir(parents=True, exist_ok=True)

        messages = memory.get_messages()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        msg_dicts = [_expand_json_content(m.to_dict()) for m in messages]

        checkpoint_data = {
            "version": 1,
            "iteration": iteration,
            "timestamp": ts,
            "message_count": len(messages),
            "messages": msg_dicts,
        }

        filename = f"checkpoint_iter_{iteration:04d}_{ts}.yaml"
        filepath = dir_path / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(
                    checkpoint_data,
                    f,
                    Dumper=_CheckpointDumper,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                    width=120,
                )
            logger.info(f"[checkpoint] Saved iteration {iteration} -> {filepath}")
        except Exception as e:
            logger.error(f"[checkpoint] Failed to save: {e}")
            return

        if max_checkpoints > 0:
            _cleanup_old_checkpoints(dir_path, max_checkpoints)

    return _hook


def _cleanup_old_checkpoints(checkpoint_dir: Path, max_keep: int) -> None:
    """删除多余的旧检查点，只保留最新的 max_keep 个"""
    files = sorted(
        checkpoint_dir.glob("checkpoint_iter_*.yaml"),
        key=lambda p: p.stat().st_mtime,
    )
    while len(files) > max_keep:
        oldest = files.pop(0)
        try:
            oldest.unlink()
            logger.debug(f"[checkpoint] Removed old checkpoint: {oldest.name}")
        except OSError:
            pass


def load_checkpoint(checkpoint_path: str) -> Dict[str, Any]:
    """
    加载检查点文件。

    Args:
        checkpoint_path: 检查点 YAML 文件路径

    Returns:
        检查点数据字典，包含:
        - version: 格式版本
        - iteration: 保存时的迭代次数
        - timestamp: 保存时间
        - message_count: 消息数量
        - messages: 消息列表（content 已还原为原始字符串）

    Raises:
        FileNotFoundError: 检查点文件不存在
        yaml.YAMLError: 文件格式错误
    """
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["messages"] = [
        _collapse_json_content(m) for m in data.get("messages", [])
    ]

    logger.info(
        f"[checkpoint] Loaded: iteration={data.get('iteration')}, "
        f"messages={data.get('message_count')}, "
        f"timestamp={data.get('timestamp')}"
    )
    return data


def restore_memory_from_checkpoint(
    checkpoint_path: str,
    memory: MemoryManager,
    session_id: str = "default",
) -> Dict[str, Any]:
    """
    从检查点恢复记忆状态。

    将检查点中的消息直接加载到 MemoryManager 中，
    替换指定 session 的全部消息。

    Args:
        checkpoint_path: 检查点文件路径
        memory: 要恢复到的 MemoryManager 实例
        session_id: 会话 ID

    Returns:
        检查点元数据（不含 messages 字段）

    Example:
        memory = MemoryManager()
        meta = restore_memory_from_checkpoint(
            ".checkpoints/checkpoint_iter_0005_20260226_143000.yaml",
            memory,
        )
        print(f"Restored from iteration {meta['iteration']}")
    """
    data = load_checkpoint(checkpoint_path)
    messages = [Message.from_dict(m) for m in data["messages"]]

    memory._cache[session_id] = messages

    meta = {k: v for k, v in data.items() if k != "messages"}
    logger.info(
        f"[checkpoint] Restored {len(messages)} messages "
        f"from iteration {data.get('iteration')} into session '{session_id}'"
    )
    return meta


def create_memory_from_checkpoint(
    checkpoint_path: str,
    session_id: str = "default",
    **memory_kwargs,
) -> Tuple[MemoryManager, Dict[str, Any]]:
    """
    从检查点创建新的 MemoryManager。

    便捷函数，等同于创建 MemoryManager 后调用 restore_memory_from_checkpoint。

    Args:
        checkpoint_path: 检查点文件路径
        session_id: 会话 ID
        **memory_kwargs: 传递给 MemoryManager 构造函数的参数

    Returns:
        (memory, meta) 元组:
        - memory: 已恢复状态的 MemoryManager
        - meta: 检查点元数据

    Example:
        memory, meta = create_memory_from_checkpoint(
            ".checkpoints/checkpoint_iter_0005_20260226_143000.yaml"
        )
        agent = SkillAgent(llm=llm, memory=memory, skill_paths=["./skills"])
        result = await agent.run("继续之前的任务")
    """
    memory = MemoryManager(**memory_kwargs)
    meta = restore_memory_from_checkpoint(checkpoint_path, memory, session_id)
    return memory, meta


def list_checkpoints(checkpoint_dir: str) -> List[Dict[str, Any]]:
    """
    列出目录中所有检查点的摘要信息。

    Args:
        checkpoint_dir: 检查点目录路径

    Returns:
        检查点摘要列表（按迭代次数排序），每项包含:
        - path: 文件路径
        - iteration: 迭代次数
        - timestamp: 保存时间
        - message_count: 消息数量
        - file_size: 文件大小（字节）

    Example:
        for ckpt in list_checkpoints(".checkpoints"):
            print(f"Iter {ckpt['iteration']} @ {ckpt['timestamp']} "
                  f"({ckpt['message_count']} msgs, {ckpt['file_size']} bytes)")
    """
    dir_path = Path(checkpoint_dir)
    if not dir_path.exists():
        return []

    summaries = []
    for fp in sorted(dir_path.glob("checkpoint_iter_*.yaml")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            summaries.append({
                "path": str(fp),
                "iteration": data.get("iteration"),
                "timestamp": data.get("timestamp"),
                "message_count": data.get("message_count"),
                "file_size": fp.stat().st_size,
            })
        except (yaml.YAMLError, OSError) as e:
            logger.warning(f"[checkpoint] Skipping invalid file {fp.name}: {e}")

    return summaries
