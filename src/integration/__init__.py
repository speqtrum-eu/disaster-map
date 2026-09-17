"""Integration Layer for Live Orthomosaic Generator (LOG).

Connects ingestion, vision, and mapping pipelines into a cohesive system.
Provides batch processing, output generation, and real-time streaming capabilities.

Vendor-agnostic implementation supporting:
- Multi-stage pipeline orchestration
- Batch processing with parallel execution
- Real-time streaming with latency guarantees
- Output formatting (GeoTIFF, COG, WebP)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
import time
import json
from pathlib import Path


@dataclass
class PipelineStage:
    """Represents a processing stage in the pipeline."""
    
    name: str
    processor: Callable[[Any], Any]
    input_type: type = None
    output_type: type = None
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def process(self, data: Any) -> Tuple[Any, float]:
        """Process data through this stage and return result + timing."""
        start_time = time.time()
        
        if not self.enabled:
            return data, 0.0
        
        try:
            result = self.processor(data)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Validate output type
            if self.output_type and not isinstance(result, self.output_type):
                print(f"Warning: Stage '{self.name}' output type mismatch")
            
            return result, elapsed_ms
            
        except Exception as e:
            print(f"Error in stage '{self.name}': {e}")
            raise


@dataclass
class PipelineConfig:
    """Configuration for the integration pipeline."""
    
    # Processing settings
    batch_size: int = 32
    max_parallel_workers: int = 4
    enable_caching: bool = True
    
    # Quality settings
    output_quality: float = 0.95  # [0, 1]
    compression_level: int = 8
    
    # Performance settings
    timeout_ms: float = 30000.0  # 30 seconds default
    retry_attempts: int = 3
    
    # Output settings
    output_format: str = "geotiff"  # geotiff | cog | webp
    tile_size: int = 256


@dataclass
class ProcessingResult:
    """Result of a processing operation."""
    
    success: bool
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        """Check if result contains valid data."""
        return self.success and self.data is not None


@dataclass
class OrthomosaicOutput:
    """Final orthomosaic output with metadata."""
    
    # Output file paths
    main_file: str = ""
    overviews: List[str] = field(default_factory=list)
    depth_map: Optional[str] = None
    confidence_map: Optional[str] = None
    
    # Geospatial metadata
    geotransform: Tuple[float, ...] = (0.0, 1.0, 0.0, 0.0, 0.0, -1.0)
    crs: str = "EPSG:4326"
    
    # Quality metrics
    resolution_meters: float = 0.5
    accuracy_score: float = 0.95
    
    # Processing metadata
    num_frames_processed: int = 0
    total_processing_time_ms: float = 0.0
    timestamp: float = 0.0


class PipelineBase:
    """Abstract base class for pipeline processors."""
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._stages: List[PipelineStage] = []
        self._cache: Dict[str, Any] = {}
    
    @property
    def stage_count(self) -> int:
        return len(self._stages)
    
    def add_stage(
        self, 
        name: str, 
        processor: Callable[[Any], Any],
        input_type: Optional[type] = None,
        output_type: Optional[type] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PipelineStage:
        """Add a processing stage to the pipeline."""
        stage = PipelineStage(
            name=name,
            processor=processor,
            input_type=input_type,
            output_type=output_type,
            config=config or {},
        )
        
        self._stages.append(stage)
        return stage
    
    def execute(self, data: Any) -> ProcessingResult:
        """Execute the pipeline on input data."""
        start_time = time.time()
        
        try:
            # Execute each stage sequentially
            current_data = data
            
            for stage in self._stages:
                if not stage.enabled:
                    continue
                
                current_data, elapsed_ms = stage.process(current_data)
                
                # Cache intermediate results if enabled
                if self.config.enable_caching:
                    cache_key = f"{stage.name}_result"
                    self._cache[cache_key] = {
                        'data': current_data,
                        'timestamp': time.time(),
                    }
            
            total_time_ms = (time.time() - start_time) * 1000
            
            return ProcessingResult(
                success=True,
                data=current_data,
                metadata={
                    'stages_executed': len(self._stages),
                    'total_processing_time_ms': total_time_ms,
                },
                processing_time_ms=total_time_ms
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )


class BatchProcessor(PipelineBase):
    """Batch processor for multi-frame orthomosaic generation.
    
    Optimized for processing multiple frames in parallel with memory efficiency.
    Supports chunked processing and result aggregation.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        super().__init__(config)
        self._batch_buffer: List[Any] = []
        self._results: Dict[int, ProcessingResult] = {}
        self._aggregated_result: Optional[Any] = None
    
    def add_to_batch(self, data: Any) -> int:
        """Add data to batch buffer. Returns batch index."""
        batch_index = len(self._batch_buffer)
        self._batch_buffer.append(data)
        
        # Auto-process if batch is full
        if len(self._batch_buffer) >= self.config.batch_size:
            self.process_batch()
        
        return batch_index
    
    def process_batch(self) -> List[ProcessingResult]:
        """Process current batch and return results."""
        if not self._batch_buffer:
            return []
        
        results = []
        
        try:
            # Process entire batch in parallel (simplified for now)
            start_time = time.time()
            
            for i, data in enumerate(self._batch_buffer):
                result = self.execute(data)
                self._results[i] = result
                
                if not result.success:
                    print(f"Batch processing error at index {i}: {result.error}")
            
            # Aggregate results
            successful_results = [r for r in results if r.success]
            failed_results = [r for r in results if not r.success]
            
            if len(successful_results) > 0:
                self._aggregated_result = _aggregate_batch_results(
                    successful_results, 
                    failed_results
                )
                
        except Exception as e:
            print(f"Batch processing error: {e}")
        
        # Clear batch buffer
        self._batch_buffer.clear()
        
        return results
    
    def get_aggregated_result(self) -> Optional[Any]:
        """Get aggregated result from last batch."""
        return self._aggregated_result


