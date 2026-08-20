import React, { useEffect, useState, useCallback } from 'react';
import { Box, Typography, Paper, IconButton, Tooltip, Chip, Card, CardContent, CardActions, Button, Grid, TextField, MenuItem, Select, FormControl, InputLabel } from '@mui/material';
import { Videocam, PlayArrow, Stop, Delete, Add, Settings, Refresh, FiberManualRecord } from '@mui/icons-material';
import { VideoStream, StreamConfig, StreamStatus, StreamType } from '../types';
import { api } from '../services/api';
import { wsClient } from '../services/api';

const StreamManager: React.FC = () => {
  const [streams, setStreams] = useState<Record<string, VideoStream>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [newStream, setNewStream] = useState<Partial<StreamConfig>>({
    type: 'rtsp',
    enabled: true,
    gps: false,
    resolution: [1920, 1080],
    fps: 30,
    altitude: 100,
    heading: 0,
    tilt: 90,
  });

  // Load streams on mount
  useEffect(() => {
    const loadStreams = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const response = await api.get('/streams');
        setStreams(response.data);
        
        // Setup WebSocket listener
        wsClient.onMessage('status_update', (data) => {
          if (data.streams) {
            setStreams(data.streams);
          }
        });
        
      } catch (err) {
        console.error('Error loading streams:', err);
        setError('Failed to load streams');
      } finally {
        setIsLoading(false);
      }
    };

    loadStreams();

    return () => {
      wsClient.offMessage('status_update');
    };
  }, []);

  // Refresh streams
  const refreshStreams = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/streams');
      setStreams(response.data);
    } catch (err) {
      console.error('Error refreshing streams:', err);
      setError('Failed to refresh streams');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Start/stop stream
  const toggleStream = useCallback(async (streamId: string, stream: VideoStream) => {
    try {
      if (stream.status === StreamStatus.CONNECTED || stream.status === StreamStatus.PROCESSING) {
        await api.post(`/streams/${streamId}/stop`);
      } else {
        await api.post(`/streams/${streamId}/start`);
      }
      // Refresh after a short delay
      setTimeout(refreshStreams, 1000);
    } catch (err) {
      console.error(`Error toggling stream ${streamId}:`, err);
      setError(`Failed to toggle stream: ${streamId}`);
    }
  }, [refreshStreams]);

  // Delete stream
  const deleteStream = useCallback(async (streamId: string) => {
    try {
      await api.delete(`/streams/${streamId}`);
      refreshStreams();
    } catch (err) {
      console.error(`Error deleting stream ${streamId}:`, err);
      setError(`Failed to delete stream: ${streamId}`);
    }
  }, [refreshStreams]);

  // Add new stream
  const handleAddStream = useCallback(async () => {
    try {
      if (!newStream.id) {
        setError('Stream ID is required');
        return;
      }
      
      await api.post('/streams', {
        ...newStream,
        id: newStream.id,
      } as StreamConfig);
      
      // Reset form
      setNewStream({
        type: 'rtsp',
        enabled: true,
        gps: false,
        resolution: [1920, 1080],
        fps: 30,
        altitude: 100,
        heading: 0,
        tilt: 90,
      });
      
      refreshStreams();
    } catch (err) {
      console.error('Error adding stream:', err);
      setError('Failed to add stream');
    }
  }, [newStream, refreshStreams]);

  // Get status color
  const getStatusColor = useCallback((status: StreamStatus) => {
    switch (status) {
      case StreamStatus.CONNECTED:
      case StreamStatus.PROCESSING:
        return 'success';
      case StreamStatus.CONNECTING:
        return 'warning';
      case StreamStatus.ERROR:
      case StreamStatus.DISCONNECTED:
      default:
        return 'error';
    }
  }, []);

  // Format status for display
  const formatStatus = useCallback((status: StreamStatus) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  }, []);

  // Format resolution
  const formatResolution = useCallback((resolution: [number, number]) => {
    return `${resolution[0]}x${resolution[1]}`;
  }, []);

  return (
    <Box sx={{ 
      width: '100%', 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      overflow: 'auto',
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h5" component="h1">
          Stream Manager
        </Typography>
        
        <Tooltip title="Refresh" arrow>
          <IconButton onClick={refreshStreams} color="primary" disabled={isLoading}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Error message */}
      {error && (
        <Paper sx={{ 
          p: 2, 
          backgroundColor: 'error.main',
          color: 'error.contrastText',
        }}>
          <Typography>{error}</Typography>
          <Button 
            onClick={() => setError(null)} 
            size="small" 
            variant="text" 
            sx={{ mt: 1, color: 'inherit' }}
          >
            Dismiss
          </Button>
        </Paper>
      )}

      {/* Add new stream form */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Add New Stream
        </Typography>
        
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              label="Stream ID"
              value={newStream.id || ''}
              onChange={(e) => setNewStream(prev => ({ ...prev, id: e.target.value }))}
              size="small"
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              label="Name"
              value={newStream.name || ''}
              onChange={(e) => setNewStream(prev => ({ ...prev, name: e.target.value }))}
              size="small"
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={newStream.type || 'rtsp'}
                onChange={(e) => setNewStream(prev => ({ ...prev, type: e.target.value as StreamType }))}
                label="Type"
              >
                <MenuItem value="rtsp">RTSP</MenuItem>
                <MenuItem value="rtmp">RTMP</MenuItem>
                <MenuItem value="http">HTTP/MJPEG</MenuItem>
                <MenuItem value="file">File</MenuItem>
                <MenuItem value="webrtc">WebRTC</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              label="URL"
              value={newStream.url || ''}
              onChange={(e) => setNewStream(prev => ({ ...prev, url: e.target.value }))}
              size="small"
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={4}>
            <TextField
              fullWidth
              label="FPS"
              type="number"
              value={newStream.fps || 30}
              onChange={(e) => setNewStream(prev => ({ ...prev, fps: Number(e.target.value) }))}
              size="small"
              InputProps={{ inputProps: { min: 1, max: 60 } }}
            />
          </Grid>
          
          <Grid item xs={12} sm={6} md={4}>
            <FormControl fullWidth size="small">
              <InputLabel>Resolution</InputLabel>
              <Select
                value={`${newStream.resolution?.[0]}x${newStream.resolution?.[1]}`}
                onChange={(e) => {
                  const [width, height] = e.target.value.split('x').map(Number);
                  setNewStream(prev => ({ ...prev, resolution: [width, height] }));
                }}
                label="Resolution"
              >
                <MenuItem value="1920x1080">1920x1080 (Full HD)</MenuItem>
                <MenuItem value="1280x720">1280x720 (HD)</MenuItem>
                <MenuItem value="2560x1440">2560x1440 (2K)</MenuItem>
                <MenuItem value="3840x2160">3840x2160 (4K)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12}>
            <Button
              onClick={handleAddStream}
              startIcon={<Add />}
              variant="contained"
              color="primary"
              disabled={!newStream.id || !newStream.url}
            >
              Add Stream
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Stream list */}
      <Typography variant="h6" sx={{ mt: 2 }}>
        Active Streams ({Object.keys(streams).length})
      </Typography>

      {isLoading ? (
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          height: 200,
        }}>
          <Typography color="text.secondary">Loading streams...</Typography>
        </Box>
      ) : Object.keys(streams).length === 0 ? (
        <Paper sx={{ 
          p: 4, 
          textAlign: 'center', 
          backgroundColor: 'background.paper',
        }}>
          <Typography color="text.secondary">
            No streams configured
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Add a stream using the form above
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {Object.entries(streams).map(([streamId, stream]) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={streamId}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Box sx={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    mb: 1,
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <FiberManualRecord 
                        fontSize="small" 
                        color={stream.status === StreamStatus.CONNECTED ? 'success' : 'error'}
                        sx={{ 
                          color: getStatusColor(stream.status),
                          animation: stream.status === StreamStatus.CONNECTING ? 'pulse 1s infinite' : 'none',
                          '@keyframes pulse': {
                            '0%, 100%': { opacity: 1 },
                            '50%': { opacity: 0.5 },
                          },
                        }}
                      />
                      <Typography variant="subtitle1" noWrap>
                        {stream.config.name || streamId}
                      </Typography>
                    </Box>
                    
                    <Chip
                      label={formatStatus(stream.status)}
                      size="small"
                      color={getStatusColor(stream.status)}
                    />
                  </Box>
                  
                  <Box sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Type: {stream.config.type}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      URL: {stream.config.url}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Resolution: {formatResolution(stream.config.resolution)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      FPS: {stream.fps_actual.toFixed(1)} / {stream.config.fps}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Frames: {stream.frame_count}
                    </Typography>
                  </Box>
                </CardContent>
                
                <CardActions sx={{ justifyContent: 'space-between' }}>
                  <Box>
                    <Tooltip title={stream.status === StreamStatus.CONNECTED ? 'Stop' : 'Start'} arrow>
                      <IconButton
                        onClick={() => toggleStream(streamId, stream)}
                        color={stream.status === StreamStatus.CONNECTED ? 'error' : 'primary'}
                        size="small"
                      >
                        {stream.status === StreamStatus.CONNECTED ? <Stop fontSize="small" /> : <PlayArrow fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title="Settings" arrow>
                      <IconButton color="primary" size="small">
                        <Settings fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  
                  <Tooltip title="Delete" arrow>
                    <IconButton onClick={() => deleteStream(streamId)} color="error" size="small">
                      <Delete fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};

export default StreamManager;
