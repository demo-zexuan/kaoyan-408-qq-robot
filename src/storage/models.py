"""
数据模型模块

定义系统中使用的所有数据模型，包括用户、上下文、消息、Token配额、封禁记录等。
"""

# ==============================================================================
# (1) 导入依赖
# ==============================================================================
from __future__ import annotations

from collections import deque
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# (2) 枚举类型定义
# ==============================================================================


class IntentType(str, Enum):
    """意图类型枚举

    定义系统支持的所有意图类型。
    """

    CHAT = "chat"  # 普通闲聊
    WEATHER = "weather"  # 天气查询
    ROLE_PLAY = "role_play"  # 角色扮演
    CONTEXT_CREATE = "context_create"  # 创建上下文
    CONTEXT_JOIN = "context_join"  # 加入上下文
    CONTEXT_LEAVE = "context_leave"  # 离开上下文
    CONTEXT_END = "context_end"  # 结束上下文
    USER_BAN = "user_ban"  # 用户封禁
    UNKNOWN = "unknown"  # 未知意图


class ContextType(str, Enum):
    """上下文类型枚举

    定义对话上下文的类型。
    """

    PRIVATE = "private"  # 私聊上下文
    GROUP = "group"  # 群聊上下文
    MULTI_USER = "multi_user"  # 多用户协作上下文
    ROLE_PLAY = "role_play"  # 角色扮演上下文


class ContextStatus(str, Enum):
    """上下文状态枚举

    定义上下文的生命周期状态。
    """

    ACTIVE = "active"  # 活跃状态
    PAUSED = "paused"  # 暂停状态
    EXPIRED = "expired"  # 过期状态
    ARCHIVED = "archived"  # 归档状态
    DELETED = "deleted"  # 删除状态


class MessageType(str, Enum):
    """消息类型枚举

    定义消息的类型。
    """

    TEXT = "text"  # 文本消息
    IMAGE = "image"  # 图片消息
    VOICE = "voice"  # 语音消息
    SYSTEM = "system"  # 系统消息
    COMMAND = "command"  # 命令消息


class MessageRole(str, Enum):
    """消息角色枚举

    定义消息发送者的角色。
    """

    USER = "user"  # 用户
    ASSISTANT = "assistant"  # AI助手
    SYSTEM = "system"  # 系统


class BanType(str, Enum):
    """封禁类型枚举

    定义封禁的类型。
    """

    TEMPORARY = "temporary"  # 临时封禁
    PERMANENT = "permanent"  # 永久封禁


class BanReason(str, Enum):
    """封禁原因枚举

    定义用户被封禁的原因。
    """

    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # 速率限制超出
    TOKEN_ABUSE = "token_abuse"  # Token滥用
    MALICIOUS_BEHAVIOR = "malicious_behavior"  # 恶意行为
    SPAMMING = "spamming"  # 刷屏
    MANUAL = "manual"  # 手动封禁


# ==============================================================================
# (3) 消息相关模型
# ==============================================================================


class ChatMessage(BaseModel):
    """聊天消息模型

    表示一条聊天消息，包含发送者、内容、时间戳等信息。
    """

    # I. 基础信息
    message_id: str = Field(..., description="消息唯一标识")
    sender_id: str = Field(..., description="发送者ID")
    sender_name: str = Field(..., description="发送者名称")
    role: MessageRole = Field(default=MessageRole.USER, description="消息角色")

    # II. 消息内容
    content: str = Field(..., description="消息内容")
    message_type: MessageType = Field(default=MessageType.TEXT, description="消息类型")

    # III. 元数据
    timestamp: datetime = Field(default_factory=datetime.now, description="消息时间戳")
    is_system: bool = Field(default=False, description="是否为系统消息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


# ==============================================================================
# (4) 上下文相关模型
# ==============================================================================


class RobotState(BaseModel):
    """机器人对话状态模型

    在LangGraph中流动的状态数据，包含消息、上下文、意图等信息。
    """

    # I. 消息相关
    messages: list[str] = Field(default_factory=list, description="历史消息列表")
    current_input: str = Field(default="", description="当前用户输入")
    response: str = Field(default="", description="生成的回复")

    # II. 上下文相关
    context_id: str = Field(default="", description="上下文ID")
    context_type: str = Field(default="", description="上下文类型")
    participants: list[str] = Field(default_factory=list, description="参与者ID列表")

    # III. 意图相关
    intent: str = Field(default="", description="识别到的意图")
    intent_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="意图识别置信度"
    )
    extracted_entities: dict[str, Any] = Field(
        default_factory=dict, description="提取的实体信息"
    )

    # IV. 角色扮演相关
    role_play_mode: bool = Field(default=False, description="是否为角色扮演模式")
    current_role: str = Field(default="", description="当前角色名称")
    role_settings: dict[str, Any] = Field(default_factory=dict, description="角色设置")

    # V. 元数据
    step_count: int = Field(default=0, ge=0, description="执行的步数")
    token_usage: int = Field(default=0, ge=0, description="已使用的Token数")
    last_action: str = Field(default="", description="上一个执行的动作")


