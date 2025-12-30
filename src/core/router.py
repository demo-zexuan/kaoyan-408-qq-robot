"""
消息路由模块

实现消息的入口处理和路由分发，连接NoneBot事件和核心处理流程。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import validate_call

from src.core.context import ContextManager, get_context_manager
from src.core.langgraph import LangGraphManager, get_langgraph_manager
from src.core.state import (
    IntentType,
    MessageProcessingResult,
    RobotState,
    create_initial_state,
)
from src.managers import BanManager, TokenController, UserManager
from src.storage import CacheManager, ContextType, DatabaseManager, MessageType
from src.utils.helpers import IDHelper
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) 消息路由器
# =============================================================================


class MessageRouter:
    """消息路由器

    负责处理进入系统的所有消息，是整个系统的入口点。

    处理流程：
    1. 预检查：用户验证、封禁检查
    2. 状态初始化：创建初始RobotState
    3. 意图识别：确定消息意图
    4. 上下文管理：获取或创建上下文
    5. LangGraph处理：执行状态图
    6. 响应返回：返回处理结果
    """

    # I. 初始化
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        user_manager: UserManager,
        token_controller: TokenController,
        ban_manager: BanManager,
        context_manager: Optional[ContextManager] = None,
        langgraph_manager: Optional[LangGraphManager] = None,
    ) -> None:
        """初始化消息路由器

        Args:
            db_manager: 数据库管理器
            cache_manager: 缓存管理器
            user_manager: 用户管理器
            token_controller: Token控制器
            ban_manager: 封禁管理器
            context_manager: 上下文管理器（可选）
            langgraph_manager: LangGraph管理器（可选）
        """
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.user_manager = user_manager
        self.token_controller = token_controller
        self.ban_manager = ban_manager

        # 初始化管理器
        if context_manager is None:
            context_manager = get_context_manager(db_manager, cache_manager)
        self.context_manager = context_manager

        if langgraph_manager is None:
            langgraph_manager = get_langgraph_manager()
        self.langgraph_manager = langgraph_manager

        logger.info("MessageRouter initialized")

    # II. 主要处理接口
    @validate_call
    async def route_message(
        self,
        user_id: str,
        user_name: str,
        message_content: str,
        group_id: Optional[str] = None,
        message_type: str = "text",
    ) -> MessageProcessingResult:
        """路由处理消息

        Args:
            user_id: 用户ID
            user_name: 用户昵称
            message_content: 消息内容
            group_id: 群组ID（私聊为None）
            message_type: 消息类型

        Returns:
            消息处理结果
        """
        start_time = datetime.now()
        message_id = IDHelper.generate_message_id()

        logger.info(
            f"Routing message {message_id} from user {user_id}: {message_content[:50]}..."
        )

        try:
            # 1. 预检查
            check_result = await self._pre_check(user_id)
            if not check_result["allowed"]:
                return MessageProcessingResult(
                    success=False,
                    response=check_result["reason"],
                    error=check_result["error_code"],
                    processing_time_ms=self._calculate_elapsed_ms(start_time),
                )

            # 2. 创建初始状态
            state = create_initial_state(
                message_id=message_id,
                user_id=user_id,
                user_name=user_name,
                group_id=group_id,
                message_content=message_content,
                message_type=message_type,
            )

            # 3. 确定上下文类型
            context_type = (
                ContextType.PRIVATE if group_id is None else ContextType.GROUP
            )
            state.context_type = context_type.value

            # 4. 获取或创建上下文
            context = await self._get_or_create_context(
                user_id, user_name, group_id, context_type, state
            )
            if context:
                state.context_id = context.context_id
                # 添加消息到上下文
                await self.context_manager.add_message(
                    context.context_id,
                    user_id,
                    user_name,
                    message_content,
                    (
                        MessageType(message_type)
                        if message_type in MessageType.__members__
                        else MessageType.TEXT
                    ),
                )

            # 5. 执行LangGraph处理
            final_state = await self.langgraph_manager.process(state)

            # 6. 生成响应
            response = final_state.response
            if final_state.error_message:
                logger.error(f"Processing error: {final_state.error_message}")

            # 7. 保存机器人响应到上下文
            if context and response:
                await self.context_manager.add_message(
                    context.context_id,
                    "robot",
                    "Robot",
                    response,
                    MessageType.TEXT,
                    is_system=False,
                )

            return MessageProcessingResult(
                success=True,
                response=response,
                processing_time_ms=self._calculate_elapsed_ms(start_time),
                state_snapshot=final_state,
            )

        except Exception as e:
            logger.exception(f"Error routing message: {e}")
            return MessageProcessingResult(
                success=False,
                response="抱歉，处理您的消息时出现错误。",
                error=str(e),
                processing_time_ms=self._calculate_elapsed_ms(start_time),
            )

    # III. 预检查方法
    async def _pre_check(self, user_id: str) -> dict[str, Any]:
        """预检查用户状态

        Args:
            user_id: 用户ID

        Returns:
            检查结果字典，包含allowed、reason、error_code
        """
        result = {"allowed": True, "reason": "", "error_code": None}

        try:
            # 1. 检查用户是否被封禁
            if await self.ban_manager.is_banned(user_id):
                result["allowed"] = False
                result["error_code"] = "USER_BANNED"

                # 获取剩余封禁时间
                remaining = await self.ban_manager.get_remaining_ban_time(user_id)
                if remaining is None:
                    result["reason"] = "您已被永久封禁。"
                elif remaining > 0:
                    minutes = remaining // 60
                    result["reason"] = f"您已被封禁，剩余 {minutes} 分钟。"
                else:
                    result["reason"] = "您已被封禁。"

                logger.warning(f"User {user_id} is banned")
                return result

            # 2. 检查Token配额
            quota_ok, quota_msg = await self.token_controller.check_quota(user_id)
            if not quota_ok:
                result["allowed"] = False
                result["error_code"] = "QUOTA_EXCEEDED"
                result["reason"] = quota_msg
                logger.warning(f"User {user_id} quota check failed: {quota_msg}")
                return result

            # 3. 检查每分钟限制
            if not await self.token_controller.check_minute_limit(user_id):
                result["allowed"] = False
                result["error_code"] = "RATE_LIMIT_EXCEEDED"
                result["reason"] = "请求过于频繁，请稍后再试。"
                logger.warning(f"User {user_id} exceeded minute limit")
                return result

            # 4. 检查每日限制
            if not await self.token_controller.check_daily_limit(user_id):
                result["allowed"] = False
                result["error_code"] = "DAILY_LIMIT_EXCEEDED"
                result["reason"] = "今日配额已用完，请明天再试。"
                logger.warning(f"User {user_id} exceeded daily limit")
                return result

        except Exception as e:
            logger.error(f"Error in pre_check: {e}")
            # 预检查失败时允许继续，避免阻塞正常用户

        return result

    # IV. 上下文管理方法
    async def _get_or_create_context(
        self,
        user_id: str,
        user_name: str,
        group_id: Optional[str],
        context_type: ContextType,
        state: RobotState,
    ) -> Optional[Any]:
        """获取或创建上下文

        Args:
            user_id: 用户ID
            user_name: 用户昵称
            group_id: 群组ID
            context_type: 上下文类型
            state: 当前状态

        Returns:
            上下文对象
        """
        try:
            # 对于私聊，获取用户当前上下文
            if context_type == ContextType.PRIVATE:
                context = await self.context_manager.get_user_context(user_id)

                # 如果没有上下文或上下文已过期，创建新的
                if not context or context.status.value != "active":
                    context = await self.context_manager.create_context(
                        context_type=context_type,
                        creator_id=user_id,
                        name=f"私聊_{user_name}",
                        participants=[user_id],
                    )
                    logger.info(f"Created new private context {context.context_id}")

                return context

            # 对于群聊，根据群组ID处理
            else:
                # 群聊上下文使用群组ID作为上下文ID的一部分
                from src.storage import ContextRepository

                ctx_repo = ContextRepository(self.db_manager)
                context_id = f"group_{group_id}"

                context = await ctx_repo.get(context_id)

                if not context or context.status.value != "active":
                    context = await self.context_manager.create_context(
                        context_type=context_type,
                        creator_id=user_id,
                        name=f"群聊_{group_id}",
                        participants=[user_id],
                    )
                    logger.info(f"Created new group context {context.context_id}")

                # 确保发送者在参与者列表中
                if user_id not in context.participants:
                    await self.context_manager.add_participant(
                        context.context_id, user_id, user_name
                    )

                return context

        except Exception as e:
            logger.error(f"Error getting/creating context: {e}")
            return None

    # V. 意图处理快捷方法
    @staticmethod
    async def handle_chat_intent(state: RobotState) -> str:
        """处理聊天意图

        Args:
            state: 机器人状态

        Returns:
            响应内容
        """
        # TODO: 集成LLM服务生成回复
        return f"你说：{state.message_content}"

    @staticmethod
    async def handle_weather_intent(state: RobotState) -> str:
        """处理天气查询意图

        Args:
            state: 机器人状态

        Returns:
            响应内容
        """
        location = state.entities.get("location", "未知地点")
        # TODO: 集成天气服务
        return f"正在查询{location}的天气信息..."

    @staticmethod
    async def handle_role_play_intent(state: RobotState) -> str:
        """处理角色扮演意图

        Args:
            state: 机器人状态

        Returns:
            响应内容
        """
        # TODO: 集成角色扮演模块
        return "角色扮演功能正在开发中..."

    async def handle_context_intent(self, state: RobotState) -> str:
        """处理上下文操作意图

        Args:
            state: 机器人状态

        Returns:
            响应内容
        """
        intent = state.intent

        if intent == IntentType.CONTEXT_CREATE:
            context = await self.context_manager.create_context(
                context_type=ContextType.PRIVATE,
                creator_id=state.user_id,
                name=f"对话_{state.user_name}",
            )
            return f"已创建新对话：{context.context_id}"

        elif intent == IntentType.CONTEXT_JOIN:
            return "加入对话功能正在开发中..."

        elif intent == IntentType.CONTEXT_LEAVE:
            if state.context_id:
                await self.context_manager.remove_participant(
                    state.context_id, state.user_id
                )
                return "已离开当前对话"
            return "您不在任何对话中"

        elif intent == IntentType.CONTEXT_END:
            if state.context_id:
                await self.context_manager.delete_context(state.context_id)
                return "对话已结束"
            return "您不在任何对话中"

        return "未知上下文操作"

    # VI. 工具方法
    @staticmethod
    def _calculate_elapsed_ms(start_time: datetime) -> int:
        """计算经过的毫秒数

        Args:
            start_time: 开始时间

        Returns:
            经过的毫秒数
        """
        return int((datetime.now() - start_time).total_seconds() * 1000)


# =============================================================================
# (4) 单例实例
# =============================================================================

_default_message_router: Optional[MessageRouter] = None


def get_message_router(
    db_manager: DatabaseManager,
    cache_manager: CacheManager,
    user_manager: UserManager,
    token_controller: TokenController,
    ban_manager: BanManager,
    context_manager: Optional[ContextManager] = None,
) -> MessageRouter:
    """获取默认消息路由器实例

    Args:
        db_manager: 数据库管理器
        cache_manager: 缓存管理器
        user_manager: 用户管理器
        token_controller: Token控制器
        ban_manager: 封禁管理器
        context_manager: 上下文管理器（可选，默认自动创建）

    Returns:
        MessageRouter实例
    """
    global _default_message_router
    if _default_message_router is None:
        _default_message_router = MessageRouter(
            db_manager,
            cache_manager,
            user_manager,
            token_controller,
            ban_manager,
            context_manager,
        )
    return _default_message_router


# =============================================================================
# (5) 导出
# =============================================================================

__all__ = [
    # 路由器
    "MessageRouter",
    "get_message_router",
]
