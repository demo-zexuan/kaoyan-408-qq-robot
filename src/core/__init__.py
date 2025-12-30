"""
核心模块初始化

导出核心模块的所有公共接口。
"""

# =============================================================================
# (1) 状态定义
# =============================================================================
from src.core.state import (
    ContextSwitchRequest,
    IntentResult,
    IntentType,
    MessageProcessingResult,
    ProcessingStage,
    RobotState,
    RouteTarget,
    clone_state,
    create_initial_state,
    is_terminal_state,
)

# =============================================================================
# (2) 意图识别
# =============================================================================
from src.core.intent import (
    DEFAULT_INTENT_RULES,
    IntentRecognizer,
    IntentRule,
    get_intent_recognizer,
)

# =============================================================================
# (3) 上下文管理
# =============================================================================
from src.core.context import (
    ContextManager,
    ContextStorage,
    DatabaseContextStorage,
    HybridContextStorage,
    RedisContextStorage,
    get_context_manager,
)

# =============================================================================
# (4) LangGraph管理
# =============================================================================
from src.core.langgraph import (
    LangGraphManager,
    get_langgraph_manager,
    messages_to_state,
    state_to_messages,
)

# =============================================================================
# (5) 消息路由
# =============================================================================
from src.core.router import MessageRouter, get_message_router

# =============================================================================
# (6) 导出列表
# =============================================================================

__all__ = [
    # 状态定义
    "IntentType",
    "RouteTarget",
    "ProcessingStage",
    "RobotState",
    "IntentResult",
    "ContextSwitchRequest",
    "MessageProcessingResult",
    "create_initial_state",
    "clone_state",
    "is_terminal_state",
    # 意图识别
    "IntentRule",
    "DEFAULT_INTENT_RULES",
    "IntentRecognizer",
    "get_intent_recognizer",
    # 上下文管理
    "ContextStorage",
    "RedisContextStorage",
    "DatabaseContextStorage",
    "HybridContextStorage",
    "ContextManager",
    "get_context_manager",
    # LangGraph管理
    "LangGraphManager",
    "get_langgraph_manager",
    "state_to_messages",
    "messages_to_state",
    # 消息路由
    "MessageRouter",
    "get_message_router",
]
