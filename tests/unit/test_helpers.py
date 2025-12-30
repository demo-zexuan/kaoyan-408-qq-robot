"""
辅助工具模块单元测试

测试文本处理、ID生成、实体提取等辅助功能。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from datetime import datetime

import pytest

from src.utils.helpers import (
    DatetimeHelper,
    EntityHelper,
    IDHelper,
    TextHelper,
)


# ==============================================================================
# (2) TextHelper 测试
# ==============================================================================

class TestTextHelper:
    """文本处理辅助类测试"""

    def test_clean_text(self) -> None:
        """测试文本清理"""
        assert TextHelper.clean_text("  hello  world  ") == "hello world"
        assert TextHelper.clean_text("") == ""
        assert TextHelper.clean_text("hello\n\nworld") == "hello world"

    def test_truncate_text(self) -> None:
        """测试文本截断"""
        assert TextHelper.truncate_text("hello", 10) == "hello"
        assert TextHelper.truncate_text("hello world", 8) == "hello..."
        # 修正: "hello world"[:6] + "~~" = "hello w~~"
        assert TextHelper.truncate_text("hello world", 9, "~~") == "hello w~~"

    def test_remove_punctuation(self) -> None:
        """测试移除标点符号"""
        assert TextHelper.remove_punctuation("Hello, world!") == "Hello world"
        assert TextHelper.remove_punctuation("你好，世界！") == "你好世界"

    def test_extract_qq_number(self) -> None:
        """测试提取QQ号"""
        assert TextHelper.extract_qq_number("请联系123456789") == ["123456789"]
        assert set(TextHelper.extract_qq_number("123456789和987654321")) == {"123456789", "987654321"}
        assert TextHelper.extract_qq_number("没有号码") == []

    def test_extract_numbers(self) -> None:
        """测试提取数字"""
        assert TextHelper.extract_numbers("今天25度，气温30度") == [25, 30]

    def test_extract_chinese(self) -> None:
        """测试提取中文"""
        assert TextHelper.extract_chinese("Hello世界ABC") == ["世界"]

    def test_extract_words(self) -> None:
        """测试提取英文单词"""
        assert TextHelper.extract_words("Hello世界123World") == ["Hello", "World"]


# ==============================================================================
# (3) IDHelper 测试
# ==============================================================================

class TestIDHelper:
    """ID生成辅助类测试"""

    def test_generate_uuid(self) -> None:
        """测试生成UUID"""
        uuid = IDHelper.generate_uuid()
        assert len(uuid) == 32

        uuid2 = IDHelper.generate_uuid()
        assert uuid != uuid2

    def test_generate_short_id(self) -> None:
        """测试生成短ID"""
        short_id = IDHelper.generate_short_id(8)
        assert len(short_id) == 8

    def test_generate_context_id(self) -> None:
        """测试生成上下文ID"""
        context_id = IDHelper.generate_context_id()
        assert context_id.startswith("ctx_")
        assert len(context_id) > 4

    def test_generate_message_id(self) -> None:
        """测试生成消息ID"""
        message_id = IDHelper.generate_message_id()
        assert message_id.startswith("msg_")
        parts = message_id.split("_")
        assert len(parts) == 3

    def test_generate_ban_record_id(self) -> None:
        """测试生成封禁记录ID"""
        ban_id = IDHelper.generate_ban_record_id()
        assert ban_id.startswith("ban_")


# ==============================================================================
# (4) EntityHelper 测试
# ==============================================================================

class TestEntityHelper:
    """实体提取辅助类测试"""

    def test_extract_time_entities(self) -> None:
        """测试提取时间实体"""
        result = EntityHelper.extract_time_entities("明天下午3点")
        assert result["has_time"] is True
        assert result["time_type"] == "afternoon"

        result = EntityHelper.extract_time_entities("你好世界")
        assert result["has_time"] is False

    def test_extract_location_entities(self) -> None:
        """测试提取地点实体"""
        result = EntityHelper.extract_location_entities("北京天气怎么样")
        assert result["has_location"] is True
        assert result["location"] == "北京"

        result = EntityHelper.extract_location_entities("你好")
        assert result["has_location"] is False

    def test_extract_intent_hints(self) -> None:
        """测试提取意图提示"""
        result = EntityHelper.extract_intent_hints("/help")
        assert result["has_command"] is True
        assert result["command"] == "help"

        result = EntityHelper.extract_intent_hints("今天天气怎么样")
        assert result["has_query"] is True
        assert result["query_type"] == "weather"


# ==============================================================================
# (5) DatetimeHelper 测试
# ==============================================================================

class TestDatetimeHelper:
    """日期时间辅助类测试"""

    def test_format_datetime(self) -> None:
        """测试格式化日期时间"""
        dt = datetime(2024, 1, 1, 12, 30, 45)
        result = DatetimeHelper.format_datetime(dt)
        assert result == "2024-01-01 12:30:45"

    def test_format_relative_time(self) -> None:
        """测试格式化相对时间"""
        now = datetime.now()
        result = DatetimeHelper.format_relative_time(now)
        assert result == "刚刚"

    def test_add_hours(self) -> None:
        """测试增加小时"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = DatetimeHelper.add_hours(dt, 3)
        assert result.hour == 15

    def test_add_days(self) -> None:
        """测试增加天数"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = DatetimeHelper.add_days(dt, 7)
        assert result.day == 8
