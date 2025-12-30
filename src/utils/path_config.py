"""
路径配置模块

提供项目路径相关的配置和功能。
"""
from __future__ import annotations

import pathlib
import tomllib
from typing import Any

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = ROOT_DIR / 'pyproject.toml'

CONFIG_DATA: dict[str, Any] = {}
with open(CONFIG_FILE, 'rb') as f:
    config_data = tomllib.load(f)


def get_resource_path(relative_path: str = "") -> pathlib.Path:
    """获取资源文件路径

    Args:
        relative_path: 相对于resource目录的路径

    Returns:
        pathlib.Path: 资源文件的完整路径
    """
    resource_dir = ROOT_DIR / "resource"
    if relative_path:
        return resource_dir / relative_path
    return resource_dir

