"""
存储模块初始化

提供数据库和缓存的访问接口。
"""

# Cache
from src.storage.cache import (
    BanCache,
    CacheManager,
    ContextCache,
    RedisManager,
    TokenCache,
    UserCache,
    get_cache_manager,
)

# Database
from src.storage.database import (
    BanRecordRepository,
    ContextRepository,
    DatabaseManager,
    RoleConfigRepository,
    TokenQuotaRepository,
    UserRepository,
    get_database_manager,
)

# ORM Models
from src.storage.orm_models import (
    BanReason,
    BanRecordORM,
    BanType,
    Base,
    ContextORM,
    ContextStatus,
    ContextType,
    IntentType,
    MessageORM,
    MessageRole,
    MessageType,
    RoleConfigORM,
    TokenQuotaORM,
    UserORM,
)

# Pydantic Models
from src.storage.models import (
    BanRecord,
    ChatMessage,
    Context,
    Intent,
    MessageRole,
    RobotState,
    RolePlayConfig,
    TokenQuota,
    User,
)

__all__ = [
    # Pydantic Models (业务模型)
    "User",
    "Context",
    "ChatMessage",
    "RobotState",
    "TokenQuota",
    "BanRecord",
    "RolePlayConfig",
    "Intent",
    # ORM Models (数据库模型)
    "Base",
    "UserORM",
    "ContextORM",
    "MessageORM",
    "TokenQuotaORM",
    "BanRecordORM",
    "RoleConfigORM",
    # Enums
    "IntentType",
    "ContextType",
    "ContextStatus",
    "MessageRole",
    "MessageType",
    "BanType",
    "BanReason",
    # Database Repositories
    "DatabaseManager",
    "get_database_manager",
    "UserRepository",
    "ContextRepository",
    "TokenQuotaRepository",
    "BanRecordRepository",
    "RoleConfigRepository",
    # Cache
    "RedisManager",
    "CacheManager",
    "get_cache_manager",
    "ContextCache",
    "UserCache",
    "TokenCache",
    "BanCache",
]