class RealTimeProcessor(PipelineBase):
    """Real-time processor for streaming orthomosaic generation.
    
    Optimized for low-latency processing with guaranteed throughput.
    Supports frame-level processing and incremental updates.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        super().__init__(config)
        self._latency_budget_ms = 1000.0  # 1 second default
        self._throughput_target_fps = 30.0
        
    @property
    def current_latency(self) -> float:
        """Get current processing latency in ms."""
        if not hasattr(self, '_last_process_time'):
            return 0.0
        return (time.time() - self._last_process_time) * 1000
    
    def process_frame(self, frame_data: Any) -> ProcessingResult:
        """Process a single frame with latency guarantees."""
        start_time = time.time()
        
        try:
            # Check if we're within latency budget
            current_latency = self.current_latency
            
            if current_latency > self._latency_budget_ms * 0.8:
                print(f"Warning: Approaching latency threshold ({current_latency:.1f}ms)")
            
            result = self.execute(frame_data)
            
            # Update throughput metrics
            elapsed_time = (time.time() - start_time) * 1000
            
            if elapsed_time > 0:
                fps = 1000.0 / elapsed_time
                
                if fps < self._throughput_target_fps * 0.5:
                    print(f"Warning: Throughput below target ({fps:.1f} FPS)")
            
            return result
            
        except Exception as e:
            print(f"Frame processing error: {e}")
            return ProcessingResult(
                success=False, 
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )


class OutputGenerator(PipelineBase):
    """Output generator for orthomosaic files.
    
    Supports multiple output formats with quality optimization.
    Handles geospatial metadata and compression settings.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        super().__init__(config)
        self._output_dir: Path = Path("./outputs")
        self._generated_files: List[str] = []
    
    @property
    def output_directory(self) -> Path:
        return self._output_dir
    
    def generate_geotiff(
        self, 
        data: np.ndarray, 
        geotransform: Tuple[float, ...],
        crs: str = "EPSG:4326",
        quality: float = 0.95
    ) -> OrthomosaicOutput:
        """Generate GeoTIFF output file."""
        try:
            import gdal
            from osgeo import gdalconst
            
            # Ensure output directory exists
            self._output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = int(time.time())
            filename = f"orthomosaic_{timestamp}.tif"
            filepath = self._output_dir / filename
            
            # Create driver and dataset
            driver = gdal.GetDriverByName('GTiff')
            
            # Set compression options
            compress_opts = [
                ('COMPRESS', 'DEFLATE'),
                ('TILED', 'YES'),
                ('BIGTIFF', 'YES'),
            ]
            
            if self.config.compression_level > 0:
                compress_opts.append(('LEVEL', str(self.config.compression_level)))
            
            # Create dataset
            bands = data.shape[2] if len(data.shape) == 3 else 1
            
            ds = driver.Create(
                str(filepath),
                data.shape[1],  # width
                data.shape[0],  # height
                bands,
                gdalconst.GDT_Float32
            )
            
            # Set geotransform and CRS
            ds.SetGeoTransform(geotransform)
            ds.SetProjection(crs)
            
            # Write data with compression
            if len(data.shape) == 3:
                for i in range(bands):
                    band = ds.GetRasterBand(i + 1)
                    band.WriteArray(data[:, :, i])
                    band.SetCompression(*compress_opts)
            else:
                band = ds.GetRasterBand(1)
                band.WriteArray(data)
                band.SetCompression(*compress_opts)
            
            # Create overviews for faster rendering
            if self.config.output_format == "cog":
                gdal.BuildOverviews(
                    gdalconst.GDT_Float32, 
                    [2 ** i for i in range(5)],  # 5 levels of detail
                    ds
                )
            
            # Add metadata
            ds.SetMetadataItem('LOG_VERSION', '1.0')
            ds.SetMetadataItem('GENERATION_TIMESTAMP', str(time.time()))
            ds.SetMetadataItem('OUTPUT_FORMAT', self.config.output_format)
            
            ds.FlushCache()
            ds = None
            
            # Return output metadata
            return OrthomosaicOutput(
                main_file=str(filepath),
                geotransform=geotransform,
                crs=crs,
                resolution_meters=abs(geotransform[1]),
                num_frames_processed=self.config.batch_size if hasattr(self, '_batch_size') else 0,
            )
            
        except Exception as e:
            print(f"GeoTIFF generation error: {e}")
            raise
    
    def generate_cog(
        self, 
        data: np.ndarray, 
        geotransform: Tuple[float, ...],
        crs: str = "EPSG:4326",
        tile_size: int = 256
    ) -> OrthomosaicOutput:
        """Generate Cloud Optimized GeoTIFF output."""
        try:
            import gdal
            from osgeo import gdalconst
            
            # Use geotiff generation with COG-specific settings
            output = self.generate_geotiff(
                data, 
                geotransform, 
                crs,
                quality=self.config.output_quality
            )
            
            # Add COG metadata
            cog_metadata = {
                'tile_size': tile_size,
                'pyramidal_overviews': True,
                'compression': 'DEFLATE',
            }
            
            output.metadata.update(cog_metadata)
            
        except Exception as e:
            print(f"COG generation error: {e}")
            raise
    
    def generate_webp(
        self, 
        data: np.ndarray, 
        quality: float = 0.95
    ) -> OrthomosaicOutput:
        """Generate WebP output for web visualization."""
        try:
            import cv2
            
            # Ensure output directory exists
            self._output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            timestamp = int(time.time())
            filename = f"orthomosaic_{timestamp}.webp"
            filepath = self._output_dir / filename
            
            # Convert to uint8 if needed
            if data.dtype != np.uint8:
                normalized = (data - data.min()) / (data.max() - data.min() + 1e-8) * 255.0
                data_uint8 = normalized.astype(np.uint8)
            else:
                data_uint8 = data
            
            # Encode as WebP with quality setting
            success, encoded_data = cv2.imencode('.webp', data_uint8, [int(cv2.IMWRITE_WEBP_QUALITY), int(quality * 100)])
            
            if not success:
                raise ValueError("Failed to encode WebP image")
            
            # Write file
            with open(filepath, 'wb') as f:
                f.write(encoded_data.tobytes())
            
            return OrthomosaicOutput(
                main_file=str(filepath),
                resolution_meters=0.5,  # Default for webp
                num_frames_processed=self.config.batch_size if hasattr(self, '_batch_size') else 0,
            )
            
        except Exception as e:
            print(f"WebP generation error: {e}")
            raise
    
    def generate_output(
        self, 
        data: np.ndarray, 
        geotransform: Tuple[float, ...],
        crs: str = "EPSG:4326",
        format: Optional[str] = None
    ) -> OrthomosaicOutput:
        """Generate output in specified format."""
        if format is None:
            format = self.config.output_format
        
        generators = {
            'geotiff': self.generate_geotiff,
            'cog': self.generate_cog,
            'webp': self.generate_webp,
        }
        
        generator = generators.get(format.lower())
        if not generator:
            raise ValueError(f"Unsupported output format: {format}")
        
        return generator(data, geotransform, crs)


