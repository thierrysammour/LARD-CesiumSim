# -*- coding: utf-8 -*-
"""
Flask web server with SocketIO integration for real-time communication with CesiumJS.

This server provides a RESTful API to control the client's view and a WebSocket
interface to receive image frames from it. It's designed to handle multiple
client sessions simultaneously, using session IDs (sid) to route messages and data.

Key Features:
- Asynchronous networking with eventlet for high performance.
- Real-time, bidirectional communication using Flask-SocketIO.
- API endpoints to set the client's view, draw shapes, and query data.
- A sophisticated endpoint (`/set_and_get`) that synchronously requests and
  waits for an image frame from a specific client.
- Image processing capabilities using OpenCV and NumPy to handle various
  formats (PNG, JPG, raw pixel data).
"""

# --- Core Imports ---
import eventlet
# Monkey-patching standard libraries to make them cooperative with eventlet's green threads.
# This is crucial for SocketIO's asynchronous performance.
eventlet.monkey_patch()

# --- Standard Library Imports ---
import base64
import threading
import os

# --- Third-Party Imports ---
import numpy as np
import cv2
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

# --- Application-Specific Imports ---
# Assumed to be a utility module containing a dictionary of airport data.
from app_utils import airports_database


# --- Flask Application Setup ---
# Initialize the Flask application.
# The static folders are configured to serve files from the root and a specific template folder.
app = Flask(__name__,
            static_url_path='', 
            static_folder='',
            template_folder='static/template')

# --- SocketIO Setup ---
# Initialize SocketIO for real-time communication.
# - cors_allowed_origins="*": Allows connections from any origin (useful for development).
# - async_handlers=False: Simplifies handler logic by running them synchronously.
# - max_http_buffer_size: Increased to handle large data payloads like images.
# - ping_timeout: Increased to prevent disconnections on slow networks.
socketio = SocketIO(app, cors_allowed_origins="*", async_handlers=False, 
                    engineio_logger=False, 
                    max_http_buffer_size=1e8, ping_timeout=100000)

# --- Shared Global State ---
# These dictionaries manage data and synchronization across different client sessions.
# They are shared between the HTTP request threads and the SocketIO event handlers.
session_frames = {}  # Stores the latest received frame (base64 encoded) for a given sid.
session_events = {}  # Stores threading.Event objects to signal frame arrival for a sid.
session_lock = threading.Lock() # A lock to ensure thread-safe access to the shared dictionaries.


# --- Web Page Route ---
@app.route('/')
def index():
    """Serves the main HTML page of the application."""
    return render_template('index.html')


