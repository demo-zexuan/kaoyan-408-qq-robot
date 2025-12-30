"""
数据库操作模块

使用SQLAlchemy ORM提供数据库访问功能。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import inspect, select, text, update, delete
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.utils.config import get_config

from src.storage.orm_models import (
    BanRecordORM,
    BanReason,
    BanType,
    Base,
    ContextORM,
    ContextStatus,
    ContextType,
    IntentType,
    MessageORM,
    MessageType,
    RoleConfigORM,
    TokenQuotaORM,
    UserORM,
)
from src.storage.models import (
    BanRecord,
    ChatMessage,
    Context,
    RolePlayConfig,
    RobotState,
    TokenQuota,
    User,
)
from src.utils.logger import logger


# ==============================================================================
# (2) 数据库管理器
# ==============================================================================

class DatabaseManager:
    """数据库管理器

    提供数据库连接管理和表初始化功能。
    """

    # I. 初始化
    def __init__(self, database_url: str) -> None:
        """初始化数据库管理器

        Args:
            database_url: 数据库连接URL
        """
        self.database_url: str = database_url
        self._engine = None
        self._session_factory = None

    # II. 连接管理
    async def connect(self, auto_init: bool = False) -> None:
        """建立数据库连接

        Args:
            auto_init: 是否自动检查并初始化缺失的表，默认为False

        """
        # 如果是 sqlite 文件，确保目录存在并使用 aiosqlite 驱动
        if self.database_url.startswith("sqlite"):
            # 如果配置里未指定 aiosqlite，自动替换为异步驱动
            if "aiosqlite" not in self.database_url:
                engine_url = self.database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            else:
                engine_url = self.database_url

            # 仅在文件数据库时创建父目录（支持 sqlite+aiosqlite:///path/to/db）
            if engine_url.startswith("sqlite+aiosqlite:///"):
                db_path = engine_url.split("sqlite+aiosqlite:///", 1)[1]
                if db_path and db_path != ":memory:":
                    # 去除可能的前导斜杠（绝对路径情况：///path 或 ////path）
                    db_path = db_path.lstrip("/")
                    if db_path:
                        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            engine_url = self.database_url

        # 创建异步引擎
        self._engine = create_async_engine(
            engine_url,
            echo=False,  # 设置为True可查看SQL日志
            pool_pre_ping=True,  # 连接健康检查
        )

        # 创建会话工厂
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # 自动检查并初始化表
        if auto_init:
            await self.ensure_tables_initialized()

        logger.info(f"Database connected: {engine_url}")

    async def disconnect(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database disconnected")

    def get_session(self) -> AsyncSession:
        """获取数据库会话

        Returns:
            AsyncSession: 数据库会话对象
        """
        if self._session_factory is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._session_factory()

    # III. 表初始化
    async def init_tables(self) -> None:
        """初始化数据库表结构"""
        if self._engine is None:
            await self.connect()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables initialized")

    async def drop_tables(self) -> None:
        """删除所有表（慎用）"""
        if self._engine is None:
            await self.connect()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.warning("All database tables dropped")

    # IV. 表检查与自动初始化
    def _get_expected_table_names(self) -> set[str]:
        """获取所有期望的表名

        Returns:
            期望的表名集合
        """
        return Base.metadata.tables.keys()

    async def _get_existing_table_names(self) -> set[str]:
        """获取数据库中已存在的表名

        Returns:
            已存在的表名集合
        """
        if self._engine is None:
            return set()

        try:
            async with self._engine.connect() as conn:
                # 使用 SQLAlchemy 的 inspect 功能
                def get_tables(connection):
                    inspector = inspect(connection)
                    return set(inspector.get_table_names())

                existing_tables = await conn.run_sync(get_tables)
                return existing_tables
        except Exception as e:
            logger.warning(f"Failed to get existing tables: {e}")
            return set()

    async def check_tables_exist(self) -> dict[str, bool]:
        """检查所有期望的表是否存在

        Returns:
            字典，键为表名，值表示表是否存在
        """
        expected_tables = self._get_expected_table_names()
        existing_tables = await self._get_existing_table_names()

        result = {}
        for table_name in expected_tables:
            result[table_name] = table_name in existing_tables

        return result

    async def get_missing_tables(self) -> list[str]:
        """获取缺失的表列表

        Returns:
            缺失的表名列表
        """
        expected_tables = self._get_expected_table_names()
        existing_tables = await self._get_existing_table_names()

        missing = expected_tables - existing_tables
        return sorted(missing)

    async def ensure_tables_initialized(self) -> bool:
        """确保所有表已初始化，如果不存在则自动创建

        此方法会检查所有必需的表是否存在，如果缺失则自动创建。
        适用于应用启动时自动初始化数据库表结构。

        Returns:
            bool: 是否进行了初始化操作（True表示创建了新表，False表示表已存在）
        """
        if self._engine is None:
            await self.connect()

        missing_tables = await self.get_missing_tables()

        if not missing_tables:
            logger.info("All database tables already exist")
            return False

        logger.info(f"Missing tables detected: {missing_tables}, initializing...")

        # 创建缺失的表
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info(f"Database tables initialized: {missing_tables}")
        return True


# ==============================================================================
# (3) 用户数据访问
# ==============================================================================

class UserRepository:
    """用户数据访问对象

    提供用户相关的数据库操作。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化用户仓库

        Args:
            db_manager: 数据库管理器实例
        """
        self.db: DatabaseManager = db_manager

    # II. CRUD操作
    async def create(self, user: User) -> User:
        """创建用户

        Args:
            user: 用户对象

        Returns:
            User: 创建后的用户对象
        """
        async with self.db.get_session() as session:
            orm_user = UserORM(
                user_id=user.user_id,
                nickname=user.nickname,
                is_active=user.is_active,
                is_banned=user.is_banned,
                current_context_id=user.current_context_id,
                meta_data=json.dumps(user.metadata),
                created_at=user.created_at,
                last_active=user.last_active,
            )
            session.add(orm_user)
            await session.commit()
            await session.refresh(orm_user)
            return self._orm_to_model(orm_user)

    async def get(self, user_id: str) -> Optional[User]:
        """获取用户

        Args:
            user_id: 用户ID

        Returns:
            Optional[User]: 用户对象，不存在则返回None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(UserORM).where(UserORM.user_id == user_id)
            )
            orm_user = result.scalar_one_or_none()
            if orm_user is None:
                return None
            return self._orm_to_model(orm_user)

    async def get_or_create(self, user_id: str, nickname: str = "") -> User:
        """获取或创建用户

        Args:
            user_id: 用户ID
            nickname: 用户昵称

        Returns:
            User: 用户对象
        """
        user = await self.get(user_id)
        if user is None:
            user = User(
                user_id=user_id,
                nickname=nickname,
                is_active=True,
                is_banned=False,
            )
            user = await self.create(user)
        return user

    async def update(self, user: User) -> User:
        """更新用户

        Args:
            user: 用户对象

        Returns:
            User: 更新后的用户对象
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(UserORM)
                .where(UserORM.user_id == user.user_id)
                .values(
                    nickname=user.nickname,
                    is_active=user.is_active,
                    is_banned=user.is_banned,
                    current_context_id=user.current_context_id,
                    meta_data=json.dumps(user.metadata),
                    last_active=user.last_active,
                )
            )
            await session.commit()
            return user

    async def delete(self, user_id: str) -> bool:
        """删除用户

        Args:
            user_id: 用户ID

        Returns:
            bool: 删除成功返回True
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                delete(UserORM).where(UserORM.user_id == user_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """列出所有用户

        Args:
            limit: 限制数量
            offset: 偏移量

        Returns:
            list[User]: 用户列表
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(UserORM).limit(limit).offset(offset)
            )
            orm_users = result.scalars().all()
            return [self._orm_to_model(u) for u in orm_users]

    async def update_last_active(self, user_id: str) -> None:
        """更新用户最后活跃时间

        Args:
            user_id: 用户ID
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(UserORM)
                .where(UserORM.user_id == user_id)
                .values(last_active=datetime.now())
            )
            await session.commit()

    # III. 辅助方法
    @staticmethod
    def _orm_to_model(orm_user: UserORM) -> User:
        """将ORM对象转换为业务模型"""
        return User(
            user_id=orm_user.user_id,
            nickname=orm_user.nickname,
            is_active=orm_user.is_active,
            is_banned=orm_user.is_banned,
            current_context_id=orm_user.current_context_id,
            metadata=json.loads(orm_user.meta_data),
            created_at=orm_user.created_at,
            last_active=orm_user.last_active,
        )


