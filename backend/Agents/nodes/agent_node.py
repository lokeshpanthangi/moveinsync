"""
Agent Node - Main decision maker
Similar to agent_node in simple_LLM.py
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from dotenv import load_dotenv
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import ALL_TOOLS

load_dotenv()

# Initialize LLM and bind tools (CRITICAL FIX!)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_with_tools = llm.bind_tools(ALL_TOOLS)


def agent_node(state):
    """
    The agent decides whether to use tools or respond directly.
    Similar to agent_node in simple_LLM.py
    
    Args:
        state: MoviState containing messages and context
        
    Returns:
        Updated state with agent's response
    """
    messages = state["messages"]
    
    # Add system message with context if first message
    if len(messages) == 1:
        system_msg = SystemMessage(content="""You are Movi, an AI assistant for transportation management.
You help manage buses, routes, stops, drivers, vehicles, and daily trips.
Use the available tools to answer user questions and perform actions.
Be helpful, concise, and professional.""")
        messages = [system_msg] + messages
    
    # Get response from LLM WITH TOOLS BOUND
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}
