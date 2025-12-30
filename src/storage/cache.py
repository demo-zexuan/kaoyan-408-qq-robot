"""
Redis缓存操作模块

提供Redis缓存的连接管理和操作功能。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool

from src.utils.config import get_config

from src.storage.models import (
    BanRecord,
    BanReason,
    BanType,
    ChatMessage,
    Context,
    ContextStatus,
    ContextType,
    MessageType,
    RolePlayConfig,
    RobotState,
    TokenQuota,
    User,
)


# ==============================================================================
# (2) Redis管理器
# ==============================================================================


class RedisManager:
    """Redis管理器

    提供Redis连接管理和基础操作功能。
    """

    # I. 初始化
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 10,
    ) -> None:
        """初始化Redis管理器

        Args:
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库编号
            password: Redis密码
            max_connections: 最大连接数
        """
        self.host: str = host
        self.port: int = port
        self.db: int = db
        self.password: Optional[str] = password
        self.max_connections: int = max_connections

        self._pool: Optional[ConnectionPool] = None

    # II. 连接管理
    async def connect(self) -> aioredis.Redis:
        """建立Redis连接池

        Returns:
            aioredis.Redis: Redis客户端对象
        """
        if self._pool is None:
            self._pool = ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=True,
            )
        return aioredis.Redis(connection_pool=self._pool)

    async def disconnect(self) -> None:
        """关闭Redis连接池"""
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    async def get_client(self) -> aioredis.Redis:
        """获取Redis客户端

        Returns:
            aioredis.Redis: Redis客户端对象
        """
        return await self.connect()

    async def ping(self) -> bool:
        """检查Redis连接状态

        Returns:
            bool: 连接正常返回True
        """
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception:
            return False


# ==============================================================================
# (3) 上下文缓存
# ==============================================================================


class ContextCache:
    """上下文缓存

    提供上下文的Redis缓存操作。
    """

    # I. 键前缀
    KEY_PREFIX: str = "ctx"
    TTL_SECONDS: int = 86400  # 24小时

    # II. 初始化
    def __init__(self, redis_manager: RedisManager) -> None:
        """初始化上下文缓存

        Args:
            redis_manager: Redis管理器实例
        """
        self.redis: RedisManager = redis_manager

    # III. 操作方法
    def _make_key(self, context_id: str) -> str:
        """生成缓存键"""
        return f"{self.KEY_PREFIX}:{context_id}"

    async def get(self, context_id: str) -> Optional[Context]:
        """获取上下文

        Args:
            context_id: 上下文ID

        Returns:
            Optional[Context]: 上下文对象，不存在则返回None
        """
        client = await self.redis.get_client()
        key = self._make_key(context_id)
        data = await client.get(key)

        if data is None:
            return None

        return self._deserialize(data)

    async def set(self, context: Context, ttl: Optional[int] = None) -> None:
        """保存上下文

        Args:
            context: 上下文对象
            ttl: 过期时间(秒)，默认使用类默认值
        """
        client = await self.redis.get_client()
        key = self._make_key(context.context_id)
        data = self._serialize(context)
        ttl = ttl or self.TTL_SECONDS
        await client.setex(key, ttl, data)

    async def delete(self, context_id: str) -> None:
        """删除上下文

        Args:
            context_id: 上下文ID
        """
        client = await self.redis.get_client()
        key = self._make_key(context_id)
        await client.delete(key)

    async def exists(self, context_id: str) -> bool:
        """检查上下文是否存在

        Args:
            context_id: 上下文ID

        Returns:
            bool: 存在返回True
        """
        client = await self.redis.get_client()
        key = self._make_key(context_id)
        return await client.exists(key) > 0

    async def set_expire(self, context_id: str, seconds: int) -> None:
        """设置上下文过期时间

        Args:
            context_id: 上下文ID
            seconds: 过期秒数
        """
        client = await self.redis.get_client()
        key = self._make_key(context_id)
        await client.expire(key, seconds)

    async def get_ttl(self, context_id: str) -> int:
        """获取上下文剩余生存时间

        Args:
            context_id: 上下文ID

        Returns:
            int: 剩余秒数，-1表示永不过期，-2表示不存在
        """
        client = await self.redis.get_client()
        key = self._make_key(context_id)
        return await client.ttl(key)

    # IV. 序列化方法
    @staticmethod
    def _serialize(context: Context) -> str:
        """序列化上下文对象"""
        # 序列化消息列表，处理datetime字段
        serialized_messages = []
        for msg in context.messages:
            msg_dict = msg.model_dump()
            # 转换datetime为ISO格式字符串
            if "timestamp" in msg_dict and msg_dict["timestamp"]:
                msg_dict["timestamp"] = msg_dict["timestamp"].isoformat()
            serialized_messages.append(msg_dict)

        return json.dumps(
            {
                "context_id": context.context_id,
                "type": context.type.value,
                "name": context.name,
                "creator_id": context.creator_id,
                "participants": context.participants,
                "status": context.status.value,
                "state": context.state.model_dump() if context.state else None,
                "metadata": context.metadata,
                "created_at": context.created_at.isoformat(),
                "updated_at": context.updated_at.isoformat(),
                "expires_at": (
                    context.expires_at.isoformat() if context.expires_at else None
                ),
                "messages": serialized_messages,
                "max_messages": context.max_messages,
            }
        )

    @staticmethod
    def _deserialize(data: str) -> Context:
        """反序列化上下文对象"""
        obj = json.loads(data)
        return Context(
            context_id=obj["context_id"],
            type=ContextType(obj["type"]),
            name=obj.get("name", ""),
            creator_id=obj["creator_id"],
            participants=obj.get("participants", []),
            status=ContextStatus(obj.get("status", "active")),
            state=RobotState(**obj["state"]) if obj.get("state") else None,
            metadata=obj.get("metadata", {}),
            created_at=datetime.fromisoformat(obj["created_at"]),
            updated_at=datetime.fromisoformat(obj["updated_at"]),
            expires_at=(
                datetime.fromisoformat(obj["expires_at"])
                if obj.get("expires_at")
                else None
            ),
            messages=[ChatMessage(**msg) for msg in obj.get("messages", [])],
            max_messages=obj.get("max_messages", 200),
        )


# ==============================================================================
# (4) 用户状态缓存
# ==============================================================================


class UserCache:
    """用户状态缓存

    提供用户状态的Redis缓存操作，用于快速访问用户当前状态。
    """

    # I. 键前缀
    KEY_PREFIX: str = "user"
    TTL_SECONDS: int = 3600  # 1小时

    # II. 初始化
    def __init__(self, redis_manager: RedisManager) -> None:
        """初始化用户缓存

        Args:
            redis_manager: Redis管理器实例
        """
        self.redis: RedisManager = redis_manager

    # III. 操作方法
    def _make_key(self, user_id: str) -> str:
        """生成缓存键"""
        return f"{self.KEY_PREFIX}:{user_id}"

    async def get_current_context(self, user_id: str) -> Optional[str]:
        """获取用户当前上下文ID

        Args:
            user_id: 用户ID

        Returns:
            Optional[str]: 上下文ID，无则返回None
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        return await client.hget(key, "current_context_id")

    async def set_current_context(
        self, user_id: str, context_id: Optional[str]
    ) -> None:
        """设置用户当前上下文ID

        Args:
            user_id: 用户ID
            context_id: 上下文ID，None表示清除
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        if context_id:
            await client.hset(key, "current_context_id", context_id)
            await client.expire(key, self.TTL_SECONDS)
        else:
            await client.hdel(key, "current_context_id")

    async def get_ban_status(self, user_id: str) -> bool:
        """检查用户是否被封禁

        Args:
            user_id: 用户ID

        Returns:
            bool: 被封禁返回True
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        value = await client.hget(key, "is_banned")
        return value == "1" if value else False

    async def set_ban_status(self, user_id: str, is_banned: bool) -> None:
        """设置用户封禁状态

        Args:
            user_id: 用户ID
            is_banned: 是否被封禁
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        await client.hset(key, "is_banned", "1" if is_banned else "0")
        await client.expire(key, self.TTL_SECONDS)

    async def update_last_active(self, user_id: str) -> None:
        """更新用户最后活跃时间

        Args:
            user_id: 用户ID
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        await client.hset(key, "last_active", datetime.now().isoformat())
        await client.expire(key, self.TTL_SECONDS)


