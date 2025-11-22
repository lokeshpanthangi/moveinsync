from langchain_openai import ChatOpenAI
from Agents.nodes import intent_node, response_node, consequence_node, tool_call_node
from Agents.tools import ALL_TOOLS
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from Agents.state import MoviState
from dotenv import load_dotenv
load_dotenv()


def build_movi_graph(llm, ALL_TOOLS):
    """
    Builds the Movi agent graph with LangGraph's interrupt mechanism.
    
    The graph now uses interrupt() in the consequence_node to pause execution
    and wait for human approval. No separate confirmation nodes needed.
    """

    graph = StateGraph(dict)

    # 1. Add nodes
    graph.add_node("intent", lambda s: intent_node(s, llm, ALL_TOOLS))
    graph.add_node("consequence", consequence_node)
    graph.add_node("tool_call", lambda s: tool_call_node(s, ALL_TOOLS))
    graph.add_node("response", lambda s: response_node(s, llm))

    # 2. Entry → Intent
    graph.set_entry_point("intent")

    # 3. Intent → Consequence (check for high-impact tools)
    graph.add_edge("intent", "consequence")

    # 4. Consequence → Tool Call
    # Note: If consequence_node calls interrupt(), execution pauses here
    # The interrupt() returns when user calls graph.invoke(Command(resume=...))
    graph.add_edge("consequence", "tool_call")

    # 5. Tool_call → response
    graph.add_edge("tool_call", "response")

    # 6. Final node
    graph.set_finish_point("response")

    # 7. Compile with checkpointer for interrupt support
    # MemorySaver is for development - use a durable checkpointer in production
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

# Initialize LLM and build the graph
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
app = build_movi_graph(llm, ALL_TOOLS)