"""
闲聊模块

提供闲聊对话功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from typing import Optional

from pydantic import validate_call

from src.core.context import ContextManager
from src.service import LLMService, get_llm_service
from src.storage import ChatMessage, Context, MessageRole
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 系统提示词
# =============================================================================

DEFAULT_SYSTEM_PROMPT = """你是一个友好、 helpful 的 AI 助手，专门为考研学生提供帮助。

你的特点：
- 回答简洁明了，通常不超过200字
- 对考研相关问题有深入了解
- 语气友善，鼓励性
- 可以适当使用表情符号增加亲和力

请用中文回答。"""


# =============================================================================
# (4) 闲聊模块
# =============================================================================


class ChatModule:
    """闲聊模块

    提供智能对话功能，集成LLM服务和上下文管理。

    主要功能：
    - 处理用户对话请求
    - 管理对话历史
    - 生成AI回复
    - 保存对话记录
    """

    # I. 初始化
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        context_manager: Optional[ContextManager] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        """初始化闲聊模块

        Args:
            llm_service: LLM服务实例
            context_manager: 上下文管理器实例
            system_prompt: 系统提示词
        """
        self.llm_service = llm_service or get_llm_service()
        self.context_manager = context_manager
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        logger.info("ChatModule initialized")

    # II. 对话处理
    @validate_call
    async def handle(
        self,
        user_message: str,
        context: Optional[Context] = None,
        user_id: str = "",
        max_history: int = 10,
    ) -> str:
        """处理闲聊请求

        Args:
            user_message: 用户消息
            context: 对话上下文
            user_id: 用户ID
            max_history: 最大历史消息数

        Returns:
            AI回复文本
        """
        # 构建消息列表
        messages = await self._build_messages(
            user_message,
            context,
            max_history,
        )

        # 调用LLM生成回复
        try:
            response = await self.llm_service.chat(messages)
            ai_message = response.strip()

            # 保存对话记录
            if context and self.context_manager:
                await self._save_messages(
                    context,
                    user_message,
                    ai_message,
                    user_id,
                )

            logger.info(f"Chat response generated for user {user_id}")
            return ai_message

        except Exception as e:
            logger.error(f"Chat handle error: {e}")
            return "抱歉，我现在无法回复，请稍后再试。"

    # III. 流式对话
    @validate_call
    async def handle_stream(
        self,
        user_message: str,
        context: Optional[Context] = None,
        user_id: str = "",
        max_history: int = 10,
    ):
        """流式处理闲聊请求

        Args:
            user_message: 用户消息
            context: 对话上下文
            user_id: 用户ID
            max_history: 最大历史消息数

        Yields:
            AI回复文本片段
        """
        messages = await self._build_messages(
            user_message,
            context,
            max_history,
        )

        full_response = ""

        try:
            async for chunk in self.llm_service.stream_chat(messages):
                full_response += chunk
                yield chunk

            # 保存对话记录
            if context and self.context_manager:
                await self._save_messages(
                    context,
                    user_message,
                    full_response,
                    user_id,
                )

        except Exception as e:
            logger.error(f"Chat stream handle error: {e}")
            yield "抱歉，我现在无法回复，请稍后再试。"

    # IV. 消息构建
    async def _build_messages(
        self,
        user_message: str,
        context: Optional[Context],
        max_history: int,
    ) -> list[dict]:
        """构建LLM消息列表

        Args:
            user_message: 用户消息
            context: 对话上下文
            max_history: 最大历史消息数

        Returns:
            消息列表
        """
        messages = [{
            "role": "system",
            "content": self.system_prompt,
        }]

        # 添加系统提示

        # 添加历史消息
        if context and self.context_manager:
            history = await self.context_manager.get_messages(
                context.context_id,
                limit=max_history,
            )

            for msg in history:
                # 跳过系统消息和当前用户消息
                if msg.role != MessageRole.SYSTEM:
                    messages.append({
                        "role": msg.role.value,
                        "content": msg.content,
                    })

        # 添加当前用户消息
        messages.append({
            "role": "user",
            "content": user_message,
        })

        return messages

    # V. 消息保存
    async def _save_messages(
        self,
        context: Context,
        user_message: str,
        ai_message: str,
        user_id: str,
    ) -> None:
        """保存对话消息

        Args:
            context: 上下文对象
            user_message: 用户消息
            ai_message: AI回复
            user_id: 用户ID
        """
        if not self.context_manager:
            return

        try:
            from src.utils.helpers import IDHelper

            # 添加用户消息
            await self.context_manager.add_message(
                context_id=context.context_id,
                sender_id=user_id,
                sender_name=user_id,
                content=user_message,
                role=MessageRole.USER,
            )

            # 添加AI回复
            await self.context_manager.add_message(
                context_id=context.context_id,
                sender_id="system",
                sender_name="AI助手",
                content=ai_message,
                role=MessageRole.ASSISTANT,
            )

            logger.debug(f"Messages saved for context {context.context_id}")

        except Exception as e:
            logger.error(f"Save messages error: {e}")

    # VI. 配置方法
    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词

        Args:
            prompt: 新的系统提示词
        """
        self.system_prompt = prompt
        logger.info("System prompt updated")

    def clear_system_prompt(self) -> None:
        """清除自定义系统提示词，恢复默认"""
        self.system_prompt = DEFAULT_SYSTEM_PROMPT
        logger.info("System prompt reset to default")


# =============================================================================
# (5) 单例实例
# =============================================================================

_default_chat_module: Optional[ChatModule] = None


def get_chat_module(
    llm_service: Optional[LLMService] = None,
    context_manager: Optional[ContextManager] = None,
    system_prompt: Optional[str] = None,
) -> ChatModule:
    """获取默认闲聊模块实例

    Args:
        llm_service: LLM服务实例
        context_manager: 上下文管理器实例
        system_prompt: 系统提示词

    Returns:
        ChatModule实例
    """
    global _default_chat_module
    if _default_chat_module is None:
        _default_chat_module = ChatModule(
            llm_service,
            context_manager,
            system_prompt,
        )
    return _default_chat_module


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    "ChatModule",
    "get_chat_module",
    "DEFAULT_SYSTEM_PROMPT",
]
