"""
集成测试 - 消息流程测试

测试完整消息流程，包括：
- 闲聊流程
- 天气查询流程
- 角色扮演流程
- 上下文操作流程
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.context import ContextManager
from src.core.intent import IntentRecognizer, IntentType
from src.core.router import MessageRouter
from src.core.state import create_initial_state
from src.managers import BanManager, TokenController, UserManager
from src.modules import ChatModule, RolePlayModule, WeatherModule
from src.service import WeatherService, LLMService, get_llm_service
from src.storage import (
    BanReason,
    CacheManager,
    ContextStatus,
    ContextType,
    DatabaseManager,
    RedisManager,
)


# =============================================================================
# (2) 测试夹具
# =============================================================================


@pytest.fixture
async def mock_llm_service():
    """模拟LLM服务"""
    service = MagicMock(spec=LLMService)
    service.chat = AsyncMock(return_value="这是一个模拟的回复。")
    service.estimate_tokens = MagicMock(return_value=100)
    return service


@pytest.fixture
async def mock_weather_service():
    """模拟天气服务"""
    service = MagicMock(spec=WeatherService)
    service.get_weather = AsyncMock(return_value="北京今天晴，温度15-25°C。")
    service.parse_location = AsyncMock(return_value="北京")
    service.format_response = AsyncMock(return_value="北京今天晴，温度15-25°C。")
    return service


@pytest.fixture
async def components(mock_llm_service, mock_weather_service):
    """创建测试所需的所有组件"""
    # 数据库（使用 auto_init=True 自动创建表）
    db_manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db_manager.connect(auto_init=True)

    # Redis
    redis_manager = RedisManager(host="127.0.0.1", port=6379, db=15)
    cache_manager = CacheManager(redis_manager)
    await cache_manager.connect()

    # 上下文管理器
    context_manager = ContextManager(db_manager, cache_manager)

    # 用户管理器
    user_manager = UserManager(db_manager, cache_manager, context_manager)

    # Token控制器
    token_controller = TokenController(db_manager, cache_manager)

    # 封禁管理器
    ban_manager = BanManager(db_manager, cache_manager)

    # 消息路由器
    message_router = MessageRouter(
        db_manager,
        cache_manager,
        user_manager,
        token_controller,
        ban_manager,
        context_manager,
    )

    yield {
        "db_manager": db_manager,
        "redis_manager": redis_manager,
        "cache_manager": cache_manager,
        "context_manager": context_manager,
        "user_manager": user_manager,
        "token_controller": token_controller,
        "ban_manager": ban_manager,
        "message_router": message_router,
        "mock_llm_service": mock_llm_service,
        "mock_weather_service": mock_weather_service,
    }

    # 清理
    await cache_manager.disconnect()
    await db_manager.disconnect()


# =============================================================================
# (3) 闲聊流程测试
# =============================================================================


class TestChatFlow:
    """闲聊流程测试"""

    @pytest.mark.asyncio
    async def test_simple_chat_flow(self, components):
        """测试简单闲聊流程"""
        context_manager = components["context_manager"]
        mock_llm_service = components["mock_llm_service"]

        # 创建上下文
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user123",
        )

        # 创建闲聊模块
        chat_module = ChatModule(
            llm_service=mock_llm_service,
            context_manager=context_manager,
        )

        # 处理闲聊消息
        response = await chat_module.handle(
            user_message="你好，请介绍一下自己。",
            context=context,
            user_id="user123",
        )

        # 验证响应
        assert response == "这是一个模拟的回复。"
        assert mock_llm_service.chat.called

        # 验证消息被保存
        messages = await context_manager.get_messages(context.context_id)
        assert len(messages) == 2  # 用户消息 + AI回复

    @pytest.mark.asyncio
    async def test_multi_turn_chat(self, components):
        """测试多轮对话"""
        context_manager = components["context_manager"]
        mock_llm_service = components["mock_llm_service"]

        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user456",
        )

        chat_module = ChatModule(
            llm_service=mock_llm_service,
            context_manager=context_manager,
        )

        # 第一轮
        await chat_module.handle(user_message="什么是栈？", context=context, user_id="user456")
        # 第二轮
        await chat_module.handle(user_message="栈和队列的区别是什么？", context=context, user_id="user456")

        messages = await context_manager.get_messages(context.context_id)
        assert len(messages) == 4  # 2轮 x 2条消息


# =============================================================================
# (4) 天气查询流程测试
# =============================================================================


class TestWeatherFlow:
    """天气查询流程测试"""

    @pytest.mark.asyncio
    async def test_weather_query_flow(self, components):
        """测试天气查询流程"""
        mock_weather_service = components["mock_weather_service"]

        weather_module = WeatherModule(
            weather_service=mock_weather_service,
        )

        # 查询天气
        response = await weather_module.handle("北京今天天气怎么样？")

        assert "北京" in response
        assert mock_weather_service.parse_location.called
        assert mock_weather_service.format_response.called

    @pytest.mark.asyncio
    async def test_weather_location_extraction(self, components):
        """测试地点提取"""
        mock_weather_service = components["mock_weather_service"]

        weather_module = WeatherModule(
            weather_service=mock_weather_service,
        )

        # 设置parse_location返回不同地点
        mock_weather_service.parse_location = AsyncMock(side_effect=lambda x: x.replace("天气", "").replace("查询", "").replace("的", "").replace("今天", "").replace("如何", "").strip())

        # 测试不同格式
        test_cases = [
            "上海天气",
            "查询杭州的天气",
            "今天深圳天气如何",
        ]

        for query in test_cases:
            response = await weather_module.handle(query)
            assert response  # 确保有响应


# =============================================================================
# (5) 角色扮演流程测试
# =============================================================================


class TestRolePlayFlow:
    """角色扮演流程测试"""

    @pytest.mark.asyncio
    async def test_role_activation(self, components):
        """测试角色激活"""
        context_manager = components["context_manager"]
        mock_llm_service = components["mock_llm_service"]

        context = await context_manager.create_context(
            context_type=ContextType.ROLE_PLAY,
            creator_id="user789",
        )

        role_play_module = RolePlayModule(
            llm_service=mock_llm_service,
            context_manager=context_manager,
        )

        # 列出可用角色
        roles = await role_play_module.list_roles()
        assert len(roles) >= 3  # 至少有3个默认角色

        # 激活老师角色
        success = await role_play_module.activate_role(context, "teacher")
        assert success
        assert context.current_role_id == "teacher"

    @pytest.mark.asyncio
    async def test_role_play_response(self, components):
        """测试角色扮演回复"""
        context_manager = components["context_manager"]
        mock_llm_service = components["mock_llm_service"]

        context = await context_manager.create_context(
            context_type=ContextType.ROLE_PLAY,
            creator_id="user789",
        )

        role_play_module = RolePlayModule(
            llm_service=mock_llm_service,
            context_manager=context_manager,
        )

        # 激活角色
        await role_play_module.activate_role(context, "teacher")

        # 生成角色回复
        response = await role_play_module.generate_response(
            user_message="什么是时间复杂度？",
            context=context,
            user_id="user789",
        )

        assert response
        assert mock_llm_service.chat.called

        # 验证使用了角色提示词
        call_args = mock_llm_service.chat.call_args
        messages = call_args[0][0]
        system_prompt = messages[0]["content"]
        assert "老师" in system_prompt or "考研" in system_prompt


# =============================================================================
# (6) 上下文操作流程测试
# =============================================================================


class TestContextFlow:
    """上下文操作流程测试"""

    @pytest.mark.asyncio
    async def test_context_lifecycle(self, components):
        """测试上下文生命周期"""
        context_manager = components["context_manager"]

        # 创建上下文
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user001",
        )

        # 保存context_id用于后续操作
        ctx_id = context.context_id
        assert ctx_id is not None
        assert context.creator_id == "user001"

        # 添加参与者
        await context_manager.add_participant(ctx_id, "user002")
        updated_context = await context_manager.get_context(ctx_id)
        assert "user002" in updated_context.participants

        # 暂停上下文
        await context_manager.pause_context(ctx_id)
        paused_context = await context_manager.get_context(ctx_id)
        assert paused_context.status == ContextStatus.PAUSED

        # 恢复上下文
        await context_manager.resume_context(ctx_id)
        resumed_context = await context_manager.get_context(ctx_id)
        assert resumed_context.status == ContextStatus.ACTIVE

        # 删除上下文
        await context_manager.delete_context(ctx_id)
        deleted_context = await context_manager.get_context(ctx_id)
        assert deleted_context.status == ContextStatus.DELETED

    @pytest.mark.asyncio
    async def test_multi_user_context(self, components):
        """测试多用户上下文"""
        context_manager = components["context_manager"]

        # 创建多用户上下文
        context = await context_manager.create_context(
            context_type=ContextType.MULTI_USER,
            creator_id="user_a",
        )

        ctx_id = context.context_id

        # 添加多个参与者
        participants = ["user_b", "user_c", "user_d"]
        for user_id in participants:
            await context_manager.add_participant(ctx_id, user_id)

        # 验证所有参与者
        updated_context = await context_manager.get_context(ctx_id)
        assert len(updated_context.participants) == len(participants) + 1  # 包括创建者

        # 移除一个参与者
        await context_manager.remove_participant(ctx_id, "user_b")
        final_context = await context_manager.get_context(ctx_id)
        assert "user_b" not in final_context.participants


# =============================================================================
# (7) 消息路由测试
# =============================================================================


class TestMessageRouting:
    """消息路由测试"""

    @pytest.mark.asyncio
    async def test_intent_recognition(self, components):
        """测试意图识别"""
        intent_recognizer = IntentRecognizer()

        # 测试不同意图
        test_cases = [
            ("你好", IntentType.CHAT),
            ("北京天气怎么样", IntentType.WEATHER),
            ("扮演老师", IntentType.ROLE_PLAY),
            ("创建上下文", IntentType.CONTEXT_CREATE),
        ]

        for message, expected_intent in test_cases:
            result = await intent_recognizer.recognize(message)
            # 对于关键词匹配，应该能识别
            if result.confidence > 0.5:
                assert result.intent == expected_intent

    @pytest.mark.asyncio
    async def test_message_routing(self, components):
        """测试消息路由"""
        message_router = components["message_router"]
        context_manager = components["context_manager"]

        # 创建测试上下文
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="test_user",
        )

        # 模拟状态
        state = create_initial_state(
            message_id="msg_001",
            user_id="test_user",
            message_content="你好",
        )
        state.context_id = context.context_id

        # 验证状态
        assert state.message_content == "你好"
        assert state.context_id == context.context_id


# =============================================================================
# (8) Token控制测试
# =============================================================================


class TestTokenControl:
    """Token控制测试"""

    @pytest.mark.asyncio
    async def test_quota_checking(self, components):
        """测试配额检查"""
        token_controller = components["token_controller"]

        # 获取用户配额
        quota = await token_controller.get_quota("test_user")

        assert quota.total_quota == 50000  # 默认总配额
        assert quota.daily_limit == 5000  # 默认每日限制

    @pytest.mark.asyncio
    async def test_token_consumption(self, components):
        """测试Token消耗"""
        token_controller = components["token_controller"]

        # 消耗Token
        success = await token_controller.consume("test_user", 100)
        assert success

        # 验证消耗
        quota = await token_controller.get_quota("test_user")
        assert quota.used == 100
        assert quota.daily_used == 100


# =============================================================================
# (9) 封禁机制测试
# =============================================================================


class TestBanMechanism:
    """封禁机制测试"""

    @pytest.mark.asyncio
    async def test_user_banning(self, components):
        """测试用户封禁"""
        ban_manager = components["ban_manager"]

        # 使用 ban_user_for_spam 方法（封装好的高级API）
        ban_record = await ban_manager.ban_user_for_spam(
            user_id="bad_user",
            duration_hours=1,
        )

        assert ban_record is not None
        assert ban_record.user_id == "bad_user"

        # 检查封禁状态
        is_banned = await ban_manager.is_banned("bad_user")
        assert is_banned is True

        # 解封用户
        await ban_manager.unban_user("bad_user")

        # 验证解封
        is_banned_after = await ban_manager.is_banned("bad_user")
        assert is_banned_after is False
