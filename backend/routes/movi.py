"""
Movi API Endpoint
FastAPI routes for Movi AI assistant
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage
import sys
import os

# Add Agents directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Agents"))

from graph import app as movi_graph

router = APIRouter(prefix="/movi", tags=["movi"])


# ========== REQUEST/RESPONSE MODELS ==========
class ChatRequest(BaseModel):
    message: str
    session_id: str
    context_page: Optional[str] = "unknown"
    image_base64: Optional[str] = None  # For future multimodal support
    audio_base64: Optional[str] = None  # For future multimodal support


class ChatResponse(BaseModel):
    response: str
    requires_confirmation: bool = False
    consequence_info: Optional[dict] = None
    awaiting_confirmation: bool = False
    audio_base64: Optional[str] = None  # For future TTS support


# ========== CHAT ENDPOINT ==========
@router.post("/chat", response_model=ChatResponse)
async def chat_with_movi(request: ChatRequest):
    """
    Main chat endpoint for Movi assistant.
    Handles text input and returns text response (voice/image support coming later).
    
    Args:
        request: ChatRequest with user message and session info
        
    Returns:
        ChatResponse with Movi's reply and any confirmation requests
    """
    try:
        # Configure session with thread_id for state persistence
        config = {"configurable": {"thread_id": request.session_id}}
        
        # Check if this is resuming an interrupted conversation
        # by getting the current state from memory
        current_state = movi_graph.get_state(config)
        
        # If there's an existing conversation, we just add the new message
        # Otherwise, initialize a new conversation
        if current_state and current_state.values:
            # Continue existing conversation - just add the new message
            # The graph will automatically load previous state from checkpointer
            input_state = {
                "messages": [HumanMessage(content=request.message)],
            }
        else:
            # New conversation - initialize full state
            input_state = {
                "messages": [HumanMessage(content=request.message)],
                "context_page": request.context_page,
                "uploaded_image": request.image_base64,
                "uploaded_audio": request.audio_base64,
                "requires_confirmation": False,
                "awaiting_confirmation": False,
                "user_confirmed": None
            }
        
        # Invoke the graph
        result = movi_graph.invoke(input_state, config=config)
        
        # Extract response
        last_message = result["messages"][-1]
        response_text = last_message.content if hasattr(last_message, "content") else str(last_message)
        
        # Build response
        return ChatResponse(
            response=response_text,
            requires_confirmation=result.get("requires_confirmation", False),
            consequence_info=result.get("consequence_info"),
            awaiting_confirmation=result.get("awaiting_confirmation", False)
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Movi Error: {str(e)}")
        print(f"Full traceback:\n{error_details}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing request: {str(e)}"
        )


# ========== HEALTH CHECK ==========
@router.get("/health")
def movi_health_check():
    """Check if Movi service is running"""
    return {"status": "healthy", "service": "Movi AI Assistant"}