# ==============================================================================
# (5) Token配额缓存
# ==============================================================================


class TokenCache:
    """Token配额缓存

    提供Token使用情况的Redis缓存操作，用于实时监控和限流。
    """

    # I. 键前缀
    QUOTA_PREFIX: str = "quota"
    MINUTE_WINDOW_PREFIX: str = "rate"

    # II. 初始化
    def __init__(self, redis_manager: RedisManager) -> None:
        """初始化Token缓存

        Args:
            redis_manager: Redis管理器实例
        """
        self.redis: RedisManager = redis_manager

    # III. 配额操作
    def _make_quota_key(self, user_id: str) -> str:
        """生成配额缓存键"""
        return f"{self.QUOTA_PREFIX}:{user_id}"

    async def get_quota(self, user_id: str) -> Optional[dict[str, Any]]:
        """获取用户配额信息

        Args:
            user_id: 用户ID

        Returns:
            Optional[dict]: 配额信息字典，不存在返回None
        """
        client = await self.redis.get_client()
        key = self._make_quota_key(user_id)
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_quota(
        self, user_id: str, quota: TokenQuota, ttl: int = 86400
    ) -> None:
        """保存用户配额信息

        Args:
            user_id: 用户ID
            quota: Token配额对象
            ttl: 过期时间(秒)
        """
        client = await self.redis.get_client()
        key = self._make_quota_key(user_id)
        data = {
            "user_id": quota.user_id,
            "total_quota": quota.total_quota,
            "used": quota.used,
            "daily_limit": quota.daily_limit,
            "daily_used": quota.daily_used,
            "daily_reset": quota.daily_reset.isoformat(),
        }
        await client.setex(key, ttl, json.dumps(data))

    async def increment_used(self, user_id: str, tokens: int) -> int:
        """增加已使用Token数

        Args:
            user_id: 用户ID
            tokens: 增加的Token数

        Returns:
            int: 增加后的已使用Token数
        """
        client = await self.redis.get_client()
        key = self._make_quota_key(user_id)
        result = await client.hincrby(key, "used", tokens)
        await client.expire(key, 86400)
        return result

    async def increment_daily_used(self, user_id: str, tokens: int) -> int:
        """增加今日已使用Token数

        Args:
            user_id: 用户ID
            tokens: 增加的Token数

        Returns:
            int: 增加后的今日已使用Token数
        """
        client = await self.redis.get_client()
        key = self._make_quota_key(user_id)
        result = await client.hincrby(key, "daily_used", tokens)
        await client.expire(key, 86400)
        return result

    # IV. 速率限制操作
    def _make_rate_key(self, user_id: str) -> str:
        """生成速率限制键"""
        return f"{self.MINUTE_WINDOW_PREFIX}:{user_id}"

    async def add_minute_request(self, user_id: str) -> int:
        """记录一分钟内的请求

        Args:
            user_id: 用户ID

        Returns:
            int: 当前分钟内的请求数
        """
        client = await self.redis.get_client()
        key = self._make_rate_key(user_id)
        now = datetime.now().timestamp()
        # 使用有序集合存储请求时间戳
        await client.zadd(key, {str(now): now})
        await client.expire(key, 60)
        # 移除60秒前的记录
        min_score = now - 60
        await client.zremrangebyscore(key, 0, min_score)
        # 返回当前计数
        return await client.zcard(key)

    async def get_minute_count(self, user_id: str) -> int:
        """获取一分钟内的请求数

        Args:
            user_id: 用户ID

        Returns:
            int: 当前分钟内的请求数
        """
        client = await self.redis.get_client()
        key = self._make_rate_key(user_id)
        now = datetime.now().timestamp()
        # 移除过期的记录
        min_score = now - 60
        await client.zremrangebyscore(key, 0, min_score)
        return await client.zcard(key)

    async def reset_minute_count(self, user_id: str) -> None:
        """重置一分钟内的请求数

        Args:
            user_id: 用户ID
        """
        client = await self.redis.get_client()
        key = self._make_rate_key(user_id)
        await client.delete(key)


