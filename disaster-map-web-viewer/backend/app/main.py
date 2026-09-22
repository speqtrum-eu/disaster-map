from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, trajectory, pose

app = FastAPI(
    title="Disaster Map Backend API",
    description="REST API for disaster map viewer services",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Disaster Map Backend API"}

# Include routers
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(trajectory.router, prefix="/api/trajectory", tags=["trajectory"])
app.include_router(pose.router, prefix="/api/pose", tags=["pose"])