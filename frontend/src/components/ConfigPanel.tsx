import React, { useEffect, useState, useCallback } from 'react';
import { Box, Typography, Paper, Grid, TextField, MenuItem, Select, FormControl, InputLabel, Switch, FormControlLabel, Button, Divider, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import { ExpandMore, Save, Refresh } from '@mui/icons-material';
import { ProcessingConfig } from '../types';
import { api } from '../services/api';

const ConfigPanel: React.FC = () => {
  const [config, setConfig] = useState<ProcessingConfig | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('processing');

  // Load configuration on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const response = await api.get('/config/processing');
        setConfig(response.data);
        
      } catch (err) {
        console.error('Error loading config:', err);
        setError('Failed to load configuration');
      } finally {
        setIsLoading(false);
      }
    };

    loadConfig();
  }, []);

  // Save configuration
  const saveConfig = useCallback(async () => {
    if (!config) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Send updated config to server
      await api.post('/config', config);
      
      // Reload to get any server-side defaults
      const response = await api.get('/config/processing');
      setConfig(response.data);
      
    } catch (err) {
      console.error('Error saving config:', err);
      setError('Failed to save configuration');
    } finally {
      setIsLoading(false);
    }
  }, [config]);

  // Reload configuration
  const reloadConfig = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await api.post('/config/reload');
      if (response.data.status === 'reloaded') {
        // Reload config
        const configResponse = await api.get('/config/processing');
        setConfig(configResponse.data);
      }
    } catch (err) {
      console.error('Error reloading config:', err);
      setError('Failed to reload configuration');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle config change
  const handleChange = useCallback((field: keyof ProcessingConfig, value: any) => {
    setConfig(prev => {
      if (!prev) return null;
      return { ...prev, [field]: value };
    });
  }, []);

  if (isLoading) {
    return (
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100%',
      }}>
        <Typography color="text.secondary">Loading configuration...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Paper sx={{ 
        p: 4, 
        textAlign: 'center', 
        backgroundColor: 'error.main',
        color: 'error.contrastText',
        height: '100%',
      }}>
        <Typography>{error}</Typography>
        <Button 
          onClick={() => setError(null)} 
          size="small" 
          variant="text" 
          sx={{ mt: 2, color: 'inherit' }}
        >
          Dismiss
        </Button>
      </Paper>
    );
  }

  if (!config) {
    return (
      <Paper sx={{ 
        p: 4, 
        textAlign: 'center', 
        backgroundColor: 'background.paper',
        height: '100%',
      }}>
        <Typography color="text.secondary">
          No configuration available
        </Typography>
      </Paper>
    );
  }

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
          Configuration
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            onClick={reloadConfig}
            startIcon={<Refresh />}
            variant="outlined"
            size="small"
            disabled={isLoading}
          >
            Reload
          </Button>
          
          <Button
            onClick={saveConfig}
            startIcon={<Save />}
            variant="contained"
            color="primary"
            size="small"
            disabled={isLoading}
          >
            Save
          </Button>
        </Box>
      </Box>

      {/* Navigation tabs */}
      <Paper sx={{ p: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Button
          variant={activeTab === 'processing' ? 'contained' : 'outlined'}
          onClick={() => setActiveTab('processing')}
          size="small"
        >
          Processing
        </Button>
        
        <Button
          variant={activeTab === 'stitching' ? 'contained' : 'outlined'}
          onClick={() => setActiveTab('stitching')}
          size="small"
        >
          Stitching
        </Button>
        
        <Button
          variant={activeTab === 'performance' ? 'contained' : 'outlined'}
          onClick={() => setActiveTab('performance')}
          size="small"
        >
          Performance
        </Button>
      </Paper>

      {/* Configuration sections */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {activeTab === 'processing' && (
          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Feature Detection</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Detector</InputLabel>
                    <Select
                      value={config.detector || 'SIFT'}
                      onChange={(e) => handleChange('detector', e.target.value)}
                      label="Detector"
                    >
                      <MenuItem value="SIFT">SIFT</MenuItem>
                      <MenuItem value="SURF">SURF</MenuItem>
                      <MenuItem value="ORB">ORB</MenuItem>
                      <MenuItem value="AKAZE">AKAZE</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Minimum Features"
                    type="number"
                    value={config.minFeatures || 1000}
                    onChange={(e) => handleChange('minFeatures', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 100, max: 10000 } }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Matcher</InputLabel>
                    <Select
                      value={config.matcher || 'FLANN'}
                      onChange={(e) => handleChange('matcher', e.target.value)}
                      label="Matcher"
                    >
                      <MenuItem value="FLANN">FLANN</MenuItem>
                      <MenuItem value="BFMatcher">BFMatcher</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Minimum Matches"
                    type="number"
                    value={config.minMatches || 50}
                    onChange={(e) => handleChange('minMatches', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 10, max: 1000 } }}
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          <Divider sx={{ my: 2 }} />

          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Frame Processing</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Frame Skip"
                    type="number"
                    value={config.frameSkip || 1}
                    onChange={(e) => handleChange('frameSkip', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 1, max: 10 } }}
                    helperText="Process every Nth frame (1 = all frames)"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Keyframe Interval (s)"
                    type="number"
                    value={config.keyframeInterval || 1.0}
                    onChange={(e) => handleChange('keyframeInterval', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 0.1, max: 10, step: 0.1 } }}
                    helperText="Seconds between keyframes"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Quality</InputLabel>
                    <Select
                      value={config.quality || 'high'}
                      onChange={(e) => handleChange('quality', e.target.value)}
                      label="Quality"
                    >
                      <MenuItem value="high">High</MenuItem>
                      <MenuItem value="medium">Medium</MenuItem>
                      <MenuItem value="low">Low</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Resolution (m/px)"
                    type="number"
                    value={config.resolution || 0.1}
                    onChange={(e) => handleChange('resolution', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 0.01, max: 1, step: 0.01 } }}
                    helperText="Meters per pixel"
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        )}

        {activeTab === 'stitching' && (
          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Stitching</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Method</InputLabel>
                    <Select
                      value={config.stitchMethod || 'homography'}
                      onChange={(e) => handleChange('stitchMethod', e.target.value)}
                      label="Method"
                    >
                      <MenuItem value="homography">Homography</MenuItem>
                      <MenuItem value="bundle_adjustment">Bundle Adjustment</MenuItem>
                      <MenuItem value="incremental">Incremental</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Confidence Threshold"
                    type="number"
                    value={config.confidenceThreshold || 0.8}
                    onChange={(e) => handleChange('confidenceThreshold', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 0, max: 1, step: 0.01 } }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Reprojection Error"
                    type="number"
                    value={config.reprojectionError || 5.0}
                    onChange={(e) => handleChange('reprojectionError', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 0, max: 50, step: 0.1 } }}
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          <Divider sx={{ my: 2 }} />

          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Tiling</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Tile Size"
                    type="number"
                    value={config.tileSize || 256}
                    onChange={(e) => handleChange('tileSize', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 64, max: 1024, step: 64 } }}
                    helperText="Pixels per tile"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Overlap (%)"
                    type="number"
                    value={config.overlap || 20}
                    onChange={(e) => handleChange('overlap', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 0, max: 50, step: 1 } }}
                    helperText="Tile overlap percentage"
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        )}

        {activeTab === 'performance' && (
          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Performance</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.useGpu || false}
                        onChange={(e) => handleChange('useGpu', e.target.checked)}
                      />
                    }
                    label="Use GPU Acceleration"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Max Memory (GB)"
                    type="number"
                    value={config.maxMemory || 8}
                    onChange={(e) => handleChange('maxMemory', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 1, max: 64, step: 1 } }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Number of Workers"
                    type="number"
                    value={config.numWorkers || 4}
                    onChange={(e) => handleChange('numWorkers', Number(e.target.value))}
                    size="small"
                    InputProps={{ inputProps: { min: 1, max: 16, step: 1 } }}
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>

          <Divider sx={{ my: 2 }} />

          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="subtitle1">Geospatial</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Coordinate System"
                    value={config.coordinateSystem || 'EPSG:4326'}
                    onChange={(e) => handleChange('coordinateSystem', e.target.value)}
                    size="small"
                    helperText="Source coordinate system (e.g., EPSG:4326 for WGS84)"
                  />
                </Grid>
                
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Target System"
                    value={config.targetSystem || 'EPSG:3857'}
                    onChange={(e) => handleChange('targetSystem', e.target.value)}
                    size="small"
                    helperText="Target coordinate system (e.g., EPSG:3857 for Web Mercator)"
                  />
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        )}
      </Box>
    </Box>
  );
};

export default ConfigPanel;
