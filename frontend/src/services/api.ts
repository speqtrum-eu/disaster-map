// API service for communicating with the backend

import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { io, Socket } from 'socket.io-client';
import {
  StreamConfig,
  VideoStream,
  Frame,
  OrthomosaicTile,
  APIStats,
  WebSocketMessage,
  FrameUpdateMessage,
  OrthomosaicUpdateMessage,
  TileUpdateMessage,
  StatusUpdateMessage,
} from '../types';

// ========== Configuration ==========
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';

// ========== HTTP API Client ==========
export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptors
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    console.error('API Error:', error.message);
    return Promise.reject(error);
  }
);

// ========== API Functions ==========

// Status endpoints
export const getStatus = async (): Promise<{ status: string; timestamp: number }> => {
  const response = await api.get('/status');
  return response.data;
};

export const getStats = async (): Promise<APIStats> => {
  const response = await api.get('/stats');
  return response.data;
};

// Stream endpoints
export const listStreams = async (): Promise<Record<string, VideoStream>> => {
  const response = await api.get('/streams');
  return response.data;
};

export const getStream = async (streamId: string): Promise<VideoStream> => {
  const response = await api.get(`/streams/${streamId}`);
  return response.data;
};

export const startStream = async (streamId: string): Promise<{ status: string; streamId: string }> => {
  const response = await api.post(`/streams/${streamId}/start`);
  return response.data;
};

export const stopStream = async (streamId: string): Promise<{ status: string; streamId: string }> => {
  const response = await api.post(`/streams/${streamId}/stop`);
  return response.data;
};

export const addStream = async (streamConfig: StreamConfig): Promise<{ status: string; streamId: string }> => {
  const response = await api.post('/streams', streamConfig);
  return response.data;
};

export const deleteStream = async (streamId: string): Promise<{ status: string; streamId: string }> => {
  const response = await api.delete(`/streams/${streamId}`);
  return response.data;
};

// Orthomosaic endpoints
export const getOrthomosaic = async (): Promise<{
  resolution: [number, number];
  preview: string;
  timestamp: number;
}> => {
  const response = await api.get('/orthomosaic');
  return response.data;
};

export const getStreamOrthomosaic = async (streamId: string): Promise<{
  streamId: string;
  resolution: [number, number];
  preview: string;
  timestamp: number;
}> => {
  const response = await api.get(`/orthomosaic/${streamId}`);
  return response.data;
};

export const downloadOrthomosaic = async (): Promise<Blob> => {
  const response = await api.get('/orthomosaic/download', {
    responseType: 'blob',
  });
  return response.data;
};

// Tile endpoints
export const listTiles = async (): Promise<
  Array<{ x: number; y: number; z: number; timestamp: number }>
> => {
  const response = await api.get('/tiles');
  return response.data;
};

export const getTile = async (z: number, x: number, y: number): Promise<{
  x: number;
  y: number;
  z: number;
  data: string;
  timestamp: number;
}> => {
  const response = await api.get(`/tiles/${z}/${x}/${y}`);
  return response.data;
};

export const getTileImage = async (z: number, x: number, y: number): Promise<Blob> => {
  const response = await api.get(`/tiles/${z}/${x}/${y}/image`, {
    responseType: 'blob',
  });
  return response.data;
};

// Config endpoints
export const getConfig = async (): Promise<any> => {
  const response = await api.get('/config');
  return response.data;
};

export const getProcessingConfig = async (): Promise<any> => {
  const response = await api.get('/config/processing');
  return response.data;
};

export const getStreamsConfig = async (): Promise<Record<string, StreamConfig>> => {
  const response = await api.get('/config/streams');
  return response.data;
};

export const reloadConfig = async (): Promise<{ status: string }> => {
  const response = await api.post('/config/reload');
  return response.data;
};

