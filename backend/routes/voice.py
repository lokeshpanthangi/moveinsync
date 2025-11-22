"""
Voice WebSocket Endpoint for Movi AI Assistant
Real-time voice conversation using OpenAI Whisper (STT) and TTS
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional
import json
import sys
import os
from datetime import datetime

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from Agents.graph import app as movi_graph
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from utils.audio_processing import (
    transcribe_audio,
    text_to_speech,
    audio_base64_to_bytes,
    audio_bytes_to_base64
)

router = APIRouter(prefix="/movi", tags=["voice"])


class VoiceSessionManager:
    """Manages active voice sessions"""
    def __init__(self):
        self.active_sessions: Dict[str, dict] = {}
    
    def create_session(self, session_id: str, websocket: WebSocket, context_page: str = "unknown"):
        self.active_sessions[session_id] = {
            "websocket": websocket,
            "context_page": context_page,
            "created_at": datetime.now(),
            "conversation_active": True
        }
        print(f"🎤 Voice session created: {session_id}")
    
    def get_session(self, session_id: str) -> Optional[dict]:
        return self.active_sessions.get(session_id)
    
    def remove_session(self, session_id: str):
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            print(f"🛑 Voice session ended: {session_id}")
    
    def update_context(self, session_id: str, context_page: str):
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["context_page"] = context_page


voice_sessions = VoiceSessionManager()


@router.websocket("/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for voice chat.
    
    Protocol:
    1. Client sends: {"type": "init", "session_id": "...", "context_page": "..."}
    2. Server responds: {"type": "ready"}
    3. Client sends: {"type": "audio", "data": "base64_audio", "format": "webm"}
    4. Server processes and responds: {"type": "transcription", "text": "..."}
    5. Server responds: {"type": "audio_response", "data": "base64_audio", "text": "..."}
    6. Client sends: {"type": "close"}
    """
    await websocket.accept()
    session_id = None
    
    try:
        print(f"🎤 Voice WebSocket connection established")
        
        # Ensure the Movi agent is available before processing messages
        if movi_graph is None:
            await websocket.send_json({"type": "error", "message": "Movi agent unavailable"})
            await websocket.close()
            return

        while True:
            # Receive message from client
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            # Handle initialization
            if msg_type == "init":
                session_id = message.get("session_id")
                context_page = message.get("context_page", "unknown")
                
                if not session_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "session_id is required"
                    })
                    continue
                
                voice_sessions.create_session(session_id, websocket, context_page)
                
                await websocket.send_json({
                    "type": "ready",
                    "message": "Voice session initialized"
                })
                
                print(f"✅ Voice session ready: {session_id} (page: {context_page})")
            
            # Handle audio input
            elif msg_type == "audio":
                if not session_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Session not initialized"
                    })
                    continue
                
                audio_base64 = message.get("data")
                audio_format = message.get("format", "webm")
                
                if not audio_base64:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No audio data provided"
                    })
                    continue
                
                print(f"🎤 Received audio from {session_id} (format: {audio_format})")
                
                try:
                    # Step 1: Convert audio to text (STT)
                    audio_bytes = audio_base64_to_bytes(audio_base64)
                    transcribed_text = transcribe_audio(audio_bytes, audio_format)
                    
                    print(f"📝 Transcription: {transcribed_text}")
                    
                    # Send transcription to client
                    await websocket.send_json({
                        "type": "transcription",
                        "text": transcribed_text
                    })
                    
                    # Step 2: Process with LangGraph (same as text chat)
                    session = voice_sessions.get_session(session_id)
                    context_page = session["context_page"]
                    
                    # Build LangGraph config
                    config = {
                        "configurable": {
                            "thread_id": session_id
                        }
                    }
                    
                    # Check if conversation state exists and if interrupted
                    current_state = movi_graph.get_state(config)
                    
                    # If graph is interrupted, handle resume
                    if current_state.next:
                        # User is responding to previous interrupt
                        user_approved = transcribed_text.lower().strip() in [
                            "yes", "y", "proceed", "confirm", "ok", "okay", "sure"
                        ]
                        result = movi_graph.invoke(Command(resume=user_approved), config=config)
                    else:
                        # Normal flow: Create proper MoviState
                        # Load existing chat history from checkpointer (if any)
                        existing_messages = current_state.values.get("messages", []) if current_state.values else []
                        
                        # Trim to last 5 conversation pairs (10 messages)
                        if len(existing_messages) > 10:
                            existing_messages = existing_messages[-10:]
                        
                        input_state = {
                            "user_msg": transcribed_text,
                            "current_page": context_page,
                            "messages": existing_messages,  # Load previous history
                            "intent": None,
                            "tool_name": None,
                            "entities": None,
                            "needs_user_input": False,
                            "consequences": None,
                            "awaiting_confirmation": False,
                            "tool_result": None
                        }
                    
                    # Invoke the graph
                    if not current_state.next:
                        result = movi_graph.invoke(input_state, config=config)
                    
                    # Check final state for interrupts
                    final_state = movi_graph.get_state(config)
                    is_interrupted = bool(final_state.next)
                    
                    # Extract response
                    if is_interrupted and "__interrupt__" in result:
                        # Get interrupt payload
                        interrupt_data = result["__interrupt__"][0].value if result["__interrupt__"] else {}
                        response_text = interrupt_data.get("details", "Confirmation required.")
                        response_text += "\n\nDo you want to proceed? (yes/no)"
                    else:
                        # Normal response
                        last_message = result.get("messages", [])[-1] if result.get("messages") else None
                        if last_message:
                            response_text = last_message.content if hasattr(last_message, "content") else str(last_message)
                        else:
                            response_text = result.get("response", "No response generated.")
                    
                    print(f"🤖 Movi response: {response_text[:100]}...")
                    
                    # Check if confirmation is needed
                    requires_confirmation = result.get("requires_confirmation", False)
                    awaiting_confirmation = result.get("awaiting_confirmation", False)
                    consequence_info = result.get("consequence_info")
                    
                    # Step 3: Convert response to speech (TTS)
                    audio_response = text_to_speech(response_text, voice="nova")  # Female voice
                    audio_base64_response = audio_bytes_to_base64(audio_response)
                    
                    print(f"🔊 Generated TTS response ({len(audio_response)} bytes)")
                    
                    # Send audio response to client
                    await websocket.send_json({
                        "type": "audio_response",
                        "data": audio_base64_response,
                        "text": response_text,
                        "requires_confirmation": requires_confirmation,
                        "awaiting_confirmation": awaiting_confirmation,
                        "consequence_info": consequence_info
                    })
                    
                except Exception as e:
                    print(f"❌ Error processing voice: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to process voice: {str(e)}"
                    })
            
            # Handle context update
            elif msg_type == "update_context":
                if session_id:
                    new_context = message.get("context_page", "unknown")
                    voice_sessions.update_context(session_id, new_context)
                    print(f"🔄 Context updated for {session_id}: {new_context}")
            
            # Handle close
            elif msg_type == "close":
                print(f"👋 Client requested close for {session_id}")
                break
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })
    
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected: {session_id}")
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if session_id:
            voice_sessions.remove_session(session_id)
        await websocket.close()


@router.get("/voice/sessions")
async def get_voice_sessions():
    """Get active voice sessions (for debugging)"""
    return {
        "active_sessions": len(voice_sessions.active_sessions),
        "sessions": [
            {
                "session_id": sid,
                "context_page": session["context_page"],
                "created_at": session["created_at"].isoformat()
            }
            for sid, session in voice_sessions.active_sessions.items()
        ]
    }
