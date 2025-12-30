"""
QQ机器人配置加载模块（Legacy）

保留以兼容旧代码。
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_qq_robot_config(config_path: str | None = None) -> dict[str, Any]:
    """加载QQ机器人配置

    Args:
        config_path: 配置文件路径，默认为pyproject.toml

    Returns:
        dict[str, Any]: 配置字典
    """
    if config_path is None:
        # 默认使用项目根目录的pyproject.toml
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "pyproject.toml"

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # 提取kaoyan-408-qa-robot配置节
    robot_config = config.get("kaoyan-408-qa-robot", {})
    return robot_config
