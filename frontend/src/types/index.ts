// Type definitions for the Disaster Map application

// ========== Stream Types ==========
export type StreamType = 'rtsp' | 'rtmp' | 'webrtc' | 'http' | 'file' | 'udp';
export type StreamStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'processing';

export interface StreamConfig {
  id: string;
  name: string;
  enabled: boolean;
  type: StreamType;
  url: string;
  resolution: [number, number];
  fps: number;
  bitrate: number;
  gps: boolean;
  gpsSource: 'embedded' | 'external' | 'manual' | 'none';
  externalGps?: {
    host: string;
    port: number;
    protocol: 'udp' | 'tcp';
  };
  altitude: number; // meters
  heading: number; // degrees
  tilt: number; // degrees
  calibration?: CameraCalibration;
  processing?: ProcessingConfig;
}

export interface VideoStream {
  config: StreamConfig;
  status: StreamStatus;
  frameCount: number;
  lastFrameTime: number;
  fpsActual: number;
  errorMessage: string;
}

// ========== GPS Types ==========
export interface GPSData {
  latitude: number;
  longitude: number;
  altitude: number;
  heading: number;
  tilt: number;
  roll: number;
  accuracy: number;
  timestamp: number;
  source: 'embedded' | 'external' | 'manual' | 'none';
}

// ========== Camera Types ==========
export interface CameraCalibration {
  fx: number;
  fy: number;
  cx: number;
  cy: number;
  width: number;
  height: number;
  distortion: [number, number, number, number, number];
}

// ========== Processing Types ==========
export interface ProcessingConfig {
  detector: 'SIFT' | 'SURF' | 'ORB' | 'AKAZE';
  minFeatures: number;
  matcher: 'FLANN' | 'BFMatcher';
  minMatches: number;
  ratioTest: number;
  stitchMethod: 'homography' | 'bundle_adjustment' | 'incremental';
  confidenceThreshold: number;
  reprojectionError: number;
  frameSkip: number;
  keyframeInterval: number;
  quality: 'high' | 'medium' | 'low';
  tileSize: number;
  overlap: number;
  resolution: number;
  coordinateSystem: string;
  targetSystem: string;
  useGpu: boolean;
  maxMemory: number;
  numWorkers: number;
}

// ========== Frame Types ==========
export interface Frame {
  id: string;
  streamId: string;
  timestamp: number;
  frameNumber: number;
  gps?: GPSData;
  calibration?: CameraCalibration;
  resolution: [number, number];
  status: 'raw' | 'processing' | 'processed' | 'failed';
}

// ========== Orthomosaic Types ==========
export interface OrthomosaicTile {
  id: string;
  x: number;
  y: number;
  z: number;
  timestamp: number;
  bounds: [number, number, number, number];
  sourceFrames: string[];
}

export interface Orthomosaic {
  id: string;
  timestamp: number;
  duration: number;
  frameCount: number;
  keyframeCount: number;
  resolution: [number, number];
  bounds: [number, number, number, number];
  gpsCenter: [number, number];
  tileCount: number;
  tiles: OrthomosaicTile[];
}

// ========== Map Viewer Types ==========
export interface MapViewport {
  center: [number, number];
  zoom: number;
  rotation: number;
  pitch: number;
}

export interface MapBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

// ========== Time Axis Types ==========
export interface TimeRange {
  start: number; // Unix timestamp
  end: number; // Unix timestamp
}

export interface TimelineMarker {
  id: string;
  timestamp: number;
  label: string;
  type: 'keyframe' | 'orthomosaic' | 'event';
}

// ========== API Types ==========
export interface APIStats {
  running: boolean;
  uptime: number;
  frameCount: number;
  keyframeCount: number;
  streams: Record<string, VideoStream>;
  orthoEngine?: any;
  tileManager?: any;
}

// ========== WebSocket Types ==========
export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: number;
}

export interface FrameUpdateMessage extends WebSocketMessage {
  type: 'frame_update';
  data: {
    id: string;
    streamId: string;
    timestamp: number;
    frameNumber: number;
    resolution: [number, number];
  };
}

export interface OrthomosaicUpdateMessage extends WebSocketMessage {
  type: 'orthomosaic_update';
  data: {
    timestamp: number;
    resolution: [number, number];
  };
}

export interface TileUpdateMessage extends WebSocketMessage {
  type: 'tile_update';
  data: {
    tileCount: number;
    tiles: Array<{
      x: number;
      y: number;
      z: number;
      timestamp: number;
    }>;
  };
}

export interface StatusUpdateMessage extends WebSocketMessage {
  type: 'status_update';
  data: APIStats;
}

// ========== UI State Types ==========
export interface AppState {
  // Map viewer
  viewport: MapViewport;
  selectedStream: string | null;
  showTimeAxis: boolean;
  
  // Time axis
  currentTime: number;
  playbackSpeed: number;
  isPlaying: boolean;
  
  // Streams
  streams: Record<string, VideoStream>;
  selectedStreamId: string | null;
  
  // Orthomosaic
  orthomosaic: Orthomosaic | null;
  tiles: Record<string, OrthomosaicTile>; // "z_x_y" -> tile
  
  // UI
  isLoading: boolean;
  error: string | null;
  
  // Connection
  isConnected: boolean;
  reconnectAttempts: number;
}

export interface AppActions {
  // Map viewer
  setViewport: (viewport: MapViewport) => void;
  setSelectedStream: (streamId: string | null) => void;
  toggleTimeAxis: () => void;
  
  // Time axis
  setCurrentTime: (timestamp: number) => void;
  setPlaybackSpeed: (speed: number) => void;
  togglePlayback: () => void;
  
  // Streams
  setStreams: (streams: Record<string, VideoStream>) => void;
  setSelectedStreamId: (streamId: string | null) => void;
  
  // Orthomosaic
  setOrthomosaic: (orthomosaic: Orthomosaic | null) => void;
  addTiles: (tiles: OrthomosaicTile[]) => void;
  
  // UI
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Connection
  setConnected: (connected: boolean) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;
}

// ========== Three.js Types ==========
export interface ThreeJSOrthomosaic {
  image: HTMLImageElement | null;
  width: number;
  height: number;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
}
