"""
天气服务模块

提供天气查询服务。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime
from typing import Optional

from httpx import AsyncClient, HTTPStatusError, RequestError
from pydantic import validate_call

from src.utils.config import get_config
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 天气数据模型
# =============================================================================


class WeatherData:
    """天气数据模型"""

    def __init__(
        self,
        location: str,
        temperature: float,
        description: str,
        humidity: Optional[int] = None,
        wind_speed: Optional[float] = None,
        forecast: Optional[list[dict]] = None,
    ) -> None:
        """初始化天气数据

        Args:
            location: 地点名称
            temperature: 温度（摄氏度）
            description: 天气描述
            humidity: 湿度（百分比）
            wind_speed: 风速（km/h）
            forecast: 未来天气预报
        """
        self.location = location
        self.temperature = temperature
        self.description = description
        self.humidity = humidity
        self.wind_speed = wind_speed
        self.forecast = forecast or []

    def format_text(self) -> str:
        """格式化为文本

        Returns:
            格式化的天气文本
        """
        lines = [
            f"📍 {self.location}天气",
            f"🌡️ 温度: {self.temperature}°C",
            f"☁️ {self.description}",
        ]

        if self.humidity is not None:
            lines.append(f"💧 湿度: {self.humidity}%")

        if self.wind_speed is not None:
            lines.append(f"🌬️ 风速: {self.wind_speed} km/h")

        if self.forecast:
            lines.append("\n📅 未来天气:")
            for f in self.forecast[:3]:  # 只显示前3天
                date = f.get("date", "")
                temp = f.get("temperature", "")
                desc = f.get("description", "")
                lines.append(f"  {date}: {temp}°C, {desc}")

        return "\n".join(lines)


# =============================================================================
# (4) 天气服务
# =============================================================================


class WeatherService:
    """天气查询服务

    提供天气查询功能，支持多种天气API。

    主要功能：
    - 查询实时天气
    - 查询天气预报
    - 解析地点信息
    """

    # I. 初始化
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ) -> None:
        """初始化天气服务

        Args:
            api_key: API密钥
            api_url: API地址
        """
        config = get_config()

        self.api_key = api_key or config.weather_api_key
        self.api_url = api_url or config.weather_api_url

        self._client: Optional[AsyncClient] = None

        if not self.api_key:
            logger.warning("Weather API key not configured")

        logger.info("WeatherService initialized")

    # II. 客户端管理
    def _get_client(self) -> AsyncClient:
        """获取或创建HTTP客户端

        Returns:
            AsyncClient实例
        """
        if self._client is None:
            self._client = AsyncClient(timeout=10.0)
        return self._client

    # III. 天气查询
    @validate_call
    async def get_weather(
        self,
        location: str,
        days: int = 1,
    ) -> Optional[WeatherData]:
        """获取天气信息

        Args:
            location: 地点名称
            days: 预报天数（1-7天）

        Returns:
            天气数据对象，失败返回None
        """
        if not self.api_key:
            logger.warning("Weather API key not configured")
            return None

        try:
            # 这里使用通用的API调用格式
            # 实际使用时需要根据具体的天气API调整
            data = await self._call_weather_api(location, days)

            if data:
                weather = self._parse_weather_data(data, location)
                logger.info(f"Weather data retrieved for {location}")
                return weather

            return None

        except Exception as e:
            logger.error(f"Get weather error for {location}: {e}")
            return None

    @validate_call
    async def get_weather_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        days: int = 1,
    ) -> Optional[WeatherData]:
        """通过坐标获取天气

        Args:
            latitude: 纬度
            longitude: 经度
            days: 预报天数

        Returns:
            天气数据对象
        """
        if not self.api_key:
            return None

        try:
            data = await self._call_weather_api_by_coords(
                latitude, longitude, days
            )

            if data:
                location = data.get("name", f"{latitude},{longitude}")
                weather = self._parse_weather_data(data, location)
                return weather

            return None

        except Exception as e:
            logger.error(f"Get weather by coords error: {e}")
            return None

    # IV. 地点解析
    @validate_call
    async def parse_location(self, text: str) -> Optional[str]:
        """从文本中解析地点

        Args:
            text: 输入文本

        Returns:
            地点名称，未找到返回None
        """
        import re

        # 常见天气查询模式
        patterns = [
            r"([^，。！？\s]{2,6})(的天气|天气怎么样|天气|气温)",
            r"查询([^，。！？\s]{2,6})",
            r"([^，。！？\s]{2,6})天气",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1)
                logger.debug(f"Extracted location: {location}")
                return location

        # 如果没有匹配，尝试提取所有可能的地点名
        # 这里可以接入NLP服务进行更准确的识别
        return None

    # V. API调用
    async def _call_weather_api(
        self,
        location: str,
        days: int,
    ) -> Optional[dict]:
        """调用天气API

        Args:
            location: 地点
            days: 天数

        Returns:
            API响应数据
        """
        client = self._get_client()

        # 这里是一个示例实现
        # 实际使用时需要根据具体的天气API调整参数
        # 支持的API包括：OpenWeatherMap、和风天气、高德天气等

        # 使用免费的wttr.in API作为示例（不需要key）
        # 实际生产环境建议使用付费API
        url = f"https://wttr.in/{location}?format=j1"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            return data

        except HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return None
        except RequestError as e:
            logger.error(f"Request error: {e}")
            return None

    async def _call_weather_api_by_coords(
        self,
        latitude: float,
        longitude: float,
        days: int,
    ) -> Optional[dict]:
        """通过坐标调用天气API

        Args:
            latitude: 纬度
            longitude: 经度
            days: 天数

        Returns:
            API响应数据
        """
        client = self._get_client()

        url = f"https://wttr.in/{latitude},{longitude}?format=j1"

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            return data

        except Exception as e:
            logger.error(f"Weather API error by coords: {e}")
            return None

    # VI. 数据解析
    @staticmethod
    def _parse_weather_data(
            data: dict,
        location: str,
    ) -> Optional[WeatherData]:
        """解析天气API数据

        Args:
            data: API返回数据
            location: 地点名称

        Returns:
            天气数据对象
        """
        try:
            # wttr.in API格式
            current = data.get("current_condition", [{}])[0]

            temperature = float(current.get("temp_C", 0))
            description = current.get("weatherDesc", [{}])[0].get("value", "未知")
            humidity = int(current.get("humidity", 0))
            wind_speed = float(current.get("windspeedKmph", 0))

            # 解析预报
            forecast = []
            for day_data in data.get("weather", [])[:7]:
                forecast.append({
                    "date": day_data.get("date", ""),
                    "temperature": f"{day_data.get('maxtempC', '')}/{day_data.get('mintempC', '')}",
                    "description": day_data.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value", ""),
                })

            return WeatherData(
                location=location,
                temperature=temperature,
                description=description,
                humidity=humidity,
                wind_speed=wind_speed,
                forecast=forecast,
            )

        except Exception as e:
            logger.error(f"Parse weather data error: {e}")
            return None

    # VII. 辅助方法
    async def format_response(
        self,
        location: str,
        days: int = 1,
    ) -> str:
        """获取格式化的天气响应

        Args:
            location: 地点
            days: 天数

        Returns:
            格式化的天气文本
        """
        weather = await self.get_weather(location, days)

        if not weather:
            return f"抱歉，无法获取 {location} 的天气信息。"

        return weather.format_text()

    async def close(self) -> None:
        """关闭服务，释放资源"""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("WeatherService closed")


# =============================================================================
# (5) 单例实例
# =============================================================================

_default_weather_service: Optional[WeatherService] = None


def get_weather_service(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
) -> WeatherService:
    """获取默认天气服务实例

    Args:
        api_key: API密钥
        api_url: API地址

    Returns:
        WeatherService实例
    """
    global _default_weather_service
    if _default_weather_service is None:
        _default_weather_service = WeatherService(api_key, api_url)
    return _default_weather_service


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    "WeatherService",
    "WeatherData",
    "get_weather_service",
]
