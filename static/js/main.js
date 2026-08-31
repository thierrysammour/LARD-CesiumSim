"use strict";


const config = {
    IP: 'localhost:8082',  // Server IP and port
    CESIUM_ION_TOKEN: 'YOUR_CESIUM_ION_TOKEN_HERE',  // Replace with your actual Cesium Ion access token

};

class CesiumSim {
    constructor(config) {
        this.config = config;

        // 2. State is initialized inside the class
        this.viewer = null;
        this.socket = null;
        this.google_primitive = null;
        this.postProcessStage = null;
        this.objects_primitive = [];
        this.drawings_primitive = [];

        this.init();
    }

    //==========================================================================
    // INITIALIZATION
    //==========================================================================

    init() {

        Cesium.Ion.defaultAccessToken = this.config.CESIUM_ION_TOKEN;
        this.socket = io(`ws://${this.config.IP}`, { forceBase64: true });

        $('#cesiumContainer, #cesiumContainerOverlay').width(1920).height(1080);

        this.viewer = new Cesium.Viewer("cesiumContainer", {
            timeline: false, animation: false, shadows: false,
            baseLayerPicker: true,
            baseLayer: Cesium.ImageryLayer.fromProviderAsync(
                Cesium.ArcGisMapServerImageryProvider.fromBasemapType(Cesium.ArcGisBaseMapType.SATELLITE)
            ),
        });


        this.viewer.scene.globe.enableLighting = true;
        this.viewer.scene.highDynamicRange = true;
        this.viewer.scene.fog.enabled = false;
        this.viewer.scene.globe.showWaterEffect = false;
        this.viewer.scene.globe.showGroundAtmosphere = false;
        this.viewer.scene.globe.tileCacheSize = 500;
        this.viewer.scene.globe.depthTestAgainstTerrain = true;

        this.load_3d_tiles();
        this.setupEventListeners();

    }

    async load_3d_tiles() {
        try {
            const google3d_tileset = await Cesium.createGooglePhotorealistic3DTileset();
            this.google_primitive = this.viewer.scene.primitives.add(google3d_tileset);
            this.google_primitive.show = false;
        } catch (error) {
            console.log(`Error loading Photorealistic 3D Tiles tileset.\n${error}`);
        }
    }

    //==========================================================================
    // CORE LOGIC & VIEW METHODS
    //==========================================================================


    async set_terrain(data) {
        if (!this.viewer || !this.viewer.scene) {
            console.error('Viewer not initialized');
            return;
        }

        const providerType = data?.providerType || "ellipsoid";
        const options = data?.options || {};
        const requestVertexNormals = options.requestVertexNormals ?? true;
        const requestWaterMask = options.requestWaterMask ?? true;

        let terrain;

        switch (providerType) {
            case "world": {
                terrain = await Cesium.Terrain.fromWorldTerrain({
                    requestVertexNormals,
                    requestWaterMask,
                });
                break;
            }

            case "arcgis": {
                const arcgisProvider = Cesium.ArcGISTiledElevationTerrainProvider.fromUrl(
                    "https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer"
                );
                terrain = new Cesium.Terrain(arcgisProvider);
                break;
            }

            case "ellipsoid":
                default: {
                // Wrap EllipsoidTerrainProvider with Cesium.Terrain
                const ellipsoidProvider = new Cesium.EllipsoidTerrainProvider();
                terrain = new Cesium.Terrain(ellipsoidProvider);
                break;
            };
        };

        this.viewer.scene.setTerrain(terrain);
    }