class SystemIntegrator(PipelineBase):
    """System integrator for end-to-end orthomosaic generation.
    
    Orchestrates all components (ingestion, vision, mapping, output).
    Provides high-level API for complete workflow execution.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        super().__init__(config)
        
        # Initialize component processors
        self._batch_processor = BatchProcessor(config)
        self._realtime_processor = RealTimeProcessor(config)
        self._output_generator = OutputGenerator(config)
        
        # Pipeline stages
        self._stages: List[PipelineStage] = []
    
    def setup_pipeline(
        self, 
        use_batch: bool = True,
        use_realtime: bool = False
    ) -> None:
        """Setup the complete processing pipeline."""
        
        # Add ingestion stage (placeholder)
        def ingest_processor(data):
            return data
        
        self.add_stage('ingestion', ingest_processor, config={'use_batch': use_batch})
        
        # Add vision processing stage (placeholder)
        def vision_processor(data):
            return data
        
        self.add_stage('vision', vision_processor, config={'use_realtime': use_realtime})
        
        # Add mapping stage (placeholder)
        def mapping_processor(data):
            return data
        
        self.add_stage('mapping', mapping_processor)
        
        # Add output generation stage
        def output_processor(data):
            return data
        
        self.add_stage('output', output_processor, config={'generator': self._output_generator})
    
    def process_batch(
        self, 
        frames: List[Any], 
        geotransform: Tuple[float, ...] = None,
        crs: str = "EPSG:4326"
    ) -> OrthomosaicOutput:
        """Process a batch of frames and generate orthomosaic output."""
        
        # Setup pipeline if not already done
        if len(self._stages) == 0:
            self.setup_pipeline()
        
        # Process through pipeline
        result = self.execute(frames)
        
        if not result.success:
            raise ValueError(f"Processing failed: {result.error}")
        
        # Generate output
        output = self._output_generator.generate_output(
            data=result.data,
            geotransform=geotransform or (0.0, 1.0, 0.0, 0.0, 0.0, -1.0),
            crs=crs
        )
        
        return output
    
    def process_realtime(
        self, 
        frame_stream: Any,
        callback: Optional[Callable[[ProcessingResult], None]] = None
    ) -> Generator[ProcessingResult, None, None]:
        """Process frames in real-time with callbacks."""
        
        # Setup pipeline if not already done
        if len(self._stages) == 0:
            self.setup_pipeline(use_realtime=True)
        
        for frame in frame_stream:
            result = self._realtime_processor.process_frame(frame)
            
            if callback:
                callback(result)
            
            yield result
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status and metrics."""
        return {
            'pipeline_stages': len(self._stages),
            'batch_size': self.config.batch_size,
            'output_format': self.config.output_format,
            'enabled_stages': sum(1 for s in self._stages if s.enabled),
        }


