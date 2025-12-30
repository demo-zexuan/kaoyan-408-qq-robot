"""
上下文管理模块

实现对话上下文的创建、获取、更新、删除等功能。
支持混合存储策略（Redis缓存 + 数据库持久化）。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import validate_call
from typing_extensions import override

from src.storage import (
    CacheManager,
    ChatMessage,
    Context,
    ContextRepository,
    ContextStatus,
    ContextType,
    DatabaseManager,
    MessageRole,
    MessageType,
    UserRepository,
)
from src.utils.helpers import IDHelper
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) 存储策略接口
# =============================================================================

class ContextStorage:
    """上下文存储策略基类

    定义上下文存储的通用接口。
    """

    async def get(self, context_id: str) -> Optional[Context]:
        """获取上下文

        Args:
            context_id: 上下文ID

        Returns:
            上下文对象，不存在则返回None
        """
        raise NotImplementedError

    async def save(self, context: Context) -> bool:
        """保存上下文

        Args:
            context: 上下文对象

        Returns:
            是否保存成功
        """
        raise NotImplementedError

    async def delete(self, context_id: str) -> bool:
        """删除上下文

        Args:
            context_id: 上下文ID

        Returns:
            是否删除成功
        """
        raise NotImplementedError

    async def list_active(self, user_id: Optional[str] = None) -> list[Context]:
        """列出活跃上下文

        Args:
            user_id: 用户ID（可选），若提供则仅返回该用户的上下文

        Returns:
            活跃上下文列表
        """
        raise NotImplementedError


class RedisContextStorage(ContextStorage):
    """Redis缓存上下文存储

    使用Redis缓存实现快速访问，适合高频读取场景。
    """

    # I. 初始化
    def __init__(self, cache_manager: CacheManager, ttl_seconds: int = 3600) -> None:
        """初始化Redis上下文存储

        Args:
            cache_manager: 缓存管理器
            ttl_seconds: 缓存过期时间（秒）
        """
        self.cache = cache_manager.context
        self.ttl_seconds = ttl_seconds

    # II. 实现接口
    @override
    async def get(self, context_id: str) -> Optional[Context]:
        """从Redis获取上下文"""
        try:
            context = await self.cache.get(context_id)
            if context:
                logger.debug(f"Context {context_id} found in Redis")
                return context
        except Exception as e:
            logger.error(f"Failed to get context from Redis: {e}")
        return None

    @override
    async def save(self, context: Context) -> bool:
        """保存上下文到Redis"""
        try:
            await self.cache.set(context, self.ttl_seconds)
            logger.debug(f"Context {context.context_id} saved to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to save context to Redis: {e}")
            return False

    @override
    async def delete(self, context_id: str) -> bool:
        """从Redis删除上下文"""
        try:
            await self.cache.delete(context_id)
            logger.debug(f"Context {context_id} deleted from Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to delete context from Redis: {e}")
            return False

    @override
    async def list_active(self, user_id: Optional[str] = None) -> list[Context]:
        """Redis不直接支持列表查询，返回空列表"""
        return []


class DatabaseContextStorage(ContextStorage):
    """数据库持久化上下文存储

    使用数据库实现持久化存储，确保数据不丢失。
    """

    # I. 初始化
    def __init__(self, db_manager: DatabaseManager) -> None:
        """初始化数据库上下文存储

        Args:
            db_manager: 数据库管理器
        """
        self.repo = ContextRepository(db_manager)

    # II. 实现接口
    @override
    async def get(self, context_id: str) -> Optional[Context]:
        """从数据库获取上下文"""
        try:
            context = await self.repo.get(context_id)
            if context:
                logger.debug(f"Context {context_id} found in database")
            return context
        except Exception as e:
            logger.error(f"Failed to get context from database: {e}")
            return None

    @override
    async def save(self, context: Context) -> bool:
        """保存上下文到数据库"""
        try:
            # 检查上下文是否已存在
            existing = await self.repo.get(context.context_id)
            if existing:
                # 已存在，更新
                await self.repo.update(context)
            else:
                # 不存在，创建
                await self.repo.create(context)
            logger.debug(f"Context {context.context_id} saved to database")
            return True
        except Exception as e:
            logger.error(f"Failed to save context to database: {e}")
            return False

    @override
    async def delete(self, context_id: str) -> bool:
        """从数据库删除上下文"""
        try:
            # 通过更新状态为DELETED实现软删除
            context = await self.repo.get(context_id)
            if context:
                context.status = ContextStatus.DELETED
                await self.repo.update(context)
                logger.debug(f"Context {context_id} marked as deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete context from database: {e}")
            return False

    @override
    async def list_active(self, user_id: Optional[str] = None) -> list[Context]:
        """从数据库列出活跃上下文"""
        try:
            # 注意：需要在ContextRepository中实现按状态查询的方法
            # 这里使用简单的获取方式
            contexts = await self.repo.list_all()
            if user_id:
                contexts = [c for c in contexts if user_id in c.participants]
            active_contexts = [c for c in contexts if c.status == ContextStatus.ACTIVE]
            return active_contexts
        except Exception as e:
            logger.error(f"Failed to list active contexts: {e}")
            return []


class HybridContextStorage(ContextStorage):
    """混合上下文存储

    结合Redis缓存和数据库持久化的优势：
    - 读取时优先从缓存获取
    - 写入时同时更新缓存和数据库
    - 删除时同时清除缓存和标记删除
    """

    # I. 初始化
    def __init__(
            self,
            cache_storage: RedisContextStorage,
            db_storage: DatabaseContextStorage,
    ) -> None:
        """初始化混合上下文存储

        Args:
            cache_storage: Redis缓存存储
            db_storage: 数据库存储
        """
        self.cache_storage = cache_storage
        self.db_storage = db_storage

    # II. 实现接口
    @override
    async def get(self, context_id: str) -> Optional[Context]:
        """获取上下文（优先从缓存）"""
        # 先从缓存获取
        context = await self.cache_storage.get(context_id)
        if context:
            return context

        # 缓存未命中，从数据库获取
        context = await self.db_storage.get(context_id)
        if context:
            # 回写缓存
            await self.cache_storage.save(context)
        return context

    @override
    async def save(self, context: Context) -> bool:
        """同时保存到缓存和数据库"""
        cache_ok = await self.cache_storage.save(context)
        db_ok = await self.db_storage.save(context)
        return cache_ok and db_ok

    @override
    async def delete(self, context_id: str) -> bool:
        """同时从缓存和数据库删除"""
        cache_ok = await self.cache_storage.delete(context_id)
        db_ok = await self.db_storage.delete(context_id)
        return cache_ok and db_ok

    @override
    async def list_active(self, user_id: Optional[str] = None) -> list[Context]:
        """从数据库列出活跃上下文"""
        return await self.db_storage.list_active(user_id)


# =============================================================================
# (4) 上下文管理器
# =============================================================================

class ContextManager:
    """上下文管理器

    提供对话上下文的完整生命周期管理功能。

    主要功能：
    - 创建上下文
    - 获取/更新/删除上下文
    - 管理参与者
    - 添加消息
    - 清理过期上下文
    """

    # I. 初始化
    def __init__(
            self,
            db_manager: DatabaseManager,
            cache_manager: CacheManager,
            storage: Optional[ContextStorage] = None,
    ) -> None:
        """初始化上下文管理器

        Args:
            db_manager: 数据库管理器
            cache_manager: 缓存管理器
            storage: 自定义存储策略，若为None则使用混合存储
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.user_repo = UserRepository(db_manager)
        self.context_repo = ContextRepository(db_manager)

        # 设置存储策略
        if storage is None:
            cache_storage = RedisContextStorage(cache_manager)
            db_storage = DatabaseContextStorage(db_manager)
            storage = HybridContextStorage(cache_storage, db_storage)
        self.storage = storage

        logger.info("ContextManager initialized")

    # II. 上下文CRUD操作
    @validate_call
    async def create_context(
            self,
            context_type: ContextType,
            creator_id: str,
            name: str = "",
            participants: Optional[list[str]] = None,
            expires_in_hours: Optional[int] = None,
            metadata: Optional[dict[str, Any]] = None,
    ) -> Context:
        """创建新上下文

        Args:
            context_type: 上下文类型
            creator_id: 创建者ID
            name: 上下文名称
            participants: 参与者ID列表
            expires_in_hours: 过期时间（小时），None表示永不过期
            metadata: 附加元数据

        Returns:
            创建的上下文对象
        """
        # 确保用户存在
        user = await self.user_repo.get_or_create(creator_id)
        if participants is None:
            participants = [creator_id]
        elif creator_id not in participants:
            participants.append(creator_id)

        # 生成上下文ID
        context_id = IDHelper.generate_context_id()

        # 计算过期时间
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now() + timedelta(hours=expires_in_hours)

        # 创建上下文对象
        context = Context(
            context_id=context_id,
            type=context_type,
            name=name or f"{context_type.value}_{context_id[:8]}",
            creator_id=creator_id,
            participants=participants,
            status=ContextStatus.ACTIVE,
            metadata=metadata or {},
            expires_at=expires_at,
        )

        # 持久化
        created = await self.context_repo.create(context)
        await self.storage.save(created)

        # 更新用户的当前上下文
        user.current_context_id = context_id
        await self.user_repo.update(user)

        logger.info(
            f"Created context {context_id} of type {context_type} for user {creator_id}"
        )
        return created

    @validate_call
    async def get_context(self, context_id: str) -> Optional[Context]:
        """获取上下文

        Args:
            context_id: 上下文ID

        Returns:
            上下文对象，不存在则返回None
        """
        return await self.storage.get(context_id)

    @validate_call
    async def update_context(self, context: Context) -> bool:
        """更新上下文

        Args:
            context: 上下文对象

        Returns:
            是否更新成功
        """
        context.updated_at = datetime.now()
        success = await self.storage.save(context)
        if success:
            logger.debug(f"Updated context {context.context_id}")
        return success

    @validate_call
    async def delete_context(self, context_id: str) -> bool:
        """删除上下文

        Args:
            context_id: 上下文ID

        Returns:
            是否删除成功
        """
        # 清除所有参与者的当前上下文
        context = await self.get_context(context_id)
        if context:
            for participant_id in context.participants:
                user = await self.user_repo.get(participant_id)
                if user and user.current_context_id == context_id:
                    user.current_context_id = None
                    await self.user_repo.update(user)

        success = await self.storage.delete(context_id)
        if success:
            logger.info(f"Deleted context {context_id}")
        return success

    # III. 参与者管理
    @validate_call
    async def add_participant(
            self, context_id: str, user_id: str, user_name: str = ""
    ) -> bool:
        """添加参与者到上下文

        Args:
            context_id: 上下文ID
            user_id: 用户ID
            user_name: 用户昵称

        Returns:
            是否添加成功
        """
        context = await self.get_context(context_id)
        if not context:
            logger.warning(f"Context {context_id} not found")
            return False

        if user_id in context.participants:
            logger.debug(f"User {user_id} already in context {context_id}")
            return True

        # 确保用户存在
        await self.user_repo.get_or_create(user_id, user_name)

        context.participants.append(user_id)
        context.updated_at = datetime.now()
        return await self.update_context(context)

    @validate_call
    async def remove_participant(self, context_id: str, user_id: str) -> bool:
        """从上下文移除参与者

        Args:
            context_id: 上下文ID
            user_id: 用户ID

        Returns:
            是否移除成功
        """
        context = await self.get_context(context_id)
        if not context:
            return False

        if user_id not in context.participants:
            return True

        context.participants.remove(user_id)
        context.updated_at = datetime.now()

        # 如果是创建者离开，归档上下文
        if user_id == context.creator_id:
            context.status = ContextStatus.ARCHIVED

        # 更新用户当前上下文
        user = await self.user_repo.get(user_id)
        if user and user.current_context_id == context_id:
            user.current_context_id = None
            await self.user_repo.update(user)

        return await self.update_context(context)

    # IV. 消息管理
    @validate_call
    async def add_message(
            self,
            context_id: str,
            sender_id: str,
            sender_name: str,
            content: str,
            message_type: MessageType = MessageType.TEXT,
            role: MessageRole = MessageRole.USER,
            is_system: bool = False,
    ) -> bool:
        """添加消息到上下文

        Args:
            context_id: 上下文ID
            sender_id: 发送者ID
            sender_name: 发送者名称
            content: 消息内容
            message_type: 消息类型
            role: 消息角色
            is_system: 是否为系统消息

        Returns:
            是否添加成功
        """
        context = await self.get_context(context_id)
        if not context:
            logger.warning(f"Context {context_id} not found")
            return False

        # 创建消息对象
        message = ChatMessage(
            message_id=IDHelper.generate_message_id(),
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            message_type=message_type,
            role=role,
            is_system=is_system,
        )

        # 添加到上下文
        await self.context_repo.add_message(context_id, message)

        # 更新上下文
        context.messages.append(message)
        context.updated_at = datetime.now()

        # 限制消息数量
        if len(context.messages) > context.max_messages:
            context.messages = context.messages[-context.max_messages:]

        return await self.update_context(context)

    async def get_messages(
            self, context_id: str, limit: Optional[int] = None
    ) -> list[ChatMessage]:
        """获取上下文消息历史

        Args:
            context_id: 上下文ID
            limit: 最大消息数，None表示返回全部

        Returns:
            消息列表
        """
        context = await self.get_context(context_id)
        if not context:
            return []

        messages = context.messages
        if limit and len(messages) > limit:
            messages = messages[-limit:]

        return messages

    # V. 查询操作
    async def list_active_contexts(self, user_id: Optional[str] = None) -> list[Context]:
        """列出活跃上下文

        Args:
            user_id: 用户ID（可选），若提供则仅返回该用户的上下文

        Returns:
            活跃上下文列表
        """
        return await self.storage.list_active(user_id)

    async def get_user_context(self, user_id: str) -> Optional[Context]:
        """获取用户当前上下文

        Args:
            user_id: 用户ID

        Returns:
            当前上下文对象，不存在则返回None
        """
        user = await self.user_repo.get(user_id)
        if not user or not user.current_context_id:
            return None

        return await self.get_context(user.current_context_id)

    # VI. 维护操作
    async def cleanup_expired(self) -> int:
        """清理过期上下文

        Returns:
            清理的上下文数量
        """
        now = datetime.now()
        all_contexts = await self.context_repo.list_all()

        cleaned_count = 0
        for context in all_contexts:
            if context.status != ContextStatus.ACTIVE:
                continue

            if context.expires_at and context.expires_at < now:
                context.status = ContextStatus.EXPIRED
                await self.update_context(context)
                cleaned_count += 1
                logger.info(f"Marked context {context.context_id} as expired")

        return cleaned_count

    async def pause_context(self, context_id: str) -> bool:
        """暂停上下文

        Args:
            context_id: 上下文ID

        Returns:
            是否操作成功
        """
        context = await self.get_context(context_id)
        if not context:
            return False

        context.status = ContextStatus.PAUSED
        return await self.update_context(context)

    async def resume_context(self, context_id: str) -> bool:
        """恢复上下文

        Args:
            context_id: 上下文ID

        Returns:
            是否操作成功
        """
        context = await self.get_context(context_id)
        if not context:
            return False

        context.status = ContextStatus.ACTIVE
        return await self.update_context(context)


# =============================================================================
# (5) 单例实例
# =============================================================================

_default_context_manager: Optional[ContextManager] = None


def get_context_manager(
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
) -> ContextManager:
    """获取默认上下文管理器实例

    Args:
        db_manager: 数据库管理器
        cache_manager: 缓存管理器

    Returns:
        ContextManager实例
    """
    global _default_context_manager
    if _default_context_manager is None:
        _default_context_manager = ContextManager(db_manager, cache_manager)
    return _default_context_manager


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    # 存储策略
    "ContextStorage",
    "RedisContextStorage",
    "DatabaseContextStorage",
    "HybridContextStorage",
    # 管理器
    "ContextManager",
    "get_context_manager",
]
