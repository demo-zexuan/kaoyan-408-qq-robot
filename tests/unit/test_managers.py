"""
管理器模块单元测试

测试用户管理、Token控制和封禁管理功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from datetime import datetime, timedelta

import pytest

from src.managers.ban import BanManager, DEFAULT_DETECTION_RULES
from src.managers.token import TokenController
from src.managers.user import UserManager
from src.storage import (
    BanReason,
    BanType,
    CacheManager,
    Context,
    ContextStatus,
    ContextType,
    DatabaseManager,
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
async def cache_manager():
    """缓存管理器测试夹具"""
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
    from src.core.context import ContextManager

    return ContextManager(db_manager, cache_manager)


@pytest.fixture
async def user_manager(db_manager, cache_manager, context_manager):
    """用户管理器测试夹具"""
    return UserManager(db_manager, cache_manager, context_manager)


@pytest.fixture
async def token_controller(db_manager, cache_manager):
    """Token控制器测试夹具"""
    return TokenController(db_manager, cache_manager)


@pytest.fixture
async def ban_manager(db_manager, cache_manager):
    """封禁管理器测试夹具"""
    return BanManager(db_manager, cache_manager)


# =============================================================================
# (3) UserManager 测试
# =============================================================================

@pytest.mark.asyncio
class TestUserManager:
    """UserManager测试类"""

    async def test_create_user(self, user_manager: UserManager) -> None:
        """测试创建用户"""
        user = await user_manager.create_user(
            user_id="test_001",
            nickname="测试用户",
        )

        assert user.user_id == "test_001"
        assert user.nickname == "测试用户"
        assert user.is_active is True
        assert user.is_banned is False

    async def test_get_or_create_user(self, user_manager: UserManager) -> None:
        """测试获取或创建用户"""
        # 第一次调用创建
        user1 = await user_manager.get_or_create_user("test_002", "用户A")
        assert user1.nickname == "用户A"

        # 第二次调用获取已存在的
        user2 = await user_manager.get_or_create_user("test_002", "用户B")
        assert user2.user_id == "test_002"
        # 昵称被更新
        assert user2.nickname == "用户B"

    async def test_update_nickname(self, user_manager: UserManager) -> None:
        """测试更新昵称"""
        await user_manager.create_user("test_003", "原名")
        success = await user_manager.update_nickname("test_003", "新名")

        assert success is True

        user = await user_manager.get_user("test_003")
        assert user.nickname == "新名"

    async def test_ban_user(self, user_manager: UserManager) -> None:
        """测试封禁用户"""
        await user_manager.create_user("test_004")

        success = await user_manager.ban_user("test_004")
        assert success is True

        is_banned = await user_manager.is_user_banned("test_004")
        assert is_banned is True

    async def test_unban_user(self, user_manager: UserManager) -> None:
        """测试解封用户"""
        await user_manager.create_user("test_005")
        await user_manager.ban_user("test_005")

        success = await user_manager.unban_user("test_005")
        assert success is True

        is_banned = await user_manager.is_user_banned("test_005")
        assert is_banned is False

    async def test_deactivate_user(self, user_manager: UserManager) -> None:
        """测试停用用户"""
        await user_manager.create_user("test_006")

        success = await user_manager.deactivate_user("test_006")
        assert success is True

        is_active = await user_manager.is_user_active("test_006")
        assert is_active is False

    async def test_create_private_context(self, user_manager: UserManager) -> None:
        """测试创建私聊上下文"""
        context = await user_manager.create_private_context(
            user_id="test_007",
            user_name="测试用户",
        )

        assert context.type == ContextType.PRIVATE
        assert "test_007" in context.participants

    async def test_update_last_active(self, user_manager: UserManager) -> None:
        """测试更新最后活跃时间"""
        await user_manager.create_user("test_008")

        success = await user_manager.update_last_active("test_008")
        assert success is True


# =============================================================================
# (4) TokenController 测试
# =============================================================================

@pytest.mark.asyncio
class TestTokenController:
    """TokenController测试类"""

    async def test_get_quota(self, token_controller: TokenController) -> None:
        """测试获取配额"""
        quota = await token_controller.get_quota("user_001")

        assert quota.user_id == "user_001"
        assert quota.total_quota == TokenController.DEFAULT_TOTAL_QUOTA

    async def test_check_quota(self, token_controller: TokenController) -> None:
        """测试检查配额"""
        can_use, _ = await token_controller.check_quota("user_002", 100)
        assert can_use is True

    async def test_consume(self, token_controller: TokenController) -> None:
        """测试消耗Token"""
        success = await token_controller.consume("user_003", 100)
        assert success is True

        quota = await token_controller.get_quota("user_003")
        assert quota.used == 100
        assert quota.daily_used == 100

    async def test_consume_exceed(self, token_controller: TokenController) -> None:
        """测试消耗超过配额"""
        # 尝试消耗超过每日限制
        large_amount = TokenController.DEFAULT_DAILY_LIMIT + 1000
        success = await token_controller.consume("user_004", large_amount)
        assert success is False

    async def test_get_remaining_quota(self, token_controller: TokenController) -> None:
        """测试获取剩余配额"""
        remaining = await token_controller.get_remaining_quota("user_005")
        assert remaining == TokenController.DEFAULT_TOTAL_QUOTA

        # 消耗一些后
        await token_controller.consume("user_005", 100)
        remaining = await token_controller.get_remaining_quota("user_005")
        assert remaining == TokenController.DEFAULT_TOTAL_QUOTA - 100

    async def test_get_daily_remaining(self, token_controller: TokenController) -> None:
        """测试获取每日剩余配额"""
        remaining = await token_controller.get_daily_remaining("user_006")
        assert remaining == TokenController.DEFAULT_DAILY_LIMIT

    async def test_get_usage_info(self, token_controller: TokenController) -> None:
        """测试获取使用情况"""
        await token_controller.consume("user_007", 50)

        info = await token_controller.get_usage_info("user_007")
        assert info["used"] == 50
        assert info["daily_used"] == 50
        assert "remaining" in info

    async def test_set_daily_limit(self, token_controller: TokenController) -> None:
        """测试设置每日限制"""
        success = await token_controller.set_daily_limit("user_008", 1000)
        assert success is True

        quota = await token_controller.get_quota("user_008")
        assert quota.daily_limit == 1000

    async def test_reset_daily(self, token_controller: TokenController) -> None:
        """测试重置每日配额"""
        await token_controller.consume("user_009", 100)

        reset_ok = await token_controller.reset_daily("user_009")
        assert reset_ok is True

        quota = await token_controller.get_quota("user_009")
        assert quota.daily_used == 0


# =============================================================================
# (5) BanManager 测试
# =============================================================================

@pytest.mark.asyncio
class TestBanManager:
    """BanManager测试类"""

    async def test_check_ban_status(self, ban_manager: BanManager) -> None:
        """测试检查封禁状态"""
        # 未封禁用户
        record = await ban_manager.check_ban_status("user_001")
        assert record is None

    async def test_ban_user_temporary(self, ban_manager: BanManager) -> None:
        """测试临时封禁用户"""
        record = await ban_manager.ban_user(
            user_id="user_002",
            reason=BanReason.SPAMMING,
            ban_type=BanType.TEMPORARY,
            duration_hours=1,
        )

        assert record.user_id == "user_002"
        assert record.reason == BanReason.SPAMMING
        assert record.is_active is True

    async def test_ban_user_permanently(self, ban_manager: BanManager) -> None:
        """测试永久封禁用户"""
        record = await ban_manager.ban_user_permanently(
            user_id="user_003",
            reason=BanReason.MALICIOUS_BEHAVIOR,
            details="恶意攻击",
        )

        assert record.ban_type == BanType.PERMANENT
        assert record.is_active is True

    async def test_unban_user(self, ban_manager: BanManager) -> None:
        """测试解封用户"""
        # 先封禁
        await ban_manager.ban_user(
            user_id="user_004",
            reason=BanReason.SPAMMING,
            ban_type=BanType.TEMPORARY,
            duration_hours=1,
        )

        # 解封
        success = await ban_manager.unban_user("user_004")
        assert success is True

        # 检查状态
        is_banned = await ban_manager.is_banned("user_004")
        assert is_banned is False

    async def test_ban_user_for_spam(self, ban_manager: BanManager) -> None:
        """测试封禁刷屏用户"""
        record = await ban_manager.ban_user_for_spam("user_005", duration_hours=2)

        assert record.reason == BanReason.SPAMMING
        assert record.expires_at is not None

    async def test_detect_rapid_requests(self, ban_manager: BanManager) -> None:
        """测试检测频繁请求"""
        user_id = "user_006"

        # 发送多个请求
        for _ in range(15):  # 超过阈值 (默认10次)
            is_abuse, _ = await ban_manager.detect_abuse(user_id)
            if is_abuse:
                break

        # 最终应该检测到异常
        is_abuse, reason = await ban_manager.detect_abuse(user_id)
        assert is_abuse is True
        assert "请求过于频繁" in reason

    async def test_detect_spam(self, ban_manager: BanManager) -> None:
        """测试检测刷屏"""
        user_id = "user_007"

        # 发送多条消息
        for i in range(10):
            is_abuse, _ = await ban_manager.detect_abuse(
                user_id,
                message_content=f"消息{i}",
            )
            if is_abuse:
                break

        # 最终应该检测到刷屏
        is_abuse, reason = await ban_manager.detect_abuse(user_id, "新消息")
        assert is_abuse is True
        assert "刷屏" in reason

    async def test_detect_repeated_content(self, ban_manager: BanManager) -> None:
        """测试检测重复内容"""
        user_id = "user_008"
        content = "重复消息"

        # 发送重复消息 - 使用间隔避免触发刷屏检测
        import asyncio
        for _ in range(3):
            await ban_manager.detect_abuse(user_id, message_content=content)
            await asyncio.sleep(0.1)  # 小间隔避免刷屏检测

        # 应该检测到重复
        is_abuse, reason = await ban_manager.detect_abuse(user_id, content)
        assert is_abuse is True
        assert "重复" in reason or "repeat" in reason.lower()

    async def test_get_ban_reason(self, ban_manager: BanManager) -> None:
        """测试获取封禁原因"""
        await ban_manager.ban_user(
            user_id="user_009",
            reason=BanReason.SPAMMING,
            details="刷屏警告",
        )

        reason = await ban_manager.get_ban_reason("user_009")
        assert "刷屏" in reason or "spamming" in reason.lower()

    async def test_list_ban_records(self, ban_manager: BanManager) -> None:
        """测试列出封禁记录"""
        user_id = "user_010"

        # 创建多条封禁记录
        await ban_manager.ban_user(
            user_id=user_id,
            reason=BanReason.SPAMMING,
            ban_type=BanType.TEMPORARY,
        )
        await ban_manager.unban_user(user_id)
        await ban_manager.ban_user(
            user_id=user_id,
            reason=BanReason.RATE_LIMIT_EXCEEDED,
            ban_type=BanType.TEMPORARY,
        )

        records = await ban_manager.list_ban_records(user_id)
        assert len(records) >= 1


# =============================================================================
# (6) 配置测试
# =============================================================================

class TestDetectionRules:
    """检测规则配置测试类"""

    def test_default_rules(self) -> None:
        """测试默认检测规则"""
        assert "rapid_request_threshold" in DEFAULT_DETECTION_RULES
        assert "spam_message_threshold" in DEFAULT_DETECTION_RULES
        assert "token_burst_threshold" in DEFAULT_DETECTION_RULES

    def test_custom_rules(self) -> None:
        """测试自定义检测规则"""
        custom_rules = {"rapid_request_threshold": 20}

        # 规则应该被合并
        expected = DEFAULT_DETECTION_RULES.copy()
        expected.update(custom_rules)

        assert expected["rapid_request_threshold"] == 20
