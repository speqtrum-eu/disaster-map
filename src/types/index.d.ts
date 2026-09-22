/**
 * Disaster Map System - Type Definitions
 * 
 * Comprehensive type definitions for TypeScript/JavaScript development.
 */

// ============================================================================
// Core Types
// ============================================================================

/** Camera pose data with position and orientation */
export interface Pose3D {
  /** Position in meters [x, y, z] */
  position: Vector3;
  
  /** Orientation as quaternion [qx, qy, qz, qw] */
  orientation: Quaternion;
  
  /** Timestamp of pose estimate */
  timestamp: number;
  
  /** Confidence score (0.0 - 1.0) */
  confidence?: number;
}

/** 3D vector type */
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

/** Quaternion for rotation representation */
export interface Quaternion {
  qx: number;
  qy: number;
  qz: number;
  qw: number;
}

// ============================================================================
// Frame Types
// ============================================================================

/** Video frame data structure */
export interface FrameData {
  /** Unique frame identifier */
  id: string;
  
  /** Timestamp in milliseconds since epoch */
  timestamp: number;
  
  /** Sequential frame number */
  frameNumber: number;
  
  /** Image dimensions */
  dimensions: FrameDimensions;
  
  /** Associated pose estimate (if available) */
  pose?: Pose3D;
  
  /** Metadata from camera/sensor */
  metadata?: FrameMetadata;
}

/** Frame image dimensions */
export interface FrameDimensions {
  width: number;
  height: number;
}

/** Camera and sensor metadata */
export interface FrameMetadata {
  /** Camera identifier */
  cameraId?: string;
  
  /** Exposure time in milliseconds */
  exposureMs?: number;
  
  /** ISO sensitivity */
  iso?: number;
  
  /** Focal length in millimeters */
  focalLengthMm?: number;
  
  /** Sensor temperature in Celsius */
  sensorTemperatureCelsius?: number;
}

// ============================================================================
// Map Types
// ============================================================================

/** Point cloud point data */
export interface Point {
  /** X coordinate in meters */
  x: number;
  
  /** Y coordinate in meters */
  y: number;
  
  /** Z coordinate (height) in meters */
  z: number;
  
  /** RGB color values [0.0 - 1.0] */
  color?: Vector3;
  
  /** Intensity value for LiDAR data */
  intensity?: number;
  
  /** Return number for multi-return scans */
  returnNumber?: number;
}

/** Point cloud map structure */
export interface PointCloudMap {
  /** Unique map identifier */
  id: string;
  
  /** Map name/description */
  name: string;
  
  /** Total point count */
  pointCount: number;
  
  /** Bounding box of the point cloud */
  boundingBox: BoundingBox;
  
  /** File size in bytes */
  fileSizeBytes: number;
  
  /** Upload/creation timestamp */
  createdAt: string;
  
  /** Associated trajectory ID */
  trajectoryId?: string;
}

/** Point cloud bounding box */
export interface BoundingBox {
  min: Vector3;
  max: Vector3;
}

// ============================================================================
// Trajectory Types
// ============================================================================

/** Camera trajectory data */
export interface Trajectory {
  /** Unique trajectory identifier */
  id: string;
  
  /** Associated map ID */
  mapId?: string;
  
  /** Array of pose estimates in order */
  poses: Pose3D[];
  
  /** Total distance traveled (meters) */
  totalDistanceMeters: number;
  
  /** Duration of trajectory (seconds) */
  durationSeconds: number;
  
  /** Average speed (m/s) */
  averageSpeedMs: number;
}

// ============================================================================
// Waypoint Types
// ============================================================================

/** Rescue waypoint for navigation */
export interface Waypoint {
  /** Unique waypoint identifier */
  id: string;
  
  /** Position coordinates */
  position: Vector3;
  
  /** Description or name */
  description?: string;
  
  /** Type of waypoint (rescue, hazard, landmark, etc.) */
  type: WaypointType;
  
  /** Priority level */
  priority: number;
  
  /** Associated mission ID */
  missionId?: string;
}

/** Waypoint classification types */
export type WaypointType = 
  | 'rescue'      // Rescue operation point
  | 'hazard'       // Hazard or danger zone
  | 'landmark'     // Notable landmark for navigation
  | 'checkpoint'   // Mission checkpoint
  | 'resource'     // Resource location (water, supplies)
  | 'evacuation'   // Evacuation point
  | 'command';     // Command center

// ============================================================================
// API Response Types
// ============================================================================

