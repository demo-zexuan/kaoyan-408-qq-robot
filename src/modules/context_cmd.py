"""
上下文命令模块

提供上下文管理命令功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from pydantic import validate_call

from src.core.context import ContextManager, ContextStatus, ContextType
from src.managers import UserManager
from src.storage import Context
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 上下文命令模块
# =============================================================================


class ContextCommandModule:
    """上下文命令模块

    提供上下文管理的命令接口。

    主要功能：
    - 创建上下文命令
    - 加入/离开上下文命令
    - 结束上下文命令
    - 查看历史命令
    - 列出上下文命令
    """

    # I. 初始化
    def __init__(
        self,
        context_manager: Optional[ContextManager] = None,
        user_manager: Optional[UserManager] = None,
    ) -> None:
        """初始化上下文命令模块

        Args:
            context_manager: 上下文管理器实例
            user_manager: 用户管理器实例
        """
        self.context_manager = context_manager
        self.user_manager = user_manager

        logger.info("ContextCommandModule initialized")

    # II. 创建上下文命令
    @validate_call
    async def cmd_create_context(
        self,
        user_id: str,
        user_name: str = "",
        context_name: str = "",
        expire_hours: int = 24,
    ) -> str:
        """创建上下文命令

        Args:
            user_id: 用户ID
            user_name: 用户名称
            context_name: 上下文名称
            expire_hours: 过期时间（小时）

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            # 创建私聊上下文
            context = await self.context_manager.create_context(
                context_type=ContextType.PRIVATE,
                creator_id=user_id,
                name=context_name or f"私聊_{user_name or user_id}",
                participants=[user_id],
                expires_in_hours=expire_hours,
            )

            # 更新用户当前上下文
            if self.user_manager:
                await self.user_manager.set_user_context(user_id, context.context_id)

            logger.info(f"Context created: {context.context_id} by {user_id}")
            return f"""✅ 上下文创建成功！

📋 上下文ID: {context.context_id}
📝 名称: {context.name}
👤 参与者: {len(context.participants)}人
⏰ 过期时间: {expire_hours}小时后

您现在可以开始对话了！"""

        except Exception as e:
            logger.error(f"Create context error: {e}")
            return f"❌ 创建上下文失败: {str(e)}"

    # III. 加入上下文命令
    @validate_call
    async def cmd_join_context(
        self,
        user_id: str,
        context_id: str,
        user_name: str = "",
    ) -> str:
        """加入上下文命令

        Args:
            user_id: 用户ID
            context_id: 上下文ID
            user_name: 用户名称

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            context = await self.context_manager.get_context(context_id)

            if not context:
                return f"❌ 未找到上下文: {context_id}"

            if context.status != ContextStatus.ACTIVE:
                return f"❌ 该上下文已{context.status.value}"

            # 检查是否已在上下文中
            if user_id in context.participants:
                return f"❌ 您已经在该上下文中了"

            # 加入上下文
            await self.context_manager.add_participant(context_id, user_id)

            # 更新用户当前上下文
            if self.user_manager:
                await self.user_manager.set_user_context(user_id, context_id)

            logger.info(f"User {user_id} joined context {context_id}")
            return f"""✅ 成功加入上下文！

