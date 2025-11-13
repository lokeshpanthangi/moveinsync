"""
Human-in-the-Loop Node
Waits for and processes user's confirmation response (yes/no)
"""
from langchain_core.messages import HumanMessage


def await_user_confirmation_node(state):
    """
    Process the user's confirmation response (yes/no).
    This is the human-in-the-loop node that interprets user's decision.
    
    Args:
        state: MoviState with user's confirmation message
        
    Returns:
        Updated state with user_confirmed flag
    """
    messages = state["messages"]
    
    # Get the last user message
    last_message = messages[-1] if messages else None
    
    if not last_message or not isinstance(last_message, HumanMessage):
        return {"user_confirmed": False}
    
    # Parse user response
    user_response = last_message.content.lower().strip()
    
    # Check for affirmative responses
    affirmative = ["yes", "y", "proceed", "continue", "ok", "confirm", "sure"]
    negative = ["no", "n", "cancel", "stop", "abort", "dont", "don't"]
    
    if any(word in user_response for word in affirmative):
        user_confirmed = True
    elif any(word in user_response for word in negative):
        user_confirmed = False
    else:
        # Unclear response, treat as "no" for safety
        user_confirmed = False
    
    return {
        "user_confirmed": user_confirmed,
        "awaiting_confirmation": False  # Clear the flag
    }
