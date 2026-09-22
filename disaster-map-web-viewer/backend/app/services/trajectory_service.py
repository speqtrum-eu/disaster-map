from app.services import trajectory_service


class TrajectoryService:
    """Service layer for trajectory operations."""
    
    def __init__(self):
        self._trajectory_data = None
    
    async def get_trajectory(self) -> dict:
        """Retrieve trajectory data."""
        if not self._trajectory_data:
            return {"points": []}
        
        return self._trajectory_data
    
    async def set_trajectory(self, data: dict) -> bool:
        """Set trajectory data."""
        if not data.get("points"):
            return False
        
        self._trajectory_data = data
        return True


# Singleton instance
instance = TrajectoryService()