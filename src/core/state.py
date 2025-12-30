"""
核心状态定义模块

定义机器人使用的所有状态模型、枚举类型和数据结构。
这些状态模型用于LangGraph的状态流转和消息路由。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# (2) 枚举类型定义
# =============================================================================


class IntentType(str, Enum):
    """意图类型枚举

    定义系统支持的所有意图类型，用于意图识别和路由。
    """

    CHAT = "chat"  # 普通聊天
    WEATHER = "weather"  # 天气查询
    ROLE_PLAY = "role_play"  # 角色扮演
    CONTEXT_CREATE = "context_create"  # 创建上下文
    CONTEXT_JOIN = "context_join"  # 加入上下文
    CONTEXT_LEAVE = "context_leave"  # 离开上下文
    CONTEXT_END = "context_end"  # 结束上下文
    USER_BAN = "user_ban"  # 用户封禁
    COMMAND = "command"  # 命令操作
    UNKNOWN = "unknown"  # 未知意图


class RouteTarget(str, Enum):
    """路由目标枚举

    定义LangGraph中节点间流转的目标节点。
    """

    CHAT_MODULE = "chat_module"
    WEATHER_MODULE = "weather_module"
    ROLE_PLAY_MODULE = "role_play_module"
    CONTEXT_HANDLER = "context_handler"
    RESPONSE_GENERATOR = "response_generator"
    ERROR_HANDLER = "error_handler"
    END = "end"


class ProcessingStage(str, Enum):
    """处理阶段枚举

    标识消息在处理流程中的当前阶段。
    """

    RECEIVED = "received"  # 已接收
    PREPROCESSING = "preprocessing"  # 预处理中
    INTENT_CLASSIFYING = "intent_classifying"  # 意图识别中
    CONTEXT_LOADING = "context_loading"  # 上下文加载中
    PROCESSING = "processing"  # 处理中
    POSTPROCESSING = "postprocessing"  # 后处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


# =============================================================================
# (3) 核心状态模型
# =============================================================================


class RobotState(BaseModel):
    """机器人核心状态模型

    这是LangGraph中流转的主要状态对象，
    包含消息处理过程中的所有必要信息。
    """

    # I. 模型配置
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )

    # II. 消息相关信息
    message_id: str = Field(description="消息ID")
    user_id: str = Field(description="发送者用户ID")
    user_name: str = Field(default="", description="发送者昵称")
    group_id: Optional[str] = Field(default=None, description="群组ID（私聊为None）")
    message_content: str = Field(description="消息内容")
    message_type: str = Field(default="text", description="消息类型")

    # III. 意图和路由
    intent: IntentType = Field(default=IntentType.UNKNOWN, description="识别的意图类型")
    intent_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="意图识别置信度"
    )
    route_target: RouteTarget = Field(
        default=RouteTarget.CHAT_MODULE, description="路由目标"
    )
    processing_stage: ProcessingStage = Field(
        default=ProcessingStage.RECEIVED, description="当前处理阶段"
    )

    # IV. 上下文信息
    context_id: Optional[str] = Field(default=None, description="当前上下文ID")
    context_type: Optional[str] = Field(default=None, description="上下文类型")
    context_data: dict[str, Any] = Field(
        default_factory=dict, description="上下文附加数据"
    )

    # V. 对话历史
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list, description="对话历史记录"
    )
    history_limit: int = Field(default=10, description="历史记录最大条数")

    # VI. 响应相关
    response: str = Field(default="", description="生成的响应内容")
    response_type: str = Field(default="text", description="响应类型")
    need_response: bool = Field(default=True, description="是否需要响应")

    # VII. 错误处理
    error_message: str = Field(default="", description="错误信息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    retry_count: int = Field(default=0, description="重试次数")

    # VIII. 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    created_at: datetime = Field(
        default_factory=datetime.now, description="状态创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="状态更新时间"
    )

    # IX. 实体提取结果
    entities: dict[str, Any] = Field(
        default_factory=dict, description="从消息中提取的实体"
    )

    # X. 角色扮演相关
    role_name: Optional[str] = Field(default=None, description="当前角色名称")
    role_config: Optional[dict[str, Any]] = Field(
        default=None, description="角色配置信息"
    )


# =============================================================================
# (4) 辅助状态模型
# =============================================================================


class IntentResult(BaseModel):
    """意图识别结果模型"""

    intent: IntentType = Field(description="识别的意图类型")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    raw_input: str = Field(description="原始输入文本")
    entities: dict[str, Any] = Field(default_factory=dict, description="提取的实体")
    reasoning: str = Field(default="", description="识别过程说明")


class ContextSwitchRequest(BaseModel):
    """上下文切换请求模型"""

    target_context_id: str = Field(description="目标上下文ID")
    reason: str = Field(default="", description="切换原因")
    preserve_history: bool = Field(default=True, description="是否保留历史记录")


class MessageProcessingResult(BaseModel):
    """消息处理结果模型"""

    success: bool = Field(description="是否成功处理")
    response: str = Field(default="", description="响应内容")
    error: Optional[str] = Field(default=None, description="错误信息")
    processing_time_ms: int = Field(default=0, description="处理耗时（毫秒）")
    tokens_used: int = Field(default=0, description="使用的Token数")
    state_snapshot: Optional[RobotState] = Field(
        default=None, description="最终状态快照"
    )


# =============================================================================
# (5) 状态工具函数
# =============================================================================


def create_initial_state(
    message_id: str,
    user_id: str,
    message_content: str,
    user_name: str = "",
    group_id: Optional[str] = None,
    message_type: str = "text",
) -> RobotState:
    """创建初始机器人状态

    Args:
        message_id: 消息ID
        user_id: 用户ID
        message_content: 消息内容
        user_name: 用户昵称
        group_id: 群组ID
        message_type: 消息类型

    Returns:
        初始化的RobotState实例
    """
    return RobotState(
        message_id=message_id,
        user_id=user_id,
        user_name=user_name,
        group_id=group_id,
        message_content=message_content,
        message_type=message_type,
        processing_stage=ProcessingStage.RECEIVED,
    )


def clone_state(state: RobotState, **updates: Any) -> RobotState:
    """克隆状态并选择性更新字段

    Args:
        state: 原始状态
        **updates: 要更新的字段

    Returns:
        新的状态实例
    """
    state_dict = state.model_dump()
    state_dict.update(updates)
    state_dict["updated_at"] = datetime.now()
    return RobotState(**state_dict)


def is_terminal_state(state: RobotState) -> bool:
    """判断是否为终止状态

    Args:
        state: 机器人状态

    Returns:
        是否为终止状态
    """
    return state.processing_stage in (
        ProcessingStage.COMPLETED,
        ProcessingStage.FAILED,
    )


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    # 枚举
    "IntentType",
    "RouteTarget",
    "ProcessingStage",
    # 核心模型
    "RobotState",
    "IntentResult",
    "ContextSwitchRequest",
    "MessageProcessingResult",
    # 工具函数
    "create_initial_state",
    "clone_state",
    "is_terminal_state",
]
