import logging
import sys
from typing import Optional, Literal
from pathlib import Path

# 默认日志目录
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_LEVEL = "INFO"

# 确保日志目录存在
DEFAULT_LOG_DIR.mkdir(exist_ok=True)


def get_logger(
        name: str,
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = DEFAULT_LOG_LEVEL,
        log_to_file: bool = True,
        log_to_console: bool = True,
        json_format: bool = False,
) -> logging.Logger:
    """
    获取一个配置好的 logger 实例。

    Args:
        name (str): Logger 名称（通常用 __name__）
        level (str): 日志级别
        log_to_file (bool): 是否写入文件
        log_to_console (bool): 是否输出到控制台
        json_format (bool): 是否使用 JSON 格式（便于日志收集系统解析）

    Returns:
        logging.Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = _get_formatter(json_format)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_to_file:
        log_file = DEFAULT_LOG_DIR / f"{name.replace('.', '_')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 不传播到 root logger，避免重复输出
    logger.propagate = False

    return logger


def _get_formatter(json_format: bool) -> logging.Formatter:
    if json_format:
        import json

        class JSONFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_entry = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_entry, ensure_ascii=False)
        return JSONFormatter()
    else:
        log_format = "[%(asctime)s] %(levelname)-8s | %(name)-20s | %(funcName)-15s:%(lineno)d | %(message)s"
        return logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    logger = get_logger("test", level="DEBUG")
    logger.debug("This is a debug message.")
    logger.info("Model loaded successfully.")
    logger.warning("High temperature detected.")
    logger.error("API call failed.")