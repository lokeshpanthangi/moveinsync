"""
Movi Agent State Definition
Defines the state schema for the Movi transportation management agent
"""
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import operator


# ========== DEFINE STATE ==========
class MoviState(TypedDict):
    """
    State schema for Movi agent.
    Tracks conversation, user intent, entities, and confirmation flows.
    """
    # Core conversation
    messages: Annotated[Sequence[HumanMessage | AIMessage | SystemMessage], operator.add]
    
    # Intent & Entity Extraction
    user_intent: Optional[str]  # e.g., "remove_vehicle_from_trip", "list_stops", "create_route"
    identified_entities: Optional[dict]  # e.g., {"trip": "Bulk - 00:01", "vehicle": "MH-12-3456"}
    
    # Consequence Checking (Tribal Knowledge)
    requires_confirmation: bool  # Flag if action needs user confirmation
    consequence_info: Optional[dict]  # Details about consequences (booking %, trip status, etc.)
    awaiting_confirmation: bool  # True when waiting for user's yes/no response
    
    # Multimodal Input
    uploaded_image: Optional[str]  # Base64 encoded image
    uploaded_audio: Optional[str]  # Base64 encoded audio
    
    # Context
    context_page: Optional[str]  # "busDashboard", "routes", "stops_paths", etc.
    session_id: Optional[str]  # Session identifier for state persistence
    
    # Tool Execution Tracking
    tool_calls_made: Optional[list]  # List of tools that have been called
    last_tool_result: Optional[str]  # Result from the last tool execution
    
    # Human-in-the-Loop
    user_confirmed: Optional[bool]  # User's confirmation response (True=yes, False=no)
