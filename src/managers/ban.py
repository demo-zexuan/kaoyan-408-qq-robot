"""
封禁管理模块

提供用户封禁和异常行为检测功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pydantic import validate_call

from src.storage import (
    BanReason,
    BanRecord,
    BanRecordRepository,
    BanType,
    CacheManager,
    DatabaseManager,
    UserRepository,
)
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) 检测规则配置
# =============================================================================

# 默认检测规则配置
DEFAULT_DETECTION_RULES = {
    # 短时间大量请求检测
    "rapid_request_threshold": 10,  # 10次请求
    "rapid_request_window": 60,     # 60秒内

    # Token消耗异常检测
    "token_burst_threshold": 1000,  # 单次1000 token
    "token_rate_threshold": 5000,   # 每分钟5000 token

    # 刷屏检测
    "spam_message_threshold": 5,    # 5条消息
    "spam_window": 10,              # 10秒内

    # 重复内容检测
    "repeat_threshold": 3,          # 3次重复
    "repeat_window": 30,            # 30秒内
}


# =============================================================================
# (4) 封禁管理器
# =============================================================================

class BanManager:
    """封禁管理器

    管理用户封禁状态和异常行为检测。

    主要功能：
    - 检查用户封禁状态
    - 封禁/解封用户
    - 异常行为检测
    - 自动封禁触发
    """

    # I. 初始化
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        detection_rules: Optional[dict] = None,
    ) -> None:
        """初始化封禁管理器

        Args:
            db_manager: 数据库管理器
            cache_manager: 缓存管理器
            detection_rules: 自定义检测规则
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.ban_repo = BanRecordRepository(db_manager)
        self.user_repo = UserRepository(db_manager)
        self.ban_cache = cache_manager.ban

        # 合并检测规则
        self.detection_rules = DEFAULT_DETECTION_RULES.copy()
        if detection_rules:
            self.detection_rules.update(detection_rules)

        # 用户行为追踪 (内存存储，生产环境可用Redis)
        self._user_requests: dict[str, list[datetime]] = {}
        self._user_messages: dict[str, list[datetime]] = {}
        self._user_content: dict[str, list[tuple[datetime, str]]] = {}

        logger.info("BanManager initialized")

    # II. 封禁状态检查
    @validate_call
    async def check_ban_status(self, user_id: str) -> Optional[BanRecord]:
        """检查用户封禁状态

        Args:
            user_id: 用户ID

        Returns:
            有效的封禁记录，未封禁则返回None
        """
        # 从数据库获取
        record = await self.ban_repo.get_active_ban(user_id)
        if record and record.is_active:
            return record

        return None

    async def is_banned(self, user_id: str) -> bool:
        """检查用户是否被封禁

        Args:
            user_id: 用户ID

        Returns:
            用户是否被封禁
        """
        record = await self.check_ban_status(user_id)
        return record is not None

    async def get_ban_reason(self, user_id: str) -> Optional[str]:
        """获取用户封禁原因

        Args:
            user_id: 用户ID

        Returns:
            封禁原因，未封禁则返回None
        """
        record = await self.check_ban_status(user_id)
        if record:
            return record.details or record.reason.value
        return None

    async def get_remaining_ban_time(self, user_id: str) -> Optional[int]:
        """获取剩余封禁时间（秒）

        Args:
            user_id: 用户ID

        Returns:
            剩余秒数，永久封禁返回None
        """
        record = await self.check_ban_status(user_id)
        if record:
            return record.remaining_seconds
        return None

    # III. 封禁操作
    @validate_call
    async def ban_user(
        self,
        user_id: str,
        reason: BanReason,
        ban_type: BanType = BanType.TEMPORARY,
        duration_hours: Optional[int] = 1,
        details: str = "",
    ) -> BanRecord:
        """封禁用户

        Args:
            user_id: 用户ID
            reason: 封禁原因
            ban_type: 封禁类型
            duration_hours: 封禁时长（小时），仅对临时封禁有效
            details: 详细信息

        Returns:
            创建的封禁记录
        """
        now = datetime.now()
        expires_at = None

        if ban_type == BanType.TEMPORARY:
            if duration_hours is None:
                duration_hours = 1
            expires_at = now + timedelta(hours=duration_hours)

        # 创建封禁记录
        record = BanRecord(
            user_id=user_id,
            reason=reason,
            ban_type=ban_type,
            started_at=now,
            expires_at=expires_at,
            details=details,
        )

        created = await self.ban_repo.create(record)

        # 更新用户状态
        user = await self.user_repo.get(user_id)
        if user:
            user.is_banned = True
            await self.user_repo.update(user)

        # Ban缓存暂不使用

        # 清除用户行为追踪
        self._clear_user_tracking(user_id)

        logger.warning(f"Banned user {user_id}: {reason.value} ({ban_type.value})")
        return created

    @validate_call
    async def unban_user(self, user_id: str) -> bool:
        """解封用户

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        # 获取活跃封禁记录
        record = await self.ban_repo.get_active_ban(user_id)
        if not record:
            return False

        # 对于临时封禁，通过设置过期时间来解封
        # 对于永久封禁，需要另外处理（这里简化为设置过期时间）
        record.expires_at = datetime.now()
        await self.ban_repo.update(record)

        # 更新用户状态
        user = await self.user_repo.get(user_id)
        if user:
            user.is_banned = False
            await self.user_repo.update(user)

        # Ban缓存暂不使用

        logger.info(f"Unbanned user: {user_id}")
        return True

    async def ban_user_for_spam(
        self,
        user_id: str,
        duration_hours: int = 1,
    ) -> BanRecord:
        """封禁刷屏用户

        Args:
            user_id: 用户ID
            duration_hours: 封禁时长（小时）

        Returns:
            创建的封禁记录
        """
        return await self.ban_user(
            user_id=user_id,
            reason=BanReason.SPAMMING,
            ban_type=BanType.TEMPORARY,
            duration_hours=duration_hours,
            details="检测到刷屏行为",
        )

    async def ban_user_for_abuse(
        self,
        user_id: str,
        duration_hours: int = 24,
    ) -> BanRecord:
        """封禁滥用用户

        Args:
            user_id: 用户ID
            duration_hours: 封禁时长（小时）

        Returns:
            创建的封禁记录
        """
        return await self.ban_user(
            user_id=user_id,
            reason=BanReason.MALICIOUS_BEHAVIOR,
            ban_type=BanType.TEMPORARY,
            duration_hours=duration_hours,
            details="检测到恶意滥用行为",
        )

    async def ban_user_permanently(
        self,
        user_id: str,
        reason: BanReason,
        details: str = "",
    ) -> BanRecord:
        """永久封禁用户

        Args:
            user_id: 用户ID
            reason: 封禁原因
            details: 详细信息

        Returns:
            创建的封禁记录
        """
        return await self.ban_user(
            user_id=user_id,
            reason=reason,
            ban_type=BanType.PERMANENT,
            details=details,
        )

    # IV. 异常行为检测
    async def detect_abuse(
        self,
        user_id: str,
        message_content: str = "",
        tokens_used: int = 0,
    ) -> tuple[bool, Optional[str]]:
        """检测异常行为

        Args:
            user_id: 用户ID
            message_content: 消息内容
            tokens_used: 使用的Token数量

        Returns:
            (是否异常, 异常原因) 元组
        """
        now = datetime.now()

        # 1. 检测短时间大量请求
        if await self._detect_rapid_requests(user_id, now):
            return True, "请求过于频繁"

        # 2. 检测Token消耗异常
        if tokens_used > 0:
            if await self._detect_token_abuse(user_id, tokens_used, now):
                return True, "Token消耗异常"

        # 3. 检测刷屏
        if message_content:
            if await self._detect_spam(user_id, message_content, now):
                return True, "检测到刷屏行为"

            # 4. 检测重复内容
            if await self._detect_repeated_content(user_id, message_content, now):
                return True, "发送重复内容"

        return False, None

    async def _detect_rapid_requests(
        self,
        user_id: str,
        now: datetime,
    ) -> bool:
        """检测短时间大量请求

        Args:
            user_id: 用户ID
            now: 当前时间

        Returns:
            是否异常
        """
        if user_id not in self._user_requests:
            self._user_requests[user_id] = []

        # 清理过期记录
        window = self.detection_rules["rapid_request_window"]
        threshold = self.detection_rules["rapid_request_threshold"]

        self._user_requests[user_id] = [
            ts for ts in self._user_requests[user_id]
            if (now - ts).total_seconds() < window
        ]

        # 记录当前请求
        self._user_requests[user_id].append(now)

        return len(self._user_requests[user_id]) > threshold

    async def _detect_token_abuse(
        self,
        user_id: str,
        tokens_used: int,
        now: datetime,
    ) -> bool:
        """检测Token消耗异常

        Args:
            user_id: 用户ID
            tokens_used: 使用的Token数量
            now: 当前时间

        Returns:
            是否异常
        """
        # 单次Token消耗异常
        burst_threshold = self.detection_rules["token_burst_threshold"]
        if tokens_used > burst_threshold:
            logger.warning(
                f"Token burst detected for {user_id}: {tokens_used} tokens"
            )
            return True

        # TODO: 实现每分钟Token消耗速率检测
        return False

    async def _detect_spam(
        self,
        user_id: str,
        message_content: str,
        now: datetime,
    ) -> bool:
        """检测刷屏行为

        Args:
            user_id: 用户ID
            message_content: 消息内容
            now: 当前时间

        Returns:
            是否异常
        """
        if user_id not in self._user_messages:
            self._user_messages[user_id] = []

        # 清理过期记录
        window = self.detection_rules["spam_window"]
        threshold = self.detection_rules["spam_message_threshold"]

        self._user_messages[user_id] = [
            ts for ts in self._user_messages[user_id]
            if (now - ts).total_seconds() < window
        ]

        # 记录当前消息
        self._user_messages[user_id].append(now)

        return len(self._user_messages[user_id]) > threshold

    async def _detect_repeated_content(
        self,
        user_id: str,
        content: str,
        now: datetime,
    ) -> bool:
        """检测重复内容

        Args:
            user_id: 用户ID
            content: 消息内容
            now: 当前时间

        Returns:
            是否异常
        """
        if not content:
            return False

        if user_id not in self._user_content:
            self._user_content[user_id] = []

        # 清理过期记录
        window = self.detection_rules["repeat_window"]
        threshold = self.detection_rules["repeat_threshold"]

        self._user_content[user_id] = [
            (ts, cnt) for ts, cnt in self._user_content[user_id]
            if (now - ts).total_seconds() < window
        ]

        # 检查是否有重复内容
        content_count = sum(
            1 for _, cnt in self._user_content[user_id]
            if cnt == content
        )

        # 记录当前内容
        self._user_content[user_id].append((now, content))

        return content_count >= threshold

    # V. 记录管理
    async def list_ban_records(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[BanRecord]:
        """列出用户封禁记录

        Args:
            user_id: 用户ID
            limit: 最大返回数量

        Returns:
            封禁记录列表
        """
        records = await self.ban_repo.list_by_user(user_id)
        return records[:limit]

    async def get_all_active_bans(self) -> list[BanRecord]:
        """获取所有活跃封禁

        Returns:
            活跃封禁记录列表
        """
        # TODO: 需要在BanRecordRepository中实现相应方法
        all_records = await self.ban_repo.list_all()
        return [r for r in all_records if r.is_active]

    # VI. 私有方法
    def _clear_user_tracking(self, user_id: str) -> None:
        """清除用户行为追踪

        Args:
            user_id: 用户ID
        """
        self._user_requests.pop(user_id, None)
        self._user_messages.pop(user_id, None)
        self._user_content.pop(user_id, None)

    def cleanup_tracking(self, before: datetime) -> None:
        """清理过期追踪数据

        Args:
            before: 清理此时间之前的数据
        """
        for user_id in list(self._user_requests.keys()):
            self._user_requests[user_id] = [
                ts for ts in self._user_requests.get(user_id, [])
                if ts > before
            ]
            if not self._user_requests[user_id]:
                del self._user_requests[user_id]

        # 类似清理其他追踪数据
        # ...


# =============================================================================
# (7) 单例实例
# =============================================================================

_default_ban_manager: Optional[BanManager] = None


def get_ban_manager(
    db_manager: DatabaseManager,
    cache_manager: CacheManager,
    detection_rules: Optional[dict] = None,
) -> BanManager:
    """获取默认封禁管理器实例

    Args:
        db_manager: 数据库管理器
        cache_manager: 缓存管理器
        detection_rules: 自定义检测规则

    Returns:
        BanManager实例
    """
    global _default_ban_manager
    if _default_ban_manager is None:
        _default_ban_manager = BanManager(db_manager, cache_manager, detection_rules)
    return _default_ban_manager


# =============================================================================
# (8) 导出
# =============================================================================

__all__ = [
    # 配置
    "DEFAULT_DETECTION_RULES",
    # 管理器
    "BanManager",
    "get_ban_manager",
]
