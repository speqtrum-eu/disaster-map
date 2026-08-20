// Time service for time-axis navigation

import { TimeRange, TimelineMarker } from '../types';

export interface TimeWindow {
  start: number;
  end: number;
  duration: number;
}

export interface PlaybackState {
  isPlaying: boolean;
  speed: number;
  currentTime: number;
}

export class TimeService {
  private markers: TimelineMarker[] = [];
  private currentTime: number = Date.now() / 1000;
  private playbackSpeed: number = 1.0; // 1x = real-time
  private isPlaying: boolean = false;
  private timeWindows: TimeWindow[] = [];
  private animationFrame: number | null = null;
  private lastUpdateTime: number = 0;

  // ========== Time Range Management ==========

  setTimeRange(range: TimeRange): void {
    this.timeWindows = [{
      start: range.start,
      end: range.end,
      duration: range.end - range.start,
    }];
  }

  addTimeWindow(window: TimeWindow): void {
    this.timeWindows.push(window);
    // Sort by start time
    this.timeWindows.sort((a, b) => a.start - b.start);
  }

  getTimeWindows(): TimeWindow[] {
    return [...this.timeWindows];
  }

  getTimeRange(): TimeRange | null {
    if (this.timeWindows.length === 0) return null;
    
    // For now, return the first window
    // In production, you might want to merge windows or select one
    const window = this.timeWindows[0];
    return {
      start: window.start,
      end: window.end,
    };
  }

  // ========== Current Time Management ==========

  getCurrentTime(): number {
    return this.currentTime;
  }

  setCurrentTime(timestamp: number): void {
    this.currentTime = this.clampTime(timestamp);
  }

  clampTime(timestamp: number): number {
    const range = this.getTimeRange();
    if (!range) return timestamp;

    return Math.max(range.start, Math.min(range.end, timestamp));
  }

  // ========== Playback Control ==========

  getPlaybackState(): PlaybackState {
    return {
      isPlaying: this.isPlaying,
      speed: this.playbackSpeed,
      currentTime: this.currentTime,
    };
  }

  setPlaybackSpeed(speed: number): void {
    this.playbackSpeed = Math.max(0.1, Math.min(10, speed));
  }

  togglePlayback(): void {
    this.isPlaying = !this.isPlaying;
    
    if (this.isPlaying) {
      this.startPlayback();
    } else {
      this.stopPlayback();
    }
  }

  startPlayback(): void {
    if (this.isPlaying) return;
    
    this.isPlaying = true;
    this.lastUpdateTime = performance.now();
    this.playbackLoop();
  }

  stopPlayback(): void {
    this.isPlaying = false;
    
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  }

  private playbackLoop(): void {
    if (!this.isPlaying) return;

    const now = performance.now();
    const deltaTime = (now - this.lastUpdateTime) / 1000; // Convert to seconds
    this.lastUpdateTime = now;

    // Update current time based on playback speed
    const range = this.getTimeRange();
    if (range) {
      const newTime = this.currentTime + deltaTime * this.playbackSpeed;
      this.currentTime = this.clampTime(newTime);
    }

    // Continue loop
    this.animationFrame = requestAnimationFrame(() => this.playbackLoop());
  }

  // ========== Timeline Markers ==========

  addMarker(marker: TimelineMarker): void {
    this.markers.push(marker);
    // Sort by timestamp
    this.markers.sort((a, b) => a.timestamp - b.timestamp);
  }

  removeMarker(markerId: string): void {
    this.markers = this.markers.filter((m) => m.id !== markerId);
  }

  getMarkers(): TimelineMarker[] {
    return [...this.markers];
  }

  getMarkersInRange(range: TimeRange): TimelineMarker[] {
    return this.markers.filter(
      (m) => m.timestamp >= range.start && m.timestamp <= range.end
    );
  }

  // ========== Time Formatting ==========

  formatTimestamp(timestamp: number, format: 'date' | 'time' | 'datetime' = 'datetime'): string {
    const date = new Date(timestamp * 1000);

    switch (format) {
      case 'date':
        return date.toLocaleDateString();
      case 'time':
        return date.toLocaleTimeString();
      case 'datetime':
      default:
        return date.toLocaleString();
    }
  }

  formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  }

  // ========== Time Navigation ==========

  goToStart(): void {
    const range = this.getTimeRange();
    if (range) {
      this.currentTime = range.start;
    }
  }

  goToEnd(): void {
    const range = this.getTimeRange();
    if (range) {
      this.currentTime = range.end;
    }
  }

  goToPreviousMarker(): void {
    const currentIndex = this.markers.findIndex(
      (m) => m.timestamp <= this.currentTime
    );
    
    if (currentIndex > 0) {
      this.currentTime = this.markers[currentIndex - 1].timestamp;
    } else if (this.markers.length > 0) {
      this.currentTime = this.markers[0].timestamp;
    }
  }

  goToNextMarker(): void {
    const currentIndex = this.markers.findIndex(
      (m) => m.timestamp >= this.currentTime
    );

    if (currentIndex < this.markers.length - 1) {
      this.currentTime = this.markers[currentIndex + 1].timestamp;
    } else if (this.markers.length > 0) {
      this.currentTime = this.markers[this.markers.length - 1].timestamp;
    }
  }

  // ========== Time Window Management ==========

  setTimeWindow(start: number, end: number): void {
    this.timeWindows = [{
      start,
      end,
      duration: end - start,
    }];
    
    // Clamp current time to new window
    this.currentTime = this.clampTime(this.currentTime);
  }

  extendTimeWindow(duration: number): void {
    if (this.timeWindows.length === 0) return;

    const window = this.timeWindows[0];
    const newEnd = window.end + duration;
    
    this.timeWindows = [{
      start: window.start,
      end: newEnd,
      duration: newEnd - window.start,
    }];
  }

  shiftTimeWindow(duration: number): void {
    if (this.timeWindows.length === 0) return;

    const window = this.timeWindows[0];
    
    this.timeWindows = [{
      start: window.start + duration,
      end: window.end + duration,
      duration: window.duration,
    }];
    
    // Shift current time as well
    this.currentTime = this.clampTime(this.currentTime + duration);
  }

  // ========== Utility Methods ==========

  getTimeProgress(): number {
    const range = this.getTimeRange();
    if (!range) return 0;

    return ((this.currentTime - range.start) / (range.end - range.start)) * 100;
  }

  getTimeRemaining(): number {
    const range = this.getTimeRange();
    if (!range) return 0;

    return range.end - this.currentTime;
  }

  getTimeElapsed(): number {
    const range = this.getTimeRange();
    if (!range) return 0;

    return this.currentTime - range.start;
  }
}

// Singleton instance
export const timeService = new TimeService();

export default timeService;