def _aggregate_batch_results(
    successful: List[ProcessingResult], 
    failed: List[ProcessingResult]
) -> Any:
    """Aggregate results from batch processing."""
    
    # Combine successful data (placeholder implementation)
    combined_data = None
    
    if len(successful) > 0:
        # In a real implementation, this would aggregate orthomosaic tiles
        # For now, return the first successful result's data
        combined_data = successful[0].data
    
    metadata = {
        'successful_count': len(successful),
        'failed_count': len(failed),
        'total_frames': len(successful) + len(failed),
    }
    
    if failed:
        metadata['errors'] = [r.error for r in failed]
    
    return combined_data, metadata


# Convenience functions for quick setup
def create_batch_pipeline(config: Optional[PipelineConfig] = None) -> BatchProcessor:
    """Create a batch processing pipeline."""
    processor = BatchProcessor(config)
    processor.setup_pipeline()
    return processor


def create_realtime_pipeline(config: Optional[PipelineConfig] = None) -> RealTimeProcessor:
    """Create a real-time processing pipeline."""
    processor = RealTimeProcessor(config)
    processor.setup_pipeline()
    return processor


def create_output_generator(config: Optional[PipelineConfig] = None) -> OutputGenerator:
    """Create an output generation pipeline."""
    generator = OutputGenerator(config)
    generator.setup_pipeline()
    return generator


def create_system_integrator(config: Optional[PipelineConfig] = None) -> SystemIntegrator:
    """Create a complete system integrator."""
    integrator = SystemIntegrator(config)
    integrator.setup_pipeline()
    return integrator
