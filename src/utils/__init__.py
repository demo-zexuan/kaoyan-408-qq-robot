"""
工具模块初始化

提供配置管理、日志记录和辅助函数。
"""

# Legacy imports
from .load_qq_robot_config import load_qq_robot_config

# New imports
from .config import AppConfig, Config, get_config, reload_config
from .helpers import (
    DatetimeHelper,
    EntityHelper,
    IDHelper,
    TextHelper,
)
from .logger import logger
from .path_config import get_resource_path

__all__ = [
    # Legacy
    "load_qq_robot_config",
    # Config
    "AppConfig",
    "Config",
    "get_config",
    "reload_config",
    # Logger
    "logger",
    # Helpers
    "TextHelper",
    "IDHelper",
    "EntityHelper",
    "DatetimeHelper",
    # Legacy
    "get_resource_path",
]