    async set_imagery_provider(data) {
        if (!this.viewer || !data?.providerType) {
            console.error('Viewer not initialized or missing providerType');
            return;
        }

        let provider;
        const providerType = data.providerType;

        switch (providerType) {
            // case 'BingMaps': {
            // // Internal API key (do NOT expose to user input)
            // const BING_MAPS_API_KEY = "Your_Hardcoded_Bing_Maps_API_Key";

            // // Convert string mapStyle to Cesium.BingMapsStyle
            // const mapStyleMap = {
            //     AERIAL: Cesium.BingMapsStyle.AERIAL,
            //     ROAD: Cesium.BingMapsStyle.ROAD,
            //     AERIAL_WITH_LABELS: Cesium.BingMapsStyle.AERIAL_WITH_LABELS
            // };

            // const mapStyle = mapStyleMap[data.mapStyle?.toUpperCase()] || Cesium.BingMapsStyle.AERIAL;

            // provider = new Cesium.BingMapsImageryProvider({
            //     url: 'https://dev.virtualearth.net',
            //     // key: BING_MAPS_API_KEY,
            //     // mapStyle: mapStyle
            // });
            // break;
            // }
            case 'OpenStreetMap':
            provider = new Cesium.OpenStreetMapImageryProvider({
                url: data.url || 'https://a.tile.openstreetmap.org/',
            });
            break;

            case 'ArcGIS':
            provider = Cesium.ArcGisMapServerImageryProvider.fromBasemapType(Cesium.ArcGisBaseMapType.SATELLITE);
            break;

            default:
            console.error('Unsupported imagery provider:', providerType);
            return;
        }

        this.viewer.imageryLayers.removeAll();

        // Add imagery layer asynchronously, waiting for it to be ready
        const imageryLayer = await Cesium.ImageryLayer.fromProviderAsync(provider);
        this.viewer.imageryLayers.add(imageryLayer);
    }

