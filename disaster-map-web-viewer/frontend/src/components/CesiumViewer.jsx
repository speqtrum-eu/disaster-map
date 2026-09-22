import * as Cesium from 'cesium';
import { useRef, useEffect } from 'react';

export function CesiumViewer() {
  const viewerRef = useRef(null);

  useEffect(() => {
    // Initialize Cesium Viewer
    if (!viewerRef.current) {
      viewerRef.current = new Cesium.Viewer('cesiumContainer', {
        terrainProvider: undefined,
        baseLayerPicker: false,
        animation: false,
        timeline: true,
        geocoder: true,
        homeButton: true,
        navigationHelpButton: true,
        sceneModePicker: true,
        selectionIndicator: true,
        infoBox: true,
        scene3DOnly: true,
      });

      // Set default camera position
      viewerRef.current.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(-122.4194, 37.7749, 500),
      });

      // Add terrain provider (optional)
      // viewerRef.current.terrainProvider = Cesium.createWorldTerrain();
    }

    return () => {
      if (viewerRef.current) {
        viewerRef.current.destroy();
      }
    };
  }, []);

  return <div id="cesiumContainer" style={{ width: '100%', height: '100vh' }} />;
}