/** Generic API response wrapper */
export interface ApiResponse<T> {
  /** Success status */
  success: boolean;
  
  /** Data payload (if successful) */
  data?: T;
  
  /** Error details (if failed) */
  error?: ApiError;
}

/** API error structure */
export interface ApiError {
  /** Error code for programmatic handling */
  code: string;
  
  /** Human-readable error message */
  message: string;
  
  /** Additional error details */
  details?: Record<string, unknown>;
}

/** Health check response */
export interface HealthStatus {
  /** System health status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Timestamp of check */
  timestamp: string;
  
  /** Application version */
  version: string;
}

/** Performance metrics response */
export interface Metrics {
  /** Timestamp of measurement */
  timestamp: string;
  
  /** Current frames per second */
  fps: number;
  
  /** Average latency in milliseconds */
  latencyMs: number;
  
  /** Memory usage in megabytes */
  memoryMb: number;
  
  /** Number of active connections */
  activeConnections: number;
}

// ============================================================================
// WebSocket Types
// ============================================================================

/** WebSocket message types */
export type WebSocketMessageType = 
  | 'pose_update'
  | 'frame_ready'
  | 'map_updated'
  | 'error'
  | 'heartbeat';

/** Base WebSocket message structure */
export interface WebSocketMessage {
  /** Message type identifier */
  type: WebSocketMessageType;
  
  /** Timestamp of message */
  timestamp: number;
}

/** Pose update message */
export interface PoseUpdateMessage extends WebSocketMessage {
  type: 'pose_update';
  data: Pose3D;
}

/** Frame ready message */
export interface FrameReadyMessage extends WebSocketMessage {
  type: 'frame_ready';
  data: FrameData;
}

// ============================================================================
// Configuration Types
// ============================================================================

/** SLAM configuration options */
export interface SlamConfig {
  /** Feature detector to use */
  featureDetector: 'orb' | 'sift' | 'akaze';
  
  /** Number of features to detect per frame */
  maxFeatures: number;
  
  /** Keyframe interval (frames between keyframes) */
  keyframeInterval: number;
  
  /** Maximum map size in points */
  maxMapSize: number;
  
  /** Loop closure detection enabled */
  loopClosureEnabled: boolean;
}

/** Viewer configuration options */
export interface ViewerConfig {
  /** Point cloud rendering settings */
  pointCloud: PointCloudConfig;
  
  /** Camera controls settings */
  cameraControls: CameraControlsConfig;
  
  /** Timeline playback settings */
  timeline: TimelineConfig;
  
  /** Map overlay settings */
  mapOverlay?: boolean;
}

/** Point cloud rendering configuration */
export interface PointCloudConfig {
  /** Maximum points to render at once */
  maxPoints: number;
  
  /** Point size in pixels */
  pointSize: number;
  
  /** Enable LOD (Level of Detail) */
  enableLOD: boolean;
  
  /** Color mode for points */
  colorMode: 'rgb' | 'height' | 'intensity';
}

/** Camera controls configuration */
export interface CameraControlsConfig {
  /** Minimum zoom distance */
  minDistance: number;
  
  /** Maximum zoom distance */
  maxDistance: number;
  
  /** Enable orbit rotation */
  enableOrbit: boolean;
  
  /** Enable fly mode */
  enableFly: boolean;
}

/** Timeline playback configuration */
export interface TimelineConfig {
  /** Playback speed multiplier */
  playbackSpeed: number;
  
  /** Auto-play on load */
  autoPlay: boolean;
  
  /** Loop playback */
  loop: boolean;
}

// ============================================================================
// Utility Types
// ============================================================================

/** Optional value type */
export type Nullable<T> = T | null;

/** Readonly array type */
export type ReadonlyArray<T> = readonly T[];

/** Deep partial type for nested objects */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

/** Extract union type members */
export type UnionToIntersection<U> = 
  (U extends any ? (k: U) => void : never) extends 
  ((k: infer I) => void) ? I : never;

// ============================================================================
// Export all types for external use
// ============================================================================

export { Pose3D, Vector3, Quaternion };
export { FrameData, FrameDimensions, FrameMetadata };
export { Point, PointCloudMap, BoundingBox };
export { Trajectory };
export { Waypoint, WaypointType };
export { ApiResponse, ApiError, HealthStatus, Metrics };
export { WebSocketMessageType, WebSocketMessage, PoseUpdateMessage, FrameReadyMessage };
export { SlamConfig, ViewerConfig, PointCloudConfig, CameraControlsConfig, TimelineConfig };
