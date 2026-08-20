"""
Time-series database for orthomosaic history
"""

import os
import json
import sqlite3
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import threading

from ..core.models import OrthomosaicTile, Frame
from ..core.utils import get_logger, ensure_directory, timestamp_now

logger = get_logger("storage.time_series_db")


@dataclass
class OrthomosaicRecord:
    """Record of an orthomosaic at a point in time"""
    
    id: str = ""
    timestamp: float = 0.0  # Unix timestamp
    duration: float = 0.0  # Duration of this orthomosaic (seconds)
    frame_count: int = 0  # Number of frames used
    keyframe_count: int = 0  # Number of keyframes used
    resolution: Tuple[int, int] = (0, 0)  # Resolution of orthomosaic
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # (min_x, min_y, max_x, max_y)
    gps_center: Tuple[float, float] = (0.0, 0.0)  # (lat, lon) of center
    tile_count: int = 0  # Number of tiles
    file_path: str = ""  # Path to saved orthomosaic
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "frame_count": self.frame_count,
            "keyframe_count": self.keyframe_count,
            "resolution": list(self.resolution),
            "bounds": list(self.bounds),
            "gps_center": list(self.gps_center),
            "tile_count": self.tile_count,
            "file_path": self.file_path,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrthomosaicRecord":
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", 0.0),
            duration=data.get("duration", 0.0),
            frame_count=data.get("frame_count", 0),
            keyframe_count=data.get("keyframe_count", 0),
            resolution=tuple(data.get("resolution", [0, 0])),
            bounds=tuple(data.get("bounds", [0.0, 0.0, 0.0, 0.0])),
            gps_center=tuple(data.get("gps_center", [0.0, 0.0])),
            tile_count=data.get("tile_count", 0),
            file_path=data.get("file_path", ""),
            metadata=data.get("metadata", {}),
        )


