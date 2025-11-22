from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt, Command
import json
from Agents.tools import ALL_TOOLS, get_tools_for_page
from database import SessionLocal
from database import get_db
from Agents.state import MoviState

def intent_node(state, llm, ALL_TOOLS):
    """
    First Node: Intent Classification

    Inputs in state:
        - user_msg
        - current_page
        - messages (history)

    Outputs added to state:
        - intent
        - tool_name
        - entities
        - messages (updated)
    """

    user_msg = state["user_msg"]
    current_page = state["current_page"]
    image_base64 = state.get("image_base64")  # Optional image input

    # Initialize history if missing
    messages = state.get("messages", [])
    if messages is None:
        messages = []
    
    # ---- Image Analysis (if provided) ----
    if image_base64:
        # Use GPT-4o (full model) for better vision and OCR capabilities
        vision_llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        vision_message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": """Analyze this image carefully and extract ALL text and information visible.

Pay special attention to:
1. ANY highlighted, circled, or marked items (these are MOST IMPORTANT)
2. Trip names, IDs, and identifiers
3. Status indicators (SCHEDULED, IN-PROGRESS, UNKNOWN, etc.)
4. Booking percentages
5. Times and schedules
6. Any arrows or visual emphasis

Provide a detailed description focusing on what the user wants to highlight or draw attention to. If there are circles, arrows, or highlighting, mention those items FIRST and PROMINENTLY."""
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                }
            ]
        )
        
        # Call vision-capable LLM (gpt-4o for better OCR)
        vision_response = vision_llm.invoke([vision_message])
        image_description = vision_response.content
        
        # Store the text description and clear the base64 (save memory)
        state["image_content"] = image_description
        state["image_base64"] = None  # Clear base64 after processing
        
        # Append image analysis to user message
        user_msg = f"{user_msg}\n\n[Image Analysis: {image_description}]"
    else:
        state["image_content"] = None

    # 1. Add user message to chat history
    messages.append(HumanMessage(content=user_msg))

    # 2. Prepare tool descriptions
    # Filter tools based on current page context
    available_tools = get_tools_for_page(current_page)
    
    tool_descriptions = "\n".join([
        f"- {tool.name}: {tool.description}"
        for tool in available_tools
    ])

    # 3. System prompt for LLM - conditionally include image instructions
    if image_base64 or state.get("image_content"):
        # Include image-specific instructions only when image is present
        system_prompt = f"""
You are Movi's intent classifier.

You receive:
- user_msg: the user's query (includes image analysis)
- current_page: UI context
- available tools

IMPORTANT: The user message includes [Image Analysis: ...]. Pay VERY CLOSE ATTENTION to:
- Items that are highlighted, circled, or marked with arrows
- Trip names that are emphasized or visually called out
- These highlighted items are what the user wants to work with

Your job:
1. Identify the user's intent.
2. Select EXACT tool_name matching the tools list.
3. Extract entities (dict) - prioritize highlighted/emphasized items from images.

Respond ONLY with JSON:

{{
  "intent": "...",
  "tool_name": "...",
  "entities": {{ ... }}
}}

Current Page: {current_page}

Available Tools:
{tool_descriptions}
"""
    else:
        # Standard prompt without image instructions
        system_prompt = f"""
You are Movi's intent classifier.

You receive:
- user_msg: the user's query
- current_page: UI context
- available tools

Your job:
1. Identify the user's intent.
2. Select EXACT tool_name matching the tools list.
3. Extract entities (dict).

Respond ONLY with JSON:

{{
  "intent": "...",
  "tool_name": "...",
  "entities": {{ ... }}
}}

Current Page: {current_page}

