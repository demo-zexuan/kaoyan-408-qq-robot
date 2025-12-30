"""
LangGraph管理模块

实现基于LangGraph的状态图管理，用于处理消息流转和响应生成。
"""

# =============================================================================
# (1) 导入依赖
# =============================================================================
from __future__ import annotations

from typing import Callable, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.state import (
    IntentType,
    ProcessingStage,
    RouteTarget,
    RobotState,
)
from src.utils.logger import get_logger

# =============================================================================
# (2) 日志配置
# =============================================================================

logger = get_logger(__name__)


# =============================================================================
# (3) LangGraph管理器
# =============================================================================


class LangGraphManager:
    """LangGraph管理器

    负责构建和管理状态图，定义消息处理的流程节点和条件边。

    节点定义：
    - input_processor: 输入预处理
    - intent_classifier: 意图分类
    - context_loader: 上下文加载
    - response_generator: 响应生成
    - error_handler: 错误处理

    条件边定义：
    - route_by_intent: 根据意图路由到不同模块
    - check_terminal: 检查是否到达终止状态
    """

    # I. 初始化
    def __init__(
        self,
        intent_classifier: Optional[Callable] = None,
        response_generator: Optional[Callable] = None,
    ) -> None:
        """初始化LangGraph管理器

        Args:
            intent_classifier: 意图分类函数 (state: RobotState) -> IntentResult
            response_generator: 响应生成函数 (state: RobotState) -> str
        """
        self.intent_classifier = intent_classifier
        self.response_generator = response_generator
        self._graph: Optional[CompiledStateGraph] = None

        logger.info("LangGraphManager initialized")

    # II. 图构建
    def compile(self) -> CompiledStateGraph:
        """编译状态图

        Returns:
            编译后的状态图
        """
        if self._graph is None:
            self._graph = self._build_graph()
            logger.info("State graph compiled successfully")
        return self._graph

    def _build_graph(self) -> CompiledStateGraph:
        """构建状态图

        Returns:
            编译后的状态图
        """
        # 创建状态图构建器
        builder = StateGraph(RobotState)

        # 添加节点
        builder.add_node("input_processor", self._input_processor_node)
        builder.add_node("intent_classifier", self._intent_classifier_node)
        builder.add_node("context_loader", self._context_loader_node)
        builder.add_node("response_generator", self._response_generator_node)
        builder.add_node("error_handler", self._error_handler_node)

        # 设置入口点
        builder.set_entry_point("input_processor")

        # 添加条件边：输入处理 -> 意图分类
        builder.add_conditional_edges(
            "input_processor",
            self._should_continue_after_input,
            {
                "continue": "intent_classifier",
                "error": "error_handler",
            },
        )

        # 添加条件边：意图分类 -> 路由
        builder.add_conditional_edges(
            "intent_classifier",
            self._route_by_intent,
            {
                RouteTarget.CHAT_MODULE: "response_generator",
                RouteTarget.WEATHER_MODULE: "response_generator",
                RouteTarget.ROLE_PLAY_MODULE: "response_generator",
                RouteTarget.CONTEXT_HANDLER: "context_loader",
                RouteTarget.ERROR_HANDLER: "error_handler",
            },
        )

        # 添加条件边：上下文加载 -> 响应生成
        builder.add_conditional_edges(
            "context_loader",
            self._should_continue_after_context,
            {
                "generate": "response_generator",
                "error": "error_handler",
            },
        )

        # 添加条件边：响应生成 -> 结束
        builder.add_conditional_edges(
            "response_generator",
            self._should_end,
            {
                "end": END,
                "continue": "response_generator",
            },
        )

        # 错误处理 -> 结束
        builder.add_edge("error_handler", END)

        # 编译图
        return builder.compile()

    # III. 节点实现
    @staticmethod
    async def _input_processor_node(state: RobotState) -> RobotState:
        """输入预处理节点

        对输入消息进行清理、规范化处理。

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Input processor node: message_id={state.message_id}")

        try:
            from src.utils.helpers import TextHelper

            # 清理消息内容
            cleaned_content = TextHelper.clean_text(state.message_content)
            state.message_content = cleaned_content

            # 提取实体
            from src.utils.helpers import EntityHelper

            state.entities = EntityHelper.extract_time_entities(cleaned_content)
            state.entities.update(
                EntityHelper.extract_location_entities(cleaned_content)
            )

            state.processing_stage = ProcessingStage.PREPROCESSING
            return state

        except Exception as e:
            logger.error(f"Error in input_processor: {e}")
            state.error_message = str(e)
            state.error_code = "INPUT_PROCESS_ERROR"
            state.processing_stage = ProcessingStage.FAILED
            return state

    async def _intent_classifier_node(self, state: RobotState) -> RobotState:
        """意图分类节点

        识别用户消息的意图类型。

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Intent classifier node: message_id={state.message_id}")

        try:
            state.processing_stage = ProcessingStage.INTENT_CLASSIFYING

            # 使用意图识别器
            if self.intent_classifier:
                result = await self.intent_classifier(state.message_content)
                state.intent = result.intent
                state.intent_confidence = result.confidence
                state.entities.update(result.entities)
            else:
                # 使用默认意图识别器
                from src.core.intent import get_intent_recognizer

                recognizer = get_intent_recognizer()
                result = recognizer.recognize_sync(state.message_content)
                state.intent = result.intent
                state.intent_confidence = result.confidence
                state.entities.update(result.entities)

            logger.info(
                f"Intent classified: {state.intent} (confidence={state.intent_confidence})"
            )
            return state

        except Exception as e:
            logger.error(f"Error in intent_classifier: {e}")
            state.error_message = str(e)
            state.error_code = "INTENT_CLASSIFY_ERROR"
            state.processing_stage = ProcessingStage.FAILED
            state.intent = IntentType.UNKNOWN
            return state

    @staticmethod
    async def _context_loader_node(state: RobotState) -> RobotState:
        """上下文加载节点

        加载或创建对话上下文。

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Context loader node: message_id={state.message_id}")

        try:
            state.processing_stage = ProcessingStage.CONTEXT_LOADING

            # TODO: 集成上下文管理器
            # 这里需要获取上下文管理器实例并加载上下文
            # 暂时跳过，使用空上下文

            state.processing_stage = ProcessingStage.PROCESSING
            return state

        except Exception as e:
            logger.error(f"Error in context_loader: {e}")
            state.error_message = str(e)
            state.error_code = "CONTEXT_LOAD_ERROR"
            state.processing_stage = ProcessingStage.FAILED
            return state

    async def _response_generator_node(self, state: RobotState) -> RobotState:
        """响应生成节点

        根据意图和上下文生成响应。

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Response generator node: message_id={state.message_id}")

        try:
            state.processing_stage = ProcessingStage.PROCESSING

            # 使用响应生成器
            if self.response_generator:
                response = await self.response_generator(state)
                state.response = response
            else:
                # 默认响应生成
                state.response = self._generate_default_response(state)

            state.processing_stage = ProcessingStage.POSTPROCESSING
            return state

        except Exception as e:
            logger.error(f"Error in response_generator: {e}")
            state.error_message = str(e)
            state.error_code = "RESPONSE_GENERATE_ERROR"
            state.processing_stage = ProcessingStage.FAILED
            state.response = "抱歉，生成回复时出现错误。"
            return state

    @staticmethod
    async def _error_handler_node(state: RobotState) -> RobotState:
        """错误处理节点

        处理流程中的错误情况。

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.warning(f"Error handler node: message_id={state.message_id}")

        state.processing_stage = ProcessingStage.FAILED

        # 根据错误类型生成用户友好的错误消息
        if state.error_code == "INTENT_CLASSIFY_ERROR":
            state.response = "抱歉，我无法理解您的意思。"
        elif state.error_code == "CONTEXT_LOAD_ERROR":
            state.response = "抱歉，加载对话上下文时出现错误。"
        elif state.error_code == "RESPONSE_GENERATE_ERROR":
            state.response = "抱歉，生成回复时出现错误。"
        else:
            state.response = "抱歉，处理您的请求时出现错误。"

        return state

    # IV. 条件边函数
    @staticmethod
    def _should_continue_after_input(state: RobotState) -> str:
        """判断输入处理后是否继续

        Args:
            state: 当前状态

        Returns:
            "continue" 或 "error"
        """
        if state.error_message:
            return "error"
        return "continue"

    @staticmethod
    def _route_by_intent(state: RobotState) -> str:
        """根据意图路由到不同模块

        Args:
            state: 当前状态

        Returns:
            路由目标
        """
        if state.error_message:
            return RouteTarget.ERROR_HANDLER

        intent = state.intent

        # 根据意图类型路由
        if intent == IntentType.WEATHER:
            return RouteTarget.WEATHER_MODULE
        elif intent == IntentType.ROLE_PLAY:
            return RouteTarget.ROLE_PLAY_MODULE
        elif intent in (
            IntentType.CONTEXT_CREATE,
            IntentType.CONTEXT_JOIN,
            IntentType.CONTEXT_LEAVE,
            IntentType.CONTEXT_END,
        ):
            return RouteTarget.CONTEXT_HANDLER
        elif intent == IntentType.CHAT:
            return RouteTarget.CHAT_MODULE
        else:
            return RouteTarget.CHAT_MODULE

    @staticmethod
    def _should_continue_after_context(state: RobotState) -> str:
        """判断上下文加载后是否继续

        Args:
            state: 当前状态

        Returns:
            "generate" 或 "error"
        """
        if state.error_message:
            return "error"
        return "generate"

    @staticmethod
    def _should_end(state: RobotState) -> str:
        """判断是否结束流程

        Args:
            state: 当前状态

        Returns:
            "end" 或 "continue"
        """
        if state.response and state.need_response:
            return "end"
        return "end"

    # V. 默认响应生成
    @staticmethod
    def _generate_default_response(state: RobotState) -> str:
        """生成默认响应

        Args:
            state: 当前状态

        Returns:
            响应内容
        """
        intent = state.intent

        # 根据意图生成默认响应
        if intent == IntentType.WEATHER:
            location = state.entities.get("location", "未知地点")
            return f"正在查询{location}的天气信息..."
        elif intent == IntentType.ROLE_PLAY:
            return "角色扮演功能正在开发中..."
        elif intent == IntentType.CHAT:
            return f"你说：{state.message_content}"
        else:
            return "我收到了你的消息。"

    # VI. 执行接口
    async def process(self, state: RobotState) -> RobotState:
        """处理消息

        Args:
            state: 初始状态

        Returns:
            最终状态
        """
        graph = self.compile()

        try:
            # 转换为LangChain格式
            input_data = state.model_dump()

            # 执行状态图
            result = await graph.ainvoke(input_data)

            # 转换回RobotState
            final_state = RobotState(**result)
            final_state.processing_stage = ProcessingStage.COMPLETED

            return final_state

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            state.error_message = str(e)
            state.error_code = "GRAPH_EXECUTION_ERROR"
            state.processing_stage = ProcessingStage.FAILED
            return state


# =============================================================================
# (4) 辅助函数
# =============================================================================


def state_to_messages(
    state: RobotState,
) -> list[HumanMessage | AIMessage | SystemMessage]:
    """将RobotState转换为LangChain消息列表

    Args:
        state: 机器人状态

    Returns:
        LangChain消息列表
    """
    messages: list[HumanMessage | AIMessage | SystemMessage] = []

    # 添加系统提示
    if state.role_config and "system_prompt" in state.role_config:
        messages.append(SystemMessage(content=state.role_config["system_prompt"]))

    # 添加对话历史
    for msg in state.conversation_history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))

    # 添加当前消息
    messages.append(HumanMessage(content=state.message_content))

    return messages


def messages_to_state(
    state: RobotState, messages: list[HumanMessage | AIMessage | SystemMessage]
) -> RobotState:
    """将LangChain消息列表转换回RobotState

    Args:
        state: 原始状态
        messages: 消息列表

    Returns:
        更新后的状态
    """
    conversation_history = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            continue
        elif isinstance(msg, HumanMessage):
            conversation_history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            conversation_history.append({"role": "assistant", "content": msg.content})

    state.conversation_history = conversation_history
    return state


# =============================================================================
# (5) 单例实例
# =============================================================================

_default_langgraph_manager: Optional[LangGraphManager] = None


def get_langgraph_manager(
    intent_classifier: Optional[Callable] = None,
    response_generator: Optional[Callable] = None,
) -> LangGraphManager:
    """获取默认LangGraph管理器实例

    Args:
        intent_classifier: 意图分类函数
        response_generator: 响应生成函数

    Returns:
        LangGraphManager实例
    """
    global _default_langgraph_manager
    if _default_langgraph_manager is None:
        _default_langgraph_manager = LangGraphManager(
            intent_classifier, response_generator
        )
    return _default_langgraph_manager


# =============================================================================
# (6) 导出
# =============================================================================

__all__ = [
    # 管理器
    "LangGraphManager",
    "get_langgraph_manager",
    # 辅助函数
    "state_to_messages",
    "messages_to_state",
]
