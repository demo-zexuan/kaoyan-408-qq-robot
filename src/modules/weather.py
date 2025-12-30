"""
天气模块

提供天气查询功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from typing import Optional

from pydantic import validate_call

from src.service import WeatherService, get_weather_service
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 天气模块
# =============================================================================


class WeatherModule:
    """天气查询模块

    提供天气查询功能，集成天气服务。

    主要功能：
    - 处理天气查询请求
    - 解析地点信息
    - 获取天气数据
    - 格式化响应
    """

    # I. 初始化
    def __init__(
        self,
        weather_service: Optional[WeatherService] = None,
    ) -> None:
        """初始化天气模块

        Args:
            weather_service: 天气服务实例
        """
        self.weather_service = weather_service or get_weather_service()

        logger.info("WeatherModule initialized")

    # II. 天气查询
    @validate_call
    async def handle(
        self,
        query: str,
        days: int = 1,
    ) -> str:
        """处理天气查询请求

        Args:
            query: 查询文本（包含地点信息）
            days: 预报天数（1-7天）

        Returns:
            格式化的天气信息
        """
        # 解析地点
        location = await self.weather_service.parse_location(query)

        if not location:
            return "抱歉，我没有识别到您要查询的地点。请告诉我您想查询哪个城市的天气？"

        # 获取天气
        return await self.weather_service.format_response(location, days)

    @validate_call
    async def get_weather(
        self,
        location: str,
        days: int = 1,
    ) -> str:
        """直接获取天气信息

        Args:
            location: 地点名称
            days: 预报天数

        Returns:
            格式化的天气信息
        """
        return await self.weather_service.format_response(location, days)

    @validate_call
    async def get_weather_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        days: int = 1,
    ) -> str:
        """通过坐标获取天气

        Args:
            latitude: 纬度
            longitude: 经度
            days: 预报天数

        Returns:
            格式化的天气信息
        """
        weather = await self.weather_service.get_weather_by_coordinates(
            latitude,
            longitude,
            days,
        )

        if not weather:
            return "抱歉，无法获取该位置的天气信息。"

        return weather.format_text()

    # III. 地点解析
    @validate_call
    async def parse_location(self, text: str) -> Optional[str]:
        """解析文本中的地点

        Args:
            text: 输入文本

        Returns:
            地点名称，未找到返回None
        """
        return await self.weather_service.parse_location(text)

    # IV. 帮助信息
    def get_help(self) -> str:
        """获取帮助信息

        Returns:
            使用帮助文本
        """
        return """🌤️ 天气查询帮助

使用方法：
- "北京天气怎么样？"
- "上海明天天气"
- "查询广州未来三天天气"

支持的功能：
- 查询实时天气
- 查询未来7天天气预报
- 自动识别地点信息"""


# =============================================================================
# (5) 单例实例
# =============================================================================

_default_weather_module: Optional[WeatherModule] = None


def get_weather_module(
    weather_service: Optional[WeatherService] = None,
) -> WeatherModule:
    """获取默认天气模块实例

    Args:
        weather_service: 天气服务实例

    Returns:
        WeatherModule实例
    """
    global _default_weather_module
    if _default_weather_module is None:
        _default_weather_module = WeatherModule(weather_service)
    return _default_weather_module


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    "WeatherModule",
    "get_weather_module",
]
