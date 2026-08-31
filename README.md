# 🚀 LARD - CesiumSim

This project provides a backend server to remotely control a CesiumJS 3D globe instance and capture rendered frames. It uses a Flask-SocketIO server for real-time, bidirectional communication and a simple RESTful API for control.

This system is ideal for applications requiring automated scene generation, data collection, and simulation in a geospatial context.

-----

## ✨ Features

  * **Remote Scene Control:** Programmatically set the camera's position, orientation, and field of view.
  * **Dynamic Overlays:** Draw 3D polygons and other shapes on the globe via API calls.
  * **Frame Capture:** Request and receive high-resolution screenshots from the CesiumJS client in various formats (PNG, JPG, raw pixels).
  * **Asynchronous Architecture:** Built with Flask, SocketIO, and Eventlet for efficient, non-blocking I/O.
  * **Data API:** Includes endpoints to serve pre-configured geospatial data, such as airport and runway coordinates.

-----

## 🔧 Installation

To get the project running locally, follow these steps.

1.  **Clone the Repository**

    ```bash
    git clone <your-repository-url>
    cd <your-repository-name>
    ```

2.  **Create a Virtual Environment**
    It's highly recommended to use a virtual environment to manage dependencies.

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install Dependencies**
    The required Python packages are listed in `requirements.txt`.

    ```bash
    pip install -r requirements.txt
    ```

-----

## ⚙️ Configuration

The application is configured using environment variables. Create a `.env` file in the project root and add the following keys:

```.env
# Server configuration
HOST="0.0.0.0"
PORT="8082"

# Path to the airport data file
DATABASE_FILEPATH="data/cesium_arcgis_db.json"
```

The server and client scripts will automatically load these variables.

## 🔑 Cesium Ion Setup

Before running the client, you must configure your **Cesium Ion Access Token** to load 3D tilesets and terrain data properly.

1. Get a free token from [Cesium Ion](https://ion.cesium.com/).
2. Open your client JavaScript file (e.g., `script.js`).
3. Replace `'YOUR_CESIUM_ION_TOKEN_HERE'` in the `config` object with your actual token:


```const config = {
    IP: 'localhost:8082',  // Server IP and port
    CESIUM_ION_TOKEN: 'YOUR_CESIUM_ION_TOKEN_HERE',  // Replace with your actual Cesium Ion access token
};
```

-----

## 🎮 Usage

The system consists of two main components: the server and the client.

1.  **Start the Server**
    Run the main Flask application. This will start the web server and wait for both HTTP requests and SocketIO connections.

    ```bash
    python app.py
    ```

    You should see output indicating the server is running on `http://0.0.0.0:8082`.

2.  **Open the CesiumJS Client**
    Navigate to `http://localhost:8082` in your web browser. This will load the `index.html` page containing the CesiumJS globe, which will automatically connect to the SocketIO server.

3.  **Run the Python Client Script**
    To control the scene and capture frames, run the client script in a separate terminal.

    ```bash
    python client.py
    ```

    This script will make API calls to the server, which then relays commands to the browser client and returns the captured image.

-----

## 📄 API Endpoints

The server exposes several HTTP endpoints to control the CesiumJS client.

| Method | Endpoint                    | Description                                                                                              |
| :----- | :-------------------------- | :------------------------------------------------------------------------------------------------------- |
| `POST` | `/set_and_get`              | **Primary endpoint.** Sets the scene (camera, drawings, etc.) and waits for the client to return a frame. |
| `POST` | `/set`                      | "Fire-and-forget" endpoint to update the view without waiting for a frame.                               |
| `POST` | `/draw`                     | Sends drawing commands (e.g., polygons) to be rendered on the globe.                                     |
| `POST` | `/set_terrain_and_imagery`  | Changes the active terrain or imagery layer on the client.                                               |
| `GET`  | `/get_airports`             | Returns a list of all available airports from the database.                                              |
| `POST` | `/get_runways`              | Returns a list of runways for a specified airport.                                                       |
| `POST` | `/get_runway_corners`       | Returns the geographic coordinates of a specific runway's corners.                                       |

-----

## 📄 Licensing & Commercial Usage

This repository is licensed under the **PolyForm Noncommercial License 1.0.0**. 

* **Academic & Research Use:** Completely free for academic, personal, and non-commercial scientific research.
* **Commercial Use:** The standard license explicitly prohibits commercial deployment, integration into paid products, or use within enterprise production workflows.

### 💼 Commercial Licensing Options

If you represent a commercial entity and wish to:
* Integrate **LARD - CesiumSim** into a commercial product or service
* Use this software for internal enterprise operations
* Obtain custom modifications, specialized support, or alternate licensing terms

A **separate commercial license** is required. 

Please reach out to discuss licensing terms and tailored integration options:

📧 **Contact:** `thierry.sammour-sawaya@airbus.com`  
💼 **Subject Line:** `[Commercial License Request] LARD - CesiumSim`

---
*Note: Third-party dependencies such as **CesiumJS** remain governed by their respective licenses (e.g., Apache 2.0).*
