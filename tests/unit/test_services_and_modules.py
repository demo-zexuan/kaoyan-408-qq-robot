"""
服务和模块单元测试

测试LLM服务、天气服务和各功能模块。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.context import ContextManager
from src.service import LLMService, WeatherService, get_llm_service, get_weather_service
from src.storage import (
    CacheManager,
    ChatMessage,
    Context,
    ContextStatus,
    ContextType,
    DatabaseManager,
    MessageRole,
    TokenQuota,
    User,
)
from src.storage.orm_models import Base


# =============================================================================
# (2) 测试配置
# =============================================================================

@pytest.fixture
async def db_manager():
    """数据库管理器测试夹具"""
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.connect()
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.disconnect()


@pytest.fixture
def mock_cache_manager():
    """缓存管理器模拟对象"""
    manager = MagicMock(spec=CacheManager)
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    # 添加context属性（模拟CacheManager的子属性）
    from src.storage.cache import ContextCache
    manager.context = MagicMock(spec=ContextCache)
    # 让cache.get返回None，以便fallback到数据库
    manager.context.get = AsyncMock(return_value=None)
    return manager


@pytest.fixture
async def context_manager(db_manager, mock_cache_manager):
    """上下文管理器测试夹具"""
    return ContextManager(db_manager, mock_cache_manager)


# =============================================================================
# (3) LLMService 测试
# =============================================================================

@pytest.mark.asyncio
class TestLLMService:
    """LLMService测试类"""

    def test_init(self):
        """测试初始化"""
        service = LLMService(
            api_key="test_key",
            base_url="https://test.com",
            model="test_model",
        )

        assert service.api_key == "test_key"
        assert service.base_url == "https://test.com"
        assert service.model == "test_model"

    def test_estimate_tokens(self):
        """测试Token估算"""
        service = LLMService()

        # 中文文本
        chinese_tokens = service.estimate_tokens("你好世界")
        assert chinese_tokens == 5  # 4个中文 + 1

        # 英文文本
        english_tokens = service.estimate_tokens("Hello world")
        # 11字符 / 4 = 2 (向下取整) + 1 = 3
        assert english_tokens >= 2

        # 混合文本
        mixed_tokens = service.estimate_tokens("Hello世界")
        assert mixed_tokens >= 3  # 2中文 + 5英文/4 + 1

    def test_estimate_messages_tokens(self):
        """测试消息列表Token估算"""
        service = LLMService()

        messages = [
            ChatMessage(
                message_id="1",
                sender_id="user1",
                sender_name="User",
                role=MessageRole.USER,
                content="你好",
            ),
            ChatMessage(
                message_id="2",
                sender_id="assistant",
                sender_name="Assistant",
                role=MessageRole.ASSISTANT,
                content="Hello",
            ),
        ]

        tokens = service.estimate_messages_tokens(messages)
        # "你好" = 2, "Hello" = 2, 4元数据开销 = 4, 总计 ≈ 8
        assert tokens > 0


@pytest.mark.asyncio
class TestWeatherService:
    """WeatherService测试类"""

    def test_init(self):
        """测试初始化"""
        service = WeatherService(
            api_key="test_key",
            api_url="https://test.weather.com",
        )

        assert service.api_key == "test_key"
        assert service.api_url == "https://test.weather.com"

    @pytest.mark.asyncio
    async def test_parse_location(self):
        """测试地点解析"""
        service = WeatherService()

        # 测试各种查询格式
        result1 = await service.parse_location("北京天气怎么样")
        assert "北京" in result1 or result1 == "北京"

        result2 = await service.parse_location("查询上海天气")
        assert "上海" in result2 or result2 == "上海"

        result3 = await service.parse_location("广州天气")
        assert "广州" in result3 or result3 == "广州"

        result4 = await service.parse_location("随便说点什么")
        assert result4 is None


@pytest.mark.asyncio
class TestChatModule:
    """ChatModule测试类"""

    async def test_handle(self, context_manager):
        """测试处理对话请求"""
        from src.modules import ChatModule

        # 使用mock的LLM服务
        with patch('src.modules.chat.get_llm_service') as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value="测试回复")
            mock_get_llm.return_value = mock_llm

            module = ChatModule(
                llm_service=mock_llm,
                context_manager=context_manager,
            )

            # 创建测试上下文
            context = await context_manager.create_context(
                context_type=ContextType.PRIVATE,
                creator_id="test_user",
                name="测试上下文",
                participants=["test_user"],
            )

            response = await module.handle(
                user_message="你好",
                context=context,
                user_id="test_user",
            )

            assert response == "测试回复"
            mock_llm.chat.assert_called_once()

    async def test_set_system_prompt(self, context_manager):
        """测试设置系统提示词"""
        from src.modules import ChatModule

        module = ChatModule(context_manager=context_manager)

        new_prompt = "你是一个测试助手"
        module.set_system_prompt(new_prompt)

        assert module.system_prompt == new_prompt

    async def test_clear_system_prompt(self, context_manager):
        """测试清除系统提示词"""
        from src.modules import ChatModule, DEFAULT_SYSTEM_PROMPT

        module = ChatModule(context_manager=context_manager)

        module.set_system_prompt("自定义提示词")
        module.clear_system_prompt()

        assert module.system_prompt == DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
class TestWeatherModule:
    """WeatherModule测试类"""

    async def test_handle(self):
        """测试处理天气查询"""
        from src.modules import WeatherModule

        # 使用mock的天气服务
        with patch('src.modules.weather.get_weather_service') as mock_get_weather:
            mock_weather = MagicMock()
            mock_weather.parse_location = AsyncMock(return_value="北京")
            mock_weather.format_response = AsyncMock(return_value="北京天气: 晴")
            mock_get_weather.return_value = mock_weather

            module = WeatherModule(weather_service=mock_weather)

            response = await module.handle("北京天气怎么样")

            assert "北京" in response
            mock_weather.parse_location.assert_called_once()
            mock_weather.format_response.assert_called_once()

    async def test_get_help(self):
        """测试获取帮助信息"""
        from src.modules import WeatherModule

        module = WeatherModule()
        help_text = module.get_help()

        assert "天气查询" in help_text
        assert "使用方法" in help_text


@pytest.mark.asyncio
class TestRolePlayModule:
    """RolePlayModule测试类"""

    async def test_get_default_role(self, context_manager, db_manager):
        """测试获取默认角色"""
        from src.modules import RolePlayModule, DEFAULT_ROLES

        module = RolePlayModule(
            context_manager=context_manager,
            db_manager=db_manager,
        )

        # 测试获取默认角色
        role = await module.get_role("assistant")

        assert role is not None
        assert role.role_id == "assistant"
        assert role.name == "助手"

    async def test_list_roles(self, context_manager, db_manager):
        """测试列出角色"""
        from src.modules import RolePlayModule

        module = RolePlayModule(
            context_manager=context_manager,
            db_manager=db_manager,
        )

        roles = await module.list_roles()

        assert len(roles) >= 3  # 至少有3个默认角色

        role_ids = {r.role_id for r in roles}
        assert "assistant" in role_ids
        assert "teacher" in role_ids
        assert "humorous" in role_ids


@pytest.mark.asyncio
class TestContextCommandModule:
    """ContextCommandModule测试类"""

    async def test_cmd_create_context(
        self,
        context_manager,
        db_manager,
    ):
        """测试创建上下文命令"""
        from src.managers import UserManager
        from src.modules import ContextCommandModule

        user_manager = UserManager(db_manager, MagicMock(), context_manager)
        module = ContextCommandModule(
            context_manager=context_manager,
            user_manager=user_manager,
        )

        result = await module.cmd_create_context(
            user_id="test_user",
            user_name="测试用户",
            context_name="测试上下文",
        )

        assert "创建成功" in result
        assert "测试上下文" in result

    async def test_get_help(self):
        """测试获取帮助信息"""
        from src.modules import ContextCommandModule

        module = ContextCommandModule()
        help_text = module.get_help()

        assert "上下文管理" in help_text
        assert "命令" in help_text


# =============================================================================
# (4) 集成测试
# =============================================================================

@pytest.mark.asyncio
class TestIntegration:
    """集成测试类"""

    async def test_chat_flow(
        self,
        db_manager,
        context_manager,
    ):
        """测试完整的对话流程"""
        from src.managers import UserManager, TokenController
        from src.modules import ChatModule

        # 准备依赖
        mock_cache = MagicMock(spec=CacheManager)
        # 添加user和token属性（模拟CacheManager的子属性）
        from src.storage.cache import UserCache, TokenCache
        mock_cache.user = MagicMock(spec=UserCache)
        mock_cache.token = MagicMock(spec=TokenCache)
        user_manager = UserManager(db_manager, mock_cache, context_manager)
        token_controller = TokenController(db_manager, mock_cache)

        # 创建用户和配额
        user = await user_manager.create_user(
            user_id="integration_test",
            nickname="测试用户",
        )

        # 创建上下文
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id=user.user_id,
            name="集成测试",
            participants=[user.user_id],
        )
        context_id = context.context_id

        # Mock LLM服务
        with patch('src.modules.chat.get_llm_service') as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value="这是一个测试回复")
            mock_get_llm.return_value = mock_llm

            chat_module = ChatModule(
                llm_service=mock_llm,
                context_manager=context_manager,
            )

            # 重新获取上下文以确保与数据库同步
            context = await context_manager.get_context(context_id)

            # 进行对话
            response = await chat_module.handle(
                user_message="测试消息",
                context=context,
                user_id=user.user_id,
            )

            assert response == "这是一个测试回复"

            # 检查消息是否保存 - 重新获取上下文以从数据库加载消息
            updated_context = await context_manager.get_context(context_id)
            messages = await context_manager.get_messages(context_id)
            assert len(messages) >= 2  # 至少包含用户消息和AI回复
