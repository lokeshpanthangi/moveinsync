"""
Movi Agent Graph
LangGraph workflow connecting all nodes with human-in-the-loop
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
from tools import ALL_TOOLS

load_dotenv()

# ========== INITIALIZE LLM WITH TOOLS ==========
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ========== DEFINE ROUTING FUNCTIONS ==========
def should_check_consequences(state: MoviState):
    """
    Router: Check if we need to verify consequences before executing
    Similar to should_continue in simple_LLM.py
    """
    last_message = state["messages"][-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Check if any tool call is a dangerous action
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            
            # Dangerous actions that need confirmation
            dangerous_tools = [
                "remove_vehicle_from_trip",
                "delete_deployment",
                "update_trip_booking_status"
            ]
            
            if tool_name in dangerous_tools:
                return "check_consequences"
        
        # Safe action, go directly to tools
        return "tools"
    
    # No tool calls, end conversation
    return "end"


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


# ========== BUILD GRAPH ==========
workflow = StateGraph(MoviState)

# Add nodes
workflow.add_node("input_processor", input_processor_node)  # NEW: Entry point
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
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

# After tools execute, go back to agent for response
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
