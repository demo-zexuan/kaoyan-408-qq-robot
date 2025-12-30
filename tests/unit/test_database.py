"""
数据库模块单元测试

测试SQLAlchemy ORM数据库操作。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
import asyncio
from datetime import datetime, timedelta

import pytest

from src.storage import (
    BanRecord,
    BanReason,
    BanType,
    ChatMessage,
    Context,
    ContextStatus,
    ContextType,
    DatabaseManager,
    MessageType,
    RolePlayConfig,
    RobotState,
    TokenQuota,
    User,
    UserRepository,
    ContextRepository,
    TokenQuotaRepository,
    BanRecordRepository,
)
from src.storage.orm_models import Base, UserORM


# ==============================================================================
# (2) 测试配置
# ==============================================================================

@pytest.fixture
async def db_manager():
    """数据库管理器测试夹具"""
    # 使用内存数据库进行测试
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.connect()
    async with db._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.disconnect()


@pytest.fixture
def sample_user():
    """示例用户数据"""
    return User(
        user_id="123456789",
        nickname="测试用户",
        is_active=True,
        is_banned=False,
    )


# ==============================================================================
# (3) UserRepository 测试
# ==============================================================================

@pytest.mark.asyncio
class TestUserRepository:
    """用户仓库测试类"""

    async def test_create_user(self, db_manager: DatabaseManager, sample_user: User):
        """测试创建用户"""
        repo = UserRepository(db_manager)
        user = await repo.create(sample_user)

        assert user.user_id == sample_user.user_id
        assert user.nickname == sample_user.nickname
        assert user.is_active is True

    async def test_get_user(self, db_manager: DatabaseManager, sample_user: User):
        """测试获取用户"""
        repo = UserRepository(db_manager)
        created = await repo.create(sample_user)
        fetched = await repo.get(created.user_id)

        assert fetched is not None
        assert fetched.user_id == created.user_id
        assert fetched.nickname == created.nickname

    async def test_get_or_create_user(self, db_manager: DatabaseManager, sample_user: User):
        """测试获取或创建用户"""
        repo = UserRepository(db_manager)

        # 第一次调用创建
        user1 = await repo.get_or_create(sample_user.user_id, sample_user.nickname)
        assert user1.nickname == sample_user.nickname

        # 第二次调用获取已存在的
        user2 = await repo.get_or_create(sample_user.user_id)
        assert user2.user_id == user1.user_id

    async def test_update_user(self, db_manager: DatabaseManager, sample_user: User):
        """测试更新用户"""
        repo = UserRepository(db_manager)
        user = await repo.create(sample_user)

        user.nickname = "新昵称"
        updated = await repo.update(user)

        assert updated.nickname == "新昵称"

    async def test_delete_user(self, db_manager: DatabaseManager, sample_user: User):
        """测试删除用户"""
        repo = UserRepository(db_manager)
        user = await repo.create(sample_user)

        result = await repo.delete(user.user_id)
        assert result is True

        fetched = await repo.get(user.user_id)
        assert fetched is None

    async def test_list_users(self, db_manager: DatabaseManager):
        """测试列出用户"""
        repo = UserRepository(db_manager)

        # 创建多个用户
        for i in range(5):
            user = User(user_id=str(i), nickname=f"用户{i}")
            await repo.create(user)

        users = await repo.list_all()
        assert len(users) == 5


# ==============================================================================
# (4) ContextRepository 测试
# ==============================================================================

@pytest.mark.asyncio
class TestContextRepository:
    """上下文仓库测试类"""

    @pytest.fixture
    def sample_context(self):
        """示例上下文数据"""
        return Context(
            context_id="ctx_test001",
            type=ContextType.PRIVATE,
            name="测试对话",
            creator_id="123456789",
            participants=["123456789"],
            status=ContextStatus.ACTIVE,
        )

    async def test_create_context(
        self, db_manager: DatabaseManager, sample_context: Context
    ):
        """测试创建上下文"""
        # 先创建用户
        user_repo = UserRepository(db_manager)
        await user_repo.create(
            User(user_id=sample_context.creator_id, nickname="测试用户")
        )

        # 创建上下文
        ctx_repo = ContextRepository(db_manager)
        context = await ctx_repo.create(sample_context)

        assert context.context_id == sample_context.context_id
        assert context.type == ContextType.PRIVATE

    async def test_get_context(
        self, db_manager: DatabaseManager, sample_context: Context
    ):
        """测试获取上下文"""
        user_repo = UserRepository(db_manager)
        await user_repo.create(
            User(user_id=sample_context.creator_id, nickname="测试用户")
        )

        ctx_repo = ContextRepository(db_manager)
        created = await ctx_repo.create(sample_context)
        fetched = await ctx_repo.get(created.context_id)

        assert fetched is not None
        assert fetched.context_id == created.context_id

    async def test_add_message_to_context(
        self, db_manager: DatabaseManager, sample_context: Context
    ):
        """测试添加消息到上下文"""
        user_repo = UserRepository(db_manager)
        await user_repo.create(
            User(user_id=sample_context.creator_id, nickname="测试用户")
        )

        ctx_repo = ContextRepository(db_manager)
        context = await ctx_repo.create(sample_context)

        message = ChatMessage(
            message_id="msg_test001",
            sender_id=sample_context.creator_id,
            sender_name="测试用户",
            content="你好",
            message_type=MessageType.TEXT,
        )

        await ctx_repo.add_message(context.context_id, message)

        # 重新获取上下文验证消息已添加
        updated = await ctx_repo.get(context.context_id)
        assert len(updated.messages) == 1
        assert updated.messages[0].content == "你好"


# ==============================================================================
# (5) TokenQuotaRepository 测试
# ==============================================================================

@pytest.mark.asyncio
class TestTokenQuotaRepository:
    """Token配额仓库测试类"""

    @pytest.fixture
    def sample_quota(self):
        """示例配额数据"""
        tomorrow = datetime.now() + timedelta(days=1)
        return TokenQuota(
            user_id="123456789",
            total_quota=10000,
            used=100,
            daily_limit=1000,
            daily_used=50,
            daily_reset=tomorrow,
        )

    async def test_create_quota(
        self, db_manager: DatabaseManager, sample_quota: TokenQuota
    ):
        """测试创建配额"""
        repo = TokenQuotaRepository(db_manager)
        quota = await repo.create(sample_quota)

        assert quota.user_id == sample_quota.user_id
        assert quota.total_quota == 10000

    async def test_get_quota(
        self, db_manager: DatabaseManager, sample_quota: TokenQuota
    ):
        """测试获取配额"""
        repo = TokenQuotaRepository(db_manager)
        created = await repo.create(sample_quota)
        fetched = await repo.get(created.user_id)

        assert fetched is not None
        assert fetched.total_quota == 10000

    async def test_increment_used(
        self, db_manager: DatabaseManager, sample_quota: TokenQuota
    ):
        """测试增加使用量"""
        repo = TokenQuotaRepository(db_manager)
        await repo.create(sample_quota)

        updated = await repo.increment_used(sample_quota.user_id, 50)
        assert updated.used == 150

    async def test_reset_daily(
        self, db_manager: DatabaseManager, sample_quota: TokenQuota
    ):
        """测试重置每日使用量"""
        repo = TokenQuotaRepository(db_manager)
        await repo.create(sample_quota)

        updated = await repo.reset_daily(sample_quota.user_id)
        assert updated.daily_used == 0


# ==============================================================================
# (6) BanRecordRepository 测试
# ==============================================================================

@pytest.mark.asyncio
class TestBanRecordRepository:
    """封禁记录仓库测试类"""

    @pytest.fixture
    def sample_ban_record(self):
        """示例封禁记录"""
        expires = datetime.now() + timedelta(hours=1)
        return BanRecord(
            user_id="123456789",
            reason=BanReason.SPAMMING,
            ban_type=BanType.TEMPORARY,
            started_at=datetime.now(),
            expires_at=expires,
            details="刷屏警告",
        )

    async def test_create_ban_record(
        self, db_manager: DatabaseManager, sample_ban_record: BanRecord
    ):
        """测试创建封禁记录"""
        repo = BanRecordRepository(db_manager)
        record = await repo.create(sample_ban_record)

        assert record.user_id == sample_ban_record.user_id
        assert record.reason == BanReason.SPAMMING

    async def test_get_active_ban(
        self, db_manager: DatabaseManager, sample_ban_record: BanRecord
    ):
        """测试获取有效封禁记录"""
        repo = BanRecordRepository(db_manager)
        await repo.create(sample_ban_record)

        active = await repo.get_active_ban(sample_ban_record.user_id)
        assert active is not None
        assert active.is_active is True

    async def test_list_ban_records_by_user(
        self, db_manager: DatabaseManager, sample_ban_record: BanRecord
    ):
        """测试列出用户封禁记录"""
        repo = BanRecordRepository(db_manager)
        await repo.create(sample_ban_record)

        records = await repo.list_by_user(sample_ban_record.user_id)
        assert len(records) == 1