# --- SocketIO Event Handlers ---
@socketio.on('frame')
def handle_frame(data):
    """
    Handles incoming 'frame' events from a client.

    This function receives image data, processes it based on the provided parameters
    (e.g., saving to disk, storing for another request), and signals any waiting
    threads that the frame has arrived.
    """
    # Extract data from the incoming message payload.
    sid = data.get('sid')                   # The client's unique session ID.
    frame_blob = data.get('frame')          # The image data (bytes or base64 string).
    id = data.get('id')                     # A unique identifier for the frame.
    save = data.get('save', False)          # Flag to indicate if the frame should be saved.
    save_folder_path = data.get('save_folder_path', '') # Directory to save the file.
    file_extension = data.get('file_extension', '.png') # File format for saving.
    ext = file_extension.lower().lstrip('.')
    get = data.get('get', False)            # Flag to indicate if the frame should be stored for retrieval.
    width = data.get('width')               # Image width, required for 'raw' format.
    height = data.get('height')             # Image height, required for 'raw' format.
    
    # Initialize variables.
    img = None                              # Will hold the decoded image (OpenCV format).
    b64_img = None                          # Will hold the base64 encoded image string.

    # Early exit if essential data is missing. This prevents errors down the line.
    if not sid or not frame_blob:
        print(f"[handle_frame] ❌ Missing 'sid' or 'frame' in received data.")
        # If a thread is waiting for a frame from this session, signal it to unblock.
        with session_lock:
            if sid in session_events:
                print(f"[handle_frame] Setting event for sid={sid} to unblock waiting thread.")
                session_events[sid].set()
        return

    print(f"[handle_frame] 📷 Received frame from sid={sid}")

    try:
        # --- Frame Saving Logic ---
        if save:
            # Handle standard image formats (PNG, JPG, etc.).
            if ext in ['png', 'jpg', 'jpeg', 'bmp', 'webp']:
                # Convert the incoming byte buffer into a NumPy array.
                img_array = np.frombuffer(frame_blob, dtype=np.uint8)
                # Decode the NumPy array into an OpenCV image.
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("Failed to decode standard image format.")
                
                # Save the decoded image to the specified path.
                os.makedirs(save_folder_path, exist_ok=True)
                filename = os.path.join(save_folder_path, id + file_extension)
                cv2.imwrite(filename, img)
                print(f"[handle_frame] ✅ Image saved to: {filename}")

            # Handle raw RGBA pixel data.
            elif ext == 'raw':
                if not (width and height):
                    raise ValueError("Width and Height must be specified for raw data.")
                # Decode base64 string if necessary, then create a NumPy array.
                raw_bytes = base64.b64decode(frame_blob) if isinstance(frame_blob, str) else frame_blob
                img_array = np.frombuffer(raw_bytes, dtype=np.uint8)
                # Reshape into a 4-channel (RGBA) image and flip vertically.
                img_array = img_array.reshape((height, width, 4))
                img_array = np.flip(img_array, axis=0)
                # Convert from RGBA to BGR for saving with OpenCV.
                img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                
                # Save the raw data as a NumPy array for later use.
                os.makedirs(save_folder_path, exist_ok=True)
                np.save(os.path.join(save_folder_path, id + '.npy'), img_array)
                print(f"[handle_frame] ✅ Raw frame saved as numpy array to: {save_folder_path}")

    except Exception as e:
        print(f"[handle_frame] ❌ Error processing/saving image for sid={sid}: {e}")

    # --- Frame Retrieval Logic ---
    if get:
        # If the frame needs to be retrieved by another part of the app (like /set_and_get),
        # ensure it's base64 encoded and store it in the shared dictionary.
        b64_img = frame_blob if isinstance(frame_blob, str) else base64.b64encode(frame_blob).decode('utf-8')
        with session_lock:
            session_frames[sid] = b64_img
        print(f"[handle_frame] ✅ Stored frame for retrieval by sid={sid}")
            
    # --- Signal Waiting Threads ---
    # This is the crucial step that connects this event handler with the /set_and_get endpoint.
    with session_lock:
        if sid in session_events:
            # If an event object exists for this session, set it.
            # This will unblock the `event.wait()` call in the /set_and_get route.
            print(f"[handle_frame] Setting event to signal frame arrival for sid={sid}")
            session_events[sid].set()
        else:
            # This can happen if a frame is sent without a corresponding /set_and_get request.
            print(f"[handle_frame] No event found for sid={sid}, frame received independently.")


# --- API Routes ---
@app.route('/set_and_get', methods=['POST'])
def set_and_get_frame():
    """
    Synchronously sets a view on a client and waits for a frame in response.

    This function orchestrates a complex round-trip operation:
    1. An HTTP POST request arrives here.
    2. An event object is created to "listen" for a frame from a specific client (sid).
    3. A 'set_and_get_view' WebSocket event is emitted to the client.
    4. The server thread BLOCKS and waits for the event to be signaled.
    5. The client receives the event, captures a frame, and sends it back via the 'frame' event.
    6. The `handle_frame` function receives the frame and signals the event, unblocking this thread.
    7. The captured frame is retrieved from shared memory and returned in the HTTP response.
    """
    if not request.json:
        return jsonify({"error": "Missing JSON"}), 400

    data = request.json
    sid = data.get('sid')  # The ID of the target client is required.

    if not sid:
        return jsonify({"error": "Missing socket ID"}), 400

    # 1. Register an event that this request will wait on.
    event = threading.Event()
    with session_lock:
        session_events[sid] = event

    # Prepare to receive a JSON response from the client's callback.
    client_response = {}
    response_lock = threading.Lock()
    response_ready = threading.Event()

    def callback(response_from_client):
        """Callback executed when the client acknowledges the 'set_and_get_view' event."""
        with response_lock:
            if response_from_client:
                client_response.update(response_from_client)
            else:
                print("[set_and_get][callback] ⚠️ No response data from client.")
        response_ready.set()  # Signal that this callback has completed.

    # 2. Emit the event to the specific client, requesting the view update and frame.
    socketio.emit('set_and_get_view', data, callback=callback)

    # 3. Wait for the `handle_frame` function to signal that a frame has arrived.
    print(f"[set_and_get] 🕒 Waiting for frame from sid={sid}...")
    event.wait(timeout=30)  # Set a timeout to avoid waiting indefinitely.

    if not event.is_set():
        print(f"[set_and_get] ⏱️ Timeout waiting for frame from sid={sid}")

    # Also wait for the client's direct JSON callback to complete.
    response_ready.wait(timeout=5)

    # 4. Clean up and retrieve the frame.
    with session_lock:
        b64_frame = session_frames.pop(sid, None)
        session_events.pop(sid, None) # Remove the event to prevent memory leaks.

    # 5. Construct the final response.
    with response_lock:
        # Add the captured frame data to the response received from the client callback.
        if b64_frame and data.get('frame', {}).get('get'):
            client_response.setdefault("frame", {})["data"] = b64_frame
        else:
            client_response.setdefault("frame", {})["data"] = None

    return jsonify(client_response)


