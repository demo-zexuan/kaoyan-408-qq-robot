"""
角色扮演模块

提供角色扮演对话功能。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import validate_call

from src.core.context import ContextManager
from src.service import LLMService, get_llm_service
from src.storage import (
    ChatMessage,
    Context,
    MessageRole,
    RolePlayConfig,
    RoleConfigRepository,
)
from src.storage import DatabaseManager
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) 默认角色配置
# =============================================================================

DEFAULT_ROLES = {
    "assistant": {
        "name": "助手",
        "description": "一个友好、专业的AI助手",
        "system_prompt": """你是一个友好、专业的AI助手。

你的特点：
- 回答简洁明了，通常不超过200字
- 语气友善，专业可靠
- 能够帮助用户解决各种问题

请用中文回答。""",
        "is_active": True,
    },
    "teacher": {
        "name": "老师",
        "description": "一位耐心、专业的考研辅导老师",
        "system_prompt": """你是一位耐心、专业的考研辅导老师。

你的特点：
- 深入了解考研408各科知识点
- 能够用通俗易懂的方式讲解复杂概念
- 语气鼓励、耐心，给学生信心
- 经常提醒学生注意学习方法

请用中文回答。""",
        "is_active": True,
    },
    "humorous": {
        "name": "幽默大师",
        "description": "一个风趣幽默的AI，能让学习变得更有趣",
        "system_prompt": """你是一个风趣幽默的AI助手。

你的特点：
- 回答轻松有趣，可以适当开玩笑
- 喜欢用网络流行语和表情符号
- 在幽默中也能提供有价值的信息
- 让学习变得不再枯燥

