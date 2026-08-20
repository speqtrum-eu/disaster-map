import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, OrthographicCamera, PerspectiveCamera, Environment } from '@react-three/drei';
import { Box, Typography, Paper, Slider, IconButton, Tooltip } from '@mui/material';
import { Navigation as NavigationIcon, ZoomIn, ZoomOut, Layers as LayersIcon, MyLocation } from '@mui/icons-material';
import { OrthomosaicTile } from '../types';
import { api, wsClient } from '../services/api';
import { mapService } from '../services/mapService';

// Three.js component for displaying orthomosaic
interface OrthomosaicPlaneProps {
  image: HTMLImageElement | null;
  width: number;
  height: number;
}

const OrthomosaicPlane: React.FC<OrthomosaicPlaneProps> = ({ image, width, height }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useEffect(() => {
    if (image && meshRef.current) {
      const texture = new THREE.Texture(image);
      texture.needsUpdate = true;
      texture.colorSpace = THREE.SRGBColorSpace;
      
      const material = new THREE.MeshBasicMaterial({ 
        map: texture,
        transparent: true,
      });
      
      meshRef.current.material = material;
      
      // Cleanup on unmount
      return () => {
        texture.dispose();
        material.dispose();
      };
    }
  }, [image]);

  if (!image) return null;

  return (
    <mesh ref={meshRef} position={[0, 0, 0]}>
      <planeGeometry args={[width, height]} />
      <meshBasicMaterial color="white" />
    </mesh>
  );
};

// Camera controller with zoom limits
const CameraController: React.FC<{ 
  minZoom: number; 
  maxZoom: number; 
  enablePan: boolean; 
  enableZoom: boolean; 
  enableRotate: boolean; 
}> = ({ minZoom, maxZoom, enablePan, enableZoom, enableRotate }) => {
  const { camera, gl } = useThree();
  
  useFrame(() => {
    // Update camera based on viewport
  });

  return (
    <OrbitControls
      args={[camera, gl.domElement]}
      enablePan={enablePan}
      enableZoom={enableZoom}
      enableRotate={enableRotate}
      minZoom={minZoom}
      maxZoom={maxZoom}
      minPolarAngle={0}
      maxPolarAngle={Math.PI / 2}
    />
  );
};

