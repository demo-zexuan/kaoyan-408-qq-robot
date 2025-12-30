"""
意图识别模块

实现用户消息的意图识别功能，支持关键词匹配、正则表达式识别和LLM分类。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

import re
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator

from src.core.state import IntentResult, IntentType
from src.utils.helpers import EntityHelper
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) 意图规则配置
# =============================================================================

class IntentRule(BaseModel):
    """意图识别规则配置"""

    intent: IntentType = Field(description="意图类型")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    patterns: list[str] = Field(default_factory=list, description="正则表达式模式")
    priority: int = Field(default=0, description="优先级（数字越大优先级越高）")
    description: str = Field(default="", description="规则描述")

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, patterns: list[str]) -> list[str]:
        """验证正则表达式模式是否有效"""
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
        return patterns


# 默认意图识别规则
DEFAULT_INTENT_RULES: list[dict[str, Any]] = [
    {
        "intent": IntentType.WEATHER,
        "keywords": ["天气", "气温", "温度", "下雨", "下雪", "晴天", "阴天", "刮风"],
        "patterns": [r".*天气.*", r".*(?:气温|温度).*", r".*(?:雨|雪|晴|阴|风).*"],
        "priority": 10,
        "description": "天气查询意图",
    },
    {
        "intent": IntentType.ROLE_PLAY,
        "keywords": ["扮演", "角色", "角色扮演", "变成", "当作"],
        "patterns": [r"扮演.*", r"角色.*", r"变成.*"],
        "priority": 15,
        "description": "角色扮演意图",
    },
    {
        "intent": IntentType.CONTEXT_CREATE,
        "keywords": ["创建对话", "新建对话", "创建上下文", "开始对话"],
        "patterns": [r"创建.*(?:对话|上下文)", r"新建.*对话"],
        "priority": 20,
        "description": "创建上下文意图",
    },
    {
        "intent": IntentType.CONTEXT_JOIN,
        "keywords": ["加入对话", "进入对话", "加入上下文"],
        "patterns": [r"加入.*(?:对话|上下文)", r"进入.*对话"],
        "priority": 20,
        "description": "加入上下文意图",
    },
    {
        "intent": IntentType.CONTEXT_LEAVE,
        "keywords": ["离开对话", "退出对话", "离开上下文"],
        "patterns": [r"(?:离开|退出).*(?:对话|上下文)"],
        "priority": 20,
        "description": "离开上下文意图",
    },
    {
        "intent": IntentType.CONTEXT_END,
        "keywords": ["结束对话", "终止对话", "结束上下文", "关闭对话"],
        "patterns": [r"(?:结束|终止|关闭).*(?:对话|上下文)"],
        "priority": 20,
        "description": "结束上下文意图",
    },
    {
        "intent": IntentType.COMMAND,
        "keywords": ["/help", "/start", "/status", "/config", "/ban", "/unban"],
        "patterns": [r"/[a-zA-Z]+"],
        "priority": 30,
        "description": "命令操作意图",
    },
    {
        "intent": IntentType.CHAT,
        "keywords": ["你好", "嗨", "在吗", "早上好", "晚安", "谢谢", "再见"],
        "patterns": [r".*"],
        "priority": 0,
        "description": "普通聊天意图（默认）",
    },
]


# =============================================================================
# (4) 意图识别器
# =============================================================================

class IntentRecognizer:
    """意图识别器

    支持多种识别方式：
    1. 关键词匹配
    2. 正则表达式匹配
    3. 实体提示识别
    4. LLM分类（预留接口）

    识别流程：
    - 遍历规则（按优先级降序）
    - 对每条规则进行关键词和正则匹配
    - 返回首个匹配的意图，若无匹配则返回UNKNOWN
    """

    # I. 初始化
    def __init__(self, rules: Optional[list[dict[str, Any]]] = None) -> None:
        """初始化意图识别器

        Args:
            rules: 自定义规则列表，若为None则使用默认规则
        """
        if rules is None:
            rules = DEFAULT_INTENT_RULES

        # 按优先级降序排序规则
        rules_list = sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)
        self.rules: list[IntentRule] = [IntentRule(**r) for r in rules_list]

        # 预编译正则表达式
        self._compiled_patterns: list[tuple[IntentRule, re.Pattern]] = []
        for rule in self.rules:
            for pattern_str in rule.patterns:
                try:
                    pattern = re.compile(pattern_str)
                    self._compiled_patterns.append((rule, pattern))
                except re.error as e:
                    logger.warning(f"Failed to compile pattern '{pattern_str}': {e}")

        logger.info(f"IntentRecognizer initialized with {len(self.rules)} rules")

    # II. 公共方法
    async def recognize(
        self,
        text: str,
        use_llm: bool = False,
    ) -> IntentResult:
        """识别文本意图

        Args:
            text: 输入文本
            use_llm: 是否使用LLM进行意图分类（暂未实现）

        Returns:
            意图识别结果
        """
        text = text.strip()
        if not text:
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                raw_input=text,
                reasoning="Empty input",
            )

        # 如果启用LLM且可用，使用LLM分类
        if use_llm:
            return await self._recognize_by_llm(text)

        # 使用规则匹配
        return self._recognize_by_rules(text)

    def recognize_sync(self, text: str) -> IntentResult:
        """同步版本的意图识别

        Args:
            text: 输入文本

        Returns:
            意图识别结果
        """
        text = text.strip()
        if not text:
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                raw_input=text,
                reasoning="Empty input",
            )

        return self._recognize_by_rules(text)

    # III. 规则匹配方法
    def _recognize_by_rules(self, text: str) -> IntentResult:
        """使用规则匹配进行意图识别

        Args:
            text: 输入文本

        Returns:
            意图识别结果
        """
        # 提取实体提示
        hints = EntityHelper.extract_intent_hints(text)

        # 检查是否包含命令
        if hints["has_command"]:
            command = hints["command"]
            for rule in self.rules:
                if rule.intent == IntentType.COMMAND and any(
                    cmd in text for cmd in rule.keywords
                ):
                    return IntentResult(
                        intent=IntentType.COMMAND,
                        confidence=0.95,
                        raw_input=text,
                        entities={"command": command},
                        reasoning=f"Command detected: /{command}",
                    )

        # 按优先级遍历规则
        for rule in self.rules:
            # 跳过命令规则（已处理）
            if rule.intent == IntentType.COMMAND:
                continue

            # 关键词匹配
            if rule.keywords and any(kw in text for kw in rule.keywords):
                confidence = self._calculate_keyword_confidence(text, rule.keywords)
                return IntentResult(
                    intent=rule.intent,
                    confidence=confidence,
                    raw_input=text,
                    reasoning=f"Keyword match: {rule.description}",
                )

            # 正则表达式匹配
            if rule.patterns:
                for rule_ref, pattern in self._compiled_patterns:
                    if rule_ref == rule and pattern.search(text):
                        return IntentResult(
                            intent=rule.intent,
                            confidence=0.85,
                            raw_input=text,
                            reasoning=f"Pattern match: {rule.description}",
                        )

        # 默认返回CHAT意图
        return IntentResult(
            intent=IntentType.CHAT,
            confidence=0.5,
            raw_input=text,
            reasoning="No specific pattern matched, default to CHAT",
        )

    @staticmethod
    def _calculate_keyword_confidence(text: str, keywords: list[str]) -> float:
        """计算关键词匹配置信度

        Args:
            text: 输入文本
            keywords: 关键词列表

        Returns:
            置信度分数（0-1）
        """
        match_count = sum(1 for kw in keywords if kw in text)
        if match_count == 0:
            return 0.0

        # 基础分数
        base_score = 0.7

        # 根据匹配数量增加分数
        bonus = min(match_count * 0.1, 0.2)

        # 根据文本长度调整（短文本匹配更可信）
        length_factor = 1.0 if len(text) < 20 else 0.9

        return min(base_score + bonus, 1.0) * length_factor

    # IV. LLM识别方法（预留）
    async def _recognize_by_llm(self, text: str) -> IntentResult:
        """使用LLM进行意图分类（预留接口）

        Args:
            text: 输入文本

        Returns:
            意图识别结果
        """
        # TODO: 集成LLM服务进行意图分类
        # 目前回退到规则匹配
        logger.warning("LLM intent recognition not implemented, falling back to rules")
        return self._recognize_by_rules(text)

    # V. 管理方法
    def add_rule(self, rule: IntentRule) -> None:
        """添加新的识别规则

        Args:
            rule: 意图规则
        """
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

        # 编译新规则的正则表达式
        for pattern_str in rule.patterns:
            try:
                pattern = re.compile(pattern_str)
                self._compiled_patterns.append((rule, pattern))
            except re.error as e:
                logger.warning(f"Failed to compile pattern '{pattern_str}': {e}")

        logger.info(f"Added rule for intent: {rule.intent}")

    def remove_rules_by_intent(self, intent: IntentType) -> int:
        """移除指定意图的所有规则

        Args:
            intent: 要移除的意图类型

        Returns:
            移除的规则数量
        """
        original_count = len(self.rules)
        self.rules = [r for r in self.rules if r.intent != intent]
        self._compiled_patterns = [
            (r, p) for r, p in self._compiled_patterns if r.intent != intent
        ]
        removed_count = original_count - len(self.rules)
        logger.info(f"Removed {removed_count} rules for intent: {intent}")
        return removed_count


# =============================================================================
# (5) 单例实例
# =============================================================================

# 默认意图识别器实例
_default_recognizer: Optional[IntentRecognizer] = None


def get_intent_recognizer() -> IntentRecognizer:
    """获取默认意图识别器实例

    Returns:
        IntentRecognizer单例实例
    """
    global _default_recognizer
    if _default_recognizer is None:
        _default_recognizer = IntentRecognizer()
    return _default_recognizer


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    # 配置
    "DEFAULT_INTENT_RULES",
    # 模型
    "IntentRule",
    "IntentRecognizer",
    # 工具函数
    "get_intent_recognizer",
]
