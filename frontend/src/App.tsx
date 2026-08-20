import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Box, CssBaseline, ThemeProvider, createTheme, AppBar, Toolbar, Typography, IconButton, Drawer, List, ListItem, ListItemIcon, ListItemText, Divider } from '@mui/material';
import { Menu as MenuIcon, Map as MapIcon, Videocam as VideocamIcon, Timeline as TimelineIcon, Settings as SettingsIcon } from '@mui/icons-material';
import MapViewer from './components/MapViewer';
import StreamManager from './components/StreamManager';
import Timeline from './components/Timeline';
import ConfigPanel from './components/ConfigPanel';
import { wsClient } from './services/api';
import { mapService } from './services/mapService';
import { timeService } from './services/timeService';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#9c27b0',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

// Drawer width
const drawerWidth = 240;

const App: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [activePage, setActivePage] = useState('map');

  // Connect to WebSocket on mount
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';
    wsClient.connect(wsUrl);

    // Setup connection listener
    const handleConnectionChange = (connected: boolean) => {
      setIsConnected(connected);
    };

    wsClient.onConnectionChange(handleConnectionChange);

    // Setup message listeners
    wsClient.onMessage('frame_update', (data) => {
      console.log('Frame update:', data);
    });

    wsClient.onMessage('orthomosaic_update', (data) => {
      console.log('Orthomosaic update:', data);
    });

    wsClient.onMessage('tile_update', (data) => {
      console.log('Tile update:', data);
    });

    wsClient.onMessage('status_update', (data) => {
      console.log('Status update:', data);
    });

    // Cleanup on unmount
    return () => {
      wsClient.offConnectionChange(handleConnectionChange);
      wsClient.disconnect();
    };
  }, []);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const drawer = (
    <div>
      <Toolbar />
      <Divider />
      <List>
        <ListItem
          button
          selected={activePage === 'map'}
          onClick={() => setActivePage('map')}
          component={Link}
          to="/"
        >
          <ListItemIcon>
            <MapIcon />
          </ListItemIcon>
          <ListItemText primary="Map Viewer" />
        </ListItem>
        <ListItem
          button
          selected={activePage === 'streams'}
          onClick={() => setActivePage('streams')}
          component={Link}
          to="/streams"
        >
          <ListItemIcon>
            <VideocamIcon />
          </ListItemIcon>
          <ListItemText primary="Streams" />
        </ListItem>
        <ListItem
          button
          selected={activePage === 'timeline'}
          onClick={() => setActivePage('timeline')}
          component={Link}
          to="/timeline"
        >
          <ListItemIcon>
            <TimelineIcon />
          </ListItemIcon>
          <ListItemText primary="Timeline" />
        </ListItem>
        <ListItem
          button
          selected={activePage === 'config'}
          onClick={() => setActivePage('config')}
          component={Link}
          to="/config"
        >
          <ListItemIcon>
            <SettingsIcon />
          </ListItemIcon>
          <ListItemText primary="Configuration" />
        </ListItem>
      </List>
      <Divider />
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          Status: {isConnected ? 'Connected' : 'Disconnected'}
        </Typography>
      </Box>
    </div>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        <AppBar
          position="fixed"
          sx={{
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            ml: { sm: `${drawerWidth}px` },
          }}
        >
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { sm: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap component="div">
              Disaster Map
            </Typography>
          </Toolbar>
        </AppBar>
        <Box
          component="nav"
          sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
          aria-label="mailbox folders"
        >
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={handleDrawerToggle}
            ModalProps={{
              keepMounted: true, // Better open performance on mobile.
            }}
            sx={{
              display: { xs: 'block', sm: 'none' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
          >
            {drawer}
          </Drawer>
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: 'none', sm: 'block' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
            open
          >
            {drawer}
          </Drawer>
        </Box>
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            width: { sm: `calc(100% - ${drawerWidth}px)` },
          }}
        >
          <Toolbar />
          <Router>
            <Routes>
              <Route path="/" element={<MapViewer />} />
              <Route path="/streams" element={<StreamManager />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/config" element={<ConfigPanel />} />
            </Routes>
          </Router>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
