"""
Tools for Movi AI Assistant
Provides 15+ tools for interacting with Routes, Stops, Paths, Vehicles, Drivers, and Trips
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
import sys
from dotenv import load_dotenv
load_dotenv()
import os
import base64
from io import BytesIO
from PIL import Image
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from crud import (
    stop as stop_crud,
    path as path_crud,
    route as route_crud,
    vehicle as vehicle_crud,
    driver as driver_crud,
    daily_trip as daily_trip_crud,
    deployment as deployment_crud
)
from models import RouteStatus, VehicleType
from schemas import (
    StopCreate, PathCreate, RouteCreate, VehicleCreate, 
    DriverCreate, DailyTripCreate, DeploymentCreate, PathStopBase
)

# LangChain Multimodal Integration
try:
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("Warning: langchain-openai not installed. Vision features will be limited.")

# OpenAI client for audio features (STT/TTS)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI not installed. Audio features (STT/TTS) will be limited.")

# LangChain SQL Agent Integration
try:
    from langchain_community.agent_toolkits import create_sql_agent
    from langchain_community.utilities import SQLDatabase
    from database import DATABASE_URL, engine
    SQL_AGENT_AVAILABLE = True
except ImportError:
    SQL_AGENT_AVAILABLE = False
    print("Warning: langchain-community not installed. SQL Agent features will be limited.")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass


# ==============================================================================
# STOPS TOOLS (Static)
# ==============================================================================

@tool
def list_all_stops() -> str:
    """
    List all stops in the system.
    Returns stop names with their IDs and coordinates.
    Use this when user asks about available stops.
    """
    db = get_db()
    try:
        stops = stop_crud.get_all_stops(db)
        if not stops:
            return "No stops found in the system."
        
        result = "Available Stops:\n"
        for stop in stops:
            result += f"- {stop.name} (ID: {stop.stop_id}, Lat: {stop.latitude}, Lon: {stop.longitude})\n"
        return result
    finally:
        db.close()


@tool
def create_new_stop(name: str, latitude: float, longitude: float) -> str:
    """
    Create a new stop in the system.
    
    Args:
        name: Name of the stop (e.g., "Odeon Circle", "Tech Park Gate")
        latitude: Latitude coordinate
        longitude: Longitude coordinate
    
    Returns:
        Confirmation message with created stop details
    """
    db = get_db()
    try:
        # Check if stop already exists
        existing = stop_crud.get_stop_by_name(db, name)
        if existing:
            return f"Stop '{name}' already exists with ID {existing.stop_id}."
        
        stop_data = StopCreate(name=name, latitude=latitude, longitude=longitude)
        stop = stop_crud.create_stop(db, stop_data)
        return f"Successfully created stop '{stop.name}' with ID {stop.stop_id} at coordinates ({latitude}, {longitude})."
    except Exception as e:
        return f"Error creating stop: {str(e)}"
    finally:
        db.close()


@tool
def get_stop_details(stop_name: str) -> str:
    """
    Get details about a specific stop by name.
    
    Args:
        stop_name: Name of the stop to look up
    
    Returns:
        Stop details including ID and coordinates
    """
    db = get_db()
    try:
        stop = stop_crud.get_stop_by_name(db, stop_name)
        if not stop:
            return f"Stop '{stop_name}' not found."
        
        return f"Stop: {stop.name}\nID: {stop.stop_id}\nCoordinates: ({stop.latitude}, {stop.longitude})"
    finally:
        db.close()


# ==============================================================================
# PATHS TOOLS (Static)
# ==============================================================================

@tool
def list_stops_for_path(path_name: str) -> str:
    """
    List all stops in a specific path in order.
    Use this when user asks "What stops are in Path-1?" or similar.
    
    Args:
        path_name: Name of the path (e.g., "Path-1", "Tech-Loop")
    
    Returns:
        Ordered list of stops in the path
    """
    db = get_db()
    try:
        path = path_crud.get_path_by_name(db, path_name)
        if not path:
            return f"Path '{path_name}' not found."
        
        # Get ordered stops
        ordered_stops = sorted(path.stops, key=lambda ps: ps.stop_order)
        
        if not ordered_stops:
            return f"Path '{path_name}' has no stops assigned."
        
        result = f"Stops in {path_name} (in order):\n"
        for path_stop in ordered_stops:
            result += f"{path_stop.stop_order}. {path_stop.stop.name}\n"
        return result
    finally:
        db.close()


@tool
def create_new_path(path_name: str, stop_names: List[str]) -> str:
    """
    Create a new path with an ordered list of stops.
    
    Args:
        path_name: Name for the new path (e.g., "Tech-Loop", "Airport Express")
        stop_names: List of stop names in order (e.g., ["Gavipuram", "Temple", "Peenya"])
    
    Returns:
        Confirmation message with created path details
    """
    db = get_db()
    try:
        # Check if path already exists
        existing = path_crud.get_path_by_name(db, path_name)
        if existing:
            return f"Path '{path_name}' already exists with ID {existing.path_id}."
        
        # Validate all stops exist and get their IDs
        stop_ids = []
        for stop_name in stop_names:
            stop = stop_crud.get_stop_by_name(db, stop_name)
            if not stop:
                return f"Error: Stop '{stop_name}' not found. Please create it first."
            stop_ids.append(stop.stop_id)
        
        # Create path with ordered stops
        path_stops = [
            PathStopBase(stop_id=stop_id, stop_order=idx + 1)
            for idx, stop_id in enumerate(stop_ids)
        ]
        path_data = PathCreate(path_name=path_name, stops=path_stops)
        path = path_crud.create_path(db, path_data)
        
        stops_str = " → ".join(stop_names)
        return f"Successfully created path '{path_name}' (ID: {path.path_id}) with {len(stop_names)} stops: {stops_str}"
    except Exception as e:
        return f"Error creating path: {str(e)}"
    finally:
        db.close()


@tool
def list_all_paths() -> str:
    """
    List all paths in the system.
    Returns path names with their IDs and stop count.
    """
    db = get_db()
    try:
        paths = path_crud.get_all_paths(db)
        if not paths:
            return "No paths found in the system."
        
        result = "Available Paths:\n"
        for path in paths:
            stop_count = len(path.stops)
            result += f"- {path.path_name} (ID: {path.path_id}, {stop_count} stops)\n"
        return result
    finally:
        db.close()


# ==============================================================================
# ROUTES TOOLS (Static)
# ==============================================================================

@tool
def list_routes_using_path(path_name: str) -> str:
    """
    List all routes that use a specific path.
    Use when user asks "Show me routes using Path-1" or similar.
    
    Args:
        path_name: Name of the path to search for
    
    Returns:
        List of routes using that path
    """
    db = get_db()
    try:
        path = path_crud.get_path_by_name(db, path_name)
        if not path:
            return f"Path '{path_name}' not found."
        
        routes = route_crud.get_routes_by_path(db, path.path_id)
        
        if not routes:
            return f"No routes found using path '{path_name}'."
        
        result = f"Routes using {path_name}:\n"
        for route in routes:
            result += f"- {route.route_display_name} ({route.direction}, {route.shift_time}, Status: {route.status.value})\n"
        return result
    finally:
        db.close()


@tool
def list_all_routes() -> str:
    """
    List all routes in the system with their details.
    Returns route names, paths, status, and capacity.
    """
    db = get_db()
    try:
        routes = route_crud.get_all_routes(db)
        if not routes:
            return "No routes found in the system."
        
        result = "Available Routes:\n"
        for route in routes:
            result += f"- {route.route_display_name} | Path: {route.path.path_name} | {route.direction} | Capacity: {route.capacity} | Status: {route.status.value}\n"
        return result
    finally:
        db.close()


@tool
def create_new_route(
    route_name: str,
    path_name: str,
    shift_time: str,
    direction: str,
    capacity: int,
    status: str = "active"
) -> str:
    """
    Create a new route on an existing path.
    
    Args:
        route_name: Display name for the route (e.g., "Morning Express")
        path_name: Name of the path to use
        shift_time: Shift time in HH:MM format (e.g., "08:30")
        direction: Direction like "pickup" or "drop"
        capacity: Maximum capacity for the route
        status: Route status ("active" or "deactivated"), defaults to "active"
    
    Returns:
        Confirmation message with created route details
    """
    db = get_db()
    try:
        # Validate path exists
        path = path_crud.get_path_by_name(db, path_name)
        if not path:
            return f"Error: Path '{path_name}' not found."
        
        # Parse time
        from datetime import datetime
        time_obj = datetime.strptime(shift_time, "%H:%M").time()
        
        route_status = RouteStatus.active if status == "active" else RouteStatus.deactivated
        
        route_data = RouteCreate(
            path_id=path.path_id,
            route_display_name=route_name,
            shift_time=time_obj,
            direction=direction,
            capacity=capacity,
            allocated_waitlist=0,
            status=route_status
        )
        route = route_crud.create_route(db, route_data)
        return f"Successfully created route '{route.route_display_name}' (ID: {route.route_id}) on path '{path_name}' for {shift_time}."
    except Exception as e:
        return f"Error creating route: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# VEHICLES TOOLS (Static/Dynamic)
# ==============================================================================

@tool
def list_all_vehicles() -> str:
    """
    List all vehicles in the system.
    Returns vehicle license plates, types, capacity, and status.
    """
    db = get_db()
    try:
        vehicles = vehicle_crud.get_all_vehicles(db)
        if not vehicles:
            return "No vehicles found in the system."
        
        result = "Available Vehicles:\n"
        for vehicle in vehicles:
            result += f"- {vehicle.license_plate} (ID: {vehicle.vehicle_id}, Type: {vehicle.type.value}, Capacity: {vehicle.capacity}, Status: {vehicle.status})\n"
        return result
    finally:
        db.close()


@tool
def count_unassigned_vehicles() -> str:
    """
    Count how many vehicles are not currently assigned to any trip.
    Use when user asks "How many vehicles are not assigned?" or similar.
    
    Returns:
        Count of unassigned vehicles with details
    """
    db = get_db()
    try:
        all_vehicles = vehicle_crud.get_all_vehicles(db)
        all_deployments = deployment_crud.get_all_deployments(db)
        
        assigned_vehicle_ids = {d.vehicle_id for d in all_deployments}
        unassigned = [v for v in all_vehicles if v.vehicle_id not in assigned_vehicle_ids]
        
        if not unassigned:
            return "All vehicles are currently assigned to trips."
        
        result = f"Found {len(unassigned)} unassigned vehicle(s):\n"
        for vehicle in unassigned:
            result += f"- {vehicle.license_plate} ({vehicle.type.value}, Capacity: {vehicle.capacity})\n"
        return result
    finally:
        db.close()


@tool
def create_new_vehicle(license_plate: str, vehicle_type: str, capacity: int) -> str:
    """
    Create a new vehicle in the system.
    
    Args:
        license_plate: License plate number (e.g., "MH-12-3456")
        vehicle_type: Type of vehicle - "bus" or "cab"
        capacity: Seating capacity of the vehicle
    
    Returns:
        Confirmation message with created vehicle details
    """
    db = get_db()
    try:
        # Check if vehicle already exists
        existing = vehicle_crud.get_vehicle_by_license_plate(db, license_plate)
        if existing:
            return f"Vehicle with license plate '{license_plate}' already exists."
        
        v_type = VehicleType.bus if vehicle_type.lower() == "bus" else VehicleType.cab
        vehicle_data = VehicleCreate(
            license_plate=license_plate,
            type=v_type,
            capacity=capacity,
            status="active"
        )
        vehicle = vehicle_crud.create_vehicle(db, vehicle_data)
        return f"Successfully created vehicle '{vehicle.license_plate}' (ID: {vehicle.vehicle_id}, Type: {vehicle.type.value}, Capacity: {capacity})."
    except Exception as e:
        return f"Error creating vehicle: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# DRIVERS TOOLS (Static)
# ==============================================================================

@tool
def list_all_drivers() -> str:
    """
    List all drivers in the system.
    Returns driver names, phone numbers, and IDs.
    """
    db = get_db()
    try:
        drivers = driver_crud.get_all_drivers(db)
        if not drivers:
            return "No drivers found in the system."
        
        result = "Available Drivers:\n"
        for driver in drivers:
            result += f"- {driver.name} (ID: {driver.driver_id}, Phone: {driver.phone_number})\n"
        return result
    finally:
        db.close()


@tool
def create_new_driver(name: str, phone_number: str) -> str:
    """
    Create a new driver in the system.
    
    Args:
        name: Driver's name
        phone_number: Driver's phone number
    
    Returns:
        Confirmation message with created driver details
    """
    db = get_db()
    try:
        driver_data = DriverCreate(name=name, phone_number=phone_number)
        driver = driver_crud.create_driver(db, driver_data)
        return f"Successfully created driver '{driver.name}' (ID: {driver.driver_id}, Phone: {phone_number})."
    except Exception as e:
        return f"Error creating driver: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# TRIPS TOOLS (Dynamic - High Complexity)
# ==============================================================================

@tool
def get_trip_status(trip_display_name: str) -> str:
    """
    Get the status and details of a specific trip.
    Use when user asks "What's the status of 'Bulk - 00:01' trip?" or similar.
    
    Args:
        trip_display_name: Display name of the trip
    
    Returns:
        Trip status including booking percentage, live status, route, and assignments
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_display_name(db, trip_display_name)
        if not trip:
            return f"Trip '{trip_display_name}' not found."
        
        result = f"Trip: {trip.display_name}\n"
        result += f"Trip ID: {trip.trip_id}\n"
        result += f"Route: {trip.route.route_display_name}\n"
        result += f"Booking Status: {trip.booking_status_percentage}%\n"
        result += f"Live Status: {trip.live_status}\n"
        
        # Check deployments
        deployments = deployment_crud.get_deployments_by_trip(db, trip.trip_id)
        if deployments:
            result += f"\nAssignments:\n"
            for dep in deployments:
                result += f"- Vehicle: {dep.vehicle.license_plate}\n"
                result += f"- Driver: {dep.driver.name}\n"
        else:
            result += "\nNo vehicle/driver assigned yet.\n"
        
        return result
    finally:
        db.close()