@app.route('/set', methods = ['POST'])
def set_frame():
    """A simple 'fire-and-forget' endpoint to update the client's view."""
    if request.json:
        # Broadcasts the 'set_view' event to all connected clients.
        socketio.emit('set_view', request.json)
    return request.json


@app.route('/get', methods = ['GET'])
def get_frame():
    """Endpoint to request data and frames from the client."""
    ev = threading.Event()
    output_data = {}
    data_frame1 = None
    data_frame2 = None
    data = request.json

    # Dynamically defining event handlers inside a request is unusual.
    # These will only be active for the duration of this specific client's request context.
    @socketio.on('frame1')
    def handle_frame1(data):
        nonlocal data_frame1
        data_frame1 = data

    @socketio.on('frame2')
    def handle_frame2(data):
        nonlocal data_frame2
        data_frame2 = data

    def get_image_callback(data):
        """Callback to handle the primary data response from the client."""
        nonlocal output_data, ev
        output_data = data
        ev.set() # Signal that the response has been received.
            
    # Emit the get request and wait for the callback.
    socketio.emit('get_view', data, callback=get_image_callback)
    ev.wait() # Block until the callback signals completion.

    # If separate frame chunks were received, combine them.
    if data_frame1 is not None and data_frame2 is not None:
        output_data["frame"] = data_frame1 + data_frame2

    return jsonify(output_data)

    
@app.route('/set_terrain_and_imagery', methods=['POST'])
def set_terrain_and_imagery():
    """Endpoint to update the client's terrain and imagery layers."""
    if request.json:
        socketio.emit('set_terain_and_imagery', request.json)
    return {}


@app.route('/draw', methods = ['POST'])
def draw():
    """Endpoint to send drawing commands to the client."""
    if request.json:
        socketio.emit('draw', request.json)
    return request.json


# --- Airport Data API Routes ---
# These routes provide a simple API to query the pre-loaded airport database.

@app.route('/get_airports', methods=['GET'])
def get_airports():
    """Returns a sorted list of all available airport codes."""
    return jsonify(np.sort(list(airports_database.keys())).tolist())


@app.route('/get_runways', methods=['POST'])
def get_runways():
    """Returns a list of runways for a given airport."""
    airport = request.json['airport']
    return jsonify(list(airports_database[airport]['runways'].keys()))


@app.route('/get_runways_labels', methods=['POST'])
def get_runways_labels():
    """Returns detailed runway information for a given airport."""
    airport = request.json['airport']
    return jsonify(airports_database[airport]['runways'])


@app.route('/get_runway_labels', methods=['POST'])
def get_runway_labels():
    """Returns information for a specific runway at an airport."""
    airport = request.json['airport']
    runway = request.json['runway']
    return jsonify(airports_database[airport]['runways'][runway])


@app.route('/get_runway_corners', methods=['POST'])
def get_runway_coordinates():
    """Returns the corner coordinates for a specific runway."""
    airport = request.json['airport']
    runway = request.json['runway']
    return jsonify(list(airports_database[airport]['runways'][runway]['corners']))


# --- Main Execution Block ---
if __name__ == '__main__':
    # Get host and port from environment variables, with defaults for local development.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8082"))
    print(f"🚀 Starting LARD - CesiumSim server on http://{host}:{port}")
    # Run the application using the eventlet server for asynchronous handling.
    socketio.run(app, host=host, port=port)