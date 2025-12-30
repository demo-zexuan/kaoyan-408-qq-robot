"""
LLM Endpoint - NoneBot插件

集成所有功能模块，提供QQ机器人对话服务。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

import asyncio
from typing import Optional

from nonebot import get_driver, on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, PrivateMessageEvent
from nonebot.plugin import PluginMetadata
from src.service import get_llm_service

from src.core.context import ContextManager, get_context_manager
from src.core.router import MessageRouter, get_message_router
from src.managers import (
    BanManager,
    TokenController,
    UserManager,
    get_ban_manager,
    get_token_controller,
    get_user_manager,
)
from src.modules import (
    ChatModule,
    ContextCommandModule,
    RolePlayModule,
    WeatherModule,
    get_chat_module,
    get_context_command_module,
    get_role_play_module,
    get_weather_module,
)
from src.storage import CacheManager, DatabaseManager, get_cache_manager, get_database_manager
from src.utils.config import get_config
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 插件元数据
# =============================================================================

__plugin_meta__ = PluginMetadata(
    name="LLM Endpoint",
    description="考研408 QQ机器人 - 智能对话助手",
    usage="""
直接发送消息进行对话
命令:
  /天气 <地点> - 查询天气
  /创建上下文 - 创建新的对话上下文
  /加入上下文 <ID> - 加入指定上下文
  /离开上下文 - 离开当前上下文
  /结束上下文 - 结束当前上下文
  /查看历史 - 查看对话历史
  /列出上下文 - 列出所有上下文
  /切换角色 <ID> - 切换对话角色
  /列出角色 - 列出可用角色
  /帮助 - 显示帮助信息
    """,
)

# =============================================================================
# (4) 全局变量
# =============================================================================

_driver = get_driver()
db_manager: Optional[DatabaseManager] = None
cache_manager: Optional[CacheManager] = None
context_manager: Optional[ContextManager] = None
user_manager: Optional[UserManager] = None
token_controller: Optional[TokenController] = None
ban_manager: Optional[BanManager] = None
message_router: Optional[MessageRouter] = None
chat_module: Optional[ChatModule] = None
weather_module: Optional[WeatherModule] = None
role_play_module: Optional[RolePlayModule] = None
context_cmd_module: Optional[ContextCommandModule] = None


# =============================================================================
# (5) 插件初始化
# =============================================================================


@_driver.on_startup
async def init_modules():
    """初始化所有模块"""
    global db_manager, cache_manager, context_manager, user_manager
    global token_controller, ban_manager, message_router
    global chat_module, weather_module, role_play_module, context_cmd_module

    try:
        config = get_config()

        # 初始化存储层
        db_manager = get_database_manager()
        await db_manager.connect(auto_init=True)

        cache_manager = get_cache_manager()
        await cache_manager.connect()

        # 初始化管理器
        context_manager = get_context_manager(db_manager, cache_manager)
        user_manager = get_user_manager(db_manager, cache_manager, context_manager)
        token_controller = get_token_controller(db_manager, cache_manager)
        ban_manager = get_ban_manager(db_manager, cache_manager)

        # 初始化消息路由器（添加context_manager参数）
        message_router = get_message_router(
            db_manager,
            cache_manager,
            user_manager,
            token_controller,
            ban_manager,
            context_manager,
        )

        # 初始化功能模块
        chat_module = get_chat_module(
            context_manager=context_manager,
        )
        weather_module = get_weather_module()
        role_play_module = get_role_play_module(
            context_manager=context_manager,
            db_manager=db_manager,
        )
        context_cmd_module = get_context_command_module(
            context_manager,
            user_manager,
        )

        logger.info("LLM Endpoint plugin initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize plugin: {e}")
        raise


@_driver.on_shutdown
async def cleanup_modules():
    """清理资源"""
    global cache_manager, db_manager

    try:
        if cache_manager:
            await cache_manager.disconnect()

        if db_manager:
            await db_manager.disconnect()

        logger.info("LLM Endpoint plugin cleaned up")

    except Exception as e:
        logger.error(f"Cleanup error: {e}")


# =============================================================================
# (6) 辅助函数
# =============================================================================


def _get_user_key(event: MessageEvent) -> str:
    """获取用户唯一标识

    Args:
        event: 消息事件

    Returns:
        用户唯一标识（群组_用户ID 或 用户ID）
    """
    user_id = str(event.user_id)
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        return f"{group_id}_{user_id}"
    return user_id


def _get_user_name(event: MessageEvent) -> str:
    """获取用户名称

    Args:
        event: 消息事件

    Returns:
        用户名称
    """
    if hasattr(event, 'sender') and event.sender:
        return event.sender.nickname or ""
    return ""


# =============================================================================
# (7) 通用消息处理器
# =============================================================================

chat_handler = on_message(priority=9999, block=False)

llm_service = get_llm_service()


@chat_handler.handle()
async def handle_message(bot: Bot, event: MessageEvent):
    """处理所有消息

    Args:
        bot: Bot实例
        event: 消息事件
    """
    content = event.get_plaintext().strip()
    if content is not None and 'csn' in content:
        # 使用 matcher.send() 而非 bot.send()，兼容性更好
        # send() 只发送消息，不抛出 FinishedException
        await bot.send(event=event, message='反弹！👴csn！', at_sender=True, reply_message=True)


# =============================================================================
# (8) 命令处理器
# =============================================================================

# 天气查询命令
weather_cmd = on_command("天气", aliases={"weather"}, priority=5, block=True)


@weather_cmd.handle()
async def handle_weather(bot: Bot, event: MessageEvent):
    """处理天气查询"""
    global weather_module

    if not weather_module:
        await weather_cmd.finish("天气服务未初始化")

    try:
        message = event.get_plaintext().strip()
        result = await weather_module.handle(message)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"Weather command error: {e}")
        await weather_cmd.finish("查询天气失败，请稍后再试。")


# 创建上下文命令
create_context_cmd = on_command("创建上下文", priority=5, block=True)

@create_context_cmd.handle()
async def handle_create_context(bot: Bot, event: MessageEvent):
    """处理创建上下文命令"""
    global context_cmd_module

    if not context_cmd_module:
        await create_context_cmd.finish(event=event, message="上下文服务未初始化", at_sender=True, reply_message=True)

    try:
        user_id = _get_user_key(event)
        user_name = _get_user_name(event)

        result = await context_cmd_module.cmd_create_context(user_id, user_name)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"Create context command error: {e}")
        await create_context_cmd.finish("创建上下文失败")


# 加入上下文命令
join_context_cmd = on_command("加入上下文", priority=5, block=True)


@join_context_cmd.handle()
async def handle_join_context(bot: Bot, event: MessageEvent):
    """处理加入上下文命令"""
    global context_cmd_module

    if not context_cmd_module:
        await join_context_cmd.finish("上下文服务未初始化")

    try:
        user_id = _get_user_key(event)
        user_name = _get_user_name(event)
        message = event.get_plaintext().strip()

        # 解析上下文ID
        context_id = message.replace("加入上下文", "").strip()

        if not context_id:
            await join_context_cmd.finish("请输入要加入的上下文ID\n格式: /加入上下文 <上下文ID>")

        result = await context_cmd_module.cmd_join_context(user_id, context_id, user_name)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"Join context command error: {e}")
        await join_context_cmd.finish("加入上下文失败")


# 离开上下文命令
leave_context_cmd = on_command("离开上下文", priority=5, block=True)


@leave_context_cmd.handle()
async def handle_leave_context(bot: Bot, event: MessageEvent):
    """处理离开上下文命令"""
    global context_cmd_module

    if not context_cmd_module:
        await leave_context_cmd.finish("上下文服务未初始化")

    try:
        user_id = _get_user_key(event)
        user_name = _get_user_name(event)

        result = await context_cmd_module.cmd_leave_context(user_id, user_name)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"Leave context command error: {e}")
        await leave_context_cmd.finish("离开上下文失败")


# 结束上下文命令
end_context_cmd = on_command("结束上下文", priority=5, block=True)


@end_context_cmd.handle()
async def handle_end_context(bot: Bot, event: MessageEvent):
    """处理结束上下文命令"""
    global context_cmd_module

    if not context_cmd_module:
        await end_context_cmd.finish("上下文服务未初始化")

    try:
        user_id = _get_user_key(event)
        message = event.get_plaintext().strip()

        # 解析上下文ID（可选）
        context_id = message.replace("结束上下文", "").strip() or None

        result = await context_cmd_module.cmd_end_context(user_id, context_id)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"End context command error: {e}")
        await end_context_cmd.finish("结束上下文失败")


# 查看历史命令
history_cmd = on_command("查看历史", aliases={"history"}, priority=5, block=True)


@history_cmd.handle()
async def handle_history(bot: Bot, event: MessageEvent):
    """处理查看历史命令"""
    global context_cmd_module

    if not context_cmd_module:
        await history_cmd.finish("上下文服务未初始化")

    try:
        user_id = _get_user_key(event)
        result = await context_cmd_module.cmd_show_history(user_id)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"History command error: {e}")
        await history_cmd.finish("查看历史失败")


# 列出上下文命令
list_contexts_cmd = on_command("列出上下文", priority=5, block=True)


@list_contexts_cmd.handle()
async def handle_list_contexts(bot: Bot, event: MessageEvent):
    """处理列出上下文命令"""
    global context_cmd_module

    if not context_cmd_module:
        await list_contexts_cmd.finish("上下文服务未初始化")

    try:
        user_id = _get_user_key(event)
        result = await context_cmd_module.cmd_list_contexts(user_id)
        await bot.send(event=event, message=result, at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"List contexts command error: {e}")
        await list_contexts_cmd.finish("列出上下文失败")


# 列出角色命令
list_roles_cmd = on_command("列出角色", priority=5, block=True)


@list_roles_cmd.handle()
async def handle_list_roles(bot: Bot, event: MessageEvent):
    """处理列出角色命令"""
    global role_play_module

    if not role_play_module:
        await list_roles_cmd.finish("角色服务未初始化")

    try:
        roles = await role_play_module.list_roles(active_only=True)

        if not roles:
            await list_roles_cmd.finish("暂无可用角色")

        lines = ["🎭 可用角色列表:\n"]
        for role in roles:
            lines.append(f"- {role.name} (ID: {role.role_id})")
            lines.append(f"  {role.description}")

        await bot.send(event=event, message="\n".join(lines), at_sender=True, reply_message=True)

    except Exception as e:
        logger.error(f"List roles command error: {e}")
        await list_roles_cmd.finish("列出角色失败")


# 切换角色命令
switch_role_cmd = on_command("切换角色", priority=5, block=True)


@switch_role_cmd.handle()
async def handle_switch_role(bot: Bot, event: MessageEvent):
    """处理切换角色命令"""
    global role_play_module, context_manager, user_manager

    if not role_play_module or not context_manager or not user_manager:
        await switch_role_cmd.finish("服务未初始化")

    try:
        user_id = _get_user_key(event)
        message = event.get_plaintext().strip()

        # 解析角色ID
        role_id = message.replace("切换角色", "").strip()

        if not role_id:
            await switch_role_cmd.finish("请指定要切换的角色ID\n格式: /切换角色 <角色ID>")

        # 获取用户当前上下文
        user = await user_manager.get_user(user_id)
        if not user or not user.current_context_id:
            await switch_role_cmd.send("请先创建一个上下文")

        context = await context_manager.get_context(user.current_context_id)
        if not context:
            await switch_role_cmd.finish("上下文不存在")

        # 激活角色
        success = await role_play_module.activate_role(context, role_id)

        if success:
            role = await role_play_module.get_role(role_id)
            await switch_role_cmd.finish(f"✅ 已切换到角色: {role.name if role else role_id}")
        else:
            await switch_role_cmd.finish("❌ 切换角色失败\n可能原因: 角色ID不存在或角色未激活")

    except Exception as e:
        logger.error(f"Switch role command error: {e}")
        await switch_role_cmd.finish(f"切换角色失败: {str(e)}")


# 帮助命令
help_cmd = on_command("帮助", aliases={"help", "?"}, priority=5, block=True)


@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    """处理帮助命令"""
    help_text = """📚 考研408 QQ机器人帮助

💬 **对话功能**
- 直接发送消息即可与AI对话
- 支持上下文记忆

🌤️ **天气查询**
- /天气 <地点> - 查询天气

📋 **上下文管理**
- /创建上下文 - 创建新的对话上下文
- /加入上下文 <ID> - 加入指定上下文
- /离开上下文 - 离开当前上下文
- /结束上下文 - 结束当前上下文
- /查看历史 - 查看对话历史
- /列出上下文 - 列出所有上下文

🎭 **角色扮演**
- /列出角色 - 查看可用角色
- /切换角色 <ID> - 切换对话角色

❓ **获取帮助**
- /帮助 - 显示此帮助信息

💡 **提示**
- 私聊和群聊都可以使用
- 上下文会自动管理，无需手动创建
- 使用 /创建上下文 可以创建专属对话空间"""

    await help_cmd.finish(help_text)


# =============================================================================
# (9) 导出
# =============================================================================

__all__ = [
    "logger",
]
