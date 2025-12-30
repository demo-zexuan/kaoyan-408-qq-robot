"""
Token控制模块

提供Token配额管理和限流功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pydantic import validate_call

from src.storage import (
    CacheManager,
    DatabaseManager,
    TokenQuota,
    TokenQuotaRepository,
)
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) Token控制器
# =============================================================================


class TokenController:
    """Token控制器

    管理用户Token配额和请求限流。

    主要功能：
    - 检查用户配额
    - 消耗Token
    - 限流检查
    - 重置配额
    """

    # I. 默认配置
    DEFAULT_TOTAL_QUOTA = 50000
    DEFAULT_DAILY_LIMIT = 5000
    DEFAULT_MINUTE_LIMIT = 200

    # II. 初始化
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
    ) -> None:
        """初始化Token控制器

        Args:
            db_manager: 数据库管理器
            cache_manager: 缓存管理器
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.quota_repo = TokenQuotaRepository(db_manager)
        self.token_cache = cache_manager.token

        logger.info("TokenController initialized")

    # III. 配额查询
    @validate_call
    async def get_quota(self, user_id: str) -> TokenQuota:
        """获取用户Token配额

        如果用户配额不存在，则自动创建默认配额。

        Args:
            user_id: 用户ID

        Returns:
            Token配额对象
        """
        quota = await self.quota_repo.get(user_id)
        if not quota:
            quota = await self._create_default_quota(user_id)
        else:
            # 检查是否需要重置每日配额
            quota = await self._check_and_reset_daily(quota)

        return quota

    async def get_remaining_quota(self, user_id: str) -> int:
        """获取用户剩余配额

        Args:
            user_id: 用户ID

        Returns:
            剩余Token数量
        """
        quota = await self.get_quota(user_id)
        return quota.remaining

    async def get_daily_remaining(self, user_id: str) -> int:
        """获取用户今日剩余配额

        Args:
            user_id: 用户ID

        Returns:
            今日剩余Token数量
        """
        quota = await self.get_quota(user_id)
        return quota.daily_remaining

    async def get_usage_info(self, user_id: str) -> dict:
        """获取用户使用情况

        Args:
            user_id: 用户ID

        Returns:
            使用信息字典
        """
        quota = await self.get_quota(user_id)
        return {
            "user_id": user_id,
            "total_quota": quota.total_quota,
            "used": quota.used,
            "remaining": quota.remaining,
            "daily_limit": quota.daily_limit,
            "daily_used": quota.daily_used,
            "daily_remaining": quota.daily_remaining,
            "minute_limit": quota.minute_limit,
            "is_minute_exceeded": quota.is_minute_limit_exceeded,
        }

    # IV. 配额检查
    async def check_quota(self, user_id: str, tokens: int = 0) -> tuple[bool, str]:
        """检查用户配额是否足够

        Args:
            user_id: 用户ID
            tokens: 需要的Token数量

        Returns:
            (是否足够, 错误信息) 元组
        """
        quota = await self.get_quota(user_id)

        # 检查总配额
        if quota.remaining < tokens:
            return False, f"配额不足，剩余 {quota.remaining} Token"

        # 检查每日配额
        if quota.daily_remaining < tokens:
            return False, f"今日配额不足，剩余 {quota.daily_remaining} Token"

        # 检查每分钟限制
        if quota.is_minute_limit_exceeded:
            return False, "请求过于频繁，请稍后再试"

        return True, ""

    async def check_minute_limit(self, user_id: str) -> bool:
        """检查分钟限制

        Args:
            user_id: 用户ID

        Returns:
            是否超过限制
        """
        quota = await self.get_quota(user_id)
        return not quota.is_minute_limit_exceeded

    async def check_daily_limit(self, user_id: str) -> bool:
        """检查每日限制

        Args:
            user_id: 用户ID

        Returns:
            是否超过限制
        """
        quota = await self.get_quota(user_id)
        return quota.daily_remaining > 0

    # V. Token消耗
    @validate_call
    async def consume(self, user_id: str, tokens: int) -> bool:
        """消耗Token

        Args:
            user_id: 用户ID
            tokens: 消耗的Token数量

        Returns:
            是否成功消耗
        """
        # 先检查配额
        can_consume, error_msg = await self.check_quota(user_id, tokens)
        if not can_consume:
            logger.warning(f"Token consume failed for {user_id}: {error_msg}")
            return False

        # 消耗Token并记录请求
        quota = await self.quota_repo.increment_used(user_id, tokens)

        # 记录请求时间戳（使用更新后的quota）
        await self._record_request(quota)

        # 更新缓存
        # Token缓存暂不使用

        logger.debug(f"Consumed {tokens} tokens for {user_id}")
        return True

    # VI. 配额管理
    async def add_quota(self, user_id: str, amount: int) -> bool:
        """增加用户配额

        Args:
            user_id: 用户ID
            amount: 增加的数量

        Returns:
            是否成功
        """
        quota = await self.get_quota(user_id)
        quota.total_quota += amount
        await self.quota_repo.update(quota)
        # Token缓存暂不使用

        logger.info(f"Added {amount} quota for {user_id}")
        return True

    async def reset_user(self, user_id: str) -> bool:
        """重置用户使用记录

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        quota = await self.get_quota(user_id)
        quota.used = 0
        quota.daily_used = 0
        quota.minute_requests = []

        await self.quota_repo.update(quota)
        # Token缓存暂不使用

        logger.info(f"Reset quota for {user_id}")
        return True

    async def reset_daily(self, user_id: str) -> bool:
        """重置用户每日配额

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        quota = await self.get_quota(user_id)
        quota = await self.quota_repo.reset_daily(user_id)
        # Token缓存暂不使用

        logger.info(f"Reset daily quota for {user_id}")
        return True

    async def set_daily_limit(self, user_id: str, limit: int) -> bool:
        """设置用户每日限制

        Args:
            user_id: 用户ID
            limit: 每日限制

        Returns:
            是否成功
        """
        quota = await self.get_quota(user_id)
        quota.daily_limit = limit
        await self.quota_repo.update(quota)
        # Token缓存暂不使用

        logger.info(f"Set daily limit {limit} for {user_id}")
        return True

    async def set_minute_limit(self, user_id: str, limit: int) -> bool:
        """设置用户每分钟限制

        Args:
            user_id: 用户ID
            limit: 每分钟限制

        Returns:
            是否成功
        """
        quota = await self.get_quota(user_id)
        quota.minute_limit = limit
        await self.quota_repo.update(quota)
        # Token缓存暂不使用

        logger.info(f"Set minute limit {limit} for {user_id}")
        return True

    # VII. 私有方法
    async def _create_default_quota(self, user_id: str) -> TokenQuota:
        """创建默认配额

        Args:
            user_id: 用户ID

        Returns:
            Token配额对象
        """
        now = datetime.now()
        tomorrow = now + timedelta(days=1)

        quota = TokenQuota(
            user_id=user_id,
            total_quota=self.DEFAULT_TOTAL_QUOTA,
            used=0,
            daily_limit=self.DEFAULT_DAILY_LIMIT,
            daily_used=0,
            daily_reset=tomorrow,
            minute_limit=self.DEFAULT_MINUTE_LIMIT,
            minute_requests=[],
        )

        created = await self.quota_repo.create(quota)
        # Token缓存暂不使用

        logger.info(f"Created default quota for {user_id}")
        return created

    async def _check_and_reset_daily(self, quota: TokenQuota) -> TokenQuota:
        """检查并重置每日配额

        Args:
            quota: Token配额对象

        Returns:
            更新后的配额对象
        """
        now = datetime.now()

        # 如果已过重置时间，重置每日配额
        if now >= quota.daily_reset:
            quota = await self.quota_repo.reset_daily(quota.user_id)
            # Token缓存暂不使用
            logger.info(f"Daily quota reset for {quota.user_id}")

        return quota

    async def _record_request(self, quota: TokenQuota) -> None:
        """记录请求时间戳

        Args:
            quota: Token配额对象
        """
        now = datetime.now()
        # 清理超过1分钟的记录
        quota.minute_requests = [
            ts for ts in quota.minute_requests if (now - ts).total_seconds() < 60
        ]
        # 添加当前请求
        quota.minute_requests.append(now)
        await self.quota_repo.update(quota)

    @staticmethod
    def _check_minute_limit(quota: TokenQuota) -> bool:
        """检查每分钟限制（同步版本）

        Args:
            quota: Token配额对象

        Returns:
            是否未超过限制
        """
        now = datetime.now()
        # 过滤1分钟内的请求
        recent = [ts for ts in quota.minute_requests if (now - ts).total_seconds() < 60]
        return len(recent) < quota.minute_limit

    @staticmethod
    def _check_daily_limit(quota: TokenQuota) -> bool:
        """检查每日限制（同步版本）

        Args:
            quota: Token配额对象

        Returns:
            是否未超过限制
        """
        return quota.daily_remaining > 0


# =============================================================================
# (4) 单例实例
# =============================================================================

_default_token_controller: Optional[TokenController] = None


def get_token_controller(
    db_manager: DatabaseManager,
    cache_manager: CacheManager,
) -> TokenController:
    """获取默认Token控制器实例

    Args:
        db_manager: 数据库管理器
        cache_manager: 缓存管理器

    Returns:
        TokenController实例
    """
    global _default_token_controller
    if _default_token_controller is None:
        _default_token_controller = TokenController(db_manager, cache_manager)
    return _default_token_controller


# =============================================================================
# (5) 导出
# =============================================================================

__all__ = [
    # 控制器
    "TokenController",
    "get_token_controller",
]
