"""Tests for Integration Layer."""

import numpy as np
import pytest
from src.integration import (
    PipelineConfig, ProcessingResult, OrthomosaicOutput,
    BatchProcessor, RealTimeProcessor, OutputGenerator, SystemIntegrator,
)


class TestPipelineConfig:
    """Tests for pipeline configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PipelineConfig()
        
        assert config.batch_size == 32
        assert config.max_parallel_workers == 4
        assert config.output_quality == 0.95
        assert config.output_format == "geotiff"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PipelineConfig(
            batch_size=64,
            max_parallel_workers=8,
            output_quality=0.99,
            compression_level=9,
        )
        
        assert config.batch_size == 64
        assert config.max_parallel_workers == 8
        assert config.output_quality == 0.99


class TestProcessingResult:
    """Tests for processing result dataclass."""

    def test_successful_result(self):
        """Test successful processing result."""
        result = ProcessingResult(
            success=True,
            data=np.random.rand(100, 100),
            metadata={'key': 'value'},
            processing_time_ms=50.0,
        )
        
        assert result.success is True
        assert result.data.shape == (100, 100)
        assert result.is_valid is True

    def test_failed_result(self):
        """Test failed processing result."""
        result = ProcessingResult(
            success=False,
            error="Processing failed",
            processing_time_ms=100.0,
        )
        
        assert result.success is False
        assert result.error == "Processing failed"
        assert result.is_valid is False


class TestOrthomosaicOutput:
    """Tests for orthomosaic output dataclass."""

    def test_default_output(self):
        """Test default orthomosaic output values."""
        output = OrthomosaicOutput()
        
        assert output.main_file == ""
        assert len(output.overviews) == 0
        assert output.crs == "EPSG:4326"
        assert output.resolution_meters == 0.5

    def test_custom_output(self):
        """Test custom orthomosaic output values."""
        output = OrthomosaicOutput(
            main_file="/tmp/test.tif",
            geotransform=(-180.0, 0.009, 0.0, 90.0, 0.0, -0.009),
            crs="EPSG:3857",
            resolution_meters=0.25,
            accuracy_score=0.99,
        )
        
        assert output.main_file == "/tmp/test.tif"
        assert output.resolution_meters == 0.25
        assert output.accuracy_score == 0.99


class TestBatchProcessor:
    """Tests for batch processor."""

    def test_batch_processor_initialization(self):
        """Test batch processor initialization."""
        config = PipelineConfig(batch_size=16)
        processor = BatchProcessor(config)
        
        assert processor.config.batch_size == 16
        assert len(processor._batch_buffer) == 0

    def test_add_to_batch(self):
        """Test adding data to batch buffer."""
        processor = BatchProcessor(PipelineConfig(batch_size=4))
        
        # Add items to batch
        for i in range(5):
            index = processor.add_to_batch(f"data_{i}")
            
            assert isinstance(index, int)

    def test_process_batch_empty(self):
        """Test processing empty batch."""
        processor = BatchProcessor(PipelineConfig(batch_size=4))
        
        results = processor.process_batch()
        
        assert len(results) == 0


class TestRealTimeProcessor:
    """Tests for real-time processor."""

    def test_realtime_processor_initialization(self):
        """Test real-time processor initialization."""
        config = PipelineConfig(batch_size=32)
        processor = RealTimeProcessor(config)
        
        assert processor._latency_budget_ms == 1000.0
        assert processor._throughput_target_fps == 30.0

    def test_process_frame(self):
        """Test processing a single frame."""
        config = PipelineConfig(batch_size=4)
        processor = RealTimeProcessor(config)
        
        # Create synthetic frame data
        frame_data = np.random.rand(128, 128, 3).astype(np.float32)
        
        result = processor.process_frame(frame_data)
        
        assert isinstance(result, ProcessingResult)


class TestOutputGenerator:
    """Tests for output generator."""

    def test_output_generator_initialization(self):
        """Test output generator initialization."""
        config = PipelineConfig(output_format="geotiff")
        generator = OutputGenerator(config)
        
        assert generator.config.output_format == "geotiff"
        assert str(generator.output_directory).endswith("outputs")

    def test_generate_geotiff_config(self):
        """Test GeoTIFF generation configuration."""
        config = PipelineConfig(
            output_format="geotiff",
            compression_level=9,
        )
        generator = OutputGenerator(config)
        
        assert generator.config.output_format == "geotiff"


class TestSystemIntegrator:
    """Tests for system integrator."""

    def test_system_integrator_initialization(self):
        """Test system integrator initialization."""
        config = PipelineConfig(batch_size=32)
        integrator = SystemIntegrator(config)
        
        assert len(integrator._stages) == 0
        assert integrator.config.batch_size == 32

    def test_setup_pipeline(self):
        """Test pipeline setup."""
        integrator = SystemIntegrator()
        integrator.setup_pipeline()
        
        # Should have stages after setup
        assert len(integrator._stages) > 0

    def test_get_status(self):
        """Test getting system status."""
        integrator = SystemIntegrator(PipelineConfig(batch_size=64))
        integrator.setup_pipeline()
        
        status = integrator.get_status()
        
        assert 'pipeline_stages' in status
        assert 'batch_size' in status


class TestDataClasses:
    """Tests for dataclasses in integration module."""

    def test_processing_result_properties(self):
        """Test ProcessingResult properties."""
        result = ProcessingResult(
            success=True,
            data=np.random.rand(10, 10),
            metadata={'test': 'data'},
            processing_time_ms=25.0,
        )
        
        assert result.is_valid is True

    def test_orthomosaic_output_properties(self):
        """Test OrthomosaicOutput properties."""
        output = OrthomosaicOutput(
            main_file="/tmp/test.tif",
            geotransform=(-180.0, 0.009, 0.0, 90.0, 0.0, -0.009),
            crs="EPSG:4326",
        )
        
        assert output.resolution_meters == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
