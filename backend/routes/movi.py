"""
Movi API Endpoint
FastAPI routes for Movi AI assistant
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage
from langgraph.types import Command
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from Agents.graph import app as agent_graph

router = APIRouter(prefix="/movi", tags=["movi"])

class ChatRequest(BaseModel):
    message: str
    session_id: str
    context_page: Optional[str] = "unknown"
    image_base64: Optional[str] = None  # For vision analysis
    audio_base64: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    requires_confirmation: bool = False
    awaiting_confirmation: bool = False
    audio_base64: Optional[str] = None

from fastapi.responses import StreamingResponse
import json

@router.post("/chat")
async def chat_with_movi(request: ChatRequest):
    """
    Handle chat with Movi using LangGraph agent with Human-in-the-Loop support.
    Returns a StreamingResponse with JSON-lines format:
    - {"type": "token", "content": "..."} -> Text chunks
    - {"type": "confirmation", "payload": {...}} -> HITL confirmation request
    - {"type": "error", "content": "..."} -> Errors
    """
    if agent_graph is None:
        raise HTTPException(status_code=503, detail="Movi agent unavailable")

    # Config with thread_id for state persistence
    config = {"configurable": {"thread_id": request.session_id}}
    
    async def event_generator():
        try:
            # Check if there's an ongoing interrupt waiting for resume
            state = agent_graph.get_state(config)
            
            # Determine input for the graph
            if state.next:
                # User is responding to an interrupt/confirmation request
                user_approved = request.message.lower().strip() in [
                    "yes", "y", "proceed", "confirm", "ok", "okay", "yeah", "yep", "sure", "approve"
                ]
                # Resume with the user's decision
                # We use astream_events even for resume to capture subsequent output
                input_data = Command(resume=user_approved)
            else:
                # Normal flow: new conversation
                existing_messages = state.values.get("messages", []) if state.values else []
                if len(existing_messages) > 10:
                    existing_messages = existing_messages[-10:]
                
                input_data = {
                    "user_msg": request.message,
                    "current_page": request.context_page or "unknown",
                    "messages": existing_messages,
                    "image_base64": request.image_base64,
                    "image_content": None,
                    "intent": None,
                    "tool_name": None,
                    "entities": None,
                    "needs_user_input": False,
                    "consequences": None,
                    "awaiting_confirmation": False,
                    "tool_result": None
                }

            # Stream events from the graph
            async for event in agent_graph.astream_events(input_data, config=config, version="v2"):
                # Filter for LLM streaming events from the 'response' node
                # This ensures we only stream the final answer, not internal thoughts or tool calls
                if (
                    event["event"] == "on_chat_model_stream" and 
                    event["metadata"].get("langgraph_node") == "response"
                ):
                    chunk_content = event["data"]["chunk"].content
                    if chunk_content:
                        yield json.dumps({"type": "token", "content": chunk_content}) + "\n"

            # After stream finishes, check if we stopped due to an interrupt
            final_state = agent_graph.get_state(config)
            if final_state.next:
                # We are interrupted (HITL) - need to generate AI alert
                # Extract consequence data from interrupt payload
                consequence_data = None
                
                if hasattr(final_state, "tasks") and final_state.tasks:
                    for task in final_state.tasks:
                        if task.interrupts:
                            consequence_data = task.interrupts[0].value
                            break
                
                # Generate AI alert based on consequences
                if consequence_data and consequence_data.get("has_consequences"):
                    # Use AI to generate a natural, context-aware confirmation message
                    from langchain_openai import ChatOpenAI
                    
                    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
                    
                    details = consequence_data.get("details", "")
                    tool_name = consequence_data.get("tool_name", "this action")
                    affected_entity = consequence_data.get("affected_entity", "")
                    
                    prompt = f"""You are a helpful assistant generating a confirmation alert for a user action.
                    
The user is about to: {tool_name}
Affected entity: {affected_entity}

Consequences:
{details}

Generate a clear, concise, and friendly confirmation message that:
1. Explains what will happen if they proceed
2. Highlights the key consequences
3. Asks if they want to continue

Keep it under 3-4 sentences. Be direct but respectful."""

                    ai_alert = llm.invoke(prompt).content
                    
                    payload = {
                        "requires_confirmation": True,
                        "message": ai_alert
                    }
                else:
                    # Fallback for tools without specific consequences
                    tool_name = consequence_data.get("tool_name", "this action") if consequence_data else "this action"
                    payload = {
                        "requires_confirmation": True,
                        "message": f"You are about to execute: {tool_name}\n\nDo you want to proceed? (yes/no)"
                    }
                
                yield json.dumps({"type": "confirmation", "payload": payload}) + "\n"
                
        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


# ========== VOICE CHAT TOKEN ==========
class VoiceTokenRequest(BaseModel):
    session_id: str
    context_page: Optional[str] = "busDashboard"


class VoiceTokenResponse(BaseModel):
    token: str
    room_name: str
    url: str


@router.post("/voice/token", response_model=VoiceTokenResponse)
async def get_voice_token(request: VoiceTokenRequest):
    """
    Get LiveKit room token for voice chat.
    
    Creates a room for this session and returns a token for the user to join.
    """
    try:
        from livekit import api
        import os
        
        # Get LiveKit credentials
        livekit_url = os.getenv("LIVEKIT_URL")
        livekit_api_key = os.getenv("LIVEKIT_API_KEY")
        livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
        
        if not all([livekit_url, livekit_api_key, livekit_api_secret]):
            raise HTTPException(
                status_code=500,
                detail="LiveKit credentials not configured"
            )
        
        # Room name based on session ID
        room_name = f"movi-{request.session_id}"
        
        # Create token with room metadata
        token = api.AccessToken(livekit_api_key, livekit_api_secret) \
            .with_identity(f"user-{request.session_id}") \
            .with_name("Movi User") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )) \
            .with_metadata(f'{{"context_page": "{request.context_page}", "session_id": "{request.session_id}"}}') \
            .to_jwt()
        
        return VoiceTokenResponse(
            token=token,
            room_name=room_name,
            url=livekit_url
        )
        
    except Exception as e:
        print(f"❌ Error generating voice token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating voice token: {str(e)}"
        )


# ========== HEALTH CHECK ==========
@router.get("/health")
def movi_health_check():
    """Check if Movi service is running"""
    return {"status": "healthy", "service": "Movi AI Assistant"}
