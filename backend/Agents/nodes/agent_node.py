"""
Agent Node - Main decision maker with page-aware tool filtering
Similar to agent_node in simple_LLM.py but with dynamic tool binding
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from dotenv import load_dotenv
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import get_tools_for_page

load_dotenv()

# Initialize LLM (tools will be bound dynamically based on page)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def agent_node(state):
    """
    The agent decides whether to use tools or respond directly.
    Tools are filtered based on the current page context.
    
    Args:
        state: MoviState containing messages and context_page
        
    Returns:
        Updated state with agent's response
    """
    messages = state["messages"]
    context_page = state.get("context_page", "unknown")
    
    # Get tools for the current page
    page_tools = get_tools_for_page(context_page)
    
    # Log tool filtering for debugging
    print(f"🔧 Agent using {len(page_tools)} tools for page: {context_page}")
    
    # Bind tools dynamically based on page context
    llm_with_tools = llm.bind_tools(page_tools)
    
    # Add system message with context if first message
    if len(messages) == 1:
        page_context_msg = {
            "busDashboard": "You're currently on the Bus Dashboard page, focusing on trips, vehicles, drivers, and deployments.",
            "stops_paths": "You're currently on the Stops & Paths page, focusing on stop locations and path configurations.",
            "routes": "You're currently on the Routes page, focusing on route management and scheduling.",
            "vehicles": "You're currently on the Vehicles page, focusing on vehicle management.",
            "drivers": "You're currently on the Drivers page, focusing on driver management.",
            "unknown": ""
        }.get(context_page, "")
        
        system_content = f"""You are Movi, an AI assistant for transportation management.
You help manage buses, routes, stops, drivers, vehicles, and daily trips.
Use the available tools to answer user questions and perform actions.
Be helpful, concise, and professional.

{page_context_msg}"""
        
        system_msg = SystemMessage(content=system_content)
        messages = [system_msg] + messages
    
    # Get response from LLM WITH PAGE-SPECIFIC TOOLS BOUND
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}
