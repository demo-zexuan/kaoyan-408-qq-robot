"""
用户管理模块

提供用户信息管理的高级接口，封装数据库操作和业务逻辑。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import validate_call

from src.core.context import ContextManager
from src.storage import (
    CacheManager,
    Context,
    ContextType,
    DatabaseManager,
    User,
    UserRepository,
)
from src.utils.helpers import IDHelper
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) 用户管理器
# =============================================================================


class UserManager:
    """用户管理器

    提供用户信息的高级管理功能，封装数据库和缓存操作。

    主要功能：
    - 获取和创建用户
    - 更新用户信息
    - 管理用户上下文
    - 更新用户活跃状态
    """

    # I. 初始化
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        context_manager: ContextManager,
    ) -> None:
        """初始化用户管理器

        Args:
            db_manager: 数据库管理器
            cache_manager: 缓存管理器
            context_manager: 上下文管理器
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.context_manager = context_manager
        self.user_repo = UserRepository(db_manager)
        self.user_cache = cache_manager.user

        logger.info("UserManager initialized")

    # II. 用户基本操作
    @validate_call
    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            用户对象，不存在则返回None
        """
        # 从数据库获取
        user = await self.user_repo.get(user_id)
        if user:
            logger.debug(f"User {user_id} found in database")
        return user

    @validate_call
    async def create_user(
        self,
        user_id: str,
        nickname: str = "",
        metadata: Optional[dict] = None,
    ) -> User:
        """创建新用户

        Args:
            user_id: 用户ID
            nickname: 用户昵称
            metadata: 附加元数据

        Returns:
            创建的用户对象
        """
        user = User(
            user_id=user_id,
            nickname=nickname or user_id,
            metadata=metadata or {},
            is_active=True,
            is_banned=False,
        )

        created = await self.user_repo.create(user)

        logger.info(f"Created user: {user_id} ({nickname})")
        return created

    @validate_call
    async def get_or_create_user(
        self,
        user_id: str,
        nickname: str = "",
    ) -> User:
        """获取或创建用户

        如果用户不存在则自动创建。

        Args:
            user_id: 用户ID
            nickname: 用户昵称

        Returns:
            用户对象
        """
        user = await self.get_user(user_id)
        if not user:
            user = await self.create_user(user_id, nickname)
        elif nickname and nickname != user.nickname:
            # 更新昵称
            user.nickname = nickname
            user = await self.update_user(user)

        return user

    @validate_call
    async def update_user(self, user: User) -> User:
        """更新用户信息

        Args:
            user: 用户对象

        Returns:
            更新后的用户对象
        """
        user.last_active = datetime.now()
        updated = await self.user_repo.update(user)

        logger.debug(f"Updated user: {user.user_id}")
        return updated

    async def update_nickname(self, user_id: str, nickname: str) -> bool:
        """更新用户昵称

        Args:
            user_id: 用户ID
            nickname: 新昵称

        Returns:
            是否更新成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.nickname = nickname
        await self.update_user(user)
        return True

    async def ban_user(self, user_id: str) -> bool:
        """封禁用户

        Args:
            user_id: 用户ID

        Returns:
            是否操作成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.is_banned = True
        await self.update_user(user)

        logger.warning(f"Banned user: {user_id}")
        return True

    async def unban_user(self, user_id: str) -> bool:
        """解封用户

        Args:
            user_id: 用户ID

        Returns:
            是否操作成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.is_banned = False
        await self.update_user(user)

        logger.info(f"Unbanned user: {user_id}")
        return True

    async def deactivate_user(self, user_id: str) -> bool:
        """停用用户

        Args:
            user_id: 用户ID

        Returns:
            是否操作成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.is_active = False
        await self.update_user(user)

        logger.info(f"Deactivated user: {user_id}")
        return True

    async def activate_user(self, user_id: str) -> bool:
        """激活用户

        Args:
            user_id: 用户ID

        Returns:
            是否操作成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.is_active = True
        await self.update_user(user)

        logger.info(f"Activated user: {user_id}")
        return True

    # III. 上下文管理
    async def get_user_context(self, user_id: str) -> Optional[Context]:
        """获取用户当前上下文

        Args:
            user_id: 用户ID

        Returns:
            当前上下文对象，不存在则返回None
        """
        user = await self.get_user(user_id)
        if not user or not user.current_context_id:
            return None

        return await self.context_manager.get_context(user.current_context_id)

    async def set_user_context(
        self,
        user_id: str,
        context_id: str,
    ) -> bool:
        """设置用户当前上下文

        Args:
            user_id: 用户ID
            context_id: 上下文ID

        Returns:
            是否设置成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.current_context_id = context_id
        await self.update_user(user)
        return True

    async def clear_user_context(self, user_id: str) -> bool:
        """清除用户当前上下文

        Args:
            user_id: 用户ID

        Returns:
            是否清除成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.current_context_id = None
        await self.update_user(user)
        return True

    async def create_private_context(
        self,
        user_id: str,
        user_name: str = "",
        context_name: str = "",
    ) -> Context:
        """为用户创建私聊上下文

        Args:
            user_id: 用户ID
            user_name: 用户昵称
            context_name: 上下文名称

        Returns:
            创建的上下文对象
        """
        # 确保用户存在
        await self.get_or_create_user(user_id, user_name)

        # 创建上下文
        context = await self.context_manager.create_context(
            context_type=ContextType.PRIVATE,
            creator_id=user_id,
            name=context_name or f"私聊_{user_name or user_id}",
            participants=[user_id],
        )

        # 设置为用户当前上下文
        await self.set_user_context(user_id, context.context_id)

        return context

    # IV. 活跃状态管理
    async def update_last_active(self, user_id: str) -> bool:
        """更新用户最后活跃时间

        Args:
            user_id: 用户ID

        Returns:
            是否更新成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        user.last_active = datetime.now()
        await self.update_user(user)
        return True

    async def get_active_users(self, limit: int = 100) -> list[User]:
        """获取活跃用户列表

        Args:
            limit: 最大返回数量

        Returns:
            活跃用户列表
        """
        # 获取所有用户
        all_users = await self.user_repo.list_all()

        # 过滤活跃用户并按最后活跃时间排序
        active_users = [u for u in all_users if u.is_active and not u.is_banned]
        active_users.sort(key=lambda u: u.last_active, reverse=True)

        return active_users[:limit]

    async def count_active_users(self) -> int:
        """统计活跃用户数量

        Returns:
            活跃用户数量
        """
        active_users = await self.get_active_users()
        return len(active_users)

    # V. 用户信息查询
    async def is_user_active(self, user_id: str) -> bool:
        """检查用户是否活跃

        Args:
            user_id: 用户ID

        Returns:
            用户是否活跃
        """
        user = await self.get_user(user_id)
        return user is not None and user.is_active

    async def is_user_banned(self, user_id: str) -> bool:
        """检查用户是否被封禁

        Args:
            user_id: 用户ID

        Returns:
            用户是否被封禁
        """
        user = await self.get_user(user_id)
        return user is not None and user.is_banned

    async def get_user_metadata(self, user_id: str) -> dict:
        """获取用户元数据

        Args:
            user_id: 用户ID

        Returns:
            用户元数据字典，用户不存在返回空字典
        """
        user = await self.get_user(user_id)
        return user.metadata if user else {}

    async def update_user_metadata(
        self,
        user_id: str,
        metadata: dict,
        merge: bool = True,
    ) -> bool:
        """更新用户元数据

        Args:
            user_id: 用户ID
            metadata: 元数据
            merge: 是否合并（True）还是覆盖（False）

        Returns:
            是否更新成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        if merge:
            user.metadata.update(metadata)
        else:
            user.metadata = metadata

        await self.update_user(user)
        return True


# =============================================================================
# (4) 单例实例
# =============================================================================

_default_user_manager: Optional[UserManager] = None


def get_user_manager(
    db_manager: DatabaseManager,
    cache_manager: CacheManager,
    context_manager: ContextManager,
) -> UserManager:
    """获取默认用户管理器实例

    Args:
        db_manager: 数据库管理器
        cache_manager: 缓存管理器
        context_manager: 上下文管理器

    Returns:
        UserManager实例
    """
    global _default_user_manager
    if _default_user_manager is None:
        _default_user_manager = UserManager(db_manager, cache_manager, context_manager)
    return _default_user_manager


# =============================================================================
# (5) 导出
# =============================================================================

__all__ = [
    # 管理器
    "UserManager",
    "get_user_manager",
]
