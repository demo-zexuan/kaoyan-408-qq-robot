"""
LangGraph 系统教程示例
====================

LangGraph 是一个用于构建有状态的、多参与者的 LLM 应用的库。
它通过图结构来定义应用逻辑，节点(Node)是计算单元，边(Edge)定义执行流程。

核心概念：
- State(状态): 在图中流动的数据，定义了节点间共享的信息结构
- Node(节点): 接收状态、处理逻辑、返回更新后的状态的函数
- Edge(边): 定义节点间的转换关系
- Graph(图): 由节点和边组成的有向图
"""

# =============================================================================
# 第一部分：基础概念 - State 定义
# =============================================================================
from typing import List
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

# =============================================================================
# 方式一：使用 Pydantic BaseModel（推荐，LangGraph 官方支持）
# =============================================================================


class SimpleState(BaseModel):
    """最简单的状态定义"""

    messages: List[str] = Field(default_factory=list)
    count: int = 0


class AgentState(BaseModel):
    """典型智能体状态 - 使用 Pydantic BaseModel"""

    messages: List[str] = Field(default_factory=list)
    user_input: str = ""
    response: str = ""
    step_count: int = 0


# =============================================================================
# 第二部分：节点(Node)定义
# =============================================================================
# 节点函数现在接收并返回完整的 State 对象


def hello_node(state: AgentState) -> dict:
    """简单的问候节点 - 返回需要更新的字段"""
    print(f"[Hello Node] 收到消息: {state.user_input}")
    return {
        "messages": state.messages + ["系统: 你好！"],
        "step_count": state.step_count + 1,
    }


def process_node(state: AgentState) -> dict:
    """处理用户输入的节点"""
    print(f"[Process Node] 处理中: {state.user_input}")
    response = f"我听到了：{state.user_input}"
    return {
        "messages": state.messages + [f"处理: {response}"],
        "response": response,
        "step_count": state.step_count + 1,
    }


def goodbye_node(state: AgentState) -> dict:
    """告别节点"""
    print(f"[Goodbye Node] 执行了 {state.step_count} 步")
    return {
        "messages": state.messages + ["系统: 再见！"],
        "step_count": state.step_count + 1,
    }


# =============================================================================
# 第三部分：条件边(Conditional Edge)定义
# =============================================================================


def should_continue(state: AgentState) -> str:
    """条件函数：决定下一步走向"""
    user_input = state.user_input.lower()
    if "再见" in user_input or "bye" in user_input:
        return "end"
    elif "天气" in user_input:
        return "weather"
    else:
        return "process"


def route_by_length(state: AgentState) -> str:
    """根据输入长度路由"""
    if len(state.user_input) > 10:
        return "long_input_handler"
    else:
        return "short_input_handler"


# =============================================================================
# 第四部分：示例 1 - 最简单的线性图
# =============================================================================


def create_simple_linear_graph():
    """
    线性图: Node A -> Node B -> Node C -> End
    这是最基础的图结构，节点按顺序依次执行
    """
    # 创建状态图 - 传入 Pydantic BaseModel 类
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("hello", hello_node)
    graph.add_node("process", process_node)
    graph.add_node("goodbye", goodbye_node)

    # 设置入口点
    graph.set_entry_point("hello")

    # 添加边（定义执行顺序）
    graph.add_edge("hello", "process")
    graph.add_edge("process", "goodbye")
    graph.add_edge("goodbye", END)

    # 编译图
    return graph.compile()


# =============================================================================
# 第五部分：示例 2 - 带条件分支的图
# =============================================================================


def conditional_response_node(state: AgentState) -> dict:
    """根据不同条件返回不同响应"""
    if "天气" in state.user_input.lower():
        response = "今天天气晴朗，温度25度"
    else:
        response = "我不太理解，请重新输入"
    return {
        "messages": state.messages + [f"响应: {response}"],
        "response": response,
        "step_count": state.step_count + 1,
    }


