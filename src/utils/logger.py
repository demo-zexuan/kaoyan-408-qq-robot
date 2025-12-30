"""
日志模块

提供统一的日志记录功能，基于loguru实现。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from src.utils.config import get_config


# ==============================================================================
# (2) 日志配置
# ==============================================================================


class LoggerConfig:
    """日志配置类

    配置loguru日志系统的各项参数。
    """

    # I. 初始化
    def __init__(self) -> None:
        """初始化日志配置"""
        self.config = get_config()
        self._setup_logger()

    # II. 配置日志
    def _setup_logger(self) -> None:
        """设置日志系统"""
        # 移除默认处理器
        logger.remove()

        # I. 添加控制台处理器
        self._add_console_handler()

        # II. 添加文件处理器
        self._add_file_handler()

    # III. 控制台处理器
    def _add_console_handler(self) -> None:
        """添加控制台日志处理器"""
        format_template = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

        logger.add(
            sys.stderr,
            format=format_template,
            level=self.config.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # IV. 文件处理器
    def _add_file_handler(self) -> None:
        """添加文件日志处理器"""
        log_file = Path(self.config.log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # 普通日志格式
        format_template = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

        logger.add(
            log_file,
            format=format_template,
            level=self.config.log_level,
            rotation=self._parse_rotation(),
            retention=self.config.log_backup_count,
            compression="zip",
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )

    # V. 辅助方法
    @staticmethod
    def _parse_rotation() -> str | int:
        """解析日志轮转配置"""
        # 格式: "10MB" -> "10 MB"
        # 这里直接返回字符串，loguru会自动解析
        return "10 MB"


# =============================================================================
# (3) 日志获取函数
# ==============================================================================


def get_logger(name: Optional[str] = None) -> any:
    """获取logger实例

    Args:
        name: logger名称，通常使用__name__

    Returns:
        loguru logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger


# =============================================================================
# (4) 初始化日志系统
# =============================================================================

# 初始化日志配置
_logger_config = LoggerConfig()

# 导出logger实例
__all__ = ["logger", "get_logger"]
