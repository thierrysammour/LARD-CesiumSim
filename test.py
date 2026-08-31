# -*- coding: utf-8 -*-
"""
Client-side script to interact with the CesiumJS Flask/SocketIO server.

This script programmatically controls a CesiumJS client by sending HTTP requests
to the server. It fetches airport data, generates randomized camera positions,
and then requests the server to update the client's view and return a rendered frame.
The returned frames are then displayed in a window using OpenCV.

This is a typical workflow for automated data generation, simulation, or
testing of a 3D visualization environment.
"""

# --- Standard Library Imports ---
import uuid
import json
import time

# --- Third-Party Imports ---
import requests  # For making HTTP requests to the server API.
import cv2       # Used to display the image frames received from the server.
import numpy as np

# --- Application-Specific Imports ---
# Assumed to be a utility function that decodes a base64 string from the metadata.
from app_utils import readb64


# --- Configuration ---
# The URL of the Flask server that bridges communication with the CesiumJS client.
CESIUM_URL = 'http://0.0.0.0:8082'


# --- API Interaction Functions ---

def get_runways_labels(airport: str) -> dict:
    """
    Fetches detailed runway information for a given airport from the server.

    Args:
        airport (str): The ICAO code of the airport (e.g., "LFBO").

    Returns:
        dict: A dictionary containing runway labels and coordinates.
    """
    # Send a POST request to the '/get_runways_labels' endpoint.
    response = requests.post(
        f'{CESIUM_URL}/get_runways_labels',
        json={"airport": airport}
    )
    # Raise an exception if the request was unsuccessful (e.g., 404, 500).
    response.raise_for_status()
    # Parse the JSON response and return it.
    return response.json()

def build_metadata(runways_coords: dict) -> dict:
    """
    Constructs the main JSON payload (metadata) for a '/set_and_get' request.

    This function defines all parameters for the desired scene in CesiumJS,
    including camera position, attitude, environment settings, and objects to draw.
    The camera position is randomized to generate different views on each call.

    Args:
        runways_coords (dict): A dictionary with runway data, used to generate
                               landmark and drawing instructions.

    Returns:
        dict: A fully-formed dictionary ready to be sent as a JSON payload.
    """
    # --- 1. Define Landmarks ---
    # Landmarks are specific points of interest. This data can be used later
    # for analysis, labeling, or validation.
    landmarks = {}
    for runway in runways_coords.keys():
        landmarks[runway] = {
            "top_left": {"coordinates": dict(zip(["latitude_deg", "longitude_deg", "altitude_m"], runways_coords[runway]['corners'][0]))},
            "top_right": {"coordinates": dict(zip(["latitude_deg", "longitude_deg", "altitude_m"], runways_coords[runway]['corners'][1]))},
            "bottom_right": {"coordinates": dict(zip(["latitude_deg", "longitude_deg", "altitude_m"], runways_coords[runway]['corners'][2]))},
            "bottom_left": {"coordinates": dict(zip(["latitude_deg", "longitude_deg", "altitude_m"], runways_coords[runway]['corners'][3]))},
        }

    # --- 2. Define Drawings ---
    # Drawings are instructions for the CesiumJS client to render visual shapes
    # in the 3D scene, like polygons on the ground.
    drawings = {}
    for runway in runways_coords.keys():
        drawings[runway] = {
                "type": 'polygon3d',
                'color_rgba': [1, 1, 1, 1], # White, fully opaque
                "points": [
                    dict(zip(["latitude_deg", "longitude_deg", "altitude_m"], pt))
                    for pt in runways_coords[runway]['corners']
                ]
        }

    # --- 3. Generate a Randomized Camera Position ---
    # This creates slight variations for each generated scene.
    base_lat = 43.61056841445068  # Base latitude (near Toulouse)
    base_lon = 1.3804829520801687  # Base longitude (near Toulouse)
    
    # Add a small random offset to the base coordinates.
    rand_lat = base_lat + np.random.uniform(-0.001, 0.001)
    rand_lon = base_lon + np.random.uniform(-0.0005, 0.0005)
    rand_alt = np.random.randint(250, 350) # Random altitude in meters.


    # --- 4. Assemble the Final Metadata Dictionary ---
    # This dictionary is the complete instruction set for the server.
    return {
        'sid': 'session_1',        # A client-defined session ID.
        'id': str(uuid.uuid4()),   # A unique ID for this specific request.

        'environment': {
            'layer': 'default',    # Specifies the map layer to use ('default', 'google3d', etc.).
        },

        'camera': {
            'coordinates': {
                'latitude_deg': rand_lat,
                'longitude_deg': rand_lon,
                'altitude_m': rand_alt,
            },
            'attitude': {
                'roll_deg': 0,
                'pitch_deg': 0,
                'heading_deg': -37,
            },
            'fov_horizontal_deg': 60,
            'fov_vertical_deg': 40,
            'width_px': 1024,      # Requested frame width.
            'height_px': 768,      # Requested frame height.
            # Post-processing settings for the rendered image.
            'brightness': 1,
            'contrast': 1,
            'hue': 0,
            'saturation': 1,
            'gamma': 1,
            # Cropping and resizing options (unused here).
            'crop_xywh_px': None,
            'crop_width_resize_px': None,
            'crop_height_resize_px': None,
        },

        'frame': {
            'get': True,           # Crucial: tells the server we want a frame back.
            'save': False,         # If true, the server would save the frame to its disk.
            'save_folder_path': 'output/', 
            'file_extension': '.png',
            'data': None,          # This will be populated in the response from the server.
        },

        'daytime': {
            'year': 2000,
            'month': 1,
            'day': 1,
            'hour': 12, # Set to noon for good lighting.
            'minute': 0,
            'second': 0,
            'timestamp': None,
        },

        'landmarks': landmarks,
        'drawings': drawings,
    }

