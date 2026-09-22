from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/pose/{frame_id}")
async def get_pose(frame_id: int):
    """Get camera pose for a specific frame."""
    if frame_id < 0:
        raise HTTPException(status_code=400, detail="Invalid frame ID")
    
    return {
        "frame_id": frame_id,
        "pose": {"x": 0.0, "y": 0.0, "z": 50.0},
        "timestamp": 1234567890.0
    }


@router.post("/pose")
async def update_pose(data: dict):
    """Update camera pose."""
    if not data.get("x") or not data.get("y"):
        raise HTTPException(status_code=400, detail="Missing position coordinates")
    
    return {"status": "success", "pose_updated": True}