class Context(BaseModel):
    """对话上下文模型

    表示一个对话上下文，包含参与者、消息历史、状态等信息。
    """

    # I. 基础信息
    context_id: str = Field(..., description="上下文唯一标识")
    type: ContextType = Field(..., description="上下文类型")
    name: str = Field(default="", description="上下文名称")

    # II. 参与者
    creator_id: str = Field(..., description="创建者ID")
    participants: list[str] = Field(default_factory=list, description="参与者ID列表")

    # III. 消息历史
    messages: list[ChatMessage] = Field(default_factory=list, description="消息历史")
    max_messages: int = Field(default=200, ge=1, description="最大消息数")

    # IV. 状态
    status: ContextStatus = Field(
        default=ContextStatus.ACTIVE, description="上下文状态"
    )
    state: Optional[RobotState] = Field(default=None, description="关联的对话状态")
    current_role_id: Optional[str] = Field(default=None, description="当前激活的角色ID")

    # V. 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")


# ==============================================================================
# (5) 用户相关模型
# ==============================================================================


class User(BaseModel):
    """用户模型

    表示一个系统用户。
    """

    # I. 基础信息
    user_id: str = Field(..., description="用户唯一标识(QQ号)")
    nickname: str = Field(default="", description="用户昵称")

    # II. 状态
    is_active: bool = Field(default=True, description="是否活跃")
    is_banned: bool = Field(default=False, description="是否被封禁")

    # III. 当前上下文
    current_context_id: Optional[str] = Field(
        default=None, description="当前所在的上下文ID"
    )

    # IV. 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_active: datetime = Field(
        default_factory=datetime.now, description="最后活跃时间"
    )


# ==============================================================================
# (6) Token配额模型
# ==============================================================================


class TokenQuota(BaseModel):
    """Token配额模型

    管理用户的Token使用配额和限制。
    """

    # I. 用户标识
    user_id: str = Field(..., description="用户ID")

    # II. 总配额
    total_quota: int = Field(default=50000, ge=0, description="总配额")
    used: int = Field(default=0, ge=0, description="已使用")

    # III. 时间窗口限制
    daily_limit: int = Field(default=5000, ge=0, description="每日限制")
    daily_used: int = Field(default=0, ge=0, description="今日已用")
    daily_reset: datetime = Field(..., description="每日重置时间")

    # IV. 速率限制 (使用列表模拟时间窗口)
    minute_limit: int = Field(default=200, ge=1, description="每分钟限制")
    minute_requests: list[datetime] = Field(
        default_factory=list, description="每分钟请求时间戳列表"
    )

    # V. 计算属性
    @property
    def remaining(self) -> int:
        """int: 剩余配额"""
        return max(0, self.total_quota - self.used)

    @property
    def daily_remaining(self) -> int:
        """int: 今日剩余配额"""
        return max(0, self.daily_limit - self.daily_used)

    @property
    def is_minute_limit_exceeded(self) -> bool:
        """bool: 是否超过每分钟限制"""
        now = datetime.now()
        # 过滤掉超过1分钟的请求
        recent = [ts for ts in self.minute_requests if (now - ts).total_seconds() < 60]
        return len(recent) >= self.minute_limit

    @field_validator("minute_requests", mode="before")
    @classmethod
    def validate_minute_requests(cls, v: list) -> list:
        """验证并清理分钟请求记录"""
        now = datetime.now()
        # 过滤掉超过1分钟的请求
        return [ts for ts in v if (now - ts).total_seconds() < 60]


# ==============================================================================
# (7) 封禁相关模型
# ==============================================================================


class BanRecord(BaseModel):
    """封禁记录模型

    记录用户被封禁的信息。
    """

    # I. 用户信息
    user_id: str = Field(..., description="被封禁的用户ID")

    # II. 封禁类型
    reason: BanReason = Field(..., description="封禁原因")
    ban_type: BanType = Field(..., description="封禁类型")

    # III. 时间信息
    started_at: datetime = Field(
        default_factory=datetime.now, description="封禁开始时间"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="封禁过期时间(永久封禁为None)"
    )

    # IV. 详细信息
    details: str = Field(default="", description="封禁详细信息")

    # V. 计算属性
    @property
    def is_active(self) -> bool:
        """bool: 封禁是否仍然有效"""
        if self.ban_type == BanType.PERMANENT:
            return True
        if self.expires_at is None:
            return False
        return datetime.now() < self.expires_at

    @property
    def remaining_seconds(self) -> Optional[int]:
        """Optional[int]: 剩余封禁秒数"""
        if self.ban_type == BanType.PERMANENT:
            return None
        if self.expires_at is None:
            return 0
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))


# ==============================================================================
# (8) 角色扮演模型
# ==============================================================================


class RolePlayConfig(BaseModel):
    """角色扮演配置模型

    定义一个角色的配置信息。
    """

    # I. 基础信息
    role_id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    description: str = Field(default="", description="角色描述")

    # II. 系统提示词
    system_prompt: str = Field(default="", description="系统提示词")

    # III. 元数据
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


# ==============================================================================
# (9) 意图识别结果模型
# ==============================================================================


class Intent(BaseModel):
    """意图识别结果模型

    表示意图识别的结果。
    """

    name: str = Field(..., description="意图名称")
    description: str = Field(..., description="意图描述")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度")
    entities: dict[str, Any] = Field(default_factory=dict, description="提取的实体")
