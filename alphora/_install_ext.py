"""
alphora_pri 扩展自动安装

在 alphora 首次 import 时自动检测平台，从 alphora/extension/ 安装对应的 alphora_pri-*.whl
"""

import sys
import os
import platform
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_wheels_dir() -> Path:
    return Path(__file__).resolve().parent / "extension"


def _find_matching_wheel(wheels_dir: Path):
    if not wheels_dir.is_dir():
        return None

    whl_files = list(wheels_dir.glob("alphora_pri-*.whl"))
    if not whl_files:
        return None

    ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
    system = platform.system().lower()
    machine = platform.machine().lower()

    arch_map = {
        "arm64": ["arm64", "aarch64"],
        "aarch64": ["arm64", "aarch64"],
        "x86_64": ["x86_64", "amd64"],
        "amd64": ["x86_64", "amd64"],
    }
    arch_keywords = arch_map.get(machine, [machine])

    os_map = {
        "darwin": ["macosx"],
        "linux": ["linux", "manylinux"],
        "windows": ["win"],
    }
    os_keywords = os_map.get(system, [system])

    for whl in whl_files:
        name = whl.name
        if (ver in name
                and any(kw in name for kw in arch_keywords)
                and any(kw in name for kw in os_keywords)):
            return whl

    return None


def ensure_ext_installed():
    try:
        import alphora_pri
        return
    except ImportError:
        pass

    wheels_dir = _get_wheels_dir()
    if not wheels_dir.is_dir():
        return

    whl = _find_matching_wheel(wheels_dir)
    if whl is None:
        ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
        machine = platform.machine().lower()
        system = platform.system().lower()
        available = [f.name for f in wheels_dir.glob("*.whl")]
        logger.warning(
            f"[alphora] 未找到匹配的 alphora_pri wheel。\n"
            f"  当前环境: Python {ver}, {system}, {machine}\n"
            f"  可用: {available}"
        )
        return

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", str(whl), "--quiet", "--no-deps"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        logger.warning(f"[alphora] alphora_pri 自动安装失败: {e}\n  请手动安装: pip install {whl}")


def ensure_license_from_env() -> None:
    """若设置环境变量 ALPHORA_LICENSE，则在 import alphora 时自动调用 alphora_pri.activate。

    仅在变量非空时生效；激活失败会记录日志并抛出异常（便于错误配置尽早暴露）。
    若未安装 alphora_pri，则记录警告并跳过（与未设置该变量时行为一致，由后续 guard 决定）。
    """
    raw = os.environ.get("ALPHORA_LICENSE", "")
    if not raw or not raw.strip():
        return
    key = raw.strip()
    try:
        import alphora_pri
    except ImportError:
        logger.warning(
            "[alphora] 已设置 ALPHORA_LICENSE，但当前环境无法 import alphora_pri，跳过激活。"
        )
        return
    try:
        alphora_pri.activate(key)
    except Exception as e:
        logger.error("[alphora] ALPHORA_LICENSE 激活失败: %s", e)
        raise

