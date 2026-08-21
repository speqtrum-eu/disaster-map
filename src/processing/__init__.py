"""
Processing module for orthomosaic generation
"""

from .stitcher import (
    OrthoStitcher,
    IncrementalStitcher,
    HomographyStitcher,
    BundleAdjustmentStitcher,
    StitchingConfig,
)
from .ortho_engine import (
    OrthomosaicEngine,
    TileGenerator,
    Georegistrator,
    MultiStreamOrthoEngine,
)
from .feature_matcher import (
    FeatureMatcher,
    SIFTMatcher,
    ORBMatcher,
    AKAZEMatcher,
)

# PyODM integration
try:
    from .pyodm_integration import (
        PyODMClient,
        ODMConfig,
        ODMResult,
        BatchOrthomosaicGenerator,
        HybridOrthomosaicEngine,
        create_pyodm_client,
        create_batch_generator,
        create_hybrid_engine,
    )
    PYODM_AVAILABLE = True
except ImportError:
    PYODM_AVAILABLE = False

# DEM generation
try:
    from .dem_generator import (
        DEMEngine,
        DEMConfig,
        DEMResult,
        StereoDEMGenerator,
        PointCloudDEMGenerator,
        MultiViewDEMGenerator,
        DEMStorage,
        DEMMethod,
        create_dem_engine,
        create_stereo_dem_generator,
        create_point_cloud_dem_generator,
    )
    DEM_AVAILABLE = True
except ImportError:
    DEM_AVAILABLE = False

# Point cloud processing
try:
    from .point_cloud import (
        PointCloud,
        PointCloudConfig,
        PointCloudGenerator,
        PointCloudIO,
        PointCloudVisualizer,
        PointCloudProcessor,
        PointCloudFormat,
        PointCloudColorMode,
        create_point_cloud_generator,
        create_point_cloud_io,
        create_point_cloud_visualizer,
        create_point_cloud_processor,
    )
    POINT_CLOUD_AVAILABLE = True
except ImportError:
    POINT_CLOUD_AVAILABLE = False

# Multi-stream synchronization
try:
    from .multi_stream_sync import (
        StreamSynchronizer,
        SyncConfig,
        SyncGroup,
        SyncResult,
        SyncMethod,
        SyncQuality,
        TimestampSynchronizer,
        GPSSynchronizer,
        FeatureSynchronizer,
        HybridSynchronizer,
        FrameBuffer,
        create_synchronizer,
        create_timestamp_synchronizer,
        create_gps_synchronizer,
        create_feature_synchronizer,
        create_hybrid_synchronizer,
    )
    SYNC_AVAILABLE = True
except ImportError:
    SYNC_AVAILABLE = False

# Advanced georegistration
try:
    from .advanced_georegistration import (
        GeoregistrationEngine,
        GeoregistrationConfig,
        GeoregistrationResult,
        HomographyGeoregistrator,
        TPSGeoregistrator,
        PolynomialGeoregistrator,
        BundleAdjustmentGeoregistrator,
        GCP,
        WarpingMethod,
        RegistrationQuality,
        create_georegistrator,
        create_homography_georegistrator,
        create_tps_georegistrator,
        create_polynomial_georegistrator,
    )
    GEOREGISTRATION_AVAILABLE = True
except ImportError:
    GEOREGISTRATION_AVAILABLE = False

# Hybrid pipeline
try:
    from .hybrid_pipeline import (
        HybridProcessingPipeline,
        HybridPipelineConfig,
        PipelineResult,
        PipelineMode,
        PipelineStatus,
        PipelineManager,
        create_hybrid_pipeline,
    )
    HYBRID_PIPELINE_AVAILABLE = True
except ImportError:
    HYBRID_PIPELINE_AVAILABLE = False

__all__ = [
    # Core processing
    "OrthoStitcher",
    "IncrementalStitcher",
    "HomographyStitcher",
    "BundleAdjustmentStitcher",
    "StitchingConfig",
    "OrthomosaicEngine",
    "TileGenerator",
    "Georegistrator",
    "MultiStreamOrthoEngine",
    "FeatureMatcher",
    "SIFTMatcher",
    "ORBMatcher",
    "AKAZEMatcher",
    
    # Availability flags
    "PYODM_AVAILABLE",
    "DEM_AVAILABLE",
    "POINT_CLOUD_AVAILABLE",
    "SYNC_AVAILABLE",
    "GEOREGISTRATION_AVAILABLE",
    "HYBRID_PIPELINE_AVAILABLE",
]

# Add PyODM exports if available
if PYODM_AVAILABLE:
    __all__.extend([
        "PyODMClient",
        "ODMConfig",
        "ODMResult",
        "BatchOrthomosaicGenerator",
        "HybridOrthomosaicEngine",
        "create_pyodm_client",
        "create_batch_generator",
        "create_hybrid_engine",
    ])

# Add DEM exports if available
if DEM_AVAILABLE:
    __all__.extend([
        "DEMEngine",
        "DEMConfig",
        "DEMResult",
        "StereoDEMGenerator",
        "PointCloudDEMGenerator",
        "MultiViewDEMGenerator",
        "DEMStorage",
        "DEMMethod",
        "create_dem_engine",
        "create_stereo_dem_generator",
        "create_point_cloud_dem_generator",
    ])

# Add point cloud exports if available
if POINT_CLOUD_AVAILABLE:
    __all__.extend([
        "PointCloud",
        "PointCloudConfig",
        "PointCloudGenerator",
        "PointCloudIO",
        "PointCloudVisualizer",
        "PointCloudProcessor",
        "PointCloudFormat",
        "PointCloudColorMode",
        "create_point_cloud_generator",
        "create_point_cloud_io",
        "create_point_cloud_visualizer",
        "create_point_cloud_processor",
    ])

# Add sync exports if available
if SYNC_AVAILABLE:
    __all__.extend([
        "StreamSynchronizer",
        "SyncConfig",
        "SyncGroup",
        "SyncResult",
        "SyncMethod",
        "SyncQuality",
        "TimestampSynchronizer",
        "GPSSynchronizer",
        "FeatureSynchronizer",
        "HybridSynchronizer",
        "FrameBuffer",
        "create_synchronizer",
        "create_timestamp_synchronizer",
        "create_gps_synchronizer",
        "create_feature_synchronizer",
        "create_hybrid_synchronizer",
    ])

# Add georegistration exports if available
if GEOREGISTRATION_AVAILABLE:
    __all__.extend([
        "GeoregistrationEngine",
        "GeoregistrationConfig",
        "GeoregistrationResult",
        "HomographyGeoregistrator",
        "TPSGeoregistrator",
        "PolynomialGeoregistrator",
        "BundleAdjustmentGeoregistrator",
        "GCP",
        "WarpingMethod",
        "RegistrationQuality",
        "create_georegistrator",
        "create_homography_georegistrator",
        "create_tps_georegistrator",
        "create_polynomial_georegistrator",
    ])

# Add hybrid pipeline exports if available
if HYBRID_PIPELINE_AVAILABLE:
    __all__.extend([
        "HybridProcessingPipeline",
        "HybridPipelineConfig",
        "PipelineResult",
        "PipelineMode",
        "PipelineStatus",
        "PipelineManager",
        "create_hybrid_pipeline",
    ])