// Main MapViewer component
const MapViewer: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [orthomosaic, setOrthomosaic] = useState<HTMLImageElement | null>(null);
  const [zoom, setZoom] = useState<number>(0);
  const [showControls, setShowControls] = useState<boolean>(true);
  const [cameraMode, setCameraMode] = useState<'perspective' | 'orthographic'>('perspective');
  const [tiles, setTiles] = useState<OrthomosaicTile[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Load orthomosaic on mount
  useEffect(() => {
    const loadOrthomosaic = async () => {
      try {
        setIsLoading(true);
        
        // Get orthomosaic from API
        const response = await api.get('/orthomosaic');
        const { preview } = response.data;
        
        // Create image element
        const img = new Image();
        img.onload = () => {
          setOrthomosaic(img);
          setIsLoading(false);
        };
        img.onerror = () => {
          setIsLoading(false);
        };
        img.src = `data:image/jpeg;base64,${preview}`;
        
        // Also get tiles
        const tilesResponse = await api.get('/tiles');
        setTiles(tilesResponse.data);
        
        // Setup WebSocket listener for updates
        wsClient.onMessage('orthomosaic_update', (data) => {
          console.log('Orthomosaic updated:', data);
          // Reload orthomosaic
          loadOrthomosaic();
        });
        
        wsClient.onMessage('tile_update', (data) => {
          console.log('Tiles updated:', data);
          // Update tiles
          setTiles(data.tiles);
        });
        
      } catch (error) {
        console.error('Error loading orthomosaic:', error);
        setIsLoading(false);
      }
    };

    loadOrthomosaic();

    // Cleanup WebSocket listeners
    return () => {
      wsClient.offMessage('orthomosaic_update');
      wsClient.offMessage('tile_update');
    };
  }, []);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case '+':
          setZoom(prev => Math.min(prev + 0.5, 10));
          break;
        case '-':
          setZoom(prev => Math.max(prev - 0.5, -10));
          break;
        case 'r':
          setZoom(0);
          break;
        case 'c':
          setShowControls(prev => !prev);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Camera controls
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.5, 10));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.5, -10));
  };

  const handleResetView = () => {
    setZoom(0);
  };

  const handleFitToWindow = () => {
    // Fit orthomosaic to window
    setZoom(0);
  };

  const toggleCameraMode = () => {
    setCameraMode(prev => prev === 'perspective' ? 'orthographic' : 'perspective');
  };

  // Calculate camera position based on zoom
  const cameraPosition = useMemo(() => {
    const distance = Math.pow(1.5, -zoom);
    return [0, 0, distance];
  }, [zoom]);

  // Calculate orthomosaic dimensions for Three.js
  const orthoDimensions = useMemo(() => {
    if (!orthomosaic) return { width: 10, height: 10 };
    
    const aspect = orthomosaic.width / orthomosaic.height;
    const scale = Math.max(orthomosaic.width, orthomosaic.height) / 10;
    
    return {
      width: 10 * aspect,
      height: 10,
    };
  }, [orthomosaic]);

  return (
    <Box sx={{ 
      width: '100%', 
      height: '100%', 
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Map container */}
      <Box sx={{ 
        flex: 1, 
        position: 'relative', 
        overflow: 'hidden',
        backgroundColor: '#1e1e1e',
      }}>
        {isLoading ? (
          <Box sx={{ 
            width: '100%', 
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Typography variant="h6" color="text.secondary">
              Loading orthomosaic...
            </Typography>
          </Box>
        ) : (
          <Canvas camera={{ 
            position: cameraPosition,
            fov: 50,
            near: 0.1,
            far: 1000,
          }}>
            <ambientLight intensity={0.5} />
            <pointLight position={[10, 10, 10]} />
            
            {cameraMode === 'perspective' ? (
              <PerspectiveCamera makeDefault position={cameraPosition} fov={50} />
            ) : (
              <OrthographicCamera 
                makeDefault 
                position={[0, 0, 10]} 
                zoom={1}
                near={0.1}
                far={1000}
              />
            )}
            
            <CameraController
              minZoom={-10}
              maxZoom={10}
              enablePan={true}
              enableZoom={true}
              enableRotate={false}
            />
            
            {/* Orthomosaic plane */}
            {orthomosaic && (
              <OrthomosaicPlane 
                image={orthomosaic} 
                width={orthoDimensions.width} 
                height={orthoDimensions.height} 
              />
            )}
            
            {/* Grid helper */}
            <gridHelper args={[100, 100, '#444', '#666']} />
            
            {/* Axes helper */}
            <axesHelper args={[5]} />
          </Canvas>
        )}
      </Box>

      {/* Controls overlay */}
      {showControls && (
        <Paper 
          elevation={3} 
          sx={{
            position: 'absolute',
            bottom: 16,
            left: 16,
            right: 16,
            padding: 2,
            display: 'flex',
            gap: 1,
            alignItems: 'center',
            justifyContent: 'center',
            flexWrap: 'wrap',
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(10px)',
          }}
        >
          <Tooltip title="Zoom In" arrow>
            <IconButton onClick={handleZoomIn} size="small" color="primary">
              <ZoomIn fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Zoom Out" arrow>
            <IconButton onClick={handleZoomOut} size="small" color="primary">
              <ZoomOut fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Reset View" arrow>
            <IconButton onClick={handleResetView} size="small" color="primary">
              <MyLocation fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Fit to Window" arrow>
            <IconButton onClick={handleFitToWindow} size="small" color="primary">
              <NavigationIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Tooltip title={cameraMode === 'perspective' ? 'Orthographic View' : 'Perspective View'} arrow>
            <IconButton onClick={toggleCameraMode} size="small" color="primary">
              <LayersIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Box sx={{ flex: 1, mx: 2 }}>
            <Slider
              value={zoom}
              onChange={(e, value) => setZoom(value as number)}
              min={-10}
              max={10}
              step={0.1}
              size="small"
              sx={{ color: 'primary.main' }}
            />
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mx: 1 }}>
            Zoom: {zoom.toFixed(1)}
          </Typography>
          
          {orthomosaic && (
            <Typography variant="body2" color="text.secondary" sx={{ mx: 1 }}>
              Size: {orthomosaic.width}x{orthomosaic.height}
            </Typography>
          )}
        </Paper>
      )}

      {/* Stats overlay */}
      <Paper 
        elevation={3} 
        sx={{
          position: 'absolute',
          top: 16,
          right: 16,
          padding: 2,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Tiles: {tiles.length}
        </Typography>
      </Paper>
    </Box>
  );
};

export default MapViewer;
