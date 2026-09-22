# Field Operator's Guide

## Quick Start

### Prerequisites

Before operating the Disaster Map system in the field, ensure you have:

1. **Hardware Requirements**
   - Drone with RTK GPS (accuracy < 2cm)
   - Camera with minimum 1080p resolution at 30fps
   - Sufficient storage (minimum 50GB for extended missions)
   - Stable power supply (battery life ≥ 20 minutes)

2. **Software Requirements**
   - Disaster Map Client v1.0+ installed on tablet/laptop
   - Internet connection for data upload (optional, works offline)
   - GPS signal with minimum 8 satellites visible

### Pre-Flight Checklist

```
□ Verify drone battery > 80%
□ Check camera lens is clean and unobstructed
□ Confirm RTK GPS base station connection
□ Test video stream transmission to ground station
□ Verify sufficient storage space available
□ Calibrate IMU if operating in challenging conditions
□ Review mission waypoints and no-fly zones
```

### System Startup

1. **Launch the Application**
   ```bash
   # On tablet/laptop
   ./disaster-map-client --config /etc/disaster-map/field.conf
   
   # Or via GUI (if available)
   disaster-map-gui
   ```

2. **Connect to Video Stream**
   - Select video source from dropdown menu
   - Verify stream quality indicator shows "GOOD" or "EXCELLENT"
   - Adjust bitrate if experiencing lag

3. **Initialize SLAM System**
   - Click "Start Mapping" button
   - Wait for initialization complete message (typically 2-5 seconds)
   - Confirm GPS lock status in the status panel

### During Flight Operations

#### Real-Time Monitoring

The main dashboard displays:

```
┌─────────────────────────────────────────────────────┐
│  LIVE VIEWER                    │  STATUS PANEL    │
│  ┌───────────────────────────┐   │  GPS: [●] LOCKED │
│  │                           │   │  RTK: [●] ACTIVE │
│  │     3D Point Cloud        │   │  FPS: 32.5      │
│  │                           │   │  Latency: 45ms  │
│  │    Camera Trajectory      │   │  Battery: 78%   │
│  └───────────────────────────┘   │  Signal: -67dBm │
│                                  │                  │
│  ┌───────────────────────────┐   │  MAP STATUS     │
│  │    TIMELINE NAVIGATION    │   │  Frames: 1,234  │
│  │  ◀◀ ◀ ▶ ▶▶                │   │  Poses: 987     │
│  └───────────────────────────┘   │  Drift: 0.02m/m │
└─────────────────────────────────────────────────────┘
```

#### Key Controls

| Button | Function | Shortcut |
|--------|----------|----------|
| Play/Pause | Start/stop real-time playback | `Space` |
| Rewind | Jump to previous keyframe | `←` |
| Fast Forward | Skip forward through frames | `→` |
| Zoom In | Increase camera zoom level | `+` or `=` |
| Zoom Out | Decrease camera zoom level | `-` or `0` |
| Reset View | Return to initial view position | `R` |
| Toggle Waypoints | Show/hide rescue waypoints | `W` |

#### Recording Data

The system automatically records:
- Camera poses and positions
- Point cloud data (compressed)
- Video frames at 1fps for reference
- GPS coordinates and timestamps

**Manual Recording:**
```bash
# Start manual recording session
./disaster-map-record --output /data/mission_001/

# Stop recording
Ctrl+C or click "Stop Recording" button
```

### Post-Flight Procedures

#### Data Export

After completing the mission:

1. **Export Point Cloud**
   - Navigate to File → Export → Point Cloud
   - Select format: PLY (recommended) or LAS
   - Choose output directory with sufficient space

2. **Generate Mission Report**
   ```bash
   ./disaster-map-report \
     --input /data/mission_001/ \
     --output /reports/mission_report.pdf \
     --include trajectory --include statistics
   ```

3. **Upload to Cloud (Optional)**
   - Click "Sync to Cloud" in the application
   - Verify upload completion before disconnecting

#### Data Validation

Verify data integrity:
```bash
# Check point cloud validity
./disaster-map-validate /data/mission_001/map.ply

# Expected output:
# Points: 152,347
# Bounding box: [-12.5, -8.3, 0.0] to [45.6, 23.1, 150.2]
# Validity: PASS (99.8% points within expected range)
```

### Troubleshooting Common Issues

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| **Low FPS (< 20)** | Weak GPS signal, high latency | Move to open area, check connection quality |
| **Drift > 5cm/m** | Poor feature tracking | Ensure good lighting and texture in scene |
| **Video lag** | Network bandwidth issues | Reduce video bitrate or use local storage |
| **GPS lock lost** | Obstructions, interference | Relocate to open sky area, wait for reacquisition |
| **Memory warning** | Large point cloud size | Export current data, continue with new session |

### Safety Guidelines

1. **Always maintain visual line of sight** with the drone during operations
2. **Never fly in restricted airspace** without proper authorization
3. **Keep emergency stop button accessible** at all times
4. **Monitor battery levels closely** - land before reaching 20%
5. **Secure all cables and connections** to prevent damage from wind or movement

### Contact Support

For technical assistance:
- **Email:** support@disaster-map.local
- **Hotline:** +1-800-DISASTER-MAP
- **Documentation:** https://docs.disaster-map.local/field-guide

---

## Appendix A: Configuration Options

Edit `/etc/disaster-map/field.conf` to customize behavior:

```ini
[general]
output_directory = /data/missions
auto_export = true
compression_level = 6

[sensor]
gps_update_rate = 10
camera_fps = 30
video_bitrate = 5000

[visualization]
point_size = 2.0
trajectory_visible = true
waypoints_visible = true
```

## Appendix B: Keyboard Shortcuts Reference

| Key | Action |
|-----|--------|
| `1-9` | Jump to frame N (if within range) |
| `G` | Toggle grid overlay |
| `H` | Toggle height reference |
| `T` | Toggle terrain view |
| `M` | Toggle measurement tools |
| `C` | Cycle camera modes (orbit, fly, follow) |
| `F1-F4` | Quick access to main functions |