class TimeSeriesDB:
    """
    SQLite database for storing orthomosaic time-series data
    """
    
    def __init__(self, db_path: str = "data/time_series.db"):
        self._db_path = Path(db_path)
        ensure_directory(self._db_path.parent)
        self._lock = threading.Lock()
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database schema"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                # Create orthomosaics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS orthomosaics (
                        id TEXT PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        duration REAL DEFAULT 0.0,
                        frame_count INTEGER DEFAULT 0,
                        keyframe_count INTEGER DEFAULT 0,
                        width INTEGER DEFAULT 0,
                        height INTEGER DEFAULT 0,
                        min_x REAL DEFAULT 0.0,
                        min_y REAL DEFAULT 0.0,
                        max_x REAL DEFAULT 0.0,
                        max_y REAL DEFAULT 0.0,
                        gps_lat REAL DEFAULT 0.0,
                        gps_lon REAL DEFAULT 0.0,
                        tile_count INTEGER DEFAULT 0,
                        file_path TEXT,
                        metadata TEXT,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """)
                
                # Create index on timestamp
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_orthomosaics_timestamp 
                    ON orthomosaics(timestamp)
                """)
                
                # Create frames table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS frames (
                        id TEXT PRIMARY KEY,
                        orthomosaic_id TEXT,
                        stream_id TEXT,
                        timestamp REAL NOT NULL,
                        frame_number INTEGER DEFAULT 0,
                        gps_lat REAL,
                        gps_lon REAL,
                        gps_alt REAL,
                        resolution_width INTEGER,
                        resolution_height INTEGER,
                        FOREIGN KEY(orthomosaic_id) REFERENCES orthomosaics(id)
                    )
                """)
                
                # Create tiles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tiles (
                        id TEXT PRIMARY KEY,
                        orthomosaic_id TEXT,
                        z INTEGER NOT NULL,
                        x INTEGER NOT NULL,
                        y INTEGER NOT NULL,
                        file_path TEXT,
                        FOREIGN KEY(orthomosaic_id) REFERENCES orthomosaics(id)
                    )
                """)
                
                conn.commit()
                logger.info(f"Initialized time-series database at {self._db_path}")
                
            except Exception as e:
                logger.error(f"Error initializing database: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def save_orthomosaic(self, record: OrthomosaicRecord) -> bool:
        """Save an orthomosaic record"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO orthomosaics 
                    (id, timestamp, duration, frame_count, keyframe_count, 
                     width, height, min_x, min_y, max_x, max_y, 
                     gps_lat, gps_lon, tile_count, file_path, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.timestamp,
                    record.duration,
                    record.frame_count,
                    record.keyframe_count,
                    record.resolution[0],
                    record.resolution[1],
                    record.bounds[0],
                    record.bounds[1],
                    record.bounds[2],
                    record.bounds[3],
                    record.gps_center[0],
                    record.gps_center[1],
                    record.tile_count,
                    record.file_path,
                    json.dumps(record.metadata),
                ))
                
                conn.commit()
                logger.debug(f"Saved orthomosaic record: {record.id}")
                return True
                
            except Exception as e:
                logger.error(f"Error saving orthomosaic: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def get_orthomosaic(self, orthomosaic_id: str) -> Optional[OrthomosaicRecord]:
        """Get an orthomosaic record by ID"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT * FROM orthomosaics WHERE id = ?
                """, (orthomosaic_id,))
                
                row = cursor.fetchone()
                if row is None:
                    return None
                
                return OrthomosaicRecord(
                    id=row[0],
                    timestamp=row[1],
                    duration=row[2],
                    frame_count=row[3],
                    keyframe_count=row[4],
                    resolution=(row[5], row[6]),
                    bounds=(row[7], row[8], row[9], row[10]),
                    gps_center=(row[11], row[12]),
                    tile_count=row[13],
                    file_path=row[14] if row[14] else "",
                    metadata=json.loads(row[15]) if row[15] else {},
                )
                
            except Exception as e:
                logger.error(f"Error getting orthomosaic: {e}")
                return None
            finally:
                conn.close()
    
    def list_orthomosaics(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[OrthomosaicRecord]:
        """List orthomosaic records in time range"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                query = "SELECT * FROM orthomosaics"
                params = []
                
                if start_time is not None or end_time is not None:
                    query += " WHERE"
                    conditions = []
                    if start_time is not None:
                        conditions.append(" timestamp >= ?")
                        params.append(start_time)
                    if end_time is not None:
                        conditions.append(" timestamp <= ?")
                        params.append(end_time)
                    query += " AND ".join(conditions)
                
                query += " ORDER BY timestamp DESC"
                if limit is not None:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, tuple(params))
                
                records = []
                for row in cursor.fetchall():
                    record = OrthomosaicRecord(
                        id=row[0],
                        timestamp=row[1],
                        duration=row[2],
                        frame_count=row[3],
                        keyframe_count=row[4],
                        resolution=(row[5], row[6]),
                        bounds=(row[7], row[8], row[9], row[10]),
                        gps_center=(row[11], row[12]),
                        tile_count=row[13],
                        file_path=row[14] if row[14] else "",
                        metadata=json.loads(row[15]) if row[15] else {},
                    )
                    records.append(record)
                
                return records
                
            except Exception as e:
                logger.error(f"Error listing orthomosaics: {e}")
                return []
            finally:
                conn.close()
    
    def delete_orthomosaic(self, orthomosaic_id: str) -> bool:
        """Delete an orthomosaic record and its related data"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                # Delete related frames
                cursor.execute("""
                    DELETE FROM frames WHERE orthomosaic_id = ?
                """, (orthomosaic_id,))
                
                # Delete related tiles
                cursor.execute("""
                    DELETE FROM tiles WHERE orthomosaic_id = ?
                """, (orthomosaic_id,))
                
                # Delete orthomosaic
                cursor.execute("""
                    DELETE FROM orthomosaics WHERE id = ?
                """, (orthomosaic_id,))
                
                conn.commit()
                logger.info(f"Deleted orthomosaic: {orthomosaic_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error deleting orthomosaic: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def save_frame(self, frame: Frame, orthomosaic_id: str) -> bool:
        """Save a frame record"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO frames 
                    (id, orthomosaic_id, stream_id, timestamp, frame_number,
                     gps_lat, gps_lon, gps_alt, resolution_width, resolution_height)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    frame.id,
                    orthomosaic_id,
                    frame.stream_id,
                    frame.timestamp,
                    frame.frame_number,
                    frame.gps.latitude if frame.gps else None,
                    frame.gps.longitude if frame.gps else None,
                    frame.gps.altitude if frame.gps else None,
                    frame.resolution[0],
                    frame.resolution[1],
                ))
                
                conn.commit()
                return True
                
            except Exception as e:
                logger.error(f"Error saving frame: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def get_frames(self, orthomosaic_id: str) -> List[Dict[str, Any]]:
        """Get frames for an orthomosaic"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT * FROM frames WHERE orthomosaic_id = ?
                    ORDER BY timestamp
                """, (orthomosaic_id,))
                
                frames = []
                for row in cursor.fetchall():
                    frame = {
                        "id": row[0],
                        "orthomosaic_id": row[1],
                        "stream_id": row[2],
                        "timestamp": row[3],
                        "frame_number": row[4],
                        "gps_lat": row[5],
                        "gps_lon": row[6],
                        "gps_alt": row[7],
                        "resolution_width": row[8],
                        "resolution_height": row[9],
                    }
                    frames.append(frame)
                
                return frames
                
            except Exception as e:
                logger.error(f"Error getting frames: {e}")
                return []
            finally:
                conn.close()
    
    def save_tile(self, tile: OrthomosaicTile, orthomosaic_id: str) -> bool:
        """Save a tile record"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO tiles 
                    (id, orthomosaic_id, z, x, y, file_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tile.id,
                    orthomosaic_id,
                    tile.z,
                    tile.x,
                    tile.y,
                    "",  # file_path would be set if stored separately
                ))
                
                conn.commit()
                return True
                
            except Exception as e:
                logger.error(f"Error saving tile: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
    
    def get_tiles(self, orthomosaic_id: str) -> List[Dict[str, Any]]:
        """Get tiles for an orthomosaic"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT * FROM tiles WHERE orthomosaic_id = ?
                """, (orthomosaic_id,))
                
                tiles = []
                for row in cursor.fetchall():
                    tile = {
                        "id": row[0],
                        "orthomosaic_id": row[1],
                        "z": row[2],
                        "x": row[3],
                        "y": row[4],
                        "file_path": row[5],
                    }
                    tiles.append(tile)
                
                return tiles
                
            except Exception as e:
                logger.error(f"Error getting tiles: {e}")
                return []
            finally:
                conn.close()
    
    def get_orthomosaic_at_time(self, timestamp: float) -> Optional[OrthomosaicRecord]:
        """Get the orthomosaic closest to a specific timestamp"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                # Find the closest orthomosaic
                cursor.execute("""
                    SELECT * FROM orthomosaics 
                    ORDER BY ABS(timestamp - ?)
                    LIMIT 1
                """, (timestamp,))
                
                row = cursor.fetchone()
                if row is None:
                    return None
                
                return OrthomosaicRecord(
                    id=row[0],
                    timestamp=row[1],
                    duration=row[2],
                    frame_count=row[3],
                    keyframe_count=row[4],
                    resolution=(row[5], row[6]),
                    bounds=(row[7], row[8], row[9], row[10]),
                    gps_center=(row[11], row[12]),
                    tile_count=row[13],
                    file_path=row[14] if row[14] else "",
                    metadata=json.loads(row[15]) if row[15] else {},
                )
                
            except Exception as e:
                logger.error(f"Error getting orthomosaic at time: {e}")
                return None
            finally:
                conn.close()
    
    def get_orthomosaics_in_range(
        self,
        start_time: float,
        end_time: float
    ) -> List[OrthomosaicRecord]:
        """Get all orthomosaics in a time range"""
        return self.list_orthomosaics(start_time=start_time, end_time=end_time)
    
    def cleanup_old_data(self, max_age_hours: float = 24.0) -> int:
        """Delete data older than max_age_hours"""
        cutoff_time = timestamp_now() - (max_age_hours * 3600)
        
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                # Get orthomosaic IDs to delete
                cursor.execute("""
                    SELECT id FROM orthomosaics WHERE timestamp < ?
                """, (cutoff_time,))
                
                orthomosaic_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete related data
                for orthomosaic_id in orthomosaic_ids:
                    cursor.execute("""
                        DELETE FROM frames WHERE orthomosaic_id = ?
                    """, (orthomosaic_id,))
                    cursor.execute("""
                        DELETE FROM tiles WHERE orthomosaic_id = ?
                    """, (orthomosaic_id,))
                
                # Delete orthomosaics
                cursor.execute("""
                    DELETE FROM orthomosaics WHERE timestamp < ?
                """, (cutoff_time,))
                
                conn.commit()
                deleted_count = len(orthomosaic_ids)
                logger.info(f"Cleaned up {deleted_count} old orthomosaic records")
                return deleted_count
                
            except Exception as e:
                logger.error(f"Error cleaning up old data: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                # Count orthomosaics
                cursor.execute("SELECT COUNT(*) FROM orthomosaics")
                orthomosaic_count = cursor.fetchone()[0]
                
                # Count frames
                cursor.execute("SELECT COUNT(*) FROM frames")
                frame_count = cursor.fetchone()[0]
                
                # Count tiles
                cursor.execute("SELECT COUNT(*) FROM tiles")
                tile_count = cursor.fetchone()[0]
                
                # Get database size
                db_size = os.path.getsize(self._db_path) if self._db_path.exists() else 0
                
                return {
                    "orthomosaic_count": orthomosaic_count,
                    "frame_count": frame_count,
                    "tile_count": tile_count,
                    "database_size_bytes": db_size,
                    "database_path": str(self._db_path),
                }
                
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                return {
                    "error": str(e)
                }
            finally:
                conn.close()
    
    def vacuum(self) -> bool:
        """Optimize the database"""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute("VACUUM")
                conn.commit()
                logger.info("Database vacuum completed")
                return True
                
            except Exception as e:
                logger.error(f"Error vacuuming database: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