    async set_view(data) {
        if ('drawings' in data) await this.draw(data);

        const layer = data.environment.layer;
        const isGoogle3d = layer === "google3d";
        const isMask = layer === "mask";

        if (this.google_primitive) this.google_primitive.show = isGoogle3d;
        this.viewer.scene.globe.show = !isGoogle3d;


        // Handle sky appearance
        if (isMask) {
            // Disable all atmospheric/sky elements
            this.viewer.scene.skyAtmosphere.show = false;
            this.viewer.scene.skyBox.show = false;
            this.viewer.scene.sun.show = false;
            this.viewer.scene.moon.show = false;
        } else {
            // Enable sky elements for other layers
            this.viewer.scene.skyAtmosphere.show = true;
            this.viewer.scene.skyBox.show = true;
            this.viewer.scene.sun.show = true;
            this.viewer.scene.moon.show = true;

            // Reset background to transparent or black
            this.viewer.scene.backgroundColor = Cesium.Color.TRANSPARENT;
        }


        // Handle globe material based on layer and optional custom color
        if (isMask) {
            // Use custom color if provided, otherwise black
            let globeColor = Cesium.Color.BLACK;
            this.viewer.scene.globe.material = new Cesium.Material({
                fabric: {
                    type: 'Color',
                    uniforms: {
                        color: globeColor
                    }
                }
            });
        } else {
                this.viewer.scene.globe.material = undefined; // fallback to default globe
        }

        this.viewer.scene.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(
                data.camera.coordinates.longitude_deg, data.camera.coordinates.latitude_deg, data.camera.coordinates.altitude_m,
            ),
            orientation: {
                heading: Cesium.Math.toRadians(data.camera.attitude.heading_deg),
                pitch: Cesium.Math.toRadians(data.camera.attitude.pitch_deg),
                roll: Cesium.Math.toRadians(data.camera.attitude.roll_deg),
            }
        });

        data.camera.position = this.viewer.scene.camera.position;
        data.camera.direction = this.viewer.scene.camera.direction;
        data.camera.matrix = this.viewer.scene.camera.viewMatrix;

        this.viewer.camera.frustum.near = 0.1;
        this.viewer.camera.frustum.fov = Cesium.Math.toRadians(data.camera.fov_horizontal_deg);
        this.viewer.camera.frustum.aspectRatio = data.camera.fov_horizontal_deg / data.camera.fov_vertical_deg;

        ['brightness', 'contrast', 'hue', 'saturation', 'gamma'].forEach(param => {
            if (param in data.camera) {
                for (let i = 0; i < this.viewer.imageryLayers.length; i++) {
                    this.viewer.imageryLayers.get(i)[param] = parseFloat(data.camera[param]);
                }
            }
        });

        $('#cesiumContainer, #cesiumContainerOverlay').width(data.camera.width_px).height(data.camera.height_px);

        let date = data.daytime.timestamp || `${data.daytime.year}-${String(data.daytime.month).padStart(2, '0')}-${String(data.daytime.day).padStart(2, '0')}T${String(data.daytime.hour).padStart(2, '0')}:${String(data.daytime.minute).padStart(2, '0')}:${String(data.daytime.second).padStart(2, '0')}`;
        this.viewer.clockViewModel.currentTime = Cesium.JulianDate.fromIso8601(date);

        this.viewer.render();
        return data;
    }

    async get_view(data, fn) {
        if (data.environment.layer !== "mask" && !this.viewer.scene.globe.tilesLoaded) await this.blockUntilTilesLoaded();

        let tempCanvas = this.viewer.canvas;
        if (data.camera.crop_xywh_px || (data.camera.crop_width_resize_px && data.camera.crop_height_resize_px)) {
            tempCanvas = document.getElementById('temp_canvas');
            const ctx3 = tempCanvas.getContext('2d');
            let [x, y, w, h] = data.camera.crop_xywh_px || [0, 0, this.viewer.canvas.width, this.viewer.canvas.height];
            tempCanvas.width = data.camera.crop_width_resize_px || w;
            tempCanvas.height = data.camera.crop_height_resize_px || h;
            ctx3.drawImage(this.viewer.scene.canvas, x, y, w, h, 0, 0, tempCanvas.width, tempCanvas.height);
        };

        if (data.frame.download) {
            const link = document.createElement('a');
            link.download = data.id + data.frame.file_extension;
            tempCanvas.toBlob(blob => {
                link.href = URL.createObjectURL(blob);
                link.click();
                URL.revokeObjectURL(link.href);
            });
            link.remove();
        };

        if (data.frame.get || data.frame.save) {
            // Normalize file extension
            let ext = data.frame.file_extension?.toLowerCase();

            // If no extension provided, fallback to ".jpg"
            if (!ext || typeof ext !== "string" || ext.trim() === "") {
                ext = ".jpg";
            }

            // Ensure extension starts with a dot
            if (!ext.startsWith(".")) {
                ext = "." + ext;
            }

            // Handle raw uncompressed RGBA buffer
            if (ext === ".raw") {

                const gl = this.viewer.scene.context._gl;
                const pixels = new Uint8Array(tempCanvas.width * tempCanvas.height * 4);
                gl.readPixels(0, 0, tempCanvas.width, tempCanvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

                function uint8ToBase64(u8Arr) {
                    const CHUNK_SIZE = 0x8000; // 32k chunks
                    let index = 0;
                    const length = u8Arr.length;
                    let result = '';
                    let slice;
                    while (index < length) {
                        slice = u8Arr.subarray(index, Math.min(index + CHUNK_SIZE, length));
                        result += String.fromCharCode.apply(null, slice);
                        index += CHUNK_SIZE;
                    }
                    return btoa(result);
                }

                this.socket.emit("frame", {
                    sid: data.sid,
                    id: data.id,
                    get: data.frame.get,
                    save: data.frame.save,
                    frame: uint8ToBase64(pixels),  // Raw RGBA buffer (ArrayBuffer)
                    width: tempCanvas.width,
                    height: tempCanvas.height,
                    save_folder_path: data.frame.save_folder_path,
                    file_extension: ext
                });
            } else {
                // Map file extension to MIME type
                let mimeType;
                switch (ext) {
                    case ".png":
                        mimeType = "image/png";
                        break;
                    case ".webp":
                        mimeType = "image/webp";
                        break;
                    case ".bmp":
                        mimeType = "image/bmp";
                        break;
                    case ".jpeg":
                    case ".jpg":
                    default:
                        mimeType = "image/jpeg";
                        break;
                }

                // Only JPEG/WebP support quality settings
                const quality = (mimeType === "image/jpeg" || mimeType === "image/webp") ? 0.95 : undefined;

                tempCanvas.toBlob((blob) => {
                    this.socket.emit("frame", {
                        sid: data.sid,
                        id: data.id,
                        get: data.frame.get,
                        save: data.frame.save,
                        frame: blob,
                        width: tempCanvas.width,
                        height: tempCanvas.height,
                        save_folder_path: data.frame.save_folder_path,
                        file_extension: ext
                    });
                }, mimeType, quality);
            }

        } else {
            this.socket.emit("frame", { sid: data.sid });
        };

        if ('landmarks' in data) {
            for (const landmarkGroup of Object.values(data.landmarks)) {
                for (const item of Object.values(landmarkGroup)) {
                    if ('coordinates' in item) {

                        item.coordinates.altitude_m = await this.getCurrentPosition(item);
                        const final_position = Cesium.Cartesian3.fromDegrees(item.coordinates.longitude_deg, item.coordinates.latitude_deg, item.coordinates.altitude_m)
                        item.cartesian = { x_m: final_position.x, y_m: final_position.y, z_m: final_position.z };

                        if(this.isPointInCameraFov(this.viewer.scene, final_position)) {
                            const pixels = Cesium.SceneTransforms.worldToWindowCoordinates(this.viewer.scene, final_position);
                            if (pixels) {
                                item.pixels = { x_px: pixels.x, y_px: pixels.y };
                            } else {
                                item.pixels = { x_px: null, y_px: null };     
                            }
                        } else {
                            item.pixels = { x_px: null, y_px: null }; 
                        }

                    } else if ('pixels' in item) {
                        const ray = this.viewer.scene.camera.getPickRay({
                            x: item.pixels.x_px,
                            y: item.pixels.y_px
                        });
                        if (ray) {
                            const cartesianPosition = this.viewer.scene.globe.pick(ray, this.viewer.scene);
                            if (cartesianPosition) {
                                item.cartesian = { x_m: cartesianPosition.x, y_m: cartesianPosition.y, z_m: cartesianPosition.z };
                                const cartographic = Cesium.Cartographic.fromCartesian(cartesianPosition);
                                item.coordinates = {
                                    latitude_deg: Cesium.Math.toDegrees(cartographic.latitude),
                                    longitude_deg: Cesium.Math.toDegrees(cartographic.longitude),
                                    altitude_m: cartographic.height
                                };
                            }
                        }
                    }
                }
            }
        };

        fn(data);
    }

    async draw(data) {
        if (data.drawings) {

            const findDrawingByName = (name) => this.drawings_primitive.find(e => e.name === name);

            this.drawings_primitive.forEach(drawing => {
                if (!(drawing.name in data.drawings)) {
                    this.viewer.entities.remove(drawing);
                }
            });
            this.drawings_primitive = this.drawings_primitive.filter(drawing => drawing.name in data.drawings);

            for (const [key, drawing] of Object.entries(data.drawings)) {
                let existing_drawing = findDrawingByName(key);
                if (existing_drawing) {
                    existing_drawing.polygon.material = new Cesium.Color(...drawing.color_rgba)
                } else {
                    if (drawing.type === "polygon3d") {
                        let geometry = Object.values(drawing.points).flatMap(p => [p.longitude_deg, p.latitude_deg]);
                        if (geometry.length < 6) continue;
                        let drawing_entity = this.viewer.entities.add({
                            name: key,
                            polygon: {
                                hierarchy: Cesium.Cartesian3.fromDegreesArray(geometry),
                                material: new Cesium.Color(...drawing.color_rgba),
                            },
                        });
                        this.drawings_primitive.push(drawing_entity);
                    }
                }
            }
            this.viewer.render();
        }
    }

    //==========================================================================
    // EVENT LISTENERS & UI HANDLERS
    //==========================================================================

    setupEventListeners() {
        // Socket Listeners
        this.socket.on('set_terrain_and_imagery', async (data) => {
            if (data.terrain) {
                await this.set_terrain(data.terrain);
            }
            if (data.imagery) {
                await this.set_imagery_provider(data.imagery);
            }
        });
        this.socket.on('get_view', async (data, fn) => this.get_view(data, fn));
        this.socket.on('set_view', async (data) => await this.set_view(data));
        this.socket.on('set_and_get_view', async (data, fn) => {
            await this.set_view(data);
            this.get_view(data, fn);
        });
        this.socket.on('draw', (data) => this.draw(data));
    }

    //==========================================================================
    // ASYNC HELPERS & SERVER COMMUNICATION
    //==========================================================================

    blockUntilTilesLoaded() {
        return new Promise(resolve => {
            if (this.viewer.scene.globe.tilesLoaded) return resolve();
            const removeListener = this.viewer.scene.globe.tileLoadProgressEvent.addEventListener(() => {
                if (this.viewer.scene.globe.tilesLoaded) { removeListener(); resolve(); }
            });
        });
    }

    secondsToHHMMSS(totalSeconds) {
        const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
        const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
        const seconds = String(Math.floor(totalSeconds % 60)).padStart(2, '0');
        return [hours, minutes, seconds];
    }

    isPointInCameraFov(scene, pointCartesian) {
    const camera = scene.camera;

    const pointInEyeCoords = Cesium.Matrix4.multiplyByPoint(
        camera.viewMatrix,
        pointCartesian,
        new Cesium.Cartesian3()
    );

    if (pointInEyeCoords.z >= 0) {
        return false;
    }

    const frustum = camera.frustum;

    if (frustum instanceof Cesium.PerspectiveFrustum) {
        const fovVertical = frustum.fovy;
        const aspectRatio = frustum.aspectRatio;
        const fovHorizontal = 2 * Math.atan(Math.tan(fovVertical / 2) * aspectRatio);

        const x = pointInEyeCoords.x;
        const y = pointInEyeCoords.y;
        const z = -pointInEyeCoords.z;

        const angleX = Math.atan(Math.abs(x / z));
        const angleY = Math.atan(Math.abs(y / z));

        return angleX <= fovHorizontal / 2 && angleY <= fovVertical / 2;

    } else if (frustum instanceof Cesium.OrthographicFrustum) {
        return (
        pointInEyeCoords.x >= frustum.left &&
        pointInEyeCoords.x <= frustum.right &&
        pointInEyeCoords.y >= frustum.bottom &&
        pointInEyeCoords.y <= frustum.top &&
        -pointInEyeCoords.z >= frustum.near &&
        -pointInEyeCoords.z <= frustum.far
        );
    }

    return false;
    }

    async getCurrentPosition(item) {
        const lon = item.coordinates.longitude_deg;
        const lat = item.coordinates.latitude_deg;
        // Use a strict check for null or undefined
        const hasAltitude = item.coordinates.altitude_m != null;

        let height;

        if (hasAltitude) {
            // --- PATH 1: Use the altitude provided in the item object. ---
            height = item.coordinates.altitude_m;
            // console.log(`Using provided altitude: ${height}m`);
            return height;
        } else {
            // --- PATH 2: No altitude provided, so sample the terrain. ---
            // console.log("No altitude provided. Sampling terrain to find height...");
            const positions = [Cesium.Cartographic.fromDegrees(lon, lat)];
            
            try {
                // `await` pauses the function until the terrain data is fetched.
                const updatedPositions = await Cesium.sampleTerrainMostDetailed(
                    this.viewer.terrainProvider,
                    positions
                );
                // Use optional chaining and a nullish coalescing operator for safety.
                height = updatedPositions[0]?.height ?? 0;
                // console.log(`Successfully sampled terrain height: ${height.toFixed(2)}m`);
                return height;
            } catch(error) {
                console.error("Terrain sampling failed:", error);
                // Fallback to 0 if the terrain provider fails for any reason.
                return 0;
            }
        }
    }
        
} 


window.onload = () => {
    const app = new CesiumSim(config);
};