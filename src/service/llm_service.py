"""
LLM服务模块

提供大语言模型API调用服务，支持多厂商。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from typing import AsyncIterator, Optional

from pydantic import validate_call

from src.storage import ChatMessage, MessageRole
from src.utils.config import get_config
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)

# =============================================================================
# (3) LLM服务
# =============================================================================

class LLMService:
    """大语言模型服务

    提供统一的LLM调用接口，支持OpenAI兼容的API。
    支持的厂商包括：OpenAI、通义千问、DeepSeek、智谱AI等。

    主要功能：
    - 同步/流式对话
    - 意图分类
    - Token估算
    """

    # I. 初始化
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """初始化LLM服务

        Args:
            api_key: API密钥，不传则从配置读取
            base_url: API基础URL，不传则从配置读取
            model: 模型名称，不传则从配置读取
        """
        config = get_config()

        self.api_key = api_key or config.llm_api_key
        self.base_url = base_url or config.llm_base_url
        self.model = model or config.llm_model
        self.max_tokens = config.llm_max_tokens
        self.temperature = config.llm_temperature

        # 懒加载客户端
        self._client: Optional[object] = None

        if not self.api_key:
            logger.warning("LLM API key not configured, service will be disabled")

        logger.info(
            f"LLMService initialized: model={self.model}, "
            f"base_url={self.base_url}"
        )

    # II. 客户端管理
    def _get_client(self) -> object:
        """获取或创建LLM客户端

        Returns:
            OpenAI客户端实例
        """
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
                logger.debug("OpenAI client created")
            except ImportError:
                logger.error(
                    "openai package not installed. "
                    "Install with: uv add openai"
                )
                raise RuntimeError(
                    "openai package is required for LLMService. "
                    "Install with: uv add openai"
                )

        return self._client

    # III. 对话接口
    @validate_call
    async def chat(
        self,
        messages: list[ChatMessage] | list[dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """发送对话请求

        Args:
            messages: 消息列表
            max_tokens: 最大生成Token数
            temperature: 温度参数

        Returns:
            模型响应文本
        """
        if not self.api_key:
            return "LLM服务未配置，请设置API密钥"

        client = self._get_client()

        # 转换消息格式
        api_messages = self._convert_messages(messages)

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
            )

            result = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            logger.info(f"LLM chat completed, tokens: {tokens_used}")
            return result or ""

        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            return f"LLM调用失败: {str(e)}"

    @validate_call
    async def stream_chat(
        self,
        messages: list[ChatMessage] | list[dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式对话接口

        Args:
            messages: 消息列表
            max_tokens: 最大生成Token数
            temperature: 温度参数

        Yields:
            模型响应文本片段
        """
        if not self.api_key:
            yield "LLM服务未配置，请设置API密钥"
            return

        client = self._get_client()
        api_messages = self._convert_messages(messages)

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"LLM stream chat error: {e}")
            yield f"LLM调用失败: {str(e)}"

    # IV. 意图分类
    @validate_call
    async def classify_intent(
        self,
        text: str,
        intents: list[str],
    ) -> dict[str, float]:
        """对文本进行意图分类

        Args:
            text: 输入文本
            intents: 候选意图列表

        Returns:
            意图得分字典 {intent: score}
        """
        if not self.api_key:
            return {}

        # 构造分类提示
        intent_list = "\n".join(f"- {i}" for i in intents)
        prompt = f"""请分析以下用户消息的意图。

用户消息: {text}

可能的意图:
{intent_list}

请返回每个意图的匹配度（0-1之间的分数），格式为JSON:
{{{{"意图名": 分数, ...}}}}

只返回JSON，不要其他内容。"""

        try:
            response = await self.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,  # 低温度确保稳定性
            )

            # 解析JSON响应
            import json

            # 提取JSON部分
            result = response.strip()
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()

            scores = json.loads(result)
            logger.debug(f"Intent classification result: {scores}")
            return scores

        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return {}

    # V. Token估算
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算文本的Token数量

        使用粗略估算：中文约1字符=1token，英文约4字符=1token

        Args:
            text: 输入文本

        Returns:
            估算的Token数量
        """
        import re

        # 统计中文字符
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        # 统计非中文字符
        other_chars = len(text) - chinese_chars

        # 中文1字符≈1token，英文/数字≈4字符≈1token
        return chinese_chars + (other_chars // 4) + 1

    def estimate_messages_tokens(
        self,
        messages: list[ChatMessage] | list[dict],
    ) -> int:
        """估算消息列表的Token数量

        Args:
            messages: 消息列表

        Returns:
            估算的Token数量
        """
        total = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                content = msg.content
            total += self.estimate_tokens(content)

        # 加上每个消息的元数据开销（约3-4 tokens/消息）
        total += len(messages) * 4
        return total

    # VI. 辅助方法
    @staticmethod
    def _convert_messages(
            messages: list[ChatMessage] | list[dict],
    ) -> list[dict]:
        """转换消息格式为API格式

        Args:
            messages: 消息列表

        Returns:
            API格式的消息列表
        """
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            elif isinstance(msg, ChatMessage):
                result.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })
            else:
                logger.warning(f"Unknown message type: {type(msg)}")
        return result

    async def check_connection(self) -> bool:
        """检查LLM服务连接

        Returns:
            是否连接正常
        """
        if not self.api_key:
            return False

        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
            return bool(response)
        except Exception as e:
            logger.error(f"LLM connection check failed: {e}")
            return False


# =============================================================================
# (4) 单例实例
# =============================================================================

_default_llm_service: Optional[LLMService] = None


def get_llm_service(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMService:
    """获取默认LLM服务实例

    Args:
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称

    Returns:
        LLMService实例
    """
    global _default_llm_service
    if _default_llm_service is None:
        _default_llm_service = LLMService(api_key, base_url, model)
    return _default_llm_service


# =============================================================================
# (5) 导出
# =============================================================================

__all__ = [
    "LLMService",
    "get_llm_service",
]
