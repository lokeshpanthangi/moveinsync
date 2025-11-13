"""
Input Processor Node
Handles text input processing (multimodal support will be added later)
"""
from langchain_core.messages import HumanMessage


def input_processor_node(state):
    """
    Process user input (currently text-only, multimodal later).
    Prepares the input for the agent.
    
    Args:
        state: MoviState with user message
        
    Returns:
        Updated state (currently passes through for text)
    """
    # For now, just pass through text messages
    # This node will be extended for voice/image processing later
    
    # Get context page if provided
    context_page = state.get("context_page", "unknown")
    
    # Return state with context
    return {
        "context_page": context_page
    }
