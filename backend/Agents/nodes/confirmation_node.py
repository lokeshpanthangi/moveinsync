"""
Confirmation Node
Generates confirmation message for user
"""
from langchain_core.messages import AIMessage


def get_confirmation_node(state):
    """
    Generate a confirmation message based on consequence info.
    Similar to agent_node structure but generates confirmation.
    
    Args:
        state: MoviState with consequence_info
        
    Returns:
        Updated state with confirmation message
    """
    consequence_info = state.get("consequence_info", {})
    
    if consequence_info:
        message = consequence_info.get("message", "This action may have consequences.")
        confirmation_text = f"⚠️ {message}\n\nDo you want to proceed? (yes/no)"
    else:
        confirmation_text = "Do you want to proceed with this action?"
    
    # Create AI message with confirmation request
    confirmation_message = AIMessage(content=confirmation_text)
    
    return {
        "messages": [confirmation_message],
        "awaiting_confirmation": True
    }
