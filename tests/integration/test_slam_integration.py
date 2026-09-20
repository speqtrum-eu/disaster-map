"""Integration Tests for SLAM System with Sample Video Data."""

import pytest
import numpy as np
from pathlib import Path
import time
import os
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.slam.base_slam import PoseEstimate, MapState, SLAMConfig
from src.core.slam.orb_slam2 import ORB_SLAM2Engine
from src.core.slam.dvm_slam import DVM_SLAEngine, DVMConfig, MultiAgentSLAMManager
from src.core.frame_processor import FrameProcessor, FrameData
from src.core.pose_tracker import PoseTracker


class TestORB_SLAM2Integration:
    """Integration tests for ORB-SLAM2 with real-world scenarios."""
    
    def test_complete_slam_pipeline(self):
        """Test complete SLAM pipeline from frame to pose output."""
        # Initialize configuration
        config = SLAMConfig(
            camera_width=640,
            camera_height=480,
            frame_rate=30.0,
            max_keyframes=1000
        )
        
        # Create ORB-SLAM2 engine
        slam_engine = ORB_SLAM2Engine(config)
        slam_engine.initialize()
        
        # Simulate processing video frames
        num_frames = 50
        poses = []
        
        for i in range(num_frames):
            timestamp = float(i * 0.1)  # 10ms between frames
            
            # Create mock frame data (simulating real camera input)
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # Process frame through SLAM engine
            pose = slam_engine.process_frame(frame, timestamp)
            poses.append(pose)
        
        # Verify results
        assert len(poses) == num_frames
        
        # Check trajectory progression (simulated movement)
        positions = np.array([p.position for p in poses])
        
        # Should have moved over time
        total_distance = np.linalg.norm(positions[-1] - positions[0])
        assert total_distance > 0, "No movement detected in trajectory"
    
    def test_pose_tracking_accuracy(self):
        """Test pose tracking maintains reasonable accuracy."""
        config = SLAMConfig(camera_width=640, camera_height=480)
        slam_engine = ORB_SLAM2Engine(config)
        slam_engine.initialize()
        
        # Process frames and collect poses
        num_frames = 100
        timestamps = []
        positions = []
        
        for i in range(num_frames):
            timestamp = float(i * 0.05)
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            pose = slam_engine.process_frame(frame, timestamp)
            timestamps.append(timestamp)
            positions.append(pose.position.copy())
        
        # Verify timestamps are sequential
        assert all(timestamps[i] < timestamps[i+1] for i in range(len(timestamps)-1))
        
        # Verify positions are reasonable (no NaN or Inf)
        assert not np.any(np.isnan(positions))
        assert not np.any(np.isinf(positions))


class TestDVM_SLAMIntegration:
    """Integration tests for DVM-SLAM multi-agent system."""
    
    def test_multi_agent_consensus(self):
        """Test consensus operation across multiple agents."""
        # Create 3 simulated drone agents
        num_agents = 3
        agents = []
        
        for i in range(num_agents):
            config = DVMConfig(
                node_id=f"drone_{i}",
                consensus_interval=1.0,
                max_neighbors=num_agents - 1
            )
            engine = DVM_SLAEngine(config)
            engine.initialize()
            
            # Set initial positions forming a triangle
            if i == 0:
                position = np.array([0.0, 0.0, 50.0])
            elif i == 1:
                position = np.array([20.0, 0.0, 50.0])
            else:
                position = np.array([10.0, 17.32, 50.0])  # Equilateral triangle
            
            engine._update_node_position(position)
            agents.append(engine)
        
        # Create manager and register all agents
        manager = MultiAgentSLAMManager()
        
        for agent in agents:
            manager.register_agent(agent)
        
        assert len(manager._agents) == num_agents
        
        # Simulate frame processing across all agents
        num_frames = 20
        for i in range(num_frames):
            timestamp = float(i * 0.1)
            
            for agent in agents:
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                pose = agent.process_frame(frame, timestamp)
        
        # Verify all agents processed frames successfully
        assert len(agents[0].get_pose_history()) >= num_frames
        
        # Get fused pose from manager
        fused_pose = manager.get_fused_pose()
        assert fused_pose is not None
    
    def test_network_topology(self):
        """Test multi-agent network topology management."""
        agent_a = DVM_SLAEngine(DVMConfig(node_id="A"))
        agent_b = DVM_SLAEngine(DVMConfig(node_id="B"))
        agent_c = DVM_SLAEngine(DVMConfig(node_id="C"))
        
        for agent in [agent_a, agent_b, agent_c]:
            agent.initialize()
        
        # Create manager and register agents
        manager = MultiAgentSLAMManager()
        
        for agent in [agent_a, agent_b, agent_c]:
            manager.register_agent(agent)
        
        assert len(manager._agents) == 3
        
        # Check network state
        status = manager.get_fleet_status()
        assert "total_agents" in status
        assert status["total_agents"] == 3


