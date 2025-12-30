"""
配置管理模块

该模块提供统一的配置管理功能，从环境变量和配置文件中加载应用配置。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils.path_config import ROOT_DIR


# ==============================================================================
# (2) 配置常量
# ==============================================================================

class Config:
    """配置常量类

    存储运行时不改变的配置常量。
    """

    # 项目根目录
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

    # 资源目录
    RESOURCE_DIR: Path = PROJECT_ROOT / "resource"
    ROLES_DIR: Path = RESOURCE_DIR / "roles"
    PROMPTS_DIR: Path = RESOURCE_DIR / "prompts"
    KNOWLEDGE_DIR: Path = RESOURCE_DIR / "knowledge"

    # 数据目录
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_DIR: Path = DATA_DIR / "db"

    # 日志目录
    LOG_DIR: Path = PROJECT_ROOT / "logs"

    @classmethod
    def ensure_directories(cls) -> None:
        """确保所有必要的目录存在"""
        for directory in [
            cls.RESOURCE_DIR,
            cls.ROLES_DIR,
            cls.PROMPTS_DIR,
            cls.KNOWLEDGE_DIR,
            cls.DATA_DIR,
            cls.DB_DIR,
            cls.LOG_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# (3) 基础配置类
# ==============================================================================

class BaseConfig(BaseSettings):
    """基础配置类

    提供配置加载的基础功能，支持从环境变量和.env文件加载配置。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ==============================================================================
# (4) 应用配置类
# ==============================================================================

class AppConfig(BaseConfig):
    """应用配置

    包含应用运行所需的所有配置项，各配置项通过环境变量提供默认值。
    """

    # --------------------------------------------------------------------------
    # I. 基础配置
    # --------------------------------------------------------------------------
    environment: Literal["dev", "prod"] = Field(
        default="dev",
        description="运行环境"
    )
    debug: bool = Field(
        default=False,
        description="调试模式"
    )
    tz: str = Field(
        default="Asia/Shanghai",
        description="时区"
    )

    # --------------------------------------------------------------------------
    # II. NoneBot配置
    # --------------------------------------------------------------------------
    host: str = Field(
        default="127.0.0.1",
        description="监听地址"
    )
    port: int = Field(
        default=8080,
        description="监听端口",
        ge=1,
        le=65535
    )
    command_start: list[str] = Field(
        default=["/"],
        description="命令起始符"
    )
    command_sep: list[str] = Field(
        default=["."],
        description="命令分隔符"
    )

    # --------------------------------------------------------------------------
    # III. NapCat连接配置
    # --------------------------------------------------------------------------
    onebot_ws_urls: list[str] = Field(
        default=["ws://127.0.0.1:3001"],
        description="OneBot WebSocket地址列表"
    )
    onebot_v12_access_token: Optional[str] = Field(
        default=None,
        description="OneBot V12访问令牌"
    )

    # --------------------------------------------------------------------------
    # IV. LLM配置
    # --------------------------------------------------------------------------
    llm_api_key: Optional[str] = Field(
        default=None,
        description="LLM API密钥"
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="LLM API基础URL"
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="LLM模型名称"
    )
    llm_max_tokens: int = Field(
        default=2000,
        description="单次请求最大Token数",
        ge=1,
        le=128000
    )
    llm_temperature: float = Field(
        default=0.7,
        description="LLM温度参数",
        ge=0.0,
        le=2.0
    )

    # --------------------------------------------------------------------------
    # V. 天气API配置
    # --------------------------------------------------------------------------
    weather_api_key: Optional[str] = Field(
        default=None,
        description="天气API密钥（可选，使用免费API时不需要）"
    )
    weather_api_url: str = Field(
        default="https://wttr.in",
        description="天气API地址"
    )

    # --------------------------------------------------------------------------
    # VI. Redis配置
    # --------------------------------------------------------------------------
    redis_host: str = Field(
        default="127.0.0.1",
        description="Redis主机地址"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis端口",
        ge=1,
        le=65535
    )
    redis_db: int = Field(
        default=0,
        description="Redis数据库编号",
        ge=0,
        le=15
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis密码"
    )
    redis_max_connections: int = Field(
        default=10,
        description="Redis最大连接数",
        ge=1
    )

    # --------------------------------------------------------------------------
    # VI. 数据库配置
    # --------------------------------------------------------------------------
    database_url: str = Field(
        default=f"sqlite:///{ROOT_DIR}/data/db/kaoyan_408.db",
        description="数据库连接URL"
    )

    # --------------------------------------------------------------------------
    # VII. Token控制配置
    # --------------------------------------------------------------------------
    default_user_quota: int = Field(
        default=50000,
        description="默认用户Token配额",
        ge=0
    )
    daily_token_limit: int = Field(
        default=5000,
        description="每日Token限制",
        ge=0
    )
    minute_rate_limit: int = Field(
        default=200,
        description="每分钟请求限制",
        ge=1
    )

    # --------------------------------------------------------------------------
    # VIII. 上下文配置
    # --------------------------------------------------------------------------
    context_expire_hours: int = Field(
        default=24,
        description="上下文过期时间(小时)",
        ge=1
    )
    max_context_per_user: int = Field(
        default=10,
        description="每用户最大上下文数",
        ge=1
    )
    max_messages_per_context: int = Field(
        default=200,
        description="每上下文最大消息数",
        ge=1
    )

    # --------------------------------------------------------------------------
    # IX. 封禁配置
    # --------------------------------------------------------------------------
    ban_minute_request_limit: int = Field(
        default=50,
        description="每分钟最大请求数(超过则触发封禁检查)",
        ge=1
    )
    ban_repeat_message_limit: int = Field(
        default=10,
        description="重复消息阈值(10秒内)",
        ge=1
    )
    ban_single_request_token_limit: int = Field(
        default=5000,
        description="单次请求最大Token数",
        ge=1
    )
    temp_ban_duration_short: int = Field(
        default=300,
        description="短期封禁时长(秒)",
        ge=1
    )
    temp_ban_duration_medium: int = Field(
        default=1800,
        description="中期封禁时长(秒)",
        ge=1
    )
    temp_ban_duration_long: int = Field(
        default=86400,
        description="长期封禁时长(秒)",
        ge=1
    )

    # --------------------------------------------------------------------------
    # X. 日志配置
    # --------------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="日志级别"
    )
    log_file: str = Field(
        default="./logs/robot.log",
        description="日志文件路径"
    )
    log_rotation_size: str = Field(
        default="10MB",
        description="日志轮转大小"
    )
    log_backup_count: int = Field(
        default=5,
        description="日志备份数量",
        ge=0
    )

    # --------------------------------------------------------------------------
    # XI. 验证器
    # --------------------------------------------------------------------------
    @field_validator("log_file", "database_url")
    @classmethod
    def ensure_directory_exists(cls, v: str) -> str:
        """确保配置的路径所在目录存在"""
        path = Path(v)
        if path.suffix:  # 是文件路径
            parent = path.parent
        else:  # 是目录路径
            parent = path
        parent.mkdir(parents=True, exist_ok=True)
        return v


# ==============================================================================
# (5) 配置单例
# ==============================================================================

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取配置单例

    Returns:
        AppConfig: 应用配置实例

    Examples:
        >>> config = get_config()
        >>> print(config.llm_model)
        'gpt-4o'
    """
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置

    主要用于测试或配置热更新场景。

    Returns:
        AppConfig: 新的配置实例
    """
    global _config
    _config = AppConfig()
    return _config


# 初始化目录
Config.ensure_directories()