# ==============================================================================
# (4) 上下文数据访问
# ==============================================================================

class ContextRepository:
    """上下文数据访问对象

    提供上下文相关的数据库操作。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化上下文仓库

        Args:
            db_manager: 数据库管理器实例
        """
        self.db: DatabaseManager = db_manager

    # II. CRUD操作
    async def create(self, context: Context) -> Context:
        """创建上下文

        Args:
            context: 上下文对象

        Returns:
            Context: 创建后的上下文对象
        """
        async with self.db.get_session() as session:
            orm_context = ContextORM(
                context_id=context.context_id,
                type=context.type,
                name=context.name,
                creator_id=context.creator_id,
                participants=json.dumps(context.participants),
                status=context.status,
                state=json.dumps(context.state.model_dump()) if context.state else None,
                current_role_id=context.current_role_id,
                meta_data=json.dumps(context.metadata),
                created_at=context.created_at,
                updated_at=context.updated_at,
                expires_at=context.expires_at,
            )
            session.add(orm_context)
            await session.commit()
            await session.refresh(orm_context)
            return await self._orm_to_model(session, orm_context)

    async def get(self, context_id: str) -> Optional[Context]:
        """获取上下文

        Args:
            context_id: 上下文ID

        Returns:
            Optional[Context]: 上下文对象，不存在则返回None
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ContextORM).where(ContextORM.context_id == context_id)
            )
            orm_context = result.scalar_one_or_none()
            if orm_context is None:
                return None
            return await self._orm_to_model(session, orm_context)

    async def update(self, context: Context) -> Context:
        """更新上下文

        Args:
            context: 上下文对象

        Returns:
            Context: 更新后的上下文对象
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(ContextORM)
                .where(ContextORM.context_id == context.context_id)
                .values(
                    type=context.type,
                    name=context.name,
                    participants=json.dumps(context.participants),
                    status=context.status,
                    state=json.dumps(context.state.model_dump()) if context.state else None,
                    current_role_id=context.current_role_id,
                    meta_data=json.dumps(context.metadata),
                    updated_at=datetime.now(),
                    expires_at=context.expires_at,
                )
            )
            await session.commit()
            return context

    async def delete(self, context_id: str) -> bool:
        """删除上下文

        Args:
            context_id: 上下文ID

        Returns:
            bool: 删除成功返回True
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                delete(ContextORM).where(ContextORM.context_id == context_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def list_by_user(self, user_id: str, active_only: bool = False) -> list[Context]:
        """列出用户的所有上下文

        Args:
            user_id: 用户ID
            active_only: 是否只返回活跃的上下文

        Returns:
            list[Context]: 上下文列表
        """
        async with self.db.get_session() as session:
            query = select(ContextORM).where(
                (ContextORM.creator_id == user_id) |
                (ContextORM.participants.like(f'%"{user_id}"%'))
            )
            if active_only:
                query = query.where(ContextORM.status == ContextStatus.ACTIVE)

            result = await session.execute(query)
            orm_contexts = result.scalars().all()
            contexts = []
            for oc in orm_contexts:
                ctx = await self._orm_to_model(session, oc)
                contexts.append(ctx)
            return contexts

    async def list_expired(self) -> list[Context]:
        """列出已过期的上下文

        Returns:
            list[Context]: 过期的上下文列表
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ContextORM).where(
                    (ContextORM.expires_at < datetime.now()) &
                    (ContextORM.status == ContextStatus.ACTIVE)
                )
            )
            orm_contexts = result.scalars().all()
            contexts = []
            for oc in orm_contexts:
                ctx = await self._orm_to_model(session, oc)
                contexts.append(ctx)
            return contexts

    async def add_message(self, context_id: str, message: ChatMessage) -> None:
        """添加消息到上下文

        Args:
            context_id: 上下文ID
            message: 消息对象
        """
        async with self.db.get_session() as session:
            orm_message = MessageORM(
                message_id=message.message_id,
                context_id=context_id,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=message.content,
                message_type=message.message_type,
                role=message.role,
                timestamp=message.timestamp,
                is_system=message.is_system,
                meta_data=json.dumps(message.metadata),
            )
            session.add(orm_message)
            await session.commit()

    # III. 辅助方法
    @staticmethod
    async def _orm_to_model(
            session: AsyncSession, orm_context: ContextORM
    ) -> Context:
        """将ORM对象转换为业务模型"""
        # 加载消息
        messages_result = await session.execute(
            select(MessageORM)
            .where(MessageORM.context_id == orm_context.context_id)
            .order_by(MessageORM.timestamp)
        )
        orm_messages = messages_result.scalars().all()

        messages = [
            ChatMessage(
                message_id=m.message_id,
                sender_id=m.sender_id,
                sender_name=m.sender_name,
                content=m.content,
                message_type=m.message_type,
                role=m.role,
                timestamp=m.timestamp,
                is_system=m.is_system,
                metadata=json.loads(m.meta_data),
            )
            for m in orm_messages
        ]

        return Context(
            context_id=orm_context.context_id,
            type=orm_context.type,
            name=orm_context.name,
            creator_id=orm_context.creator_id,
            participants=json.loads(orm_context.participants),
            status=orm_context.status,
            state=RobotState(**json.loads(orm_context.state)) if orm_context.state else None,
            current_role_id=orm_context.current_role_id,
            metadata=json.loads(orm_context.meta_data),
            created_at=orm_context.created_at,
            updated_at=orm_context.updated_at,
            expires_at=orm_context.expires_at,
            messages=messages,
            max_messages=200,
        )