📋 上下文ID: {context_id}
📝 名称: {context.name}
👥 当前参与者: {len(context.participants) + 1}人"""

        except Exception as e:
            logger.error(f"Join context error: {e}")
            return f"❌ 加入上下文失败: {str(e)}"

    # IV. 离开上下文命令
    @validate_call
    async def cmd_leave_context(
        self,
        user_id: str,
        user_name: str = "",
    ) -> str:
        """离开当前上下文命令

        Args:
            user_id: 用户ID
            user_name: 用户名称

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            # 获取用户当前上下文
            if self.user_manager:
                user = await self.user_manager.get_user(user_id)
                if not user or not user.current_context_id:
                    return "❌ 您当前没有在任何上下文中"

                context_id = user.current_context_id
            else:
                return "❌ 无法获取用户信息"

            context = await self.context_manager.get_context(context_id)

            if not context:
                return f"❌ 上下文不存在: {context_id}"

            # 移除参与者
            await self.context_manager.remove_participant(context_id, user_id)

            # 清除用户当前上下文
            await self.user_manager.clear_user_context(user_id)

            logger.info(f"User {user_id} left context {context_id}")
            return f"✅ 已离开上下文: {context.name}"

        except Exception as e:
            logger.error(f"Leave context error: {e}")
            return f"❌ 离开上下文失败: {str(e)}"

    # V. 结束上下文命令
    @validate_call
    async def cmd_end_context(
        self,
        user_id: str,
        context_id: Optional[str] = None,
    ) -> str:
        """结束上下文命令

        Args:
            user_id: 用户ID（必须为上下文创建者）
            context_id: 上下文ID，不传则使用当前上下文

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            # 获取上下文ID
            if not context_id:
                if self.user_manager:
                    user = await self.user_manager.get_user(user_id)
                    if not user:
                        return "❌ 用户不存在"
                    context_id = user.current_context_id
                else:
                    return "❌ 无法获取用户信息"

            if not context_id:
                return "❌ 请指定要结束的上下文"

            context = await self.context_manager.get_context(context_id)

            if not context:
                return f"❌ 上下文不存在: {context_id}"

            # 检查权限
            if context.creator_id != user_id:
                return "❌ 只有上下文创建者才能结束上下文"

            # 结束上下文
            await self.context_manager.pause_context(context_id)

            # 清除所有参与者的当前上下文
            if self.user_manager:
                for participant_id in context.participants:
                    await self.user_manager.clear_user_context(participant_id)

            logger.info(f"Context {context_id} ended by {user_id}")
            return f"✅ 上下文已结束: {context.name}"

        except Exception as e:
            logger.error(f"End context error: {e}")
            return f"❌ 结束上下文失败: {str(e)}"

    # VI. 查看历史命令
    @validate_call
    async def cmd_show_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> str:
        """查看对话历史命令

        Args:
            user_id: 用户ID
            limit: 显示消息数量

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            # 获取用户当前上下文
            if self.user_manager:
                user = await self.user_manager.get_user(user_id)
                if not user or not user.current_context_id:
                    return "❌ 您当前没有在任何上下文中"

                context_id = user.current_context_id
            else:
                return "❌ 无法获取用户信息"

            messages = await self.context_manager.get_messages(
                context_id,
                limit=limit,
            )

            if not messages:
                return "📭 暂无对话记录"

            lines = [f"📜 对话历史 (最近{len(messages)}条):\n"]

            for msg in messages:
                role_icon = {
                    "user": "👤",
                    "assistant": "🤖",
                    "system": "⚙️",
                }.get(msg.role.value, "💬")

                content = msg.content[:100]
                if len(msg.content) > 100:
                    content += "..."

                lines.append(f"{role_icon} {content}")

            logger.info(f"History shown for context {context_id}")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Show history error: {e}")
            return f"❌ 查看历史失败: {str(e)}"

    # VII. 列出上下文命令
    async def cmd_list_contexts(self, user_id: str) -> str:
        """列出用户的上下文命令

        Args:
            user_id: 用户ID

        Returns:
            命令执行结果
        """
        if not self.context_manager:
            return "上下文管理器未初始化"

        try:
            contexts = await self.context_manager.list_active_contexts()

            # 过滤用户参与的上下文
            user_contexts = [ctx for ctx in contexts if user_id in ctx.participants]

            if not user_contexts:
                return "📭 您暂无活跃的上下文"

            lines = [f"📋 您的上下文列表 ({len(user_contexts)}个):\n"]

            for ctx in user_contexts:
                status_icon = "🟢" if ctx.status == ContextStatus.ACTIVE else "⏸️"
                lines.append(
                    f"{status_icon} {ctx.name} (ID: {ctx.context_id})\n"
                    f"   参与者: {len(ctx.participants)}人"
                )

            logger.info(f"Contexts listed for user {user_id}")
            return "\n\n".join(lines)

        except Exception as e:
            logger.error(f"List contexts error: {e}")
            return f"❌ 列出上下文失败: {str(e)}"

    # VIII. 帮助信息
    @staticmethod
    def get_help() -> str:
        """获取帮助信息

        Returns:
            使用帮助文本
        """
        return """📚 上下文管理命令帮助

**创建上下文**
- 创建一个新的对话上下文

**加入上下文 <上下文ID>**
- 加入指定的上下文

**离开上下文**
- 离开当前上下文

**结束上下文 [上下文ID]**
- 结束指定上下文（仅创建者）

**查看历史 [数量]**
- 查看对话历史，默认显示10条

**列出上下文**
- 列出您参与的所有上下文"""


# =============================================================================
# (4) 单例实例
# =============================================================================

_default_context_cmd_module: Optional[ContextCommandModule] = None


def get_context_command_module(
    context_manager: Optional[ContextManager] = None,
    user_manager: Optional[UserManager] = None,
) -> ContextCommandModule:
    """获取默认上下文命令模块实例

    Args:
        context_manager: 上下文管理器实例
        user_manager: 用户管理器实例

    Returns:
        ContextCommandModule实例
    """
    global _default_context_cmd_module
    if _default_context_cmd_module is None:
        _default_context_cmd_module = ContextCommandModule(
            context_manager,
            user_manager,
        )
    return _default_context_cmd_module


# =============================================================================
# (5) 导出
# =============================================================================

__all__ = [
    "ContextCommandModule",
    "get_context_command_module",
]