@tool
def get_trip_booking_info(trip_display_name: str) -> Dict[str, Any]:
    """
    Get booking information for consequence checking.
    Returns structured data about trip bookings for decision making.
    
    Args:
        trip_display_name: Display name of the trip
    
    Returns:
        Dictionary with booking percentage and live status
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_display_name(db, trip_display_name)
        if not trip:
            return {"error": f"Trip '{trip_display_name}' not found"}
        
        return {
            "trip_id": trip.trip_id,
            "trip_name": trip.display_name,
            "booking_percentage": trip.booking_status_percentage,
            "live_status": trip.live_status,
            "has_bookings": trip.booking_status_percentage > 0,
            "is_scheduled": trip.live_status in ["scheduled", "in_progress"]
        }
    finally:
        db.close()


@tool
def list_all_trips() -> str:
    """
    List all daily trips in the system.
    Returns trip names, routes, booking status, and live status.
    """
    db = get_db()
    try:
        trips = daily_trip_crud.get_all_daily_trips(db)
        if not trips:
            return "No trips found in the system."
        
        result = "Available Trips:\n"
        for trip in trips:
            result += f"- {trip.display_name} | Route: {trip.route.route_display_name} | Booking: {trip.booking_status_percentage}% | Status: {trip.live_status}\n"
        return result
    finally:
        db.close()


# ==============================================================================
# DEPLOYMENT TOOLS (Dynamic - Consequences)
# ==============================================================================

@tool
def assign_vehicle_and_driver_to_trip(
    trip_display_name: str,
    vehicle_license_plate: str,
    driver_name: str
) -> str:
    """
    Assign a vehicle and driver to a trip.
    Use when user says "Assign vehicle X and driver Y to trip Z".
    
    Args:
        trip_display_name: Display name of the trip
        vehicle_license_plate: License plate of the vehicle
        driver_name: Name of the driver
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        # Get trip
        trip = daily_trip_crud.get_daily_trip_by_display_name(db, trip_display_name)
        if not trip:
            return f"Error: Trip '{trip_display_name}' not found."
        
        # Get vehicle
        vehicle = vehicle_crud.get_vehicle_by_license_plate(db, vehicle_license_plate)
        if not vehicle:
            return f"Error: Vehicle '{vehicle_license_plate}' not found."
        
        # Get driver
        driver = driver_crud.get_driver_by_name(db, driver_name)
        if not driver:
            return f"Error: Driver '{driver_name}' not found."
        
        # Create deployment
        deployment_data = DeploymentCreate(
            trip_id=trip.trip_id,
            vehicle_id=vehicle.vehicle_id,
            driver_id=driver.driver_id
        )
        deployment = deployment_crud.create_deployment(db, deployment_data)
        
        return f"Successfully assigned vehicle '{vehicle_license_plate}' and driver '{driver_name}' to trip '{trip_display_name}'."
    except Exception as e:
        return f"Error creating deployment: {str(e)}"
    finally:
        db.close()


