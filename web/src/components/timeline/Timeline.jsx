import React, { useState, useEffect, useRef } from 'react';
import Cesium from 'cesium';

const { JulianDate, Interval, Clock } = Cesium;

/**
 * Timeline Navigation Component for Disaster Map Viewer
 * Provides playback controls, frame markers, and smooth scrubbing
 */
function Timeline({ 
  trajectoryData, 
  onFrameChange, 
  onPlaybackSpeedChange,
  autoPlay = false,
  playRate = 1.0,
}) {
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  
  const clockRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    if (!trajectoryData || !trajectoryData.poses) return;

    // Calculate duration based on frame interval
    const frameIntervalMs = trajectoryData.metadata?.frameIntervalMs || 100;
    const totalFrames = trajectoryData.poses.length;
    
    setDuration(totalFrames * frameIntervalMs / 1000);
    
    // Initialize clock
    if (clockRef.current) {
      clockRef.current.destroy();
    }

    clockRef.current = new Clock({
      currentTime: JulianDate.fromSeconds(0),
      clockRangeDuration: JulianDate.secondsFrom(now, duration),
      shouldLoop: false,
    });

    // Start playback if auto-play is enabled
    if (autoPlay) {
      setIsPlaying(true);
      play();
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      clockRef.current?.destroy();
    };
  }, [trajectoryData, autoPlay]);

  // Playback loop
  const play = () => {
    setIsPlaying(true);
    
    const updateClock = () => {
      if (!isPlaying) return;

      animationFrameRef.current = requestAnimationFrame(updateClock);
      
      // Advance clock by one frame interval
      const frameIntervalSeconds = (trajectoryData.metadata?.frameIntervalMs || 100) / 1000;
      clockRef.current.currentTime = JulianDate.addSeconds(
        clockRef.current.currentTime, 
        frameIntervalSeconds
      );

      // Update current time display
      setCurrentTime(clockRef.current.getTime());
      
      // Find current frame index
      const currentTimeMs = clockRef.current.getTime() * 1000;
      let newIndex = Math.floor(currentTimeMs / (trajectoryData.metadata?.frameIntervalMs || 100));
      newIndex = Math.min(newIndex, trajectoryData.poses.length - 1);
      
      setFrameIndex(newIndex);
      onFrameChange && onFrameChange(newIndex);
    };

    updateClock();
  };

  const pause = () => {
    setIsPlaying(false);
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
  };

  const togglePlay = () => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  };

  // Handle playback speed change
  useEffect(() => {
    if (clockRef.current && isPlaying) {
      clockRef.current.multiplier = playRate;
      onPlaybackSpeedChange && onPlaybackSpeedChange(playRate);
    }
  }, [playRate]);

  // Seek to specific time
  const seekToTime = (timeSeconds) => {
    if (!clockRef.current) return;
    
    clockRef.current.currentTime = JulianDate.fromSeconds(timeSeconds);
    setCurrentTime(timeSeconds);
    
    // Calculate frame index at this time
    const frameIntervalMs = trajectoryData.metadata?.frameIntervalMs || 100;
    const newIndex = Math.floor((timeSeconds * 1000) / frameIntervalMs);
    setFrameIndex(Math.min(newIndex, trajectoryData.poses.length - 1));
    
    onFrameChange && onFrameChange(newIndex);
  };

  // Handle scrubbing via timeline slider
  const handleTimelineClick = (time) => {
    seekToTime(time);
  };

  // Format time for display
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Get progress percentage
  const getProgress = () => {
    if (duration === 0) return 0;
    return Math.min((currentTime / duration) * 100, 100);
  };

  // Generate frame markers for timeline
  const frameMarkers = trajectoryData.poses.map((pose, index) => ({
    name: `Frame ${index}`,
    time: pose.timestamp,
    description: `Position: [${pose.position.join(', ')}]`,
  }));

  return (
    <div style={{ 
      padding: '10px', 
      backgroundColor: '#1a1a2e', 
      borderBottom: '1px solid #333',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {/* Playback Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button 
          onClick={togglePlay}
          style={{
            padding: '8px 16px',
            backgroundColor: isPlaying ? '#e74c3c' : '#2ecc71',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
          }}
        >
          {isPlaying ? '⏸ Pause' : '▶ Play'}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: '#888', fontSize: '12px' }}>Speed:</span>
          {[0.5, 1, 2, 4].map((rate) => (
            <button
              key={rate}
              onClick={() => onPlaybackSpeedChange && onPlaybackSpeedChange(rate)}
              style={{
                padding: '4px 8px',
                backgroundColor: playRate === rate ? '#3498db' : '#2c3e50',
                color: 'white',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              {rate}x
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: '#888', fontSize: '12px' }}>Frame:</span>
          <input
            type="number"
            min="0"
            max={trajectoryData.poses.length - 1}
            value={frameIndex}
            onChange={(e) => {
              const index = parseInt(e.target.value);
              if (!isNaN(index) && index >= 0 && index < trajectoryData.poses.length) {
                seekToTime(trajectoryData.poses[index].timestamp);
              }
            }}
            style={{
              width: '60px',
              padding: '4px',
              backgroundColor: '#2c3e50',
              color: 'white',
              border: '1px solid #444',
              borderRadius: '3px',
            }}
          />
        </div>
      </div>

      {/* Timeline Slider */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          fontSize: '12px',
          color: '#888',
        }}>
          <span>{formatTime(currentTime)}</span>
          <span>/ {formatTime(duration)}</span>
        </div>

        <input
          type="range"
          min="0"
          max={duration}
          step="0.1"
          value={currentTime}
          onChange={(e) => seekToTime(parseFloat(e.target.value))}
          onClick={(e) => handleTimelineClick(parseFloat(e.target.value))}
          style={{
            width: '100%',
            height: '8px',
            backgroundColor: '#2c3e50',
            borderRadius: '4px',
            outline: 'none',
            cursor: 'pointer',
          }}
        />

        {/* Progress Bar */}
        <div style={{ 
          width: '100%', 
          height: '6px', 
          backgroundColor: '#333', 
          borderRadius: '3px',
          overflow: 'hidden',
        }}>
          <div style={{
            width: `${getProgress()}%`,
            height: '100%',
            backgroundColor: isPlaying ? '#2ecc71' : '#e74c3c',
            transition: 'width 0.1s linear',
          }} />
        </div>

        {/* Frame Markers */}
        <div style={{ 
          display: 'flex', 
          gap: '2px', 
          overflowX: 'auto',
          padding: '4px 0',
        }}>
          {frameMarkers.map((marker, index) => (
            <div
              key={index}
              onClick={() => seekToTime(marker.time)}
              style={{
                position: 'relative',
                cursor: 'pointer',
                padding: '2px 4px',
                backgroundColor: frameIndex === index ? '#3498db' : 'transparent',
                borderRadius: '3px',
                fontSize: '10px',
                color: '#ccc',
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ fontWeight: 'bold' }}>{index}</span>
              {frameIndex === index && (
                <div 
                  style={{
                    position: 'absolute',
                    top: '-4px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    width: '6px',
                    height: '6px',
                    backgroundColor: '#2ecc71',
                    borderRadius: '50%',
                  }} 
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Current Frame Info */}
      <div style={{ 
        fontSize: '11px', 
        color: '#666', 
        display: 'flex', 
        justifyContent: 'space-between',
      }}>
        <span>Current Frame:</span>
        <span>{frameIndex + 1} / {trajectoryData.poses.length}</span>
      </div>

      {/* Playback Controls */}
      <div style={{ display: 'flex', gap: '5px' }}>
        <button 
          onClick={() => seekToTime(0)}
          style={{
            padding: '4px 8px',
            backgroundColor: '#2c3e50',
            color: '#ccc',
            border: '1px solid #444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '11px',
          }}
        >
          ⏮ Rewind
        </button>

        <button 
          onClick={() => seekToTime(duration)}
          style={{
            padding: '4px 8px',
            backgroundColor: '#2c3e50',
            color: '#ccc',
            border: '1px solid #444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '11px',
          }}
        >
          ⏭ Fast Forward
        </button>

        <button 
          onClick={() => {
            // Snap to nearest waypoint
            const viewer = window.viewerRef;
            if (viewer) {
              viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(
                  trajectoryData.poses[frameIndex]?.position[0] || 0,
                  trajectoryData.poses[frameIndex]?.position[1] || 0,
                  trajectoryData.poses[frameIndex]?.position[2] || 50
                ),
              });
            }
          }}
          style={{
            padding: '4px 8px',
            backgroundColor: '#2c3e50',
            color: '#ccc',
            border: '1px solid #444',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '11px',
          }}
        >
          📍 Snap to Frame
        </button>
      </div>
    </div>
  );
}

export default Timeline;