# ==============================================================================
# (5) Token配额数据访问
# ==============================================================================

class TokenQuotaRepository:
    """Token配额数据访问对象

    提供Token配额相关的数据库操作。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化Token配额仓库

        Args:
            db_manager: 数据库管理器实例
        """
        self.db: DatabaseManager = db_manager

    # II. CRUD操作
    async def get(self, user_id: str) -> Optional[TokenQuota]:
        """获取用户Token配额

        Args:
            user_id: 用户ID

        Returns:
            Optional[TokenQuota]: Token配额对象
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(TokenQuotaORM).where(TokenQuotaORM.user_id == user_id)
            )
            orm_quota = result.scalar_one_or_none()
            if orm_quota is None:
                return None
            return self._orm_to_model(orm_quota)

    async def create(self, quota: TokenQuota) -> TokenQuota:
        """创建Token配额

        Args:
            quota: Token配额对象

        Returns:
            TokenQuota: 创建后的配额对象
        """
        async with self.db.get_session() as session:
            orm_quota = TokenQuotaORM(
                user_id=quota.user_id,
                total_quota=quota.total_quota,
                used=quota.used,
                daily_limit=quota.daily_limit,
                daily_used=quota.daily_used,
                daily_reset=quota.daily_reset,
                minute_limit=quota.minute_limit,
                minute_requests=json.dumps([ts.isoformat() for ts in quota.minute_requests]),
            )
            session.add(orm_quota)
            await session.commit()
            await session.refresh(orm_quota)
            return self._orm_to_model(orm_quota)

    async def update(self, quota: TokenQuota) -> TokenQuota:
        """更新Token配额

        Args:
            quota: Token配额对象

        Returns:
            TokenQuota: 更新后的配额对象
        """
        async with self.db.get_session() as session:
            await session.execute(
                update(TokenQuotaORM)
                .where(TokenQuotaORM.user_id == quota.user_id)
                .values(
                    total_quota=quota.total_quota,
                    used=quota.used,
                    daily_limit=quota.daily_limit,
                    daily_used=quota.daily_used,
                    daily_reset=quota.daily_reset,
                    minute_limit=quota.minute_limit,
                    minute_requests=json.dumps([ts.isoformat() for ts in quota.minute_requests]),
                )
            )
            await session.commit()
            return quota

    async def increment_used(self, user_id: str, tokens: int) -> TokenQuota:
        """增加已使用Token数

        Args:
            user_id: 用户ID
            tokens: 增加的Token数

        Returns:
            TokenQuota: 更新后的配额对象
        """
        quota = await self.get(user_id)
        if quota is None:
            raise ValueError(f"Token quota not found for user: {user_id}")

        quota.used += tokens
        quota.daily_used += tokens
        return await self.update(quota)

    async def reset_daily(self, user_id: str) -> TokenQuota:
        """重置每日使用量

        Args:
            user_id: 用户ID

        Returns:
            TokenQuota: 更新后的配额对象
        """
        quota = await self.get(user_id)
        if quota is None:
            raise ValueError(f"Token quota not found for user: {user_id}")

        quota.daily_used = 0
        quota.daily_reset = datetime.now() + timedelta(days=1)
        return await self.update(quota)

    # III. 辅助方法
    @staticmethod
    def _orm_to_model(orm_quota: TokenQuotaORM) -> TokenQuota:
        """将ORM对象转换为业务模型"""
        minute_requests = [
            datetime.fromisoformat(ts)
            for ts in json.loads(orm_quota.minute_requests)
        ]
        return TokenQuota(
            user_id=orm_quota.user_id,
            total_quota=orm_quota.total_quota,
            used=orm_quota.used,
            daily_limit=orm_quota.daily_limit,
            daily_used=orm_quota.daily_used,
            daily_reset=orm_quota.daily_reset,
            minute_limit=orm_quota.minute_limit,
            minute_requests=minute_requests,
        )


# ==============================================================================
# (6) 封禁记录数据访问
# ==============================================================================

class BanRecordRepository:
    """封禁记录数据访问对象

    提供封禁记录相关的数据库操作。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化封禁记录仓库

        Args:
            db_manager: 数据库管理器实例
        """
        self.db: DatabaseManager = db_manager

    # II. CRUD操作
    async def create(self, record: BanRecord) -> BanRecord:
        """创建封禁记录

        Args:
            record: 封禁记录对象

        Returns:
            BanRecord: 创建后的封禁记录对象
        """
        async with self.db.get_session() as session:
            orm_record = BanRecordORM(
                user_id=record.user_id,
                reason=record.reason,
                ban_type=record.ban_type,
                started_at=record.started_at,
                expires_at=record.expires_at,
                details=record.details,
            )
            session.add(orm_record)
            await session.commit()
            await session.refresh(orm_record)
            return self._orm_to_model(orm_record)

    async def update(self, record: BanRecord) -> BanRecord:
        """更新封禁记录

        Args:
            record: 封禁记录对象

        Returns:
            BanRecord: 更新后的封禁记录对象
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(BanRecordORM).where(
                    (BanRecordORM.user_id == record.user_id) &
                    (BanRecordORM.started_at == record.started_at)
                )
            )
            orm_record = result.scalar_one_or_none()
            if orm_record is None:
                raise ValueError(f"Ban record not found for user: {record.user_id} at {record.started_at}")

            orm_record.expires_at = record.expires_at
            orm_record.details = record.details

            await session.commit()
            await session.refresh(orm_record)
            return self._orm_to_model(orm_record)

    async def get_active_ban(self, user_id: str) -> Optional[BanRecord]:
        """获取用户的有效封禁记录

        Args:
            user_id: 用户ID

        Returns:
            Optional[BanRecord]: 封禁记录对象，无有效封禁返回None
        """
        async with self.db.get_session() as session:
            now = datetime.now()
            result = await session.execute(
                select(BanRecordORM)
                .where(
                    (BanRecordORM.user_id == user_id) &
                    (
                        (BanRecordORM.ban_type == BanType.PERMANENT) |
                        (BanRecordORM.expires_at > now)
                    )
                )
                .order_by(BanRecordORM.started_at.desc())
                .limit(1)
            )
            orm_record = result.scalar_one_or_none()
            if orm_record is None:
                return None
            return self._orm_to_model(orm_record)

    async def list_by_user(self, user_id: str) -> list[BanRecord]:
        """列出用户的所有封禁记录

        Args:
            user_id: 用户ID

        Returns:
            list[BanRecord]: 封禁记录列表
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(BanRecordORM)
                .where(BanRecordORM.user_id == user_id)
                .order_by(BanRecordORM.started_at.desc())
            )
            orm_records = result.scalars().all()
            return [self._orm_to_model(r) for r in orm_records]

    # III. 辅助方法
    @staticmethod
    def _orm_to_model(orm_record: BanRecordORM) -> BanRecord:
        """将ORM对象转换为业务模型"""
        return BanRecord(
            user_id=orm_record.user_id,
            reason=orm_record.reason,
            ban_type=orm_record.ban_type,
            started_at=orm_record.started_at,
            expires_at=orm_record.expires_at,
            details=orm_record.details,
        )


# ==============================================================================
# (7) 角色配置数据访问
# ==============================================================================

class RoleConfigRepository:
    """角色配置数据访问对象

    提供角色配置相关的数据库操作。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化角色配置仓库

        Args:
            db_manager: 数据库管理器实例
        """
        self.db: DatabaseManager = db_manager

    # II. CRUD操作
    async def get(self, role_id: str) -> Optional[RolePlayConfig]:
        """获取角色配置

        Args:
            role_id: 角色ID

        Returns:
            Optional[RolePlayConfig]: 角色配置对象
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RoleConfigORM).where(RoleConfigORM.role_id == role_id)
            )
            orm_role = result.scalar_one_or_none()
            if orm_role is None:
                return None
            return self._orm_to_model(orm_role)

    async def create(self, role: RolePlayConfig) -> RolePlayConfig:
        """创建角色配置

        Args:
            role: 角色配置对象

        Returns:
            RolePlayConfig: 创建后的角色配置对象
        """
        async with self.db.get_session() as session:
            orm_role = RoleConfigORM(
                role_id=role.role_id,
                name=role.name,
                description=role.description,
                system_prompt=role.system_prompt,
                created_at=role.created_at,
                is_active=role.is_active,
            )
            session.add(orm_role)
            await session.commit()
            await session.refresh(orm_role)
            return self._orm_to_model(orm_role)

    async def list_active(self) -> list[RolePlayConfig]:
        """列出所有启用的角色配置

        Returns:
            list[RolePlayConfig]: 角色配置列表
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RoleConfigORM)
                .where(RoleConfigORM.is_active == True)
                .order_by(RoleConfigORM.created_at)
            )
            orm_roles = result.scalars().all()
            return [self._orm_to_model(r) for r in orm_roles]

    # III. 辅助方法
    @staticmethod
    def _orm_to_model(orm_role: RoleConfigORM) -> RolePlayConfig:
        """将ORM对象转换为业务模型"""
        return RolePlayConfig(
            role_id=orm_role.role_id,
            name=orm_role.name,
            description=orm_role.description,
            system_prompt=orm_role.system_prompt,
            created_at=orm_role.created_at,
            is_active=orm_role.is_active,
        )


# ==============================================================================
# (8) 单例实例
# ==============================================================================

_default_database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """获取数据库管理器单例

    从配置中读取数据库连接参数，首次调用时创建实例。

    Returns:
        DatabaseManager: 数据库管理器实例

    Examples:
        >>> db_mgr = get_database_manager()
        >>> await db_mgr.connect()
    """
    global _default_database_manager
    if _default_database_manager is None:
        config = get_config()
        _default_database_manager = DatabaseManager(database_url=config.database_url)
    return _default_database_manager


# ==============================================================================
# (9) 导出
# ==============================================================================

__all__ = [
    # 数据库管理器
    "DatabaseManager",
    "get_database_manager",
    # 数据访问仓库
    "UserRepository",
    "ContextRepository",
    "TokenQuotaRepository",
    "BanRecordRepository",
    "RoleConfigRepository",
]