@tool
def remove_vehicle_from_trip(trip_display_name: str) -> str:
    """
    Remove vehicle assignment from a trip.
    ⚠️ THIS REQUIRES CONSEQUENCE CHECKING - should be routed through check_consequences node.
    
    Args:
        trip_display_name: Display name of the trip
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_display_name(db, trip_display_name)
        if not trip:
            return f"Error: Trip '{trip_display_name}' not found."
        
        deployments = deployment_crud.get_deployments_by_trip(db, trip.trip_id)
        if not deployments:
            return f"No vehicle assigned to trip '{trip_display_name}'."
        
        # Delete all deployments for this trip
        for deployment in deployments:
            deployment_crud.delete_deployment(db, deployment.deployment_id)
        
        return f"Successfully removed vehicle and driver assignments from trip '{trip_display_name}'."
    except Exception as e:
        return f"Error removing vehicle: {str(e)}"
    finally:
        db.close()


@tool
def update_trip_booking_status(trip_display_name: str, new_percentage: float) -> str:
    """
    Update the booking status percentage for a trip.
    
    Args:
        trip_display_name: Display name of the trip
        new_percentage: New booking percentage (0-100)
    
    Returns:
        Confirmation message
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_display_name(db, trip_display_name)
        if not trip:
            return f"Error: Trip '{trip_display_name}' not found."
        
        trip.booking_status_percentage = new_percentage
        db.commit()
        
        return f"Updated booking status for trip '{trip_display_name}' to {new_percentage}%."
    except Exception as e:
        return f"Error updating booking status: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# NEW DELETION TOOLS
