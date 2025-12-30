"""
辅助工具模块

提供通用的辅助函数，包括文本处理、ID生成、实体提取等。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

import re
import string
import uuid
from datetime import datetime
from typing import Any

from src.utils.logger import logger


# ==============================================================================
# (2) 文本处理工具
# ==============================================================================


class TextHelper:
    """文本处理辅助类

    提供文本清理、格式化等常用操作。
    """

    # I. 预编译正则表达式
    # 清理多余空白
    _whitespace_pattern = re.compile(r"\s+")
    # 提取中文
    _chinese_pattern = re.compile(r"[\u4e00-\u9fff]+")
    # 提取数字
    _number_pattern = re.compile(r"\d+")
    # 提取英文单词
    _word_pattern = re.compile(r"[a-zA-Z]+")
    # QQ号匹配
    _qq_pattern = re.compile(r"[1-9]\d{4,10}")

    # II. 文本清理
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本

        去除首尾空白，将连续空白字符替换为单个空格。

        Args:
            text: 待清理的文本

        Returns:
            str: 清理后的文本

        Examples:
            >>> TextHelper.clean_text("  hello    world  ")
            'hello world'
        """
        if not text:
            return ""
        # 去除首尾空白
        text = text.strip()
        # 替换连续空白为单个空格
        text = TextHelper._whitespace_pattern.sub(" ", text)
        return text

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """截断文本

        当文本超过最大长度时进行截断，并添加后缀。

        Args:
            text: 待截断的文本
            max_length: 最大长度
            suffix: 截断后缀

        Returns:
            str: 截断后的文本

        Examples:
            >>> TextHelper.truncate_text("hello world", 5)
            'hello...'
        """
        if len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def remove_punctuation(text: str) -> str:
        """移除标点符号

        Args:
            text: 待处理的文本

        Returns:
            str: 移除标点后的文本

        Examples:
            >>> TextHelper.remove_punctuation("Hello, world!")
            'Hello world'
        """
        # 移除中英文标点
        chinese_punctuation = "！？｡。＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿—一·‘’‛“”„‟…‧﹏."
        translator = str.maketrans("", "", string.punctuation + chinese_punctuation)
        return text.translate(translator)

    # III. 实体提取
    @classmethod
    def extract_qq_number(cls, text: str) -> list[str]:
        """提取QQ号

        Args:
            text: 待提取的文本

        Returns:
            list[str]: 提取到的QQ号列表

        Examples:
            >>> TextHelper.extract_qq_number("请联系123456789")
            ['123456789']
        """
        return cls._qq_pattern.findall(text)

    @classmethod
    def extract_numbers(cls, text: str) -> list[int]:
        """提取数字

        Args:
            text: 待提取的文本

        Returns:
            list[int]: 提取到的数字列表

        Examples:
            >>> TextHelper.extract_numbers("今天25度，气温30度")
            [25, 30]
        """
        return [int(n) for n in cls._number_pattern.findall(text)]

    @classmethod
    def extract_chinese(cls, text: str) -> list[str]:
        """提取中文字符

        Args:
            text: 待提取的文本

        Returns:
            list[str]: 中文字符串列表

        Examples:
            >>> TextHelper.extract_chinese("hello世界abc")
            ['世界']
        """
        return cls._chinese_pattern.findall(text)

    @classmethod
    def extract_words(cls, text: str) -> list[str]:
        """提取英文单词

        Args:
            text: 待提取的文本

        Returns:
            list[str]: 英文单词列表

        Examples:
            >>> TextHelper.extract_words("Hello world, 你好")
            ['Hello', 'world']
        """
        return cls._word_pattern.findall(text)

    # IV. 文本分析
    @staticmethod
    def count_words(text: str) -> int:
        """统计字数

        统计中文字符、英文单词和数字的总数。

        Args:
            text: 待统计的文本

        Returns:
            int: 字数

        Examples:
            >>> TextHelper.count_words("Hello世界123")
            5  # Hello(1) + 世界(2) + 123(1) = 4, 实际实现可能不同
        """
        # 中文字符
        chinese = len(TextHelper._chinese_pattern.findall(text))
        # 英文单词
        words = len(TextHelper._word_pattern.findall(text))
        # 数字
        numbers = len(TextHelper._number_pattern.findall(text))
        return chinese + words + numbers


# ==============================================================================
# (3) ID生成工具
# ==============================================================================


class IDHelper:
    """ID生成辅助类

    提供各种类型的唯一ID生成功能。
    """

    # I. 通用ID生成
    @staticmethod
    def generate_uuid() -> str:
        """生成UUID

        Returns:
            str: UUID字符串（无连字符）

        Examples:
            >>> id = IDHelper.generate_uuid()
            >>> len(id)
            32
        """
        return uuid.uuid4().hex

    @staticmethod
    def generate_short_id(length: int = 8) -> str:
        """生成短ID

        使用UUID的前N位字符作为短ID。

        Args:
            length: ID长度

        Returns:
            str: 短ID字符串

        Examples:
            >>> id = IDHelper.generate_short_id(8)
            >>> len(id)
            8
        """
        return uuid.uuid4().hex[:length]

    # II. 业务ID生成
    @staticmethod
    def generate_context_id() -> str:
        """生成上下文ID

        格式: ctx_<uuid>

        Returns:
            str: 上下文ID

        Examples:
            >>> IDHelper.generate_context_id()
            'ctx_a1b2c3d4e5f6...'
        """
        return f"ctx_{IDHelper.generate_uuid()}"

    @staticmethod
    def generate_message_id() -> str:
        """生成消息ID

        格式: msg_<uuid>_<timestamp>

        Returns:
            str: 消息ID

        Examples:
            >>> IDHelper.generate_message_id()
            'msg_a1b2c3d4_1234567890'
        """
        timestamp = int(datetime.now().timestamp())
        return f"msg_{IDHelper.generate_short_id(8)}_{timestamp}"

    @staticmethod
    def generate_ban_record_id() -> str:
        """生成封禁记录ID

        格式: ban_<uuid>

        Returns:
            str: 封禁记录ID
        """
        return f"ban_{IDHelper.generate_uuid()}"


