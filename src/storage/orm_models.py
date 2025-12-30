"""
ORM数据模型模块

使用SQLAlchemy定义数据库表模型。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ==============================================================================
# (2) ORM Base
# ==============================================================================


class Base(DeclarativeBase):
    """SQLAlchemy声明式基类

    所有ORM模型都应继承此类。
    """

    pass


# ==============================================================================
# (3) 枚举类型定义
# ==============================================================================


class IntentType(str, Enum):
    """意图类型枚举"""

    CHAT = "chat"
    WEATHER = "weather"
    ROLE_PLAY = "role_play"
    CONTEXT_CREATE = "context_create"
    CONTEXT_JOIN = "context_join"
    CONTEXT_LEAVE = "context_leave"
    CONTEXT_END = "context_end"
    USER_BAN = "user_ban"
    UNKNOWN = "unknown"


class ContextType(str, Enum):
    """上下文类型枚举"""

    PRIVATE = "private"
    GROUP = "group"
    MULTI_USER = "multi_user"
    ROLE_PLAY = "role_play"


class ContextStatus(str, Enum):
    """上下文状态枚举"""

    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageType(str, Enum):
    """消息类型枚举"""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    SYSTEM = "system"
    COMMAND = "command"


class MessageRole(str, Enum):
    """消息角色枚举"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class BanType(str, Enum):
    """封禁类型枚举"""

    TEMPORARY = "temporary"
    PERMANENT = "permanent"


class BanReason(str, Enum):
    """封禁原因枚举"""

    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOKEN_ABUSE = "token_abuse"
    MALICIOUS_BEHAVIOR = "malicious_behavior"
    SPAMMING = "spamming"
    MANUAL = "manual"


# ==============================================================================
# (4) ORM模型定义
# ==============================================================================


class UserORM(Base):
    """用户表ORM模型

    对应users表，存储用户基本信息。
    """

    # I. 表名
    __tablename__ = "users"

    # II. 列定义
    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    current_context_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("contexts.context_id"), nullable=True
    )

    # JSON字段使用Text存储 (使用meta_data避免与SQLAlchemy的metadata冲突)
    meta_data: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # III. 关系
    current_context: Mapped[Optional["ContextORM"]] = relationship(
        "ContextORM", foreign_keys=[current_context_id]
    )
    created_contexts: Mapped[list["ContextORM"]] = relationship(
        "ContextORM", back_populates="creator", foreign_keys="ContextORM.creator_id"
    )
    token_quota: Mapped[Optional["TokenQuotaORM"]] = relationship(
        "TokenQuotaORM", back_populates="user", uselist=False
    )
    ban_records: Mapped[list["BanRecordORM"]] = relationship(
        "BanRecordORM", back_populates="user"
    )
    sent_messages: Mapped[list["MessageORM"]] = relationship(
        "MessageORM", back_populates="sender"
    )


class ContextORM(Base):
    """上下文表ORM模型

    对应contexts表，存储对话上下文信息。
    """

    # I. 表名
    __tablename__ = "contexts"

    # II. 列定义
    context_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    type: Mapped[ContextType] = mapped_column(SQLEnum(ContextType), nullable=False)
    name: Mapped[str] = mapped_column(String(200), default="")
    creator_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id"), nullable=False
    )
    participants: Mapped[str] = mapped_column(Text, default="[]")  # JSON数组
    status: Mapped[ContextStatus] = mapped_column(
        SQLEnum(ContextStatus), default=ContextStatus.ACTIVE
    )
    state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    current_role_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    meta_data: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # III. 关系
    creator: Mapped["UserORM"] = relationship(
        "UserORM", back_populates="created_contexts", foreign_keys=[creator_id]
    )
    messages: Mapped[list["MessageORM"]] = relationship(
        "MessageORM", back_populates="context", cascade="all, delete-orphan"
    )


class MessageORM(Base):
    """消息表ORM模型

    对应messages表，存储聊天消息。
    """

    # I. 表名
    __tablename__ = "messages"

    # II. 列定义
    message_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    context_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("contexts.context_id"), nullable=False
    )
    sender_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id"), nullable=False
    )
    sender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType), default=MessageType.TEXT
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole), default=MessageRole.USER
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_data: Mapped[str] = mapped_column("metadata", Text, default="{}")

    # III. 关系
    context: Mapped["ContextORM"] = relationship(
        "ContextORM", back_populates="messages"
    )
    sender: Mapped["UserORM"] = relationship("UserORM", back_populates="sent_messages")


class TokenQuotaORM(Base):
    """Token配额表ORM模型

    对应token_quotas表，存储用户Token使用配额。
    """

    # I. 表名
    __tablename__ = "token_quotas"

    # II. 列定义
    user_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id"), primary_key=True
    )
    total_quota: Mapped[int] = mapped_column(Integer, default=50000)
    used: Mapped[int] = mapped_column(Integer, default=0)
    daily_limit: Mapped[int] = mapped_column(Integer, default=5000)
    daily_used: Mapped[int] = mapped_column(Integer, default=0)
    daily_reset: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    minute_limit: Mapped[int] = mapped_column(Integer, default=200)
    minute_requests: Mapped[str] = mapped_column(Text, default="[]")  # JSON数组

    # III. 关系
    user: Mapped["UserORM"] = relationship("UserORM", back_populates="token_quota")


class BanRecordORM(Base):
    """封禁记录表ORM模型

    对应ban_records表，存储用户封禁记录。
    """

    # I. 表名
    __tablename__ = "ban_records"

    # II. 列定义
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("users.user_id"), nullable=False
    )
    reason: Mapped[BanReason] = mapped_column(SQLEnum(BanReason), nullable=False)
    ban_type: Mapped[BanType] = mapped_column(SQLEnum(BanType), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")

    # III. 关系
    user: Mapped["UserORM"] = relationship("UserORM", back_populates="ban_records")


class RoleConfigORM(Base):
    """角色配置表ORM模型

    对应role_configs表，存储角色扮演配置。
    """

    # I. 表名
    __tablename__ = "role_configs"

    # II. 列定义
    role_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
