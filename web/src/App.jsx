import React, { useState, useEffect } from 'react';
import DisasterMapViewer from './components/viewer/DisasterMapViewer';
import Timeline from './components/timeline/Timeline';
import WaypointList from './components/ui/WaypointList';
import StatsPanel from './components/ui/StatsPanel';
import CameraControls from './components/navigation/CameraControls';

/**
 * Main App Component - Disaster Map 3D Viewer
 * Integrates all components for a complete disaster mapping visualization
 */
function App() {
  // Load trajectory and waypoint data
  const [trajectoryData, setTrajectoryData] = useState(null);
  const [waypointsData, setWaypointsData] = useState(null);
  
  // Viewer state
  const [fps, setFps] = useState(60);
  const [latency, setLatency] = useState(0);
  const [memoryUsage, setMemoryUsage] = useState(0);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);
  
  // Playback controls
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [autoRotate, setAutoRotate] = useState(false);

  useEffect(() => {
    // Load trajectory data from demo files
    loadTrajectoryData();
    loadWaypointsData();
    
    // Set up performance monitoring
    setupPerformanceMonitoring();
  }, []);

  /**
   * Load trajectory JSON file
   */
  const loadTrajectoryData = async () => {
    try {
      const response = await fetch(
        '/data/trajectory.json'
      );
      const data = await response.json();
      
      // Set default demo data if loading fails
      setTrajectoryData({
        metadata: {
          video_path: 'test_data/videos/mixkit-aerial-footage-of-historical-lithuanian-village-48396-hd-ready.mp4',
          algorithm: 'orb_slam2',
          generated_at: new Date().toISOString(),
          total_frames: 150,
        },
        poses: data.poses || [
          { frame: 0, timestamp: 0.0, position: [50.9934, 49.7235, 100.6477] },
          { frame: 1, timestamp: 0.0333, position: [50.1984, 53.6918, 100.5674] },
          // ... more poses would be loaded here
        ],
      });
    } catch (error) {
      console.warn('Failed to load trajectory data:', error);
      
      setTrajectoryData({
        metadata: { total_frames: 150, frameIntervalMs: 100 },
        poses: Array.from({ length: 150 }, (_, i) => ({
          frame: i,
          timestamp: i * 0.0333,
          position: [
            50 + Math.sin(i * 0.1) * 20,
            49 + Math.cos(i * 0.1) * 20,
            95 + Math.random() * 10,
          ],
        })),
      });
    }
  };

  /**
   * Load waypoints JSON file
   */
  const loadWaypointsData = async () => {
    try {
      const response = await fetch(
        '/data/rescue_waypoints.json'
      );
      const data = await response.json();
      
      // Set default demo data if loading fails
      setWaypointsData({
        scenario: 'search_and_rescue',
        metadata: { generated_at: new Date().toISOString() },
        waypoints: [
          { name: 'Start Point', position: [50.9934, 49.7235, 100.6477], action: 'deploy' },
          { name: 'Search Zone A', position: [35, 45, 95], action: 'scan' },
          { name: 'Search Zone B', position: [65, 75, 85], action: 'scan' },
          { name: 'Evacuation Route', position: [100, 30, 70], action: 'mark_safe' },
          { name: 'Rescue Point Alpha', position: [45, 20, 60], action: 'deploy_team' },
        ],
      });
    } catch (error) {
      console.warn('Failed to load waypoints data:', error);
      
      setWaypointsData({
        scenario: 'search_and_rescue',
        waypoints: [
          { name: 'Start Point', position: [50.9934, 49.7235, 100.6477], action: 'deploy' },
          { name: 'Search Zone A', position: [35, 45, 95], action: 'scan' },
        ],
      });
    }
  };

  /**
   * Set up performance monitoring
   */
  const setupPerformanceMonitoring = () => {
    // Monitor FPS using requestAnimationFrame
    let frameCount = 0;
    let lastTime = performance.now();
    
    const monitorFPS = () => {
      frameCount++;
      
      const currentTime = performance.now();
      if (currentTime - lastTime >= 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastTime = currentTime;
      }
      
      requestAnimationFrame(monitorFPS);
    };
    
    monitorFPS();

    // Monitor memory usage periodically
    const monitorMemory = setInterval(() => {
      try {
        if (performance.memory) {
          setMemoryUsage(performance.memory.usedJSHeapSize / 1024 / 1024);
        }
      } catch (error) {
        // Memory API not available in all browsers
      }
    }, 500);

    return () => {
      clearInterval(monitorMemory);
    };
  };

  /**
   * Handle frame change from timeline
   */
  const handleFrameChange = (frameIndex) => {
    setCurrentFrame(frameIndex);
    setTotalFrames(trajectoryData?.poses.length || 0);
  };

  /**
   * Handle playback speed change
   */
  const handlePlaybackSpeedChange = (speed) => {
    setPlaybackSpeed(speed);
  };

  // Calculate point cloud URL for demo data
  const pointCloudUrl = '/data/disaster_zone.ply';

  return (
    <div style={{ 
      width: '100vw', 
      height: '100vh', 
      backgroundColor: '#0a0a15',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      overflow: 'hidden',
    }}>
      {/* Header with Controls */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'stretch',
      }}>
        {/* Left Panel - Camera Controls */}
        <CameraControls 
          autoRotate={autoRotate}
          onAutoRotateChange={setAutoRotate}
          snapToWaypoint={false}
        />

        {/* Center - Timeline Navigation */}
        <Timeline 
          trajectoryData={trajectoryData}
          currentFrame={currentFrame}
          totalFrames={totalFrames}
          isPlaying={isPlaying}
          onFrameChange={handleFrameChange}
          onPlaybackSpeedChange={handlePlaybackSpeedChange}
          playRate={playbackSpeed}
        />

        {/* Right Panel - Waypoints & Stats */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <WaypointList waypointsData={waypointsData} />
          <StatsPanel 
            fps={fps}
            latency={latency}
            memoryUsage={memoryUsage}
            currentFrame={currentFrame}
            totalFrames={totalFrames}
            isPlaying={isPlaying}
          />
        </div>
      </div>

      {/* Main 3D Viewer */}
      <DisasterMapViewer 
        trajectoryData={trajectoryData}
        waypointsData={waypointsData}
        pointCloudUrl={pointCloudUrl}
        onStatsUpdate={(stats) => {
          setCurrentFrame(stats.currentFrame);
          setTotalFrames(stats.totalFrames);
        }}
      />

      {/* Legend Overlay */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        right: '20px',
        padding: '15px',
        backgroundColor: 'rgba(26, 26, 46, 0.9)',
        borderRadius: '8px',
        color: '#ccc',
        fontSize: '13px',
        zIndex: 1000,
      }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#fff' }}>🗺️ Legend</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <LegendItem 
            icon="📍" 
            label="Waypoints" 
            color="#FFD700" 
            description="Rescue points and objectives"
          />
          <LegendItem 
            icon="🔴" 
            label="Trajectory Path" 
            color="#E74C3C" 
            description="Camera movement path"
          />
          <LegendItem 
            icon="📊" 
            label="Point Cloud" 
            color="#3498DB" 
            description="Disaster zone terrain data"
          />
        </div>

        {/* Performance Summary */}
        <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #333' }}>
          <p style={{ margin: 0, fontSize: '12px', color: '#888' }}>
            <strong>Performance:</strong> {fps.toFixed(0)} FPS | 
            Latency: {latency.toFixed(1)}ms | 
            Memory: {(memoryUsage / 1024).toFixed(2)} GB
          </p>
        </div>
      </div>

      {/* Info Overlay */}
      <div style={{
        position: 'absolute',
        top: '20px',
        left: '20px',
        padding: '15px',
        backgroundColor: 'rgba(26, 26, 46, 0.9)',
        borderRadius: '8px',
        color: '#ccc',
        fontSize: '13px',
        zIndex: 1000,
      }}>
        <h4 style={{ margin: '0 0 8px 0', color: '#fff' }}>🚁 Disaster Map Viewer</h4>
        <p style={{ margin: 0, fontSize: '12px', lineHeight: '1.6' }}>
          <strong>Data:</strong> {trajectoryData?.metadata?.algorithm || 'ORB-SLAM2'}<br />
          <strong>Frames:</strong> {currentFrame + 1} / {totalFrames}<br />
          <strong>Mode:</strong> {autoRotate ? 'Auto-Rotate' : 'Manual Navigation'}
        </p>

        {/* Quick Actions */}
        <div style={{ marginTop: '10px', display: 'flex', gap: '5px' }}>
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              padding: '6px 12px',
              backgroundColor: isPlaying ? '#e74c3c' : '#2ecc71',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>

          <button 
            onClick={() => setAutoRotate(!autoRotate)}
            style={{
              padding: '6px 12px',
              backgroundColor: autoRotate ? '#3498db' : '#2c3e50',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            {autoRotate ? '🔄 Auto-Rotate' : '⏹ Stop Rotate'}
          </button>

          <button 
            onClick={() => {
              const viewer = window.viewerRef;
              if (viewer) {
                viewer.camera.flyTo({
                  destination: Cesium.Cartesian3.fromDegrees(
                    trajectoryData?.poses[0]?.position[0] || 50,
                    trajectoryData?.poses[0]?.position[1] || 49,
                    120
                  ),
                });
              }
            }}
            style={{
              padding: '6px 12px',
              backgroundColor: '#f39c12',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            🏠 Home
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Legend Item Component for overlay legend
 */
function LegendItem({ icon, label, color, description }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ 
        fontSize: '16px', 
        filter: `drop-shadow(0 0 2px ${color})`,
      }}>{icon}</span>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ color: '#fff', fontWeight: '500' }}>{label}</span>
        <span style={{ fontSize: '11px', color: '#888' }}>{description}</span>
      </div>
    </div>
  );
}

export default App;
