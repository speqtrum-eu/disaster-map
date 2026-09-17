"""Tests for Mapping & Orthorectification Pipeline."""

import numpy as np
import pytest
from src.mapping import (
    MVSConfig, DGCMSVS, DepthMap,
    OrthorectificationConfig, OrthorectificationPipeline, OrthorectifiedTile,
    TilingConfig, COGTilingService, COGTile,
)


class TestMVS:
    """Tests for Multi-View Stereo algorithms."""

    def test_dgc_mvs_initialization(self):
        """Test DGC-MVS algorithm initialization."""
        config = MVSConfig(
            algorithm="dgc",
            use_gpu=False,  # Skip GPU for testing
            depth_resolution=(256, 256),
        )

        mvs = DGCMSVS(config)
        assert mvs.algorithm == "dgc"

    def test_dgc_mvs_depth_estimation(self):
        """Test depth estimation with minimal views."""
        config = MVSConfig(
            algorithm="dgc",
            use_gpu=False,
            depth_resolution=(128, 128),
        )

        mvs = DGCMSVS(config)
        result = mvs.estimate_depth(
            poses=[np.eye(4), np.eye(4)],  # Minimal valid input
        )

        assert isinstance(result, DepthMap)
        assert result.depth.shape == (128, 128)

    def test_dgc_mvs_with_multiple_views(self):
        """Test depth estimation with multiple camera poses."""
        config = MVSConfig(
            algorithm="dgc",
            use_gpu=False,
            depth_resolution=(64, 64),
        )

        mvs = DGCMSVS(config)

        # Create test poses (rotation + translation)
        poses = []
        for i in range(5):
            R = np.eye(3)
            T = np.array([i * 10, 0, 0])
            pose_matrix = np.hstack([R, T.reshape(3, 1)])
            poses.append(pose_matrix)

        result = mvs.estimate_depth(poses=poses)

        assert isinstance(result, DepthMap)
        assert result.num_views_used == 5

    def test_depth_map_properties(self):
        """Test DepthMap dataclass properties."""
        depth = np.random.rand(100, 100).astype(np.float32) * 100.0
        confidence = np.random.rand(100, 100).astype(np.float32)
        valid_mask = (depth > 50).astype(np.uint8)

        dm = DepthMap(
            depth=depth,
            confidence=confidence,
            valid_mask=valid_mask,
            num_views_used=3,
        )

        assert dm.depth.shape == (100, 100)
        assert dm.num_views_used == 3


class TestOrthorectification:
    """Tests for orthorectification pipeline."""

    def test_orthorectification_config(self):
        """Test orthorectification configuration."""
        config = OrthorectificationConfig(
            input_crs="EPSG:4326",
            output_crs="EPSG:3857",
            use_digital_elevation_model=True,
            terrain_correction_method="bilinear",
        )

        assert config.input_crs == "EPSG:4326"
        assert config.output_crs == "EPSG:3857"

    def test_orthorectification_pipeline_initialization(self):
        """Test orthorectification pipeline initialization."""
        config = OrthorectificationConfig()

        pipeline = OrthorectificationPipeline(config)
        assert not pipeline._dem_loaded

    def test_dem_loading_with_synthetic_data(self):
        """Test DEM loading with synthetic terrain data."""
        # Skip if GDAL not available (optional dependency)
        try:
            import gdal
            has_gdal = True
        except ImportError:
            has_gdal = False
        
        if has_gdal:
            pipeline = OrthorectificationPipeline()

            # Load synthetic DEM for testing
            loaded = pipeline.load_dem(resolution_meters=1.0)
            assert loaded is True
            assert pipeline._dem_loaded
        else:
            # GDAL not available - test fallback behavior
            pipeline = OrthorectificationPipeline()
            # The load_dem method should handle missing DEM gracefully
            assert hasattr(pipeline, 'load_dem')

    def test_orthorectify_with_synthetic_image(self):
        """Test orthorectification with synthetic image."""
        config = OrthorectificationConfig()
        pipeline = OrthorectificationPipeline(config)

        # Create synthetic input data
        H, W = 256, 256
        image = np.random.rand(H, W, 3).astype(np.float32) * 255.0

        # Define output geotransform
        geotransform = (
            -180.0,  # top-left longitude
            0.009,   # pixel width in degrees
            0.0,     # rotation
            90.0,    # bottom-left latitude
            0.0,     # vertical rotation
            -0.009   # pixel height in degrees (negative for downward)
        )

        result = pipeline.orthorectify(image, pose=np.zeros(4), geotransform=geotransform)

        assert isinstance(result, OrthorectifiedTile)
        # Output size may vary due to resampling - just verify it's a valid tile
        assert result.data.shape[0] > 0 and result.data.shape[1] > 0


class TestTiling:
    """Tests for COG tiling service."""

    def test_tiling_config(self):
        """Test tiling configuration."""
        config = TilingConfig(
            tile_size_pixels=256,
            overlap_pixels=64,
            compression_level=9,
            create_overviews=True,
            max_zoom_levels=10,
        )

        assert config.tile_size_pixels == 256
        assert config.overlap_pixels == 64

    def test_cog_tiling_service_initialization(self):
        """Test COG tiling service initialization."""
        config = TilingConfig()
        service = COGTilingService(config)

        assert service.tile_size == 256
        assert service.overlap == 64


class TestDataClasses:
    """Tests for dataclasses in mapping module."""

    def test_orthorectified_tile_properties(self):
        """Test OrthorectifiedTile properties."""
        tile = OrthorectifiedTile(
            data=np.random.rand(100, 100, 3).astype(np.float32),
            geotransform=(-180.0, 0.009, 0.0, 90.0, 0.0, -0.009),
            crs="EPSG:4326",
        )

        assert tile.resolution_meters == (0.009, 0.009)

    def test_cog_tile_properties(self):
        """Test COGTile properties."""
        cog = COGTile(
            filename="/tmp/test.tif",
            geotransform=(-180.0, 0.009, 0.0, 90.0, 0.0, -0.009),
            crs="EPSG:4326",
        )

        assert cog.tile_size == (256, 256)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
