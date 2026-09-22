from app.services import trajectory_service


class PoseService:
    """Service layer for pose operations."""
    
    def __init__(self):
        self._pose_cache = {}
    
    async def get_pose(self, frame_id: int) -> dict:
        """Get cached pose data."""
        if frame_id in self._pose_cache:
            return self._pose_cache[frame_id]
        
        # Default pose for demo
        return {
            "frame_id": frame_id,
            "pose": {"x": 0.0, "y": 0.0, "z": 50.0},
            "timestamp": 1234567890.0
        }
    
    async def cache_pose(self, frame_id: int, pose_data: dict):
        """Cache pose data."""
        self._pose_cache[frame_id] = pose_data


# Singleton instance
instance = PoseService()