// Map service for orthomosaic visualization

import { OrthomosaicTile, MapViewport, MapBounds, ThreeJSOrthomosaic } from '../types';
import * as THREE from 'three';

export interface MapLayer {
  id: string;
  name: string;
  visible: boolean;
  opacity: number;
  tiles: Record<string, OrthomosaicTile>;
}

export interface MapSource {
  id: string;
  type: 'orthomosaic' | 'vector' | 'raster';
  url: string;
  attribution?: string;
  minZoom: number;
  maxZoom: number;
}

export class MapService {
  private layers: Map<string, MapLayer> = new Map();
  private viewport: MapViewport = {
    center: [0, 0],
    zoom: 0,
    rotation: 0,
    pitch: 0,
  };
  private bounds: MapBounds = {
    minX: -180,
    minY: -90,
    maxX: 180,
    maxY: 90,
  };

  constructor() {
    // Initialize with default layer
    this.addLayer({
      id: 'orthomosaic',
      name: 'Orthomosaic',
      visible: true,
      opacity: 1,
      tiles: {},
    });
  }

  // ========== Layer Management ==========

  addLayer(layer: MapLayer): void {
    this.layers.set(layer.id, layer);
  }

  getLayer(layerId: string): MapLayer | undefined {
    return this.layers.get(layerId);
  }

  updateLayer(layerId: string, updates: Partial<MapLayer>): void {
    const layer = this.layers.get(layerId);
    if (layer) {
      this.layers.set(layerId, { ...layer, ...updates });
    }
  }

  removeLayer(layerId: string): void {
    this.layers.delete(layerId);
  }

  getLayers(): MapLayer[] {
    return Array.from(this.layers.values());
  }

  // ========== Viewport Management ==========

  getViewport(): MapViewport {
    return { ...this.viewport };
  }

  setViewport(viewport: MapViewport): void {
    this.viewport = { ...viewport };
  }

  updateViewport(updates: Partial<MapViewport>): void {
    this.viewport = { ...this.viewport, ...updates };
  }

  // ========== Bounds Management ==========

  getBounds(): MapBounds {
    return { ...this.bounds };
  }

  setBounds(bounds: MapBounds): void {
    this.bounds = { ...bounds };
  }

  fitBounds(bounds: MapBounds, padding: number = 0): void {
    const width = bounds.maxX - bounds.minX + padding * 2;
    const height = bounds.maxY - bounds.minY + padding * 2;
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;

    // Calculate zoom level that fits the bounds
    // This is a simplified calculation
    const worldWidth = this.bounds.maxX - this.bounds.minX;
    const worldHeight = this.bounds.maxY - this.bounds.minY;
    const zoomX = Math.log2(worldWidth / width);
    const zoomY = Math.log2(worldHeight / height);
    const zoom = Math.min(zoomX, zoomY);

    this.viewport = {
      ...this.viewport,
      center: [centerX, centerY],
      zoom,
    };
  }

  // ========== Tile Management ==========

  addTile(tile: OrthomosaicTile, layerId: string = 'orthomosaic'): void {
    const layer = this.layers.get(layerId);
    if (layer) {
      const tileKey = `${tile.z}_${tile.x}_${tile.y}`;
      layer.tiles[tileKey] = tile;
    }
  }

  getTile(z: number, x: number, y: number, layerId: string = 'orthomosaic'): OrthomosaicTile | undefined {
    const layer = this.layers.get(layerId);
    if (layer) {
      const tileKey = `${z}_${x}_${y}`;
      return layer.tiles[tileKey];
    }
    return undefined;
  }

  getTilesInViewport(layerId: string = 'orthomosaic'): OrthomosaicTile[] {
    const layer = this.layers.get(layerId);
    if (!layer) return [];

    const { center, zoom } = this.viewport;
    const [centerX, centerY] = center;

    // Calculate visible tile range based on viewport
    // This is a simplified calculation
    const tileSize = 256; // Assuming 256x256 tiles
    const scale = Math.pow(2, zoom);
    const halfViewportWidth = (window.innerWidth / 2) / scale;
    const halfViewportHeight = (window.innerHeight / 2) / scale;

    const minX = Math.floor((centerX - halfViewportWidth) / tileSize);
    const maxX = Math.ceil((centerX + halfViewportWidth) / tileSize);
    const minY = Math.floor((centerY - halfViewportHeight) / tileSize);
    const maxY = Math.ceil((centerY + halfViewportHeight) / tileSize);

    const visibleTiles: OrthomosaicTile[] = [];
    const currentZoom = Math.round(zoom);

    for (let x = minX; x <= maxX; x++) {
      for (let y = minY; y <= maxY; y++) {
        const tile = this.getTile(currentZoom, x, y, layerId);
        if (tile) {
          visibleTiles.push(tile);
        }
      }
    }

    return visibleTiles;
  }

  removeTile(z: number, x: number, y: number, layerId: string = 'orthomosaic'): void {
    const layer = this.layers.get(layerId);
    if (layer) {
      const tileKey = `${z}_${x}_${y}`;
      delete layer.tiles[tileKey];
    }
  }

  clearTiles(layerId: string = 'orthomosaic'): void {
    const layer = this.layers.get(layerId);
    if (layer) {
      layer.tiles = {};
    }
  }

  // ========== Three.js Integration ==========

  createThreeJSOrthomosaic(tiles: OrthomosaicTile[]): ThreeJSOrthomosaic | null {
    if (tiles.length === 0) return null;

    // For now, assume tiles form a single orthomosaic
    // In production, you'd need to calculate the layout
    const firstTile = tiles[0];
    const width = 256 * tiles.length; // Simplified
    const height = 256;

    return {
      image: null, // Would be set when texture is loaded
      width,
      height,
      position: [0, 0, 0],
      rotation: [0, 0, 0],
      scale: [1, 1, 1],
    };
  }

  // ========== Coordinate Conversion ==========

  worldToPixel(coords: [number, number], zoom: number): [number, number] {
    // Convert world coordinates to pixel coordinates at given zoom level
    const scale = Math.pow(2, zoom);
    const worldSize = 256 * scale;
    const halfWorld = worldSize / 2;

    const x = (coords[0] + 180) / 360 * worldSize - halfWorld;
    const y = halfWorld - (coords[1] + 90) / 180 * worldSize;

    return [x, y];
  }

  pixelToWorld(pixel: [number, number], zoom: number): [number, number] {
    // Convert pixel coordinates to world coordinates
    const scale = Math.pow(2, zoom);
    const worldSize = 256 * scale;
    const halfWorld = worldSize / 2;

    const lon = (pixel[0] + halfWorld) / worldSize * 360 - 180;
    const lat = 90 - (pixel[1] + halfWorld) / worldSize * 180;

    return [lon, lat];
  }

  tileToWorld(z: number, x: number, y: number): [number, number] {
    // Convert tile coordinates to world coordinates
    const n = Math.PI - (2.0 * Math.PI * y) / Math.pow(2, z);
    const lon = (x / Math.pow(2, z)) * 360 - 180;
    const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));

    return [lon, lat];
  }

  worldToTile(coords: [number, number], zoom: number): [number, number, number] {
    // Convert world coordinates to tile coordinates
    const latRad = (coords[1] * Math.PI) / 180.0;
    const n = Math.pow(2, zoom);
    const x = ((coords[0] + 180.0) / 360.0) * n;
    const y = (1.0 - Math.log(Math.tan(latRad) + (1 / Math.cos(latRad))) / Math.PI) / 2.0 * n;

    return [Math.floor(x), Math.floor(y), zoom];
  }
}

// Singleton instance
export const mapService = new MapService();

export default mapService;
