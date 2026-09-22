import React, { useEffect, useRef, useState } from 'react';
import Cesium from 'cesium';
import * as THREE from 'three';
import PointCloudTileProvider from '../../tile-provider/PointCloudTileProvider';
import Timeline from '../timeline/Timeline';
import WaypointList from '../ui/WaypointList';
import StatsPanel from '../ui/StatsPanel';
import CameraControls from '../navigation/CameraControls';

const { Viewer, OrbitControls, ScreenSpaceEventHelper } = Cesium;

/**
 * Main Disaster Map 3D Viewer Component
 * Loads point cloud data, displays trajectory, and provides navigation controls
 */
function DisasterMapViewer({ 
  trajectoryData, 
  waypointsData, 
  pointCloudUrl,
  onStatsUpdate 
}) {
  const viewerRef = useRef(null);
  const containerRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);

  useEffect(() => {
    if (!trajectoryData || !pointCloudUrl) return;

    // Initialize Cesium viewer
    const viewer = new Viewer(containerRef.current, {
      terrainProvider: undefined,
      baseLayerPicker: false,
      animation: false,
      timeline: true,
      geocoder: false,
      homeButton: false,
      navigationHelpButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: {
        showPlayPauseButton: true,
        showLoopButton: true,
        showSpeedControl: true,
        showTimeRangeSlider: true,
      },
    });

    viewerRef.current = viewer;

    // Set up scene
    const scene = viewer.scene;
    
    // Enable high dynamic range for better visualization
    scene.highDynamicRange = true;
    scene.globe.enableLighting = true;

    // Add point cloud tile provider (3D Tiles)
    let pointCloudLayer = null;
    if (pointCloudUrl) {
      try {
        const tileProvider = new PointCloudTileProvider(pointCloudUrl);
        pointCloudLayer = viewer.scene.primitives.add(tileProvider);
        
        // Set transparency for better visibility
        if (tileProvider.tileSet) {
          tileProvider.tileSet.show = true;
        }
      } catch (error) {
        console.warn('Failed to load point cloud:', error);
      }
    }

    // Add trajectory path line
    const trajectoryPositions = trajectoryData.poses.map(p => ({
      longitude: p.position[0],
      latitude: p.position[1],
      height: p.position[2] || 0,
    }));

    if (trajectoryPositions.length > 0) {
      const polyline = new Cesium.PolylineCollection({
        id: 'trajectory-path',
      });

      const positions = trajectoryPositions.map(pos => 
        Cesium.Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.height)
      );

      const material = new Cesium.PolylineMaterialProperty({
        color: Cesium.Color.RED.withAlpha(0.7),
        width: 5,
        dashLength: 10,
        gapLength: 3,
      });

      polyline.add({
        positions: positions,
        material: material,
        width: 8,
      });

      viewer.scene.primitives.add(polyline);
    }

    // Add waypoints markers
    if (waypointsData && waypointsData.waypoints) {
      const markerCollection = new Cesium.MarkersCollection();
      
      waypointsData.waypoints.forEach((wp, index) => {
        const position = Cesium.Cartesian3.fromDegrees(
          wp.position[0],
          wp.position[1],
          wp.position[2] || 0
        );

        const marker = new Cesium.Marker({
          position: position,
          pixelOffset: new Cesium.Cartesian2(-15, -25),
          image: new Cesium.CesiumImageResource(
            `data:image/svg+xml;base64,${btoa(`
              <svg xmlns="http://www.w3.org/2000/svg" width="30" height="40">
                <circle cx="15" cy="15" r="12" fill="#FFD700" stroke="#B8860B" stroke-width="2"/>
                <text x="15" y="22" text-anchor="middle" font-size="14" fill="#000">${index + 1}</text>
              </svg>`)}`
          ),
        });

        markerCollection.add(marker);
      });

      viewer.scene.primitives.add(markerCollection);
    }

    // Add frame markers for timeline navigation
    const frameMarkers = trajectoryData.poses.map((pose, index) => ({
      name: `Frame ${index}`,
      time: pose.timestamp * 1000, // Convert to milliseconds
      description: `Position: [${pose.position.join(', ')}]`,
    }));

    viewer.timeline.markers.removeAll();
    frameMarkers.forEach(marker => {
      viewer.timeline.addMarker({
        name: marker.name,
        time: Cesium.JulianDate.fromSeconds(0) + 
              Cesium.secondsToJulian(marker.time / 1000),
        description: marker.description,
      });
    });

    // Set timeline range
    const startTime = Cesium.JulianDate.fromSeconds(0);
    const durationMs = trajectoryData.poses.length * (trajectoryData.metadata?.frameIntervalMs || 100);
    const endTime = Cesium.addSeconds(startTime, durationMs / 1000);

    viewer.timeline.setRange(startTime, endTime);

    // Enable auto-rotation to follow trajectory
    let autoRotate = false;
    let autoRotateInterval = null;

    const startAutoRotate = () => {
      if (autoRotate) return;
      
      autoRotate = true;
      viewer.camera.startTracking();
      
      autoRotateInterval = setInterval(() => {
        viewer.camera.rotate(0.001, new Cesium.Cartesian3(0, 0, 1));
      }, 50);
    };

    const stopAutoRotate = () => {
      if (!autoRotate) return;
      
      autoRotate = false;
      clearInterval(autoRotateInterval);
      viewer.camera.stopTracking();
    };

    // Add camera controls
    const orbitControls = new OrbitControls(viewer.scene, viewer.canvas);
    
    // Handle window resize
    const handleResize = () => {
      viewer.resolutionScale = 
        window.devicePixelRatio > 1 ? Math.min(2, window.devicePixelRatio) : 1;
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    // Expose methods to parent component
    const api = {
      setAutoRotate: (enabled) => {
        if (enabled) startAutoRotate();
        else stopAutoRotate();
      },
      getCurrentFrame: () => currentFrame,
      getTotalFrames: () => totalFrames,
      navigateToFrame: (frameIndex) => {
        const time = trajectoryData.poses[frameIndex]?.timestamp || 0;
        viewer.clock.currentTime = Cesium.JulianDate.fromSeconds(time);
        setCurrentFrame(frameIndex);
      },
    };

    // Cleanup on unmount
    return () => {
      window.removeEventListener('resize', handleResize);
      stopAutoRotate();
      
      if (pointCloudLayer) {
        viewer.scene.primitives.remove(pointCloudLayer);
      }
      
      viewer.destroy();
    };
  }, [trajectoryData, waypointsData, pointCloudUrl]);

  // Handle trajectory data updates
  useEffect(() => {
    if (trajectoryData && trajectoryData.poses) {
      setTotalFrames(trajectoryData.poses.length);
      setCurrentFrame(0);
      
      // Update timeline markers
      const viewer = viewerRef.current;
      if (viewer) {
        viewer.timeline.markers.removeAll();
        
        trajectoryData.poses.forEach((pose, index) => {
          viewer.timeline.addMarker({
            name: `Frame ${index}`,
            time: Cesium.JulianDate.fromSeconds(pose.timestamp),
            description: `Position: [${pose.position.join(', ')}]`,
          });
        });

        const startTime = Cesium.JulianDate.fromSeconds(0);
        const endTime = trajectoryData.poses.length > 0 
          ? Cesium.addSeconds(startTime, trajectoryData.poses[trajectoryData.poses.length - 1].timestamp)
          : startTime;
        
        viewer.timeline.setRange(startTime, endTime);
      }
    }
  }, [trajectoryData]);

  // Handle waypoints data updates
  useEffect(() => {
    if (waypointsData && waypointsData.waypoints && viewerRef.current) {
      const viewer = viewerRef.current;
      
      // Remove existing markers
      const markerCollection = viewer.scene.primitives.find(p => p instanceof Cesium.MarkersCollection);
      if (markerCollection) {
        viewer.scene.primitives.remove(markerCollection);
      }

      // Add new markers
      const markerCollection = new Cesium.MarkersCollection();
      
      waypointsData.waypoints.forEach((wp, index) => {
        const position = Cesium.Cartesian3.fromDegrees(
          wp.position[0],
          wp.position[1],
          wp.position[2] || 0
        );

        const marker = new Cesium.Marker({
          position: position,
          pixelOffset: new Cesium.Cartesian2(-15, -25),
          image: new Cesium.CesiumImageResource(
            `data:image/svg+xml;base64,${btoa(`
              <svg xmlns="http://www.w3.org/2000/svg" width="30" height="40">
                <circle cx="15" cy="15" r="12" fill="#FFD700" stroke="#B8860B" stroke-width="2"/>
                <text x="15" y="22" text-anchor="middle" font-size="14" fill="#000">${index + 1}</text>
              </svg>`)}`
          ),
        });

        markerCollection.add(marker);
      });

      viewer.scene.primitives.add(markerCollection);
    }
  }, [waypointsData]);

  // Update stats when frame changes
  useEffect(() => {
    if (onStatsUpdate && currentFrame !== undefined) {
      onStatsUpdate({
        currentFrame,
        totalFrames,
        isPlaying: false,
      });
    }
  }, [currentFrame, totalFrames]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100vh' }} />
  );
}

export default DisasterMapViewer;
