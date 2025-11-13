"""
Consequence Checking Node
Checks if an action has consequences that require user confirmation
"""
from langchain_core.messages import AIMessage
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import get_trip_booking_info


# Define dangerous actions that need consequence checking
DANGEROUS_ACTIONS = [
    "remove_vehicle_from_trip",
    "delete_deployment",
    "delete_route",
    "cancel_trip",
    "deactivate_route"
]


def check_consequences_node(state):
    """
    Check if the planned action has consequences.
    Similar to agent_node structure but checks consequences.
    
    Args:
        state: MoviState with user_intent and identified_entities
        
    Returns:
        Updated state with consequence info
    """
    user_intent = state.get("user_intent", "")
    entities = state.get("identified_entities", {})
    
    # Default: no confirmation needed
    requires_confirmation = False
    consequence_info = None
    
    # Check if action is dangerous
    if user_intent == "remove_vehicle_from_trip":
        trip_name = entities.get("trip", "")
        if trip_name:
            # Get booking info using tool
            booking_info = get_trip_booking_info.invoke({"trip_display_name": trip_name})
            
            # Check if trip has bookings
            if isinstance(booking_info, dict) and booking_info.get("booking_percentage", 0) > 0:
                requires_confirmation = True
                consequence_info = {
                    "type": "booked_trip_vehicle_removal",
                    "booking_percentage": booking_info["booking_percentage"],
                    "live_status": booking_info.get("live_status", "unknown"),
                    "message": f"Trip '{trip_name}' is {booking_info['booking_percentage']}% booked. "
                              f"Removing vehicle will cancel bookings and prevent trip-sheet generation."
                }
    
    return {
        "requires_confirmation": requires_confirmation,
        "consequence_info": consequence_info
    }