# ==============================================================================
# (6) 封禁记录缓存
# ==============================================================================


class BanCache:
    """封禁记录缓存

    提供封禁状态的快速查询缓存。
    """

    # I. 键前缀
    KEY_PREFIX: str = "ban"

    # II. 初始化
    def __init__(self, redis_manager: RedisManager) -> None:
        """初始化封禁缓存

        Args:
            redis_manager: Redis管理器实例
        """
        self.redis: RedisManager = redis_manager

    # III. 操作方法
    def _make_key(self, user_id: str) -> str:
        """生成缓存键"""
        return f"{self.KEY_PREFIX}:{user_id}"

    async def get_active_ban(self, user_id: str) -> Optional[dict[str, Any]]:
        """获取用户的有效封禁记录

        Args:
            user_id: 用户ID

        Returns:
            Optional[dict]: 封禁记录字典，无有效封禁返回None
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        data = await client.get(key)

        if data is None:
            return None

        ban_data = json.loads(data)
        # 检查是否过期
        expires_at = ban_data.get("expires_at")
        if expires_at:
            expire_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expire_time:
                await self.delete(user_id)
                return None

        return ban_data

    async def set_ban(self, ban_record: BanRecord, ttl: Optional[int] = None) -> None:
        """设置封禁记录

        Args:
            ban_record: 封禁记录对象
            ttl: 过期时间(秒)，None表示永不过期
        """
        client = await self.redis.get_client()
        key = self._make_key(ban_record.user_id)

        data = {
            "user_id": ban_record.user_id,
            "reason": ban_record.reason.value,
            "ban_type": ban_record.ban_type.value,
            "started_at": ban_record.started_at.isoformat(),
            "expires_at": (
                ban_record.expires_at.isoformat() if ban_record.expires_at else None
            ),
            "details": ban_record.details,
        }

        if ttl:
            await client.setex(key, ttl, json.dumps(data))
        else:
            await client.set(key, json.dumps(data))

    async def delete(self, user_id: str) -> None:
        """删除封禁记录

        Args:
            user_id: 用户ID
        """
        client = await self.redis.get_client()
        key = self._make_key(user_id)
        await client.delete(key)

    async def is_banned(self, user_id: str) -> bool:
        """检查用户是否被封禁

        Args:
            user_id: 用户ID

        Returns:
            bool: 被封禁返回True
        """
        return await self.get_active_ban(user_id) is not None


# ==============================================================================
# (7) 统一缓存管理器
# ==============================================================================


class CacheManager:
    """统一缓存管理器

    提供对所有缓存类型的访问接口。
    """

    # I. 初始化
    def __init__(self, redis_manager: RedisManager) -> None:
        """初始化缓存管理器

        Args:
            redis_manager: Redis管理器实例
        """
        self.redis_manager: RedisManager = redis_manager
        self.context: ContextCache = ContextCache(redis_manager)
        self.user: UserCache = UserCache(redis_manager)
        self.token: TokenCache = TokenCache(redis_manager)
        self.ban: BanCache = BanCache(redis_manager)

    # II. 连接管理
    async def connect(self) -> None:
        """建立连接"""
        await self.redis_manager.connect()

    async def disconnect(self) -> None:
        """断开连接"""
        await self.redis_manager.disconnect()

    async def ping(self) -> bool:
        """检查连接状态"""
        return await self.redis_manager.ping()


# ==============================================================================
# (8) 单例实例
# ==============================================================================

_default_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器单例

    从配置中读取Redis连接参数，首次调用时创建实例。

    Returns:
        CacheManager: 缓存管理器实例

    Examples:
        >>> cache_mgr = get_cache_manager()
        >>> await cache_mgr.connect()
    """
    global _default_cache_manager
    if _default_cache_manager is None:
        config = get_config()
        redis_manager = RedisManager(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password,
            max_connections=config.redis_max_connections,
        )
        _default_cache_manager = CacheManager(redis_manager)
    return _default_cache_manager


# ==============================================================================
# (9) 导出
# ==============================================================================

__all__ = [
    # Redis管理器
    "RedisManager",
    # 缓存类
    "ContextCache",
    "UserCache",
    "TokenCache",
    "BanCache",
    # 统一管理器
    "CacheManager",
    "get_cache_manager",
]