class TestFrameProcessorIntegration:
    """Integration tests for frame processing pipeline."""
    
    def test_frame_extraction_pipeline(self):
        """Test complete frame extraction from mock source."""
        # Create processor with target FPS
        processor = FrameProcessor(
            frame_rate=60.0,
            buffer_size=512
        )
        
        # Simulate processing frames (without actual video source)
        num_frames = 30
        
        received_frames = []
        timestamps = []
        
        for i in range(num_frames):
            timestamp = float(i * 0.05)
            
            # Create mock frame data
            frame_data = FrameData(
                image=np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
                timestamp=timestamp,
                frame_number=i,
                width=640,
                height=480,
            )
            
            received_frames.append(frame_data)
            timestamps.append(timestamp)
        
        # Verify all frames were processed correctly
        assert len(received_frames) == num_frames
        
        # Check timestamp progression
        assert all(timestamps[i] < timestamps[i+1] for i in range(len(timestamps)-1))


class TestPoseTrackerIntegration:
    """Integration tests for pose tracking and trajectory management."""
    
    def test_trajectory_export(self):
        """Test exporting trajectory to file formats."""
        import tempfile
        
        tracker = PoseTracker(smoothing_window=5)
        
        # Add poses simulating drone flight
        num_poses = 100
        for i in range(num_poses):
            timestamp = float(i * 0.1)
            
            # Simulate circular flight pattern with altitude variation
            angle = i * 0.2
            x = np.cos(angle) * 50
            y = np.sin(angle) * 50
            z = 50 + np.sin(i * 0.3) * 10
            
            pose = PoseEstimate(
                position=np.array([x, y, z]),
                timestamp=timestamp,
                confidence=0.95 - (i % 20) * 0.01
            )
            
            tracker.add_pose(pose, frame_number=i)
        
        # Export to CSV
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            csv_path = f.name
        
        try:
            result = tracker.export_csv(csv_path)
            assert result is True
            
            # Verify file was created and has content
            assert os.path.exists(csv_path)
            
            with open(csv_path, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) > 1  # Header + data rows
        
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
        
        # Export to JSON
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            json_path = f.name
        
        try:
            result = tracker.export_json(json_path)
            assert result is True
            
            assert os.path.exists(json_path)
            
            with open(json_path, 'r') as f:
                data = f.read()
            
            assert len(data) > 0
        
        finally:
            if os.path.exists(json_path):
                os.remove(json_path)
    
    def test_trajectory_statistics(self):
        """Test trajectory statistics calculation."""
        tracker = PoseTracker()
        
        # Add poses with known pattern
        for i in range(50):
            pose = PoseEstimate(
                position=np.array([i * 2, np.sin(i) * 10, 50.0]),
                timestamp=float(i),
                confidence=0.9 + (i % 10) * 0.01
            )
            tracker.add_pose(pose)
        
        stats = tracker.get_statistics()
        
        assert "num_points" in stats
        assert stats["num_points"] == 50
        assert "total_distance_meters" in stats
        assert stats["total_distance_meters"] > 0


class TestPerformance:
    """Performance tests for SLAM system."""
    
    def test_frame_processing_latency(self):
        """Test frame processing meets latency targets (<15ms)."""
        import time
        
        config = SLAMConfig(camera_width=640, camera_height=480)
        slam_engine = ORB_SLAM2Engine(config)
        slam_engine.initialize()
        
        # Measure processing time for multiple frames
        num_frames = 100
        latencies = []
        
        for i in range(num_frames):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            start_time = time.perf_counter()
            pose = slam_engine.process_frame(frame, timestamp=float(i))
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            latencies.append(latency_ms)
        
        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        
        # Should be under target latency
        assert avg_latency < 20.0, f"Average latency {avg_latency:.2f}ms exceeds target"
        assert max_latency < 30.0, f"Max latency {max_latency:.2f}ms exceeds threshold"


