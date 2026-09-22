import React, { useState, useEffect } from 'react';

/**
 * Camera Controls Component
 * Provides orbit controls, zoom/pan, and auto-rotate functionality
 */
function CameraControls({ 
  onAutoRotateChange, 
  autoRotate = false,
  snapToWaypoint = false,
}) {
  const [rotation, setRotation] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isDragging, setIsDragging] = useState(false);

  // Handle auto-rotate toggle
  useEffect(() => {
    onAutoRotateChange && onAutoRotateChange(autoRotate);
  }, [autoRotate]);

  // Simulate camera rotation for auto-rotate mode
  useEffect(() => {
    if (!autoRotate) return;

    let animationFrameId;
    
    const rotateCamera = () => {
      setRotation(prev => (prev + 0.1) % 360);
      animationFrameId = requestAnimationFrame(rotateCamera);
    };

    animationFrameId = requestAnimationFrame(rotateCamera);

    return () => cancelAnimationFrame(animationFrameId);
  }, [autoRotate]);

  // Handle zoom with mouse wheel
  const handleZoom = (delta) => {
    setZoomLevel(prev => Math.max(0.5, Math.min(5, prev + delta * 0.1)));
  };

  // Handle drag to rotate view
  const handleMouseDown = () => setIsDragging(true);
  const handleMouseUp = () => setIsDragging(false);
  const handleMouseMove = (e) => {
    if (!isDragging) return;
    
    setRotation(prev => prev - e.movementX * 0.5);
  };

  // Reset camera to initial position
  const resetCamera = () => {
    setZoomLevel(1);
    setRotation(0);
  };

  // Snap to waypoint (simulated)
  const snapToWaypointHandler = () => {
    if (!snapToWaypoint) return;
    
    // In a real implementation, this would navigate to the selected waypoint
    console.log('Snapping to waypoint...');
  };

  return (
    <div style={{ 
      padding: '10px', 
      backgroundColor: '#2c3e50', 
      borderBottom: '1px solid #333',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {/* Camera View Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ color: '#888', fontSize: '12px' }}>View:</span>
          
          <button 
            onClick={() => setZoomLevel(prev => Math.min(5, prev + 0.5))}
            style={{
              padding: '4px 8px',
              backgroundColor: '#1a1a2e',
              border: '1px solid #444',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            + Zoom In
          </button>

          <button 
            onClick={() => setZoomLevel(prev => Math.max(0.5, prev - 0.5))}
            style={{
              padding: '4px 8px',
              backgroundColor: '#1a1a2e',
              border: '1px solid #444',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            - Zoom Out
          </button>

          <span style={{ color: '#666', fontSize: '12px' }}>
            {zoomLevel.toFixed(1)}x
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <button 
            onClick={resetCamera}
            style={{
              padding: '4px 8px',
              backgroundColor: '#1a1a2e',
              border: '1px solid #444',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            🔄 Reset View
          </button>

          <button 
            onClick={snapToWaypointHandler}
            style={{
              padding: '4px 8px',
              backgroundColor: snapToWaypoint ? '#3498db' : '#1a1a2e',
              border: `1px solid ${snapToWaypoint ? '#3498db' : '#444'}`,
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            📍 Snap Waypoint
          </button>
        </div>
      </div>

      {/* Auto-Rotate Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ color: '#888', fontSize: '12px' }}>Auto-Rotate:</span>
        
        <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
          <input 
            type="checkbox" 
            checked={autoRotate}
            onChange={(e) => onAutoRotateChange && onAutoRotateChange(e.target.checked)}
            style={{ width: '16px', height: '16px' }}
          />
          <span style={{ color: '#ccc' }}>Follow Path</span>
        </label>

        {autoRotate && (
          <div style={{ marginLeft: '20px', padding: '8px', backgroundColor: '#3498db20', borderRadius: '4px' }}>
            <p style={{ margin: 0, fontSize: '11px', color: '#888' }}>
              🔄 Camera is following trajectory path
            </p>
          </div>
        )}
      </div>

      {/* Navigation Mode */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
        <span style={{ color: '#888', fontSize: '12px' }}>Navigation:</span>
        
        <select 
          value={snapToWaypoint ? 'waypoint' : 'orbit'}
          onChange={(e) => {
            if (e.target.value === 'waypoint') snapToWaypointHandler();
          }}
          style={{
            padding: '4px 8px',
            backgroundColor: '#1a1a2e',
            border: '1px solid #444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          <option value="orbit">Orbit Mode</option>
          <option value="waypoint">Waypoint Snap</option>
          <option value="follow">Follow Path</option>
        </select>
      </div>

      {/* Keyboard Shortcuts */}
      <div style={{ 
        marginTop: '8px', 
        padding: '8px', 
        backgroundColor: '#1a1a2e', 
        borderRadius: '4px',
        fontSize: '11px',
      }}>
        <span style={{ color: '#666' }}>⌨️ Keyboard Shortcuts:</span>
        <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
          <span><kbd style={{ 
            padding: '2px 6px', 
            backgroundColor: '#333', 
            borderRadius: '3px',
            fontSize: '10px',
          }}>R</kbd> Reset View</span>
          <span><kbd style={{ 
            padding: '2px 6px', 
            backgroundColor: '#333', 
            borderRadius: '3px',
            fontSize: '10px',
          }}>+</kbd> Zoom In</span>
          <span><kbd style={{ 
            padding: '2px 6px', 
            backgroundColor: '#333', 
            borderRadius: '3px',
            fontSize: '10px',
          }}>-</kbd> Zoom Out</span>
        </div>
      </div>

      {/* View Orientation */}
      <div style={{ 
        marginTop: '8px', 
        padding: '6px', 
        backgroundColor: '#3498db20', 
        borderRadius: '4px',
        fontSize: '11px',
      }}>
        <span style={{ color: '#888' }}>Orientation:</span>
        <span style={{ marginLeft: '5px', color: '#fff' }}>
          {rotation.toFixed(0)}° rotation
        </span>
      </div>
    </div>
  );
}

export default CameraControls;