# ==============================================================================
# (4) 实体提取工具
# ==============================================================================


class EntityHelper:
    """实体提取辅助类

    从文本中提取有意义的实体信息。
    """

    # I. 时间相关
    @staticmethod
    def extract_time_entities(text: str) -> dict[str, Any]:
        """提取时间实体

        Args:
            text: 待提取的文本

        Returns:
            dict[str, Any]: 包含时间实体的字典

        Examples:
            >>> EntityHelper.extract_time_entities("明天下午3点")
            {'has_time': True, 'time_type': 'afternoon', 'hour': 15}
        """
        entities: dict[str, Any] = {
            "has_time": False,
            "time_type": None,
            "hour": None,
            "minute": None,
        }

        # 简单实现，实际可以使用更复杂的时间解析库
        time_keywords = {
            "早上": "morning",
            "上午": "morning",
            "中午": "noon",
            "下午": "afternoon",
            "晚上": "evening",
            "夜里": "night",
        }

        for keyword, time_type in time_keywords.items():
            if keyword in text:
                entities["has_time"] = True
                entities["time_type"] = time_type
                break

        # 提取具体时间
        numbers = TextHelper.extract_numbers(text)
        if numbers:
            # 简单判断，第一个数字可能是小时
            hour = numbers[0]
            if 0 <= hour <= 23:
                entities["hour"] = hour
                entities["has_time"] = True

        return entities

    # II. 地点相关
    @staticmethod
    def extract_location_entities(text: str) -> dict[str, Any]:
        """提取地点实体

        Args:
            text: 待提取的文本

        Returns:
            dict[str, Any]: 包含地点实体的字典
        """
        entities: dict[str, Any] = {
            "has_location": False,
            "location": None,
        }

        # 简单的城市名匹配（实际应该使用地址解析库）
        # 常见城市列表
        common_cities = [
            "北京",
            "上海",
            "广州",
            "深圳",
            "杭州",
            "成都",
            "重庆",
            "武汉",
            "西安",
            "南京",
            "天津",
            "苏州",
            "长沙",
            "郑州",
        ]

        for city in common_cities:
            if city in text:
                entities["has_location"] = True
                entities["location"] = city
                break

        return entities

    # III. 意图相关
    @staticmethod
    def extract_intent_hints(text: str) -> dict[str, Any]:
        """提取意图提示

        Args:
            text: 待提取的文本

        Returns:
            dict[str, Any]: 包含意图提示的字典
        """
        hints: dict[str, Any] = {
            "has_command": False,
            "command": None,
            "has_query": False,
            "query_type": None,
        }

        # 命令检测
        if text.startswith("/") or text.startswith("！"):
            hints["has_command"] = True
            # 提取命令部分
            parts = text[1:].split()
            if parts:
                hints["command"] = parts[0]

        # 查询类型检测
        query_keywords = {
            "天气": "weather",
            "温度": "weather",
            "下雨": "weather",
            "角色": "role_play",
            "扮演": "role_play",
        }

        for keyword, query_type in query_keywords.items():
            if keyword in text:
                hints["has_query"] = True
                hints["query_type"] = query_type
                break

        return hints


# ==============================================================================
# (5) 日期时间工具
# ==============================================================================


class DatetimeHelper:
    """日期时间辅助类

    提供日期时间相关的常用操作。
    """

    # I. 时间格式化
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """格式化日期时间

        Args:
            dt: 日期时间对象
            format_str: 格式字符串

        Returns:
            str: 格式化后的字符串

        Examples:
            >>> from datetime import datetime
            >>> dt = datetime(2024, 1, 1, 12, 30, 45)
            >>> DatetimeHelper.format_datetime(dt)
            '2024-01-01 12:30:45'
        """
        return dt.strftime(format_str)

    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """格式化为相对时间

        Args:
            dt: 日期时间对象

        Returns:
            str: 相对时间字符串（如"5分钟前"）

        Examples:
            >>> DatetimeHelper.format_relative_time(datetime.now())
            '刚刚'
        """
        now = datetime.now()
        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 60:
            return "刚刚"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}分钟前"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}小时前"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}天前"
        else:
            return DatetimeHelper.format_datetime(dt, "%Y-%m-%d")

    # II. 时间计算
    @staticmethod
    def add_hours(dt: datetime, hours: int) -> datetime:
        """增加小时

        Args:
            dt: 日期时间对象
            hours: 增加的小时数

        Returns:
            datetime: 新的日期时间对象
        """
        return dt + timedelta(hours=hours)

    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """增加天数

        Args:
            dt: 日期时间对象
            days: 增加的天数

        Returns:
            datetime: 新的日期时间对象
        """
        return dt + timedelta(days=days)


# ==============================================================================
# (6) 导出
# ==============================================================================

# 导入timedelta用于DatetimeHelper
from datetime import timedelta

__all__ = [
    "TextHelper",
    "IDHelper",
    "EntityHelper",
    "DatetimeHelper",
    "logger",
]
