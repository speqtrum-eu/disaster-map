import React, { useState } from 'react';

/**
 * Waypoint List Component
 * Displays and allows interaction with rescue waypoints
 */
function WaypointList({ waypointsData }) {
  const [selectedWaypoint, setSelectedWaypoint] = useState(null);
  const [showCoordinates, setShowCoordinates] = useState(true);

  if (!waypointsData || !waypointsData.waypoints) {
    return (
      <div style={{ 
        padding: '15px', 
        backgroundColor: '#2c3e50', 
        borderRadius: '8px',
        color: '#ccc',
      }}>
        <p>No waypoints loaded</p>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: '15px', 
      backgroundColor: '#2c3e50', 
      borderRadius: '8px',
      color: '#ccc',
      maxHeight: '400px',
      overflowY: 'auto',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h3 style={{ margin: 0, color: '#3498db' }}>📍 Waypoints</h3>
        <button 
          onClick={() => setShowCoordinates(!showCoordinates)}
          style={{
            padding: '4px 8px',
            backgroundColor: '#1a1a2e',
            border: '1px solid #444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          {showCoordinates ? 'Hide Coords' : 'Show Coords'}
        </button>
      </div>

      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {waypointsData.waypoints.map((wp, index) => (
          <li 
            key={index}
            onClick={() => setSelectedWaypoint(wp.name)}
            style={{
              padding: '12px',
              marginBottom: '8px',
              backgroundColor: selectedWaypoint === wp.name ? '#3498db' : '#1a1a2e',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 'bold', color: '#fff' }}>{wp.name}</span>
              <span 
                style={{
                  padding: '2px 8px',
                  backgroundColor: getActionColor(wp.action),
                  borderRadius: '12px',
                  fontSize: '10px',
                  textTransform: 'uppercase',
                }}
              >
                {wp.action}
              </span>
            </div>

            {showCoordinates && (
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#888' }}>
                <div><strong>Position:</strong></div>
                <div>[{wp.position.join(', ')}]</div>
              </div>
            )}

            {selectedWaypoint === wp.name && (
              <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#2c3e50', borderRadius: '4px' }}>
                <p style={{ margin: 0, fontSize: '13px' }}>
                  <strong>Selected:</strong> {wp.name}
                </p>
                <p style={{ margin: '5px 0 0 0', fontSize: '12px', color: '#888' }}>
                  Action: {wp.action.replace('_', ' ').toUpperCase()}
                </p>
              </div>
            )}
          </li>
        ))}
      </ul>

      {/* Legend */}
      <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#1a1a2e', borderRadius: '6px' }}>
        <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#888' }}>📊 Legend</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '12px' }}>
          {['deploy', 'scan', 'mark_safe', 'deploy_team'].map((action) => (
            <div key={action} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span 
                style={{
                  width: '12px',
                  height: '12px',
                  backgroundColor: getActionColor(action),
                  borderRadius: '50%',
                }}
              />
              <span style={{ color: '#888' }}>{action.replace('_', ' ').toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Actions */}
      {selectedWaypoint && (
        <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#2c3e50', borderRadius: '6px' }}>
          <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#fff' }}>🧭 Navigate</h4>
          <div style={{ display: 'flex', gap: '5px' }}>
            <button 
              onClick={() => {
                const viewer = window.viewerRef;
                if (viewer) {
                  // Fly to waypoint
                  viewer.camera.flyTo({
                    destination: Cesium.Cartesian3.fromDegrees(
                      waypointsData.waypoints.find(w => w.name === selectedWaypoint)?.position[0] || 0,
                      waypointsData.waypoints.find(w => w.name === selectedWaypoint)?.position[1] || 0,
                      waypointsData.waypoints.find(w => w.name === selectedWaypoint)?.position[2] || 50
                    ),
                  });
                }
              }}
              style={{
                padding: '6px 12px',
                backgroundColor: '#3498db',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              🚀 Fly To
            </button>
            <button 
              onClick={() => {
                const viewer = window.viewerRef;
                if (viewer) {
                  // Add a marker at waypoint position
                  const wp = waypointsData.waypoints.find(w => w.name === selectedWaypoint);
                  if (wp) {
                    const position = Cesium.Cartesian3.fromDegrees(
                      wp.position[0],
                      wp.position[1],
                      wp.position[2] || 0
                    );
                    
                    viewer.entities.add({
                      name: `Selected Waypoint: ${selectedWaypoint}`,
                      point: {
                        position: position,
                        pixelSize: 20,
                        color: Cesium.Color.YELLOW.withAlpha(1.0),
                        outlineColor: Cesium.Color.BLACK,
                        outlineWidth: 2,
                      },
                    });
                  }
                }
              }}
              style={{
                padding: '6px 12px',
                backgroundColor: '#27ae60',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              📌 Add Marker
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper function to get color based on action type
function getActionColor(action) {
  const colors = {
    deploy: '#e74c3c',     // Red for deployment points
    scan: '#3498db',       // Blue for scanning zones
    mark_safe: '#2ecc71',  // Green for safe zones
    deploy_team: '#f39c12', // Orange for team deployment
  };
  return colors[action] || '#95a5a6';
}

export default WaypointList;
