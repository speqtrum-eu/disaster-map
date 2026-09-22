from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/trajectory")
async def get_trajectory():
    """Get trajectory data for visualization."""
    return {
        "points": [
            {"lat": 37.7749, "lon": -122.4194, "alt": 50},
            {"lat": 37.7849, "lon": -122.4294, "alt": 60},
        ]
    }


@router.post("/trajectory")
async def upload_trajectory(data: dict):
    """Upload trajectory data."""
    if not data.get("points"):
        raise HTTPException(status_code=400, detail="Missing points in request")
    
    return {"status": "success", "points_count": len(data["points"])}