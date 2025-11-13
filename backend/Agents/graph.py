"""
Movi Agent Graph
LangGraph workflow connecting all nodes with human-in-the-loop and page-aware tool filtering
Following the structure of simple_LLM.py with interrupt_before for human confirmation
"""
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import uuid

# Import state and nodes
from State import MoviState
from nodes import (
    agent_node,
    input_processor_node,
    check_consequences_node,
    get_confirmation_node,
    await_user_confirmation_node
)
from tools import ALL_TOOLS, get_tools_for_page

load_dotenv()

# ========== INITIALIZE LLM ==========
# Note: Tools are now bound dynamically in agent_node based on page context
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ========== DEFINE ROUTING FUNCTIONS ==========
def should_check_consequences(state: MoviState):
    """
    Router: Check if we need to verify consequences before executing
    Similar to should_continue in simple_LLM.py
    
    This checks the AGENT'S INTENT to call dangerous tools BEFORE executing them.
    """
    last_message = state["messages"][-1]
    
    # Check if the last message has tool calls (this means agent wants to call tools)
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Define dangerous actions that need human confirmation
        dangerous_tools = [
            "remove_vehicle_from_trip",           # Deletion - needs HITL
            "delete_deployment",                   # Deletion - needs HITL
            "execute_safe_sql_mutation",          # Mutation - needs HITL
            "update_trip_booking_status",         # Could affect bookings
        ]
        
        # Check if any tool call is a dangerous action
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            
            if tool_name in dangerous_tools:
                # Extract entities from tool arguments for consequence checking
                tool_args = tool_call.get("args", {})
                
                # Update state with intent and entities
                state["user_intent"] = tool_name
                state["identified_entities"] = tool_args
                
                return "check_consequences"
        
        # Safe action, go directly to tools
        return "tools"
    
    # No tool calls, end conversation (agent provided final answer)
    return "end"


def route_after_tools(state: MoviState):
    """
    Router: After tools execute, check if agent should continue or end
    """
    # After tools execute, always go back to agent to process results
    # Agent will decide if it needs more tools or can provide final answer
    return "agent"


def should_get_confirmation(state: MoviState):
    """
    Router: After checking consequences, decide if we need user confirmation
    """
    if state.get("requires_confirmation", False):
        return "confirmation"
    else:
        return "tools"


def should_execute_or_cancel(state: MoviState):
    """
    Router: After user confirmation, decide whether to execute or cancel
    """
    if state.get("user_confirmed", False):
        return "tools"
    else:
        return "cancelled"


# ========== DEFINE CANCELLATION NODE ==========
def cancellation_node(state: MoviState):
    """
    Handle action cancellation when user says no
    """
    cancel_message = AIMessage(content="Action cancelled. How else can I help you?")
    return {
        "messages": [cancel_message],
        "requires_confirmation": False,
        "awaiting_confirmation": False,
        "user_confirmed": None
    }


# ========== DEFINE PAGE-AWARE TOOL NODE ==========
def page_aware_tool_node(state: MoviState):
    """
    Execute tools filtered by the current page context.
    This ensures only relevant tools are available for execution.
    """
    context_page = state.get("context_page", "unknown")
    page_tools = get_tools_for_page(context_page)
    
    # Create a ToolNode with page-specific tools
    tool_executor = ToolNode(page_tools)
    return tool_executor(state)


# ========== BUILD GRAPH ==========
workflow = StateGraph(MoviState)

# Add nodes
workflow.add_node("input_processor", input_processor_node)  # NEW: Entry point
workflow.add_node("agent", agent_node)
workflow.add_node("tools", page_aware_tool_node)  # Page-aware tool execution
workflow.add_node("check_consequences", check_consequences_node)
workflow.add_node("confirmation", get_confirmation_node)
workflow.add_node("human_confirmation", await_user_confirmation_node)
workflow.add_node("cancelled", cancellation_node)

# Set entry point to input processor
workflow.set_entry_point("input_processor")

# Connect input processor to agent
workflow.add_edge("input_processor", "agent")

# Add conditional edges from agent
workflow.add_conditional_edges(
    "agent",
    should_check_consequences,
    {
        "check_consequences": "check_consequences",
        "tools": "tools",
        "end": END
    }
)

# After checking consequences
workflow.add_conditional_edges(
    "check_consequences",
    should_get_confirmation,
    {
        "confirmation": "confirmation",
        "tools": "tools"
    }
)

# After showing confirmation message, wait for human input
workflow.add_edge("confirmation", "human_confirmation")

# After human responds
workflow.add_conditional_edges(
    "human_confirmation",
    should_execute_or_cancel,
    {
        "tools": "tools",
        "cancelled": "cancelled"
    }
)

# After tools execute, ALWAYS go back to agent to process results
# Agent will either call more tools or provide final answer
workflow.add_edge("tools", "agent")

# After cancellation, end
workflow.add_edge("cancelled", END)

# Compile the graph WITH checkpointing and interrupt before human confirmation
# This makes the graph PAUSE before "human_confirmation" node and wait for user input
memory = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_confirmation"]  # ⭐ THIS PAUSES THE GRAPH!
)


# ========== MAIN LOOP (for testing) ==========
if __name__ == "__main__":
    print("🤖 Movi Transportation AI Assistant")
    print("=" * 60)
    print("I can help you with:")
    print("  • Managing vehicles and drivers")
    print("  • Creating and viewing routes")
    print("  • Trip assignments and status")
    print("  • Consequence checking for critical actions")
    print("\nType 'exit' or 'quit' to stop")
    print("=" * 60)
    
    # Create a unique thread ID for this conversation session
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    while True:
        user_input = input("\n👤 You: ")
        
        if user_input.lower() in ["exit", "quit"]:
            print("\n👋 Goodbye!")
            break
        
        try:
            # Create initial state with user message
            initial_state = {
                "messages": [HumanMessage(content=user_input)],
                "requires_confirmation": False,
                "awaiting_confirmation": False,
                "user_confirmed": None
            }
            
            # Run the agent with checkpointing
            # If graph is interrupted (needs confirmation), it will pause here
            result = app.invoke(initial_state, config=config)
            
            # Check if graph is waiting for confirmation
            if result.get("awaiting_confirmation", False):
                print("\n🤖 Movi:", result["messages"][-1].content)
                
                # NOW WE WAIT FOR USER INPUT (this is the human-in-the-loop!)
                user_confirmation = input("\n👤 You: ")
                
                # Resume the graph with user's response
                resume_state = {
                    "messages": [HumanMessage(content=user_confirmation)]
                }
                
                # Continue from where we left off (after the interrupt)
                result = app.invoke(resume_state, config=config)
            
            # Get the final response
            last_message = result["messages"][-1]
            print(f"\n🤖 Movi: {last_message.content}")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Make sure your OPENAI_API_KEY is set and database is accessible")