请用中文回答。""",
        "is_active": True,
    },
}


# =============================================================================
# (4) 角色文件加载辅助函数
# =============================================================================


def _load_role_from_file(role_file: Path) -> Optional[dict]:
    """从单个文件加载角色配置

    Args:
        role_file: 角色配置文件路径

    Returns:
        角色配置字典，失败返回None
    """
    try:
        if not role_file.exists():
            return None

        with open(role_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load role file {role_file}: {e}")
        return None


def _load_roles_from_directory(roles_dir: Path) -> dict[str, dict]:
    """从目录加载所有角色配置

    Args:
        roles_dir: 角色配置目录路径

    Returns:
        角色配置字典 {role_id: role_config}
    """
    roles = {}
    if not roles_dir.exists():
        logger.warning(f"Roles directory not found: {roles_dir}")
        return roles

    for role_file in roles_dir.glob("*.json"):
        role_id = role_file.stem
        role_data = _load_role_from_file(role_file)
        if role_data:
            roles[role_id] = role_data
            logger.debug(f"Loaded role: {role_id} from {role_file}")

    return roles

# =============================================================================
# (5) 角色扮演模块
# =============================================================================


class RolePlayModule:
    """角色扮演模块

    提供角色扮演对话功能。

    主要功能：
    - 创建和管理角色配置
    - 激活/切换角色
    - 以角色身份生成回复
    - 列出可用角色
    """

    # I. 初始化
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        context_manager: Optional[ContextManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        roles_dir: Optional[Path] = None,
    ) -> None:
        """初始化角色扮演模块

        Args:
            llm_service: LLM服务实例
            context_manager: 上下文管理器实例
            db_manager: 数据库管理器实例
            roles_dir: 角色配置文件目录
        """
        self.llm_service = llm_service or get_llm_service()
        self.context_manager = context_manager
        self.db_manager = db_manager

        if db_manager:
            self.role_repo = RoleConfigRepository(db_manager)
        else:
            self.role_repo = None

        self.roles_dir = roles_dir or Path("resource/roles")

        # 加载默认角色（优先从文件加载，回退到硬编码配置）
        self._default_roles = self._load_default_roles()

        logger.info("RolePlayModule initialized")

    def _load_default_roles(self) -> dict[str, dict]:
        """加载默认角色配置

        优先从resource/roles/目录加载，如果目录不存在或为空，
        则使用硬编码的DEFAULT_ROLES作为回退。

        Returns:
            角色配置字典
        """
        # 尝试从目录加载
        if self.roles_dir:
            file_roles = _load_roles_from_directory(self.roles_dir)
            if file_roles:
                logger.info(f"Loaded {len(file_roles)} roles from {self.roles_dir}")
                return file_roles

        # 回退到硬编码配置
        logger.info("Using hardcoded default roles")
        return DEFAULT_ROLES

    # II. 角色管理
    @validate_call
    async def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        system_prompt: str,
        is_active: bool = True,
    ) -> RolePlayConfig:
        """创建新角色

        Args:
            role_id: 角色ID
            name: 角色名称
            description: 角色描述
            system_prompt: 系统提示词
            is_active: 是否激活

        Returns:
            创建的角色配置
        """
        role = RolePlayConfig(
            role_id=role_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            is_active=is_active,
        )

        if self.role_repo:
            created = await self.role_repo.create(role)
            logger.info(f"Role created: {role_id}")
            return created

        return role

    @validate_call
    async def get_role(self, role_id: str) -> Optional[RolePlayConfig]:
        """获取角色配置

        Args:
            role_id: 角色ID

        Returns:
            角色配置对象，不存在返回None
        """
        # 先从数据库查找
        if self.role_repo:
            role = await self.role_repo.get(role_id)
            if role:
                return role

        # 从默认角色查找
        if role_id in self._default_roles:
            data = self._default_roles[role_id]
            return RolePlayConfig(
                role_id=role_id,
                **data,
            )

        return None

    async def list_roles(
        self,
        active_only: bool = False,
    ) -> list[RolePlayConfig]:
        """列出可用角色

        Args:
            active_only: 只返回激活的角色

        Returns:
            角色配置列表
        """
        roles = []

        # 从数据库获取
        if self.role_repo:
            db_roles = await self.role_repo.list_active()
            if active_only:
                roles.extend(db_roles)
            else:
                roles.extend(db_roles)

        # 添加默认角色（去重）
        existing_ids = {r.role_id for r in roles}
        for role_id, data in self._default_roles.items():
            if role_id not in existing_ids:
                role = RolePlayConfig(
                    role_id=role_id,
                    **data,
                )
                if not active_only or role.is_active:
                    roles.append(role)

        logger.debug(f"Listed {len(roles)} roles")
        return roles

    # III. 角色激活
    @validate_call
    async def activate_role(
        self,
        context: Context,
        role_id: str,
    ) -> bool:
        """激活上下文的当前角色

        Args:
            context: 上下文对象
            role_id: 角色ID

        Returns:
            是否成功激活
        """
        role = await self.get_role(role_id)

        if not role:
            logger.warning(f"Role not found: {role_id}")
            return False

        if not role.is_active:
            logger.warning(f"Role is inactive: {role_id}")
            return False

        # 更新上下文的角色配置
        if self.context_manager:
            context.current_role_id = role_id
            await self.context_manager.update_context(context)
            logger.info(
                f"Role activated: {role_id} for context {context.context_id}"
            )
            return True

        return False

    # IV. 对话生成
    @validate_call
    async def generate_response(
        self,
        user_message: str,
        context: Optional[Context] = None,
        user_id: str = "",
        max_history: int = 10,
    ) -> str:
        """以角色身份生成回复

        Args:
            user_message: 用户消息
            context: 对话上下文
            user_id: 用户ID
            max_history: 最大历史消息数

        Returns:
            角色回复文本
        """
        # 获取当前角色
        role_id = context.current_role_id if context else None
        role = None

        if role_id:
            role = await self.get_role(role_id)

        # 使用角色提示词或默认提示词
        system_prompt = role.system_prompt if role else "你是一个AI助手。"

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史消息
        if context and self.context_manager:
            history = await self.context_manager.get_messages(
                context.context_id,
                limit=max_history,
            )

            for msg in history:
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

            role_name = role.name if role else "AI"
            logger.info(
                f"Role response generated: {role_name} for user {user_id}"
            )
            return ai_message

        except Exception as e:
            logger.error(f"Role play error: {e}")
            return "抱歉，我现在无法回复，请稍后再试。"

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

            await self.context_manager.add_message(
                context_id=context.context_id,
                sender_id=user_id,
                sender_name=user_id,
                content=user_message,
                role=MessageRole.USER,
            )

            await self.context_manager.add_message(
                context_id=context.context_id,
                sender_id="system",
                sender_name="AI助手",
                content=ai_message,
                role=MessageRole.ASSISTANT,
            )

        except Exception as e:
            logger.error(f"Save messages error: {e}")

    # VI. 角色文件操作
    async def load_roles_from_file(self, filepath: Path) -> int:
        """从文件加载角色配置

        Args:
            filepath: 配置文件路径

        Returns:
            加载的角色数量
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            count = 0
            for role_id, role_data in data.items():
                role = RolePlayConfig(
                    role_id=role_id,
                    **role_data,
                )
                if self.role_repo:
                    await self.role_repo.create(role)
                count += 1

            logger.info(f"Loaded {count} roles from {filepath}")
            return count

        except Exception as e:
            logger.error(f"Load roles error: {e}")
            return 0


# =============================================================================
# (6) 单例实例
# =============================================================================

_default_role_play_module: Optional[RolePlayModule] = None


def get_role_play_module(
    llm_service: Optional[LLMService] = None,
    context_manager: Optional[ContextManager] = None,
    db_manager: Optional[DatabaseManager] = None,
    roles_dir: Optional[Path] = None,
) -> RolePlayModule:
    """获取默认角色扮演模块实例

    Args:
        llm_service: LLM服务实例
        context_manager: 上下文管理器实例
        db_manager: 数据库管理器实例
        roles_dir: 角色配置文件目录

    Returns:
        RolePlayModule实例
    """
    global _default_role_play_module
    if _default_role_play_module is None:
        _default_role_play_module = RolePlayModule(
            llm_service,
            context_manager,
            db_manager,
            roles_dir,
        )
    return _default_role_play_module


# =============================================================================
# (7) 导出
# =============================================================================

__all__ = [
    "RolePlayModule",
    "get_role_play_module",
    "DEFAULT_ROLES",
]
