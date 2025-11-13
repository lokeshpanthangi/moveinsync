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
    This node queries the database to find impacts of dangerous actions.
    
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
    
    # Rule 1: Removing vehicle from trip
    if user_intent == "remove_vehicle_from_trip":
        trip_name = entities.get("trip_display_name", "")
        if trip_name:
            try:
                # Get booking info using tool
                booking_info = get_trip_booking_info.invoke({"trip_display_name": trip_name})
                
                # Check if trip has bookings OR is scheduled
                if isinstance(booking_info, dict):
                    booking_pct = booking_info.get("booking_percentage", 0)
                    is_scheduled = booking_info.get("is_scheduled", False)
                    
                    if booking_pct > 0 or is_scheduled:
                        requires_confirmation = True
                        consequence_info = {
                            "type": "booked_trip_vehicle_removal",
                            "booking_percentage": booking_pct,
                            "live_status": booking_info.get("live_status", "unknown"),
                            "message": f"⚠️ Trip '{trip_name}' is {booking_pct}% booked and scheduled to run. "
                                      f"Removing the vehicle will cancel these bookings and prevent trip-sheet generation."
                        }
            except Exception as e:
                # If we can't check consequences, require confirmation anyway (safety first)
                requires_confirmation = True
                consequence_info = {
                    "type": "unknown_consequences",
                    "message": f"⚠️ Unable to verify consequences for removing vehicle from '{trip_name}'. "
                              f"This action may affect bookings."
                }
    
    # Rule 2: Deleting deployment (same as removing vehicle)
    elif user_intent == "delete_deployment":
        requires_confirmation = True
        consequence_info = {
            "type": "deployment_deletion",
            "message": "⚠️ Deleting this deployment will unassign the vehicle and driver from the trip."
        }
    
    # Rule 3: SQL mutations
    elif user_intent == "execute_safe_sql_mutation":
        requires_confirmation = True
        consequence_info = {
            "type": "database_mutation",
            "message": "⚠️ This will modify database records directly. This action cannot be undone."
        }
    
    return {
        "requires_confirmation": requires_confirmation,
        "consequence_info": consequence_info
    }
