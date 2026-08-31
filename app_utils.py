# -*- coding: utf-8 -*-
"""
Utility module for the CesiumJS client application.

This script provides helper functions and loads shared data resources.
Its main responsibilities are:
1.  Loading a shared airport database from a JSON file specified by an
    environment variable.
2.  Providing a robust function (`readb64`) to decode image data received
    from the server. This function can handle both standard image formats
    (e.g., PNG, JPG) and raw RGBA pixel data, both encoded in base64.
"""

# --- Third-Party Imports ---
import cv2          # For image processing (decoding, color conversion, etc.).
import base64       # For handling base64 encoding and decoding.
import numpy as np  # For numerical operations, especially creating arrays from byte buffers.

# --- Standard Library Imports ---
import json         # For parsing the JSON database file.
import os           # For accessing environment variables and file paths.
from dotenv import load_dotenv # For loading environment variables from a .env file.

# --- Initialization and Data Loading ---

# Load environment variables from a .env file in the project root.
# This allows for easy configuration of file paths without changing the code.
load_dotenv()

# Load the airport database from a JSON file.
# The file path is retrieved from an environment variable 'DATABASE_FILEPATH'.
# If the variable is not set, it defaults to 'data/cesium_arcgis_db.json'.
database_path = os.environ.get('DATABASE_FILEPATH', 'data/cesium_arcgis_db.json')
print(f"🌍 Loading airport database from: {database_path}")
with open(database_path, 'r') as f:
    airports_database = json.load(f)


def readb64(metadata: dict) -> np.ndarray | None:
   """
   Decodes a base64 image string from a metadata dictionary into an OpenCV image.

   This function is designed to parse the JSON response from the server. It can
   handle two types of image data:
   1. Standard formats (PNG, JPG) which are decoded directly by OpenCV.
   2. A 'raw' format, which is assumed to be raw RGBA pixel data that needs to
      be reshaped and color-corrected.

   Args:
       metadata (dict): The dictionary received from the server, expected to
                        contain a `frame` key with image data and details.

   Returns:
       np.ndarray | None: An OpenCV image in BGR format if decoding is successful,
                          otherwise None.
   """
   # Extract the base64-encoded string from the nested dictionary.
   base64_string = metadata["frame"]['data']
   
   # If there's no image data, return None immediately.
   if base64_string is None:
      return None

   # The client might send a "data URI" (e.g., "data:image/png;base64,iVBOR...").
   # This line safely removes that prefix, leaving only the pure base64 data.
   encoded_data = base64_string.split(',')[1] if ',' in base64_string else base64_string
   
   # Decode the base64 string into a raw byte buffer and create a NumPy array from it.
   decoded_bytes = base64.b64decode(encoded_data)
   nparr = np.frombuffer(decoded_bytes, dtype=np.uint8)

   # --- Conditional Decoding based on File Extension ---
   
   # Handle 'raw' RGBA pixel data.
   if 'raw' in metadata["frame"]['file_extension']:
      # Reshape the 1D array into a 3D array (height, width, channels).
      # The dimensions are taken from the camera metadata.
      height = metadata["camera"]['height_px']
      width = metadata["camera"]['width_px']
      nparr = nparr.reshape((height, width, 4)) # 4 channels for RGBA
      
      # WebGL/OpenGL and NumPy have different coordinate origins (bottom-left vs. top-left).
      # A vertical flip is often needed to correct the image orientation.
      nparr = np.flip(nparr, axis=0)
      
      # Convert the image from RGBA (from browser) to BGR (for OpenCV).
      img = cv2.cvtColor(nparr, cv2.COLOR_RGBA2BGR)
   
   # Handle standard, compressed image formats (e.g., PNG, JPG).
   else:
      # Let OpenCV's imdecode handle the format detection and decoding.
      img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

   return img