// ========== WebSocket Client ==========
class WebSocketClient {
  private socket: Socket | null = null;
  private listeners: Map<string, (message: any) => void> = new Map();
  private connectionListeners: Array<(connected: boolean) => void> = [];
  private reconnectInterval: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 3000; // 3 seconds

  connect(url: string = WS_BASE_URL): void {
    if (this.socket && this.socket.connected) {
      console.log('Already connected');
      return;
    }

    console.log(`Connecting to WebSocket at ${url}...`);

    this.socket = io(url, {
      reconnection: false,
      transports: ['websocket'],
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.notifyConnectionListeners(true);
    });

    this.socket?.on('disconnect', () => {
      console.log('WebSocket disconnected');
      this.notifyConnectionListeners(false);
      this.scheduleReconnect(url);
    });

    this.socket?.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error.message);
      this.notifyConnectionListeners(false);
      this.scheduleReconnect(url);
    });

    this.socket?.on('error', (error) => {
      console.error('WebSocket error:', error.message);
    });

    // Handle different message types
    this.socket?.on('frame_update', (data: FrameUpdateMessage['data']) => {
      this.notifyListeners('frame_update', data);
    });

    this.socket?.on('orthomosaic_update', (data: OrthomosaicUpdateMessage['data']) => {
      this.notifyListeners('orthomosaic_update', data);
    });

    this.socket?.on('tile_update', (data: TileUpdateMessage['data']) => {
      this.notifyListeners('tile_update', data);
    });

    this.socket?.on('status_update', (data: StatusUpdateMessage['data']) => {
      this.notifyListeners('status_update', data);
    });

    this.socket?.on('ack', (data: any) => {
      // Acknowledgment, can be ignored or logged
    });

    this.socket?.on('error', (data: any) => {
      this.notifyListeners('error', data);
    });
  }

  private scheduleReconnect(url: string): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting in ${this.reconnectDelay / 1000} seconds... (attempt ${this.reconnectAttempts})`);

    this.reconnectInterval = window.setTimeout(() => {
      this.connect(url);
    }, this.reconnectDelay);
  }

  disconnect(): void {
    if (this.reconnectInterval) {
      window.clearTimeout(this.reconnectInterval);
      this.reconnectInterval = null;
    }

    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }

    this.reconnectAttempts = 0;
    this.notifyConnectionListeners(false);
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }

  onMessage(type: string, callback: (message: any) => void): void {
    this.listeners.set(type, callback);
  }

  offMessage(type: string): void {
    this.listeners.delete(type);
  }

  private notifyListeners(type: string, data: any): void {
    const callback = this.listeners.get(type);
    if (callback) {
      callback(data);
    }
  }

  onConnectionChange(callback: (connected: boolean) => void): void {
    this.connectionListeners.push(callback);
  }

  offConnectionChange(callback: (connected: boolean) => void): void {
    this.connectionListeners = this.connectionListeners.filter((cb) => cb !== callback);
  }

  private notifyConnectionListeners(connected: boolean): void {
    this.connectionListeners.forEach((callback) => callback(connected));
  }

  send(message: WebSocketMessage): void {
    if (this.socket && this.socket.connected) {
      this.socket.emit(message.type, message.data);
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }
}

// Singleton WebSocket client instance
export const wsClient = new WebSocketClient();

// ========== Utility Functions ==========

export const sleep = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

export const retry = async <T>(
  fn: () => Promise<T>,
  maxAttempts: number = 3,
  delay: number = 1000
): Promise<T> => {
  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxAttempts) {
        await sleep(delay);
      }
    }
  }

  throw lastError;
};

export default {
  api,
  wsClient,
  getStatus,
  getStats,
  listStreams,
  getStream,
  startStream,
  stopStream,
  addStream,
  deleteStream,
  getOrthomosaic,
  getStreamOrthomosaic,
  downloadOrthomosaic,
  listTiles,
  getTile,
  getTileImage,
  getConfig,
  getProcessingConfig,
  getStreamsConfig,
  reloadConfig,
  sleep,
  retry,
};