# ==============================================================================

@tool
def delete_deployment(deployment_id: int) -> str:
    """
    Delete a specific deployment by ID.
    This removes the vehicle and driver assignment from a trip.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - will trigger confirmation flow.
    
    Args:
        deployment_id: ID of the deployment to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        deployment = deployment_crud.get_deployment_by_id(db, deployment_id)
        if not deployment:
            return f"Error: Deployment with ID {deployment_id} not found."
        
        # Get details before deletion
        trip_id = deployment.trip_id
        vehicle_plate = deployment.vehicle.license_plate if deployment.vehicle else "Unknown"
        
        # Delete deployment
        deployment_crud.delete_deployment(db, deployment_id)
        
        return f"Successfully deleted deployment (ID: {deployment_id}). Vehicle {vehicle_plate} is now unassigned from trip."
    except Exception as e:
        return f"Error deleting deployment: {str(e)}"
    finally:
        db.close()


@tool
def delete_route(route_id: int) -> str:
    """
    Delete a route by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if route has active trips.
    
    Args:
        route_id: ID of the route to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        route = route_crud.get_route(db, route_id)
        if not route:
            return f"Error: Route with ID {route_id} not found."
        
        route_name = route.route_display_name
        
        # Check for active trips (this should be caught by consequence checker)
        trips = daily_trip_crud.get_daily_trips_by_route(db, route_id)
        if trips:
            return f"Warning: Route '{route_name}' has {len(trips)} trip(s). Delete anyway?"
        
        # Delete route
        route_crud.delete_route(db, route_id)
        
        return f"Successfully deleted route '{route_name}' (ID: {route_id})."
    except Exception as e:
        return f"Error deleting route: {str(e)}"
    finally:
        db.close()


@tool
def delete_stop(stop_id: int) -> str:
    """
    Delete a stop by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if stop is used in any paths.
    
    Args:
        stop_id: ID of the stop to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        stop = stop_crud.get_stop(db, stop_id)
        if not stop:
            return f"Error: Stop with ID {stop_id} not found."
        
        stop_name = stop.name
        
        # Check if stop is used in paths
        if stop.path_stops and len(stop.path_stops) > 0:
            path_count = len(set(ps.path_id for ps in stop.path_stops))
            return f"Warning: Stop '{stop_name}' is used in {path_count} path(s). Deleting will affect these paths."
        
        # Delete stop
        stop_crud.delete_stop(db, stop_id)
        
        return f"Successfully deleted stop '{stop_name}' (ID: {stop_id})."
    except Exception as e:
        return f"Error deleting stop: {str(e)}"
    finally:
        db.close()


@tool
def delete_path(path_id: int) -> str:
    """
    Delete a path by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if path is used in any routes.
    
    Args:
        path_id: ID of the path to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        path = path_crud.get_path(db, path_id)
        if not path:
            return f"Error: Path with ID {path_id} not found."
        
        path_name = path.path_name
        
        # Check if path is used in routes
        routes = route_crud.get_routes_by_path(db, path_id)
        if routes:
            return f"Warning: Path '{path_name}' is used in {len(routes)} route(s). Deleting will affect these routes."
        
        # Delete path
        path_crud.delete_path(db, path_id)
        
        return f"Successfully deleted path '{path_name}' (ID: {path_id})."
    except Exception as e:
        return f"Error deleting path: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# UPDATE TOOLS - For modifying existing data
# ==============================================================================