Available Tools:
{tool_descriptions}
"""

    # 4. LLM input
    llm_messages = [
        SystemMessage(content=system_prompt),
        *messages
    ]

    # 5. Call the LLM
    llm_response = llm.invoke(llm_messages)

    # 6. Parse safely
    try:
        parsed = json.loads(llm_response.content)
    except Exception:
        parsed = {"intent": None, "tool_name": None, "entities": {}}

    # 7. Update state
    state["intent"] = parsed.get("intent")
    state["tool_name"] = parsed.get("tool_name")
    state["entities"] = parsed.get("entities", {})

    # 8. Update chat history
    messages.append(AIMessage(content=llm_response.content))
    state["messages"] = messages

    return state



from sqlalchemy.orm import Session

# import your DB session + models + check functions
from database import SessionLocal
from models import DailyTrip, Route
from Agents.tools import (
    check_trip_consequences,
    check_route_deactivation_consequences,
)

# High-impact tool list (tools that require user confirmation)
HIGH_IMPACT_TOOLS = {
    "remove_vehicle_from_trip",
    "update_route_status",
    "update_route",
    "update_trip",
    "delete_trip",
    "delete_deployment",
}


def consequence_node(state):
    """
    Second Node: Consequence Checker with LangGraph Interrupt

    Reads:
        state.tool_name
        state.entities

    Uses LangGraph's interrupt() to pause execution and wait for human approval.
    For ANY tool in HIGH_IMPACT_TOOLS, this will trigger interrupt().
    Fetches actual consequences from database and stores them in state for AI to generate alert.
    """

    tool_name = state.get("tool_name")
    entities = state.get("entities", {})

    # ---- 1. Default: no consequences ----
    state["consequences"] = None
    state["awaiting_confirmation"] = False

    # ---- 2. If tool is NOT high-impact → done ----
    if tool_name not in HIGH_IMPACT_TOOLS:
        return state

    # ---- 3. Tool IS high-impact → Fetch consequence details from DB ----
    db: Session = SessionLocal()
    consequence_data = None
    
    try:
        # Fetch specific consequence details based on tool
        if tool_name in ["remove_vehicle_from_trip", "delete_trip", "delete_deployment", "update_trip"]:
            trip_name = entities.get("trip_display_name") or entities.get("trip_name") or entities.get("trip")
            if trip_name:
                result = check_trip_consequences(trip_name, db)
                if result.get("has_consequences"):
                    consequence_data = {
                        "has_consequences": True,
                        "details": result.get("details"),
                        "tool_name": tool_name,
                        "affected_entity": trip_name
                    }
        
        elif tool_name in ["update_route_status", "update_route"]:
            route_name = entities.get("route_display_name") or entities.get("route_name") or entities.get("route")
            if route_name:
                result = check_route_deactivation_consequences(route_name, db)
                if result.get("has_consequences"):
                    consequence_data = {
                        "has_consequences": True,
                        "details": result.get("details"),
                        "tool_name": tool_name,
                        "affected_entity": route_name
                    }
        
        db.close()
    except Exception as e:
        db.close()
        consequence_data = None

    # ---- 4. Store consequences in state for AI to process ----
    state["consequences"] = consequence_data
    
    # ---- 5. ALWAYS trigger HITL interrupt for high-impact tools ----
    is_approved = interrupt(consequence_data or {
        "type": "confirmation_required",
        "tool_name": tool_name,
        "entities": entities
    })

    # When resumed with Command(resume=True/False), execution continues here
    # If user rejected, cancel the tool
    if not is_approved:
        state["tool_name"] = None
        state["tool_result"] = "Action cancelled by user."
        state["consequences"] = None
        return state

    # If approved, continue with the tool execution
    state["consequences"] = None
    state["awaiting_confirmation"] = False
    return state


def tool_call_node(state, ALL_TOOLS):
    """
    Generic Tool Executor
    - Looks up the correct tool from ALL_TOOLS by name
    - Calls exactly that tool
    - Stores the result
    
    ALL_TOOLS can contain any number of tools.
    """

    tool_name = state.get("tool_name")
    entities = state.get("entities", {})
    state["tool_result"] = None

    if not tool_name:
        return state

    # 1. Find the tool by exact name
    tool = None
    for t in ALL_TOOLS:
        if t.name == tool_name:
            tool = t
            break

    # If no matching tool
    if tool is None:
        state["tool_result"] = f"Error: Tool '{tool_name}' not found."
        return state

    try:
        # 2. Normalize entities to match tool parameter names
        # The LLM may extract "trip_name" but tools expect "trip_display_name"
        normalized_entities = entities.copy()
        
        # Map trip_name/trip -> trip_display_name
        if "trip_name" in normalized_entities and "trip_display_name" not in normalized_entities:
            normalized_entities["trip_display_name"] = normalized_entities.pop("trip_name")
        elif "trip" in normalized_entities and "trip_display_name" not in normalized_entities:
            normalized_entities["trip_display_name"] = normalized_entities.pop("trip")
        
        # Map route_name/route -> route_display_name
        if "route_name" in normalized_entities and "route_display_name" not in normalized_entities:
            normalized_entities["route_display_name"] = normalized_entities.pop("route_name")
        elif "route" in normalized_entities and "route_display_name" not in normalized_entities:
            normalized_entities["route_display_name"] = normalized_entities.pop("route")
        
        # Call the tool with normalized entities
        result = tool.invoke(normalized_entities)

        # 3. Save tool output
        state["tool_result"] = result
        return state

    except Exception as e:
        state["tool_result"] = f"Tool execution failed: {str(e)}"
        return state


# NOTE: confirmation_response_node and human_confirmation_node have been removed
# They are replaced by the interrupt() mechanism in consequence_node
# The interrupt() pauses execution and waits for Command(resume=True/False)


from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

def response_node(state, llm):
    """
    Final Response Node
    Uses the LLM to generate the assistant's final reply to the user.

    Input State:
        - messages (chat history)
        - tool_result (optional)
        - consequences (optional)
        - current_page
        - intent

    Output:
        - LLM reply appended to state.messages
        - state["response"] (string)
    """

    messages = state.get("messages", [])

    # 1. Build system instructions
    system_prompt = f"""
You are Movi, the MoveInSync internal admin assistant.
Generate a clear, helpful response for the user.

Available Info:
- Current Page: {state.get("current_page")}
- Last Intent: {state.get("intent")}
- Tool Result: {state.get("tool_result")}
- Consequences: {state.get("consequences")}

Rules:
- If tool_result exists, summarize it naturally.
- If consequences exist AND awaiting_confirmation is False (user cancelled), summarize cancellation.
- Be clear and to the point.
- The answer should be Structured
- No JSON, only natural language.
    """

    # 2. Build LLM messages
    llm_messages = [
        SystemMessage(content=system_prompt),
        *messages
    ]

    # 3. Invoke LLM
    output = llm.invoke(llm_messages)

    # 4. Save final assistant message
    assistant_msg = AIMessage(content=output.content)
    messages.append(assistant_msg)

    state["messages"] = messages
    state["response"] = output.content

    return state
