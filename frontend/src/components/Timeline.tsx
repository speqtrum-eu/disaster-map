import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Box, Typography, Slider, IconButton, Tooltip, Paper } from '@mui/material';
import { PlayArrow, Pause, SkipPrevious, SkipNext, FastForward, FastRewind, Timeline as TimelineIcon } from '@mui/icons-material';
import { timeService } from '../services/timeService';
import { api } from '../services/api';

interface TimelineProps {
  onTimeChange?: (timestamp: number) => void;
}

const Timeline: React.FC<TimelineProps> = ({ onTimeChange }) => {
  const [currentTime, setCurrentTime] = useState<number>(timeService.getCurrentTime());
  const [timeRange, setTimeRange] = useState<{ start: number; end: number } | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(timeService.getPlaybackState().isPlaying);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(timeService.getPlaybackState().speed);
  const [markers, setMarkers] = useState<Array<{ id: string; timestamp: number; label: string }>>([]);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const timelineRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);

  // Load time range and markers
  useEffect(() => {
    const loadData = async () => {
      try {
        // Get stats to determine time range
        const stats = await api.get('/stats');
        
        // For demo, use a default time range
        // In production, this would come from the API
        const now = Date.now() / 1000;
        const oneHourAgo = now - 3600;
        
        setTimeRange({ start: oneHourAgo, end: now });
        timeService.setTimeRange({ start: oneHourAgo, end: now });
        
        // Set initial time
        setCurrentTime(now);
        timeService.setCurrentTime(now);
        
        // Add some demo markers
        const demoMarkers = [];
        for (let i = 0; i < 10; i++) {
          const timestamp = oneHourAgo + (i * 360); // Every 6 minutes
          demoMarkers.push({
            id: `marker_${i}`,
            timestamp,
            label: `Event ${i + 1}`,
          });
        }
        setMarkers(demoMarkers);
        demoMarkers.forEach(marker => timeService.addMarker({
          id: marker.id,
          timestamp: marker.timestamp,
          label: marker.label,
          type: 'event',
        }));
        
      } catch (error) {
        console.error('Error loading timeline data:', error);
      }
    };

    loadData();

    // Setup time service listeners
    const handleTimeChange = () => {
      setCurrentTime(timeService.getCurrentTime());
    };

    const handlePlaybackChange = () => {
      const state = timeService.getPlaybackState();
      setIsPlaying(state.isPlaying);
      setPlaybackSpeed(state.speed);
    };

    timeService.addMarker = timeService.addMarker.bind(timeService);
    
    // Poll for updates (simplified - in production use WebSocket)
    const interval = setInterval(() => {
      handleTimeChange();
      handlePlaybackChange();
    }, 100);

    return () => clearInterval(interval);
  }, []);

  // Handle time change
  const handleTimeChange = useCallback((event: Event, value: number | number[]) => {
    const newTime = Array.isArray(value) ? value[0] : value;
    setCurrentTime(newTime);
    timeService.setCurrentTime(newTime);
    onTimeChange?.(newTime);
  }, [onTimeChange]);

  // Playback controls
  const togglePlayback = useCallback(() => {
    timeService.togglePlayback();
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  const handlePlaybackSpeed = useCallback((speed: number) => {
    timeService.setPlaybackSpeed(speed);
    setPlaybackSpeed(speed);
  }, []);

  const goToPreviousMarker = useCallback(() => {
    timeService.goToPreviousMarker();
    setCurrentTime(timeService.getCurrentTime());
  }, []);

  const goToNextMarker = useCallback(() => {
    timeService.goToNextMarker();
    setCurrentTime(timeService.getCurrentTime());
  }, []);

  const goToStart = useCallback(() => {
    timeService.goToStart();
    setCurrentTime(timeService.getCurrentTime());
  }, []);

  const goToEnd = useCallback(() => {
    timeService.goToEnd();
    setCurrentTime(timeService.getCurrentTime());
  }, []);

  // Calculate position for thumb and markers
  const getPosition = useCallback((timestamp: number) => {
    if (!timeRange || !timelineRef.current) return 0;
    
    const { start, end } = timeRange;
    const duration = end - start;
    const progress = (timestamp - start) / duration;
    
    return Math.max(0, Math.min(100, progress * 100));
  }, [timeRange]);

  // Handle mouse down on thumb
  const handleThumbMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!timelineRef.current || !thumbRef.current) return;
      
      const rect = timelineRef.current.getBoundingClientRect();
      const thumbWidth = thumbRef.current.offsetWidth;
      const x = moveEvent.clientX - rect.left;
      const percentage = (x / rect.width) * 100;
      
      if (timeRange) {
        const { start, end } = timeRange;
        const newTime = start + ((end - start) * percentage) / 100;
        setCurrentTime(newTime);
        timeService.setCurrentTime(newTime);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, []);

  // Handle click on timeline
  const handleTimelineClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!timelineRef.current || !timeRange) return;
    
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = (x / rect.width) * 100;
    
    const { start, end } = timeRange;
    const newTime = start + ((end - start) * percentage) / 100;
    setCurrentTime(newTime);
    timeService.setCurrentTime(newTime);
  }, [timeRange]);

  // Format time for display
  const formatTime = useCallback((timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }, []);

  return (
    <Box sx={{ 
      width: '100%', 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#1e1e1e',
    }}>
      {/* Timeline track */}
      <Box 
        ref={timelineRef}
        sx={{
          flex: 1,
          position: 'relative',
          backgroundColor: '#2d2d2d',
          borderRadius: 1,
          overflow: 'hidden',
          cursor: 'pointer',
          mx: 2,
          my: 1,
        }}
        onClick={handleTimelineClick}
      >
        {/* Track background */}
        <Box sx={{
          position: 'absolute',
          top: '50%',
          left: 0,
          right: 0,
          height: 4,
          backgroundColor: '#444',
          transform: 'translateY(-50%)',
          borderRadius: 2,
        }} />

        {/* Markers */}
        <Box sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'none',
        }}>
          {markers.map((marker) => (
            <Box
              key={marker.id}
              sx={{
                position: 'absolute',
                left: `${getPosition(marker.timestamp)}%`,
                top: '50%',
                width: 2,
                height: 20,
                backgroundColor: '#ff5722',
                transform: 'translate(-50%, -50%)',
                borderRadius: 1,
              }}
              title={marker.label}
            />
          ))}
        </Box>

        {/* Thumb */}
        <Box
          ref={thumbRef}
          sx={{
            position: 'absolute',
            left: `${getPosition(currentTime)}%`,
            top: '50%',
            width: 16,
            height: 60,
            backgroundColor: isDragging ? '#2196f3' : '#1976d2',
            borderRadius: 2,
            transform: 'translate(-50%, -50%)',
            cursor: 'pointer',
            boxShadow: 1,
            transition: 'background-color 0.2s',
            '&:hover': {
              backgroundColor: '#2196f3',
            },
          }}
          onMouseDown={handleThumbMouseDown}
        />
      </Box>

      {/* Time labels */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        px: 2,
        pb: 1,
      }}>
        <Typography variant="caption" color="text.secondary">
          {timeRange ? formatTime(timeRange.start) : '--:--:--'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {timeRange ? formatTime(timeRange.end) : '--:--:--'}
        </Typography>
      </Box>

      {/* Current time display */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        my: 1,
      }}>
        <Typography variant="h6" color="primary.main">
          {formatTime(currentTime)}
        </Typography>
      </Box>

      {/* Controls */}
      <Paper 
        elevation={3} 
        sx={{
          p: 1,
          display: 'flex',
          gap: 1,
          alignItems: 'center',
          justifyContent: 'center',
          flexWrap: 'wrap',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <Tooltip title="Previous Marker" arrow>
          <IconButton onClick={goToPreviousMarker} size="small" color="primary">
            <SkipPrevious fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title="Rewind" arrow>
          <IconButton onClick={() => handlePlaybackSpeed(0.5)} size="small" color="primary">
            <FastRewind fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title={isPlaying ? 'Pause' : 'Play'} arrow>
          <IconButton onClick={togglePlayback} size="small" color="primary">
            {isPlaying ? <Pause fontSize="small" /> : <PlayArrow fontSize="small" />}
          </IconButton>
        </Tooltip>

        <Tooltip title="Fast Forward" arrow>
          <IconButton onClick={() => handlePlaybackSpeed(2.0)} size="small" color="primary">
            <FastForward fontSize="small" />
          </IconButton>
        </Tooltip>

        <Tooltip title="Next Marker" arrow>
          <IconButton onClick={goToNextMarker} size="small" color="primary">
            <SkipNext fontSize="small" />
          </IconButton>
        </Tooltip>

        <Box sx={{ flex: 1, mx: 2, minWidth: 100 }}>
          <Slider
            value={playbackSpeed}
            onChange={(e, value) => handlePlaybackSpeed(value as number)}
            min={0.1}
            max={10}
            step={0.1}
            size="small"
            sx={{ color: 'primary.main' }}
          />
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mx: 1, minWidth: 40 }}>
          {playbackSpeed}x
        </Typography>

        <Tooltip title="Go to Start" arrow>
          <IconButton onClick={goToStart} size="small" color="primary">
            <TimelineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Paper>
    </Box>
  );
};

export default Timeline;
