"""
Tool Node - Executes tools
Similar to ToolNode in simple_LLM.py
"""
from langgraph.prebuilt import ToolNode
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.tools import ALL_TOOLS

# Create tool node with all available tools
tool_node = ToolNode(ALL_TOOLS)