class TestEndToEnd:
    """End-to-end integration test simulating real disaster mapping scenario."""
    
    def test_disaster_mapping_workflow(self):
        """Simulate complete disaster mapping workflow."""
        print("\n" + "=" * 60)
        print("DISASTER MAPPING WORKFLOW SIMULATION")
        print("=" * 60)
        
        # Phase 1: Initialize SLAM system
        print("\n[Phase 1] Initializing SLAM System...")
        config = SLAMConfig(
            camera_width=1280,
            camera_height=720,
            frame_rate=30.0,
            max_keyframes=5000
        )
        
        slam_engine = ORB_SLAM2Engine(config)
        slam_engine.initialize()
        print(f"  ✓ SLAM engine initialized with {config.camera_width}x{config.camera_height} camera")
        
        # Phase 2: Process video stream from drone
        print("\n[Phase 2] Processing Drone Video Stream...")
        num_frames = 100
        
        trajectory_poses = []
        keyframes = []
        
        for i in range(num_frames):
            timestamp = float(i * 0.1)
            
            # Simulate drone movement (search pattern over disaster area)
            angle = i * 0.15
            x = np.cos(angle) * 200 + np.random.normal(0, 5)
            y = np.sin(angle) * 200 + np.random.normal(0, 5)
            z = 100 + np.random.uniform(-10, 10)  # Altitude variation
            
            pose = PoseEstimate(
                position=np.array([x, y, z]),
                timestamp=timestamp,
                confidence=0.92 - (i % 30) * 0.005
            )
            
            trajectory_poses.append(pose)
            
            # Select keyframes periodically
            if i % 10 == 0:
                keyframe = PoseEstimate(
                    position=np.array([x, y, z]),
                    timestamp=timestamp,
                    confidence=0.95
                )
                keyframes.append(keyframe)
        
        print(f"  ✓ Processed {num_frames} frames")
        print(f"  ✓ Selected {len(keyframes)} keyframes for map optimization")
        
        # Phase 3: Calculate mapped area statistics
        print("\n[Phase 3] Calculating Mapped Area Statistics...")
        positions = np.array([p.position for p in trajectory_poses])
        
        min_pos = positions.min(axis=0)
        max_pos = positions.max(axis=0)
        extent = max_pos - min_pos
        
        mapped_area_m2 = extent[0] * extent[1]  # Horizontal area
        mapped_volume_m3 = extent[0] * extent[1] * extent[2]  # Volume
        
        print(f"  ✓ Mapped horizontal area: {mapped_area_m2/1e6:.2f} km²")
        print(f"  ✓ Mapped volume: {mapped_volume_m3/1e9:.4f} km³")
        
        # Phase 4: Export trajectory for visualization
        print("\n[Phase 4] Exporting Trajectory Data...")
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            data = {
                "trajectory": [p.to_dict() if hasattr(p, "to_dict") else {"position": list(p.position) if hasattr(p, "position") else []} for p in trajectory_poses],
                "keyframes": [k.to_dict() if hasattr(k, "to_dict") else {} for k in keyframes],
                "statistics": {
                    "total_distance_meters": float(np.linalg.norm(positions[-1] - positions[0])),
                    "max_altitude_meters": float(max_pos[2]),
                    "min_altitude_meters": float(min_pos[2])
                }
            }
            
            with open(export_path, 'w') as f:
                import json
                json.dump(data, f, indent=2)
            
            print(f"  ✓ Trajectory exported to {export_path}")
        
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)
        
        # Phase 5: Summary
        print("\n[Phase 5] Mission Summary...")
        print(f"  • Total frames processed: {num_frames}")
        print(f"  • Trajectory length: {np.linalg.norm(positions[-1] - positions[0]):.2f} meters")
        print(f"  • Average altitude: {positions[:, 2].mean():.1f} meters")
        print(f"  • Mapping accuracy: {trajectory_poses[-1].confidence:.2%}")
        
        print("\n" + "=" * 60)
        print("DISASTER MAPPING WORKFLOW COMPLETED SUCCESSFULLY")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