def create_conditional_graph():
    r"""
    条件分支图:
           [Entry]
              |
           [hello]
              |
         [should_continue]
          /      \
    [process]  [conditional_response]
          \      /
           [goodbye]
               |
             [END]
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("hello", hello_node)
    graph.add_node("process", process_node)
    graph.add_node("conditional", conditional_response_node)
    graph.add_node("goodbye", goodbye_node)

    # 设置入口
    graph.set_entry_point("hello")

    # 添加条件边：从hello节点根据条件决定下一步
    graph.add_conditional_edges(
        "hello",
        should_continue,
        {
            "process": "process",  # 正常处理
            "weather": "conditional",  # 天气查询
            "end": "goodbye",  # 直接结束
        },
    )

    # 汇聚到goodbye节点
    graph.add_edge("process", "goodbye")
    graph.add_edge("conditional", "goodbye")
    graph.add_edge("goodbye", END)

    return graph.compile()


# =============================================================================
# 第六部分：示例 3 - 带循环的图（典型RAG模式）
# =============================================================================


class RAGState(BaseModel):
    """RAG应用的状态定义"""

    question: str = ""
    documents: List[str] = Field(default_factory=list)
    answer: str = ""
    iterations: int = 0


def retrieve_node(state: RAGState) -> dict:
    """检索节点：模拟从知识库检索相关文档"""
    print(f"[检索] 为问题检索文档: {state.question}")
    # 模拟检索结果
    docs = [
        f"文档1: 关于{state.question}的相关信息",
        f"文档2: {state.question}的详细说明",
    ]
    return {"documents": docs, "iterations": state.iterations + 1}


def generate_node(state: RAGState) -> dict:
    """生成节点：基于检索结果生成答案"""
    print(f"[生成] 基于文档生成答案")
    answer = f"基于 {len(state.documents)} 个文档，针对问题 '{state.question}' 的答案是：这是一个模拟答案。"
    return {"answer": answer, "iterations": state.iterations + 1}


def grade_answer(state: RAGState) -> str:
    """评估答案质量"""
    if len(state.answer) < 20:
        return "retrieve"  # 答案太短，重新检索
    return "end"


def create_rag_graph():
    r"""
    RAG循环图:
        [Entry]
           |
       [retrieve] <-------+
           |              |
       [generate] --------+
           |
         [grade]
          /    \
    [retrieve]  [END]
    """
    graph = StateGraph(RAGState)

    # 添加节点
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    # 设置入口
    graph.set_entry_point("retrieve")

    # 检索后生成
    graph.add_edge("retrieve", "generate")

    # 生成后评估，决定是否循环
    graph.add_conditional_edges(
        "generate",
        grade_answer,
        {"retrieve": "retrieve", "end": END},  # 重新检索  # 结束
    )

    return graph.compile()


# =============================================================================
# 第七部分：示例 4 - 多智能体协作图
# =============================================================================


class MultiAgentState(BaseModel):
    """多智能体协作的状态"""

    task: str = ""
    research_result: str = ""
    analysis_result: str = ""
    final_report: str = ""
    agent_history: List[str] = Field(default_factory=list)


def researcher_agent(state: MultiAgentState) -> dict:
    """研究智能体：负责信息收集"""
    print(f"[研究智能体] 正在研究: {state.task}")
    result = f"关于'{state.task}'的研究数据：[模拟数据1, 模拟数据2, 模拟数据3]"
    return {
        "research_result": result,
        "agent_history": state.agent_history + ["研究智能体已完成"],
    }


def analyst_agent(state: MultiAgentState) -> dict:
    """分析智能体：负责数据分析"""
    print(f"[分析智能体] 正在分析研究数据")
    result = f"分析结果：基于研究数据 '{state.research_result[:20]}...' 的深度分析"
    return {
        "analysis_result": result,
        "agent_history": state.agent_history + ["分析智能体已完成"],
    }


def writer_agent(state: MultiAgentState) -> dict:
    """写作智能体：负责生成报告"""
    print(f"[写作智能体] 正在撰写最终报告")
    report = f"""
    # 最终报告

    ## 研究数据
    {state.research_result}

    ## 分析结论
    {state.analysis_result}

    ## 总结
    这是一个由多智能体协作生成的报告。
    """
    return {
        "final_report": report,
        "agent_history": state.agent_history + ["写作智能体已完成"],
    }


def create_multi_agent_graph():
    """
    多智能体协作图:
        [Entry]
           |
       [researcher]
           |
       [analyst]
           |
       [writer]
           |
         [END]
    """
    graph = StateGraph(MultiAgentState)

    # 添加智能体节点
    graph.add_node("researcher", researcher_agent)
    graph.add_node("analyst", analyst_agent)
    graph.add_node("writer", writer_agent)

    # 设置入口
    graph.set_entry_point("researcher")

    # 串联智能体
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


# =============================================================================
# 第八部分：运行示例的主函数
# =============================================================================


def print_separator(title: str) -> None:
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_examples() -> None:
    """运行所有示例"""

    # ========== 示例 1: 线性图 ==========
    print_separator("示例 1: 简单线性图")
    linear_graph = create_simple_linear_graph()
    result = linear_graph.invoke(
        AgentState(user_input="测试消息", messages=[], response="", step_count=0)
    )
    print(f"\n最终结果:")
    print(f"  消息记录: {result['messages']}")
    print(f"  执行步数: {result['step_count']}")

    # ========== 示例 2: 条件分支图 ==========
    print_separator("示例 2: 条件分支图（天气查询）")
    conditional_graph = create_conditional_graph()
    result = conditional_graph.invoke(
        AgentState(user_input="今天天气怎么样", messages=[], response="", step_count=0)
    )
    print(f"\n最终结果:")
    print(f"  响应: {result['response']}")
    print(f"  消息记录: {result['messages']}")

    # ========== 示例 3: RAG循环图 ==========
    print_separator("示例 3: RAG循环图")
    rag_graph = create_rag_graph()
    result = rag_graph.invoke(
        RAGState(question="什么是LangGraph？", documents=[], answer="", iterations=0)
    )
    print(f"\n最终结果:")
    print(f"  问题: {result['question']}")
    print(f"  答案: {result['answer']}")
    print(f"  检索文档数: {len(result['documents'])}")

    # ========== 示例 4: 多智能体协作 ==========
    print_separator("示例 4: 多智能体协作")
    multi_agent_graph = create_multi_agent_graph()
    result = multi_agent_graph.invoke(
        MultiAgentState(
            task="分析2024年AI发展趋势",
            research_result="",
            analysis_result="",
            final_report="",
            agent_history=[],
        )
    )
    print(f"\n最终结果:")
    print(f"  任务: {result['task']}")
    print(f"  智能体执行历史: {result['agent_history']}")
    print(f"  最终报告长度: {len(result['final_report'])} 字符")

    print("\n" + "=" * 60)
    print("  所有示例运行完毕！")
    print("=" * 60)


# =============================================================================
# 第九部分：可视化图结构（需要额外依赖）
# =============================================================================


def visualize_graphs() -> None:
    """
    可视化图结构（需要安装 graphviz）
    安装: brew install graphviz  (macOS)
    """
    try:
        from IPython.display import Image, display

        print_separator("图结构可视化")

        # 线性图
        print("线性图结构:")
        linear_graph = create_simple_linear_graph()
        png_data = linear_graph.get_graph().draw_mermaid_png()
        display(Image(png_data))

        # 条件图
        print("\n条件分支图结构:")
        conditional_graph = create_conditional_graph()
        png_data = conditional_graph.get_graph().draw_mermaid_png()
        display(Image(png_data))

    except ImportError:
        print("可视化需要安装 IPython: pip install ipython")


# =============================================================================
# 原有代码：文档加载示例
# =============================================================================
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_documents_example() -> List:
    """
    LangChain 文档加载示例
    用于在 LangGraph 中构建知识库
    """
    urls = [
        "https://lilianweng.github.io/posts/2024-11-28-reward-hacking/",
        "https://lilianweng.github.io/posts/2024-07-07-hallucination/",
        "https://lilianweng.github.io/posts/2024-04-12-diffusion-video/",
    ]

    # 加载网页文档
    docs = [WebBaseLoader(url).load() for url in urls]
    docs_list = [item for sublist in docs for item in sublist]

    # 文档分块
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=100, chunk_overlap=50
    )
    doc_splits = text_splitter.split_documents(docs_list)

    print(f"加载了 {len(docs_list)} 个文档")
    print(f"分割为 {len(doc_splits)} 个文本块")

    return doc_splits


# =============================================================================
# 程序入口
# =============================================================================

if __name__ == "__main__":
    # 运行所有示例
    run_examples()

    # 如果需要，可以单独运行文档加载示例
    # load_documents_example()

    # 如果有相关依赖，可以可视化图结构
    # visualize_graphs()
