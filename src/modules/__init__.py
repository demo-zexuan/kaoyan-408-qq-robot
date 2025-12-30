"""
功能模块初始化

导出所有功能模块的公共接口。
"""

# =============================================================================
# (1) 闲聊模块
# =============================================================================
from src.modules.chat import ChatModule, get_chat_module, DEFAULT_SYSTEM_PROMPT

# =============================================================================
# (2) 天气模块
# =============================================================================
from src.modules.weather import WeatherModule, get_weather_module

# =============================================================================
# (3) 角色扮演模块
# =============================================================================
from src.modules.role_play import RolePlayModule, get_role_play_module, DEFAULT_ROLES

# =============================================================================
# (4) 上下文命令模块
# =============================================================================
from src.modules.context_cmd import (
    ContextCommandModule,
    get_context_command_module,
)

# =============================================================================
# (5) 导出列表
# =============================================================================

__all__ = [
    # 闲聊模块
    "ChatModule",
    "get_chat_module",
    "DEFAULT_SYSTEM_PROMPT",
    # 天气模块
    "WeatherModule",
    "get_weather_module",
    # 角色扮演模块
    "RolePlayModule",
    "get_role_play_module",
    "DEFAULT_ROLES",
    # 上下文命令模块
    "ContextCommandModule",
    "get_context_command_module",
]