@tool
def update_stop(stop_id: int, name: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
    """
    Update an existing stop's details.
    
    Args:
        stop_id: ID of the stop to update
        name: Optional new name for the stop
        latitude: Optional new latitude
        longitude: Optional new longitude
    
    Returns:
        Confirmation message with updated stop details
    """
    db = get_db()
    try:
        from schemas import StopUpdate
        stop = stop_crud.get_stop(db, stop_id)
        if not stop:
            return f"Error: Stop with ID {stop_id} not found."
        
        # Build update dict with only provided fields
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if latitude is not None:
            update_data['latitude'] = latitude
        if longitude is not None:
            update_data['longitude'] = longitude
        
        if not update_data:
            return "No fields provided to update."
        
        # Apply updates
        for key, value in update_data.items():
            setattr(stop, key, value)
        
        db.commit()
        db.refresh(stop)
        
        return f"Successfully updated stop (ID: {stop_id}): {stop.name} at ({stop.latitude}, {stop.longitude})."
    except Exception as e:
        db.rollback()
        return f"Error updating stop: {str(e)}"
    finally:
        db.close()


@tool
def update_vehicle(
    vehicle_id: int,
    license_plate: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    capacity: Optional[int] = None,
    status: Optional[str] = None
) -> str:
    """
    Update an existing vehicle's details.
    
    Args:
        vehicle_id: ID of the vehicle to update
        license_plate: Optional new license plate
        vehicle_type: Optional new type ("bus" or "cab")
        capacity: Optional new capacity
        status: Optional new status
    
    Returns:
        Confirmation message with updated vehicle details
    """
    db = get_db()
    try:
        vehicle = vehicle_crud.get_vehicle(db, vehicle_id)
        if not vehicle:
            return f"Error: Vehicle with ID {vehicle_id} not found."
        
        # Apply updates
        if license_plate is not None:
            vehicle.license_plate = license_plate
        if vehicle_type is not None:
            v_type = VehicleType.bus if vehicle_type.lower() == "bus" else VehicleType.cab
            vehicle.type = v_type
        if capacity is not None:
            vehicle.capacity = capacity
        if status is not None:
            vehicle.status = status
        
        db.commit()
        db.refresh(vehicle)
        
        return f"Successfully updated vehicle (ID: {vehicle_id}): {vehicle.license_plate}, Type: {vehicle.type.value}, Capacity: {vehicle.capacity}, Status: {vehicle.status}."
    except Exception as e:
        db.rollback()
        return f"Error updating vehicle: {str(e)}"
    finally:
        db.close()


@tool
def update_driver(driver_id: int, name: Optional[str] = None, phone_number: Optional[str] = None) -> str:
    """
    Update an existing driver's details.
    
    Args:
        driver_id: ID of the driver to update
        name: Optional new name
        phone_number: Optional new phone number
    
    Returns:
        Confirmation message with updated driver details
    """
    db = get_db()
    try:
        driver = driver_crud.get_driver(db, driver_id)
        if not driver:
            return f"Error: Driver with ID {driver_id} not found."
        
        if name is not None:
            driver.name = name
        if phone_number is not None:
            driver.phone_number = phone_number
        
        db.commit()
        db.refresh(driver)
        
        return f"Successfully updated driver (ID: {driver_id}): {driver.name}, Phone: {driver.phone_number}."
    except Exception as e:
        db.rollback()
        return f"Error updating driver: {str(e)}"
    finally:
        db.close()


@tool
def update_route(
    route_id: int,
    route_display_name: Optional[str] = None,
    capacity: Optional[int] = None,
    status: Optional[str] = None
) -> str:
    """
    Update an existing route's details.
    
    Args:
        route_id: ID of the route to update
        route_display_name: Optional new display name
        capacity: Optional new capacity
        status: Optional new status ("active" or "deactivated")
    
    Returns:
        Confirmation message with updated route details
    """
    db = get_db()
    try:
        route = route_crud.get_route(db, route_id)
        if not route:
            return f"Error: Route with ID {route_id} not found."
        
        if route_display_name is not None:
            route.route_display_name = route_display_name
        if capacity is not None:
            route.capacity = capacity
        if status is not None:
            route.status = RouteStatus.active if status == "active" else RouteStatus.deactivated
        
        db.commit()
        db.refresh(route)
        
        return f"Successfully updated route (ID: {route_id}): {route.route_display_name}, Capacity: {route.capacity}, Status: {route.status.value}."
    except Exception as e:
        db.rollback()
        return f"Error updating route: {str(e)}"
    finally:
        db.close()


@tool
def update_trip(
    trip_id: int,
    display_name: Optional[str] = None,
    booking_status_percentage: Optional[float] = None,
    live_status: Optional[str] = None
) -> str:
    """
    Update an existing trip's details.
    
    Args:
        trip_id: ID of the trip to update
        display_name: Optional new display name
        booking_status_percentage: Optional new booking percentage (0-100)
        live_status: Optional new status ("scheduled", "in_progress", "completed", "cancelled")
    
    Returns:
        Confirmation message with updated trip details
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_id(db, trip_id)
        if not trip:
            return f"Error: Trip with ID {trip_id} not found."
        
        if display_name is not None:
            trip.display_name = display_name
        if booking_status_percentage is not None:
            trip.booking_status_percentage = booking_status_percentage
        if live_status is not None:
            trip.live_status = live_status
        
        db.commit()
        db.refresh(trip)
        
        return f"Successfully updated trip (ID: {trip_id}): {trip.display_name}, Booking: {trip.booking_status_percentage}%, Status: {trip.live_status}."
    except Exception as e:
        db.rollback()
        return f"Error updating trip: {str(e)}"
    finally:
        db.close()


@tool
def delete_vehicle(vehicle_id: int) -> str:
    """
    Delete a vehicle by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if vehicle is currently assigned to any trip.
    
    Args:
        vehicle_id: ID of the vehicle to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        vehicle = vehicle_crud.get_vehicle(db, vehicle_id)
        if not vehicle:
            return f"Error: Vehicle with ID {vehicle_id} not found."
        
        vehicle_plate = vehicle.license_plate
        
        # Check for active deployments
        deployments = deployment_crud.get_deployments_by_vehicle(db, vehicle_id)
        if deployments:
            return f"Warning: Vehicle '{vehicle_plate}' is assigned to {len(deployments)} trip(s). Remove assignments first."
        
        # Delete vehicle
        vehicle_crud.delete_vehicle(db, vehicle_id)
        
        return f"Successfully deleted vehicle '{vehicle_plate}' (ID: {vehicle_id})."
    except Exception as e:
        return f"Error deleting vehicle: {str(e)}"
    finally:
        db.close()


@tool
def delete_driver(driver_id: int) -> str:
    """
    Delete a driver by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if driver is currently assigned to any trip.
    
    Args:
        driver_id: ID of the driver to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        driver = driver_crud.get_driver(db, driver_id)
        if not driver:
            return f"Error: Driver with ID {driver_id} not found."
        
        driver_name = driver.name
        
        # Check for active deployments
        deployments = deployment_crud.get_deployments_by_driver(db, driver_id)
        if deployments:
            return f"Warning: Driver '{driver_name}' is assigned to {len(deployments)} trip(s). Remove assignments first."
        
        # Delete driver
        driver_crud.delete_driver(db, driver_id)
        
        return f"Successfully deleted driver '{driver_name}' (ID: {driver_id})."
    except Exception as e:
        return f"Error deleting driver: {str(e)}"
    finally:
        db.close()


@tool
def delete_trip(trip_id: int) -> str:
    """
    Delete a trip by ID.
    ⚠️ REQUIRES CONSEQUENCE CHECKING - checks if trip has vehicle/driver assignments or bookings.
    
    Args:
        trip_id: ID of the trip to delete
    
    Returns:
        Confirmation message or error
    """
    db = get_db()
    try:
        trip = daily_trip_crud.get_daily_trip_by_id(db, trip_id)
        if not trip:
            return f"Error: Trip with ID {trip_id} not found."
        
        trip_name = trip.display_name
        
        # Check for deployments
        deployments = deployment_crud.get_deployments_by_trip(db, trip_id)
        if deployments:
            return f"Warning: Trip '{trip_name}' has {len(deployments)} deployment(s). Delete deployments first."
        
        # Check for bookings
        if trip.booking_status_percentage > 0:
            return f"Warning: Trip '{trip_name}' has {trip.booking_status_percentage}% bookings. This will affect passengers."
        
        # Delete trip
        daily_trip_crud.delete_daily_trip(db, trip_id)
        
        return f"Successfully deleted trip '{trip_name}' (ID: {trip_id})."
    except Exception as e:
        return f"Error deleting trip: {str(e)}"
    finally:
        db.close()


# ==============================================================================
# ANALYTICS TOOLS
# ==============================================================================

@tool
def get_vehicle_utilization_summary() -> str:
    """
    Get a summary of vehicle utilization across all trips.
    Shows assigned vs unassigned vehicles.
    """
    db = get_db()
    try:
        all_vehicles = vehicle_crud.get_all_vehicles(db)
        all_deployments = deployment_crud.get_all_deployments(db)
        
        total_vehicles = len(all_vehicles)
        assigned_vehicles = len(set(d.vehicle_id for d in all_deployments))
        unassigned_vehicles = total_vehicles - assigned_vehicles
        
        utilization_rate = (assigned_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0
        
        result = "Vehicle Utilization Summary:\n"
        result += f"Total Vehicles: {total_vehicles}\n"
        result += f"Assigned: {assigned_vehicles}\n"
        result += f"Unassigned: {unassigned_vehicles}\n"
        result += f"Utilization Rate: {utilization_rate:.1f}%\n"
        
        return result
    finally:
        db.close()


# ==============================================================================
# SQL AGENT TOOLS (For Complex Queries)
# ==============================================================================

def _get_sql_agent():
    """
    Internal helper to initialize the SQL Agent.
    This agent can convert natural language to SQL and execute queries.
    """
    if not SQL_AGENT_AVAILABLE or not LANGCHAIN_AVAILABLE:
        return None
    
    try:
        # Create SQLDatabase wrapper
        db = SQLDatabase.from_uri(DATABASE_URL)
        
        # Create LLM for SQL Agent
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Create SQL Agent with toolkit
        agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="openai-tools",
            verbose=True,
            handle_parsing_errors=True
        )
        
        return agent
    except Exception as e:
        print(f"Error creating SQL Agent: {e}")
        return None


@tool
def query_database_with_natural_language(query: str) -> str:
    """
    Execute complex database queries using natural language.
    This tool uses an AI SQL Agent to convert your question into SQL and execute it.
    
    Use this for:
    - Complex analytical queries (e.g., "Show routes with most unassigned trips")
    - Multi-table joins (e.g., "Which drivers worked on trips with >50% booking?")
    - Aggregations (e.g., "Average booking percentage per route")
    - Questions that don't fit predefined tools
    
    Args:
        query: Natural language question about the database
    
    Returns:
        Query results in human-readable format
    
    Examples:
        - "Show me all trips on routes that use Path-1"
        - "Which vehicles are assigned to trips with booking > 80%?"
        - "List drivers who are not currently deployed"
        - "What's the average capacity of active routes?"
    """
    if not SQL_AGENT_AVAILABLE:
        return "Error: SQL Agent not available. Please install langchain-community package."
    
    try:
        agent = _get_sql_agent()
        if not agent:
            return "Error: Failed to initialize SQL Agent."
        
        # Execute the query using the agent
        result = agent.invoke({"input": query})
        
        # Return the output
        return result.get("output", "No results found.")
        
    except Exception as e:
        return f"Error executing query: {str(e)}"


@tool
def execute_safe_sql_mutation(natural_language_action: str) -> str:
    """
    Execute write operations (INSERT, UPDATE, DELETE) using natural language.
    ⚠️ This should be used with CAUTION and only after consequence checking.
    
    Use this for:
    - Bulk updates that don't have predefined tools
    - Complex conditional updates
    - Data corrections
    
    Args:
        natural_language_action: Natural language description of what to change
    
    Returns:
        Confirmation message or error
    
    Examples:
        - "Update all trips with 0% booking to status 'cancelled'"
        - "Remove all deployments for vehicles with status 'inactive'"
        - "Set allocated_waitlist to 0 for all deactivated routes"
    """
    if not SQL_AGENT_AVAILABLE:
        return "Error: SQL Agent not available. Please install langchain-community package."
    
    # Safety check: Don't allow dangerous operations
    dangerous_keywords = ["drop", "truncate", "delete from stops", "delete from vehicles"]
    if any(keyword in natural_language_action.lower() for keyword in dangerous_keywords):
        return "Error: This operation is too dangerous. Please use specific tools or manual SQL."
    
    try:
        agent = _get_sql_agent()
        if not agent:
            return "Error: Failed to initialize SQL Agent."
        
        # Add safety instruction to the prompt
        safe_prompt = f"""
        Execute this database operation: {natural_language_action}
        
        IMPORTANT SAFETY RULES:
        1. Do NOT drop tables
        2. Do NOT truncate tables
        3. Use transactions where possible
        4. Confirm the operation affects the intended records only
        
        If the operation seems unsafe, explain why and don't execute it.
        """
        
        result = agent.invoke({"input": safe_prompt})
        
        return result.get("output", "Operation completed.")
        
    except Exception as e:
        return f"Error executing mutation: {str(e)}"


@tool
def analyze_database_schema() -> str:
    """
    Get information about the database schema and available tables.
    Useful for understanding what data is available.
    
    Returns:
        Description of database tables and their relationships
    """
    if not SQL_AGENT_AVAILABLE:
        return "Error: SQL Agent not available."
    
    try:
        db = SQLDatabase.from_uri(DATABASE_URL)
        
        # Get table names
        tables = db.get_usable_table_names()
        
        result = "Database Schema:\n\n"
        result += f"Available Tables: {', '.join(tables)}\n\n"
        
        # Get schema for each table
        for table in tables:
            result += f"\n{table.upper()} Table:\n"
            result += db.get_table_info([table])
            result += "\n" + "-"*50 + "\n"
        
        return result
        
    except Exception as e:
        return f"Error analyzing schema: {str(e)}"


# ==============================================================================
# MULTIMODAL TOOLS (Vision, Speech) - Using LangChain
# ==============================================================================

@tool
def analyze_screenshot(image_base64: str, user_query: str) -> Dict[str, Any]:
    """
    Analyze a screenshot using LangChain's vision models to extract relevant information.
    This tool enables the agent to understand visual context from uploaded images.
    
    Use cases:
    - User uploads busDashboard screenshot and says "Remove vehicle from this trip"
    - User points to a specific trip with an arrow/highlight
    - User shows a routes page and asks about specific routes
    
    Args:
        image_base64: Base64 encoded image string
        user_query: The user's question/request about the image
    
    Returns:
        Dictionary containing:
        - identified_entities: List of trips, vehicles, routes, etc. found in image
        - user_intent: What the user wants to do
        - context: Additional context extracted from the image
    """
    if not LANGCHAIN_AVAILABLE:
        return {
            "error": "Vision model not available. Please install langchain-openai package.",
            "identified_entities": [],
            "user_intent": user_query,
            "context": "Vision analysis unavailable"
        }
    
    try:
        # Initialize LangChain vision model
        llm = ChatOpenAI(
            model="gpt-4o",  # Supports vision
            temperature=0,
            max_tokens=1000
        )
        
        # Prepare the vision prompt
        vision_prompt = f"""
        You are analyzing a screenshot from a transportation management system dashboard.
        The user asked: "{user_query}"
        
        Please analyze the image and extract:
        1. Any trip names/IDs visible (e.g., "Bulk - 00:01", "Path Path - 00:02")
        2. Vehicle license plates visible (e.g., "MH-12-3456")
        3. Route names or path names visible
        4. Booking percentages or status information
        5. Any highlighted, circled, or pointed-to elements
        6. The page type (busDashboard, routes, stops & paths, etc.)
        
        Return ONLY a valid JSON response (no markdown, no code blocks) with this exact structure:
        {{
            "page_type": "busDashboard|routes|stops_paths|unknown",
            "identified_trips": ["trip_name1", "trip_name2"],
            "identified_vehicles": ["vehicle_plate1"],
            "identified_routes": ["route_name1"],
            "highlighted_element": "description of what user pointed to",
            "user_intent": "what the user wants to do",
            "additional_context": "any other relevant information"
        }}
        """
        
        # Create message with image
        message = HumanMessage(
            content=[
                {"type": "text", "text": vision_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        )
        
        # Invoke the vision model
        response = llm.invoke([message])
        
        # Parse the response
        response_text = response.content.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        result = json.loads(response_text)
        
        return {
            "success": True,
            "page_type": result.get("page_type", "unknown"),
            "identified_entities": {
                "trips": result.get("identified_trips", []),
                "vehicles": result.get("identified_vehicles", []),
                "routes": result.get("identified_routes", [])
            },
            "highlighted_element": result.get("highlighted_element", ""),
            "user_intent": result.get("user_intent", user_query),
            "context": result.get("additional_context", "")
        }
        
    except Exception as e:
        return {
            "error": f"Vision analysis failed: {str(e)}",
            "identified_entities": {},
            "user_intent": user_query,
            "context": "Error processing image"
        }


@tool
def transcribe_audio(audio_base64: str) -> str:
    """
    Convert speech to text using OpenAI Whisper via LangChain.
    This enables voice input for the Movi assistant.
    
    Args:
        audio_base64: Base64 encoded audio file (webm, mp3, wav, etc.)
    
    Returns:
        Transcribed text from the audio
    """
    # Note: LangChain doesn't have native STT, so we use OpenAI client directly
    # But keep it modular for future LangChain audio support
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Create a temporary file-like object
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "audio.webm"  # Whisper needs a filename
        
        # Transcribe using Whisper
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        return transcript.text
        
    except ImportError:
        return "Error: OpenAI package not installed. Please install openai package for audio transcription."
    except Exception as e:
        return f"Error transcribing audio: {str(e)}"


@tool
def generate_speech(text: str) -> str:
    """
    Convert text to speech using OpenAI TTS.
    This enables voice output for the Movi assistant.
    
    Args:
        text: The text to convert to speech
    
    Returns:
        Base64 encoded audio file (mp3)
    """
    # Note: LangChain doesn't have native TTS yet, so we use OpenAI client directly
    # But keep it modular for future LangChain audio support
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",  # or "alloy", "echo", "fable", "onyx", "shimmer"
            input=text
        )
        
        # Convert to base64
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        
        return audio_base64
        
    except ImportError:
        return "Error: OpenAI package not installed. Please install openai package for text-to-speech."
    except Exception as e:
        return f"Error generating speech: {str(e)}"


# ==============================================================================
# TOOL CATEGORIES - PAGE-BASED FILTERING
# ==============================================================================

# Global tools available on ALL pages
GLOBAL_TOOLS = [
    # SQL Agent Tools (advanced queries work everywhere)
    query_database_with_natural_language,
    execute_safe_sql_mutation,
    analyze_database_schema,
    # Multimodal Tools (vision/audio work everywhere)
    analyze_screenshot,
    transcribe_audio,
    generate_speech,
]

# Bus Dashboard page tools (trips, vehicles, drivers, deployments)
BUS_DASHBOARD_TOOLS = [
    list_all_trips,
    get_trip_status,
    get_trip_booking_info,
    assign_vehicle_and_driver_to_trip,
    remove_vehicle_from_trip,
    update_trip_booking_status,
    update_trip,
    delete_trip,
    delete_deployment,
    list_all_vehicles,
    count_unassigned_vehicles,
    create_new_vehicle,
    update_vehicle,
    delete_vehicle,
    list_all_drivers,
    create_new_driver,
    update_driver,
    delete_driver,
    get_vehicle_utilization_summary,
]

# Stops & Paths page tools
STOPS_PATHS_TOOLS = [
    list_all_stops,
    create_new_stop,
    get_stop_details,
    update_stop,
    delete_stop,
    list_all_paths,
    list_stops_for_path,
    create_new_path,
    delete_path,
]

# Routes page tools
ROUTES_TOOLS = [
    list_all_routes,
    list_routes_using_path,
    create_new_route,
    update_route,
    delete_route,
]

# Export all tools as a list for backward compatibility
ALL_TOOLS = (
    GLOBAL_TOOLS + 
    BUS_DASHBOARD_TOOLS + 
    STOPS_PATHS_TOOLS + 
    ROUTES_TOOLS
)


def get_tools_for_page(page: str) -> list:
    """
    Get tools available for a specific page context.
    This enables page-aware tool filtering for better agent performance.
    
    Args:
        page: Page context (busDashboard, stops_paths, routes, vehicles, drivers, unknown)
    
    Returns:
        List of tools available for that page (always includes GLOBAL_TOOLS)
    """
    page_tools = {
        "busDashboard": GLOBAL_TOOLS + BUS_DASHBOARD_TOOLS,
        "stops_paths": GLOBAL_TOOLS + STOPS_PATHS_TOOLS,
        "routes": GLOBAL_TOOLS + ROUTES_TOOLS,
        "vehicles": GLOBAL_TOOLS + BUS_DASHBOARD_TOOLS,  # Vehicles are part of bus dashboard
        "drivers": GLOBAL_TOOLS + BUS_DASHBOARD_TOOLS,   # Drivers are part of bus dashboard
        "unknown": GLOBAL_TOOLS + BUS_DASHBOARD_TOOLS,   # Default to bus dashboard
    }
    
    tools = page_tools.get(page, GLOBAL_TOOLS + BUS_DASHBOARD_TOOLS)
    
    # Log tool breakdown
    print(f"📊 Tool Breakdown for '{page}':")
    print(f"   - Global Tools: {len(GLOBAL_TOOLS)}")
    if page in ["busDashboard", "vehicles", "drivers", "unknown"]:
        print(f"   - Bus Dashboard Tools: {len(BUS_DASHBOARD_TOOLS)}")
    elif page == "stops_paths":
        print(f"   - Stops & Paths Tools: {len(STOPS_PATHS_TOOLS)}")
    elif page == "routes":
        print(f"   - Routes Tools: {len(ROUTES_TOOLS)}")
    print(f"   - Total: {len(tools)} tools available")
    
    return tools