def set_and_get(metadata: dict) -> dict:
    """
    Sends the metadata to the server and waits for the response containing the frame.

    Args:
        metadata (dict): The payload generated by `build_metadata`.

    Returns:
        dict: The server's JSON response, which should include the frame data.
    """
    response = requests.post(f'{CESIUM_URL}/set_and_get', json=metadata)
    response.raise_for_status()
    return response.json()

def show_frame(metadata: dict):
    """
    Decodes the frame data from the metadata and displays it in a window.

    Args:
        metadata (dict): The response JSON from the server.
    """
    # The 'readb64' utility is expected to extract and decode the base64 frame string.
    frame = readb64(metadata)
    if frame is not None:
        # Display the image using OpenCV.
        cv2.namedWindow('frame', cv2.WINDOW_NORMAL) # Create a resizable window.
        cv2.imshow('frame', frame)
        cv2.waitKey(1) # Wait for 1ms; allows the window to update.

# --- Main Execution Block ---

def main():
    """
    The main loop of the client application.
    """
    # Define the target airport. LFBO is Toulouse–Blagnac Airport.
    AIRPORT = "LFBO"

    # 1. Fetch runway data once at the beginning.
    runways = get_runways_labels(AIRPORT)
    
    # 2. Start the main data generation loop.
    print(f"🚀 Starting data generation loop for airport {AIRPORT}...")
    for i in range(100):
        # 3. Build a new scene with a randomized camera position.
        metadata = build_metadata(runways)

        # 4. Send the request and time the round trip.
        start_time = time.time()
        metadata_response = set_and_get(metadata)
        elapsed_time = time.time() - start_time
        print(f"Request {i+1:03d} | Round-trip time: {elapsed_time:.2f} seconds")

        # 5. If a frame was received, display it.
        if "frame" in metadata_response and metadata_response.get("frame", {}).get("data"):
            show_frame(metadata_response)
        else:
            print("  -> No frame data received in response.")

if __name__ == "__main__":
    main()
