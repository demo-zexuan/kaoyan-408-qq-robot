"""
核心模块单元测试

测试状态定义、意图识别、上下文管理、LangGraph和消息路由功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
import asyncio
from datetime import datetime, timedelta

import pytest

from src.core.context import (
    ContextManager,
    DatabaseContextStorage,
    HybridContextStorage,
    RedisContextStorage,
)
from src.core.intent import IntentRecognizer, IntentRule
from src.core.langgraph import LangGraphManager
from src.core.router import MessageRouter
from src.core.state import (
    IntentResult,
    IntentType,
    MessageProcessingResult,
    ProcessingStage,
    RobotState,
    RouteTarget,
    clone_state,
    create_initial_state,
    is_terminal_state,
)
from src.storage import (
    CacheManager,
    ChatMessage,
    Context,
    ContextStatus,
    ContextType,
    DatabaseManager,
    MessageType,
    User,
    UserRepository,
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
async def cache_manager():
    """缓存管理器测试夹具"""
    # 使用内存Redis进行测试（需要redis-py mock或使用fakeredis）
    # 对于单元测试，我们创建一个简单的RedisManager
    from src.storage import RedisManager

    redis_manager = RedisManager(
        host="127.0.0.1",
        port=6379,
        db=15,  # 使用单独的测试数据库
    )
    cache = CacheManager(redis_manager)
    try:
        await cache.connect()
        yield cache
    finally:
        await cache.disconnect()


@pytest.fixture
async def context_manager(db_manager, cache_manager):
    """上下文管理器测试夹具"""
    return ContextManager(db_manager, cache_manager)


@pytest.fixture
async def message_router(db_manager, cache_manager, context_manager):
    """消息路由器测试夹具"""
    from src.managers import UserManager, TokenController, BanManager
    user_manager = UserManager(db_manager, cache_manager, context_manager)
    token_controller = TokenController(db_manager, cache_manager)
    ban_manager = BanManager(db_manager, cache_manager)
    return MessageRouter(
        db_manager,
        cache_manager,
        user_manager,
        token_controller,
        ban_manager,
        context_manager,
    )


# =============================================================================
# (3) 状态模型测试
# =============================================================================

class TestRobotState:
    """RobotState模型测试类"""

    def test_create_state(self) -> None:
        """测试创建状态"""
        state = RobotState(
            message_id="msg_test001",
            user_id="123456",
            message_content="你好",
        )

        assert state.message_id == "msg_test001"
        assert state.user_id == "123456"
        assert state.message_content == "你好"
        assert state.intent == IntentType.UNKNOWN
        assert state.processing_stage == ProcessingStage.RECEIVED

    def test_state_with_updates(self) -> None:
        """测试状态更新"""
        state = RobotState(
            message_id="msg_test002",
            user_id="123456",
            message_content="天气怎么样",
        )

        state.intent = IntentType.WEATHER
        state.intent_confidence = 0.9
        state.processing_stage = ProcessingStage.PROCESSING

        assert state.intent == IntentType.WEATHER
        assert state.intent_confidence == 0.9
        assert state.processing_stage == ProcessingStage.PROCESSING


class TestStateHelpers:
    """状态工具函数测试类"""

    def test_create_initial_state(self) -> None:
        """测试创建初始状态"""
        state = create_initial_state(
            message_id="msg_001",
            user_id="user_123",
            message_content="测试消息",
            user_name="测试用户",
            group_id="group_456",
        )

        assert state.message_id == "msg_001"
        assert state.user_id == "user_123"
        assert state.message_content == "测试消息"
        assert state.user_name == "测试用户"
        assert state.group_id == "group_456"
        assert state.processing_stage == ProcessingStage.RECEIVED

    def test_clone_state(self) -> None:
        """测试克隆状态"""
        original = RobotState(
            message_id="msg_001",
            user_id="user_123",
            message_content="原始消息",
        )
        original.intent = IntentType.WEATHER

        cloned = clone_state(original, message_content="更新后的消息")

        assert cloned.message_id == original.message_id
        assert cloned.message_content == "更新后的消息"
        assert cloned.intent == IntentType.WEATHER
        # 验证updated_at被更新
        assert cloned.updated_at >= original.updated_at

    def test_is_terminal_state(self) -> None:
        """测试终止状态判断"""
        completed_state = RobotState(
            message_id="msg_001",
            user_id="user_123",
            message_content="测试",
            processing_stage=ProcessingStage.COMPLETED,
        )
        assert is_terminal_state(completed_state) is True

        failed_state = RobotState(
            message_id="msg_002",
            user_id="user_123",
            message_content="测试",
            processing_stage=ProcessingStage.FAILED,
        )
        assert is_terminal_state(failed_state) is True

        processing_state = RobotState(
            message_id="msg_003",
            user_id="user_123",
            message_content="测试",
            processing_stage=ProcessingStage.PROCESSING,
        )
        assert is_terminal_state(processing_state) is False


# =============================================================================
# (4) 意图识别测试
# =============================================================================

class TestIntentRecognizer:
    """意图识别器测试类"""

    def test_recognize_weather_intent(self) -> None:
        """测试识别天气意图"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("今天北京天气怎么样")

        assert result.intent == IntentType.WEATHER
        assert result.confidence > 0.5
        assert result.raw_input == "今天北京天气怎么样"

    def test_recognize_chat_intent(self) -> None:
        """测试识别聊天意图"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("你好")

        assert result.intent == IntentType.CHAT
        assert result.raw_input == "你好"

    def test_recognize_role_play_intent(self) -> None:
        """测试识别角色扮演意图"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("扮演一个老师")

        assert result.intent == IntentType.ROLE_PLAY
        assert result.confidence > 0.5

    def test_recognize_command_intent(self) -> None:
        """测试识别命令意图"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("/help")

        assert result.intent == IntentType.COMMAND
        assert result.confidence > 0.9

    def test_recognize_empty_input(self) -> None:
        """测试识别空输入"""
        recognizer = IntentRecognizer()
        result = recognizer.recognize_sync("   ")

        assert result.intent == IntentType.UNKNOWN
        assert result.confidence == 0.0

    def test_add_custom_rule(self) -> None:
        """测试添加自定义规则"""
        recognizer = IntentRecognizer()
        custom_rule = IntentRule(
            intent=IntentType.WEATHER,
            keywords=["气温", "温度"],
            patterns=[r".*气温.*"],
            priority=20,
            description="自定义气温规则",
        )

        recognizer.add_rule(custom_rule)

        result = recognizer.recognize_sync("现在气温多少")
        assert result.intent == IntentType.WEATHER

    def test_remove_rules_by_intent(self) -> None:
        """测试移除意图规则"""
        recognizer = IntentRecognizer()
        original_count = len(recognizer.rules)

        removed = recognizer.remove_rules_by_intent(IntentType.WEATHER)
        assert removed > 0
        assert len(recognizer.rules) < original_count

        # 再次移除应该返回0
        removed_again = recognizer.remove_rules_by_intent(IntentType.WEATHER)
        assert removed_again == 0


# =============================================================================
# (5) 上下文管理测试
# =============================================================================

@pytest.mark.asyncio
class TestContextManager:
    """上下文管理器测试类"""

    async def test_create_private_context(self, context_manager: ContextManager) -> None:
        """测试创建私聊上下文"""
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
            name="测试对话",
        )

        assert context.type == ContextType.PRIVATE
        assert context.creator_id == "user_123"
        assert context.status == ContextStatus.ACTIVE
        assert "user_123" in context.participants

    async def test_create_group_context(self, context_manager: ContextManager) -> None:
        """测试创建群聊上下文"""
        context = await context_manager.create_context(
            context_type=ContextType.GROUP,
            creator_id="user_123",
            name="测试群聊",
            participants=["user_123", "user_456"],
        )

        assert context.type == ContextType.GROUP
        assert len(context.participants) == 2

    async def test_get_context(self, context_manager: ContextManager) -> None:
        """测试获取上下文"""
        created = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        fetched = await context_manager.get_context(created.context_id)
        assert fetched is not None
        assert fetched.context_id == created.context_id

    async def test_add_participant(self, context_manager: ContextManager) -> None:
        """测试添加参与者"""
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        success = await context_manager.add_participant(
            context.context_id, "user_456", "用户456"
        )
        assert success is True

        updated = await context_manager.get_context(context.context_id)
        assert "user_456" in updated.participants

    async def test_remove_participant(self, context_manager: ContextManager) -> None:
        """测试移除参与者"""
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
            participants=["user_123", "user_456"],
        )

        success = await context_manager.remove_participant(context.context_id, "user_456")
        assert success is True

        updated = await context_manager.get_context(context.context_id)
        assert "user_456" not in updated.participants

    async def test_add_message(self, context_manager: ContextManager) -> None:
        """测试添加消息"""
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        success = await context_manager.add_message(
            context_id=context.context_id,
            sender_id="user_123",
            sender_name="测试用户",
            content="你好",
            message_type=MessageType.TEXT,
        )
        assert success is True

        messages = await context_manager.get_messages(context.context_id)
        assert len(messages) == 1
        assert messages[0].content == "你好"

    async def test_pause_and_resume_context(self, context_manager: ContextManager) -> None:
        """测试暂停和恢复上下文"""
        context = await context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        # 暂停
        pause_success = await context_manager.pause_context(context.context_id)
        assert pause_success is True

        paused = await context_manager.get_context(context.context_id)
        assert paused.status == ContextStatus.PAUSED

        # 恢复
        resume_success = await context_manager.resume_context(context.context_id)
        assert resume_success is True

        resumed = await context_manager.get_context(context.context_id)
        assert resumed.status == ContextStatus.ACTIVE


@pytest.mark.asyncio
class TestContextStorage:
    """上下文存储测试类"""

    async def test_redis_storage(self, cache_manager: CacheManager) -> None:
        """测试Redis存储"""
        storage = RedisContextStorage(cache_manager, ttl_seconds=60)

        context = Context(
            context_id="ctx_test001",
            type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        # 保存
        save_result = await storage.save(context)
        assert save_result is True

        # 获取
        fetched = await storage.get("ctx_test001")
        assert fetched is not None
        assert fetched.context_id == "ctx_test001"

        # 删除
        delete_result = await storage.delete("ctx_test001")
        assert delete_result is True

    async def test_database_storage(self, db_manager: DatabaseManager) -> None:
        """测试数据库存储"""
        storage = DatabaseContextStorage(db_manager)

        # 先创建用户
        user_repo = UserRepository(db_manager)
        await user_repo.create(User(user_id="user_123", nickname="测试用户"))

        context = Context(
            context_id="ctx_test002",
            type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        # 保存
        save_result = await storage.save(context)
        assert save_result is True

        # 获取
        fetched = await storage.get("ctx_test002")
        assert fetched is not None
        assert fetched.context_id == "ctx_test002"

    async def test_hybrid_storage(
        self, db_manager: DatabaseManager, cache_manager: CacheManager
    ) -> None:
        """测试混合存储"""
        # 先创建用户
        user_repo = UserRepository(db_manager)
        await user_repo.create(User(user_id="user_123", nickname="测试用户"))

        cache_storage = RedisContextStorage(cache_manager)
        db_storage = DatabaseContextStorage(db_manager)
        storage = HybridContextStorage(cache_storage, db_storage)

        context = Context(
            context_id="ctx_test003",
            type=ContextType.PRIVATE,
            creator_id="user_123",
        )

        # 保存（应该同时保存到缓存和数据库）
        save_result = await storage.save(context)
        assert save_result is True

        # 获取（应该从缓存获取）
        fetched = await storage.get("ctx_test003")
        assert fetched is not None
        assert fetched.context_id == "ctx_test003"


# =============================================================================
# (6) LangGraph管理测试
# =============================================================================

@pytest.mark.asyncio
class TestLangGraphManager:
    """LangGraph管理器测试类"""

    def test_compile_graph(self) -> None:
        """测试编译状态图"""
        manager = LangGraphManager()
        graph = manager.compile()

        assert graph is not None

    async def test_process_simple_message(self) -> None:
        """测试处理简单消息"""
        manager = LangGraphManager()

        state = RobotState(
            message_id="msg_001",
            user_id="user_123",
            message_content="你好",
        )

        result = await manager.process(state)

        assert result.processing_stage in (
            ProcessingStage.COMPLETED,
            ProcessingStage.FAILED,
        )
        assert result.message_id == "msg_001"


# =============================================================================
# (7) 消息路由测试
# =============================================================================

@pytest.mark.asyncio
class TestMessageRouter:
    """消息路由器测试类"""

    async def test_route_private_message(
        self, message_router: MessageRouter
    ) -> None:
        """测试路由私聊消息"""
        result = await message_router.route_message(
            user_id="user_123",
            user_name="测试用户",
            message_content="你好",
            group_id=None,
        )

        assert isinstance(result, MessageProcessingResult)
        assert result.processing_time_ms >= 0

    async def test_route_group_message(
        self, message_router: MessageRouter
    ) -> None:
        """测试路由群聊消息"""
        result = await message_router.route_message(
            user_id="user_123",
            user_name="测试用户",
            message_content="大家好",
            group_id="group_456",
        )

        assert isinstance(result, MessageProcessingResult)

    async def test_route_weather_query(
        self, message_router: MessageRouter
    ) -> None:
        """测试路由天气查询"""
        result = await message_router.route_message(
            user_id="user_123",
            user_name="测试用户",
            message_content="今天天气怎么样",
            group_id=None,
        )

        assert isinstance(result, MessageProcessingResult)


# =============================================================================
# (8) 辅助模型测试
# =============================================================================

class TestIntentResult:
    """IntentResult模型测试类"""

    def test_create_intent_result(self) -> None:
        """测试创建意图结果"""
        result = IntentResult(
            intent=IntentType.WEATHER,
            confidence=0.9,
            raw_input="今天天气",
            reasoning="关键词匹配",
        )

        assert result.intent == IntentType.WEATHER
        assert result.confidence == 0.9
        assert result.raw_input == "今天天气"


class TestMessageProcessingResult:
    """MessageProcessingResult模型测试类"""

    def test_create_success_result(self) -> None:
        """测试创建成功结果"""
        result = MessageProcessingResult(
            success=True,
            response="你好！",
            processing_time_ms=100,
        )

        assert result.success is True
        assert result.response == "你好！"
        assert result.processing_time_ms == 100
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """测试创建失败结果"""
        result = MessageProcessingResult(
            success=False,
            response="",
            error="处理失败",
            processing_time_ms=50,
        )

        assert result.success is False
        assert result.error == "处理失败"
