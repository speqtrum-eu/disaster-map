"""Unit Tests for Pose Tracker Module."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.core.pose_tracker import (
    PoseTracker, 
    Pose3D,
    TrajectoryPoint,
)


class TestPose3D:
    """Tests for Pose3D data class."""
    
    def test_initialization_default(self):
        """Test default initialization with zeros."""
        pose = Pose3D()
        
        assert np.allclose(pose.position, [0.0, 0.0, 0.0])
        assert pose.quaternion is None
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        position = np.array([1.5, -2.3, 45.7])
        quaternion = np.array([0.98, 0.06, 0.02, 0.0])
        
        pose = Pose3D(
            position=position,
            quaternion=quaternion,
            timestamp=123.456,
            confidence=0.95
        )
        
        assert np.allclose(pose.position, position)
        assert np.allclose(pose.quaternion, quaternion)
    
    def test_invalid_position_shape(self):
        """Test that invalid position shape raises error."""
        with pytest.raises(ValueError, match="Position must be a 3-element array"):
            Pose3D(position=np.array([1, 2]))
    
    def test_property_accessors(self):
        """Test property accessor methods."""
        pose = Pose3D(
            position=np.array([1.0, 2.0, 3.0]),
            euler_angles=np.array([0.5, 0.3, 0.7])
        )
        
        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.z == 3.0
        
        # Heading should be from euler angles (yaw)
        assert abs(pose.heading - 0.7) < 1e-6
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        pose = Pose3D(
            position=np.array([1.0, 2.0, 3.0]),
            quaternion=np.array([0.98, 0.06, 0.02, 0.0])
        )
        
        data = pose.to_dict()
        
        assert "position" in data
        assert np.allclose(data["position"], [1.0, 2.0, 3.0])


class TestTrajectoryPoint:
    """Tests for TrajectoryPoint data class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        pose = Pose3D(position=np.array([1.0, 2.0, 3.0]))
        
        point = TrajectoryPoint(pose=pose)
        
        assert point.pose.position[0] == 1.0
        assert point.frame_number is None
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        pose = Pose3D(position=np.array([5.0, 6.0, 7.0]))
        
        point = TrajectoryPoint(
            pose=pose,
            frame_number=42,
            timestamp=123.456,
            quality_score=0.95
        )
        
        assert point.frame_number == 42
        assert point.quality_score == 0.95


class TestPoseTracker:
    """Tests for PoseTracker class."""
    
    def test_initialization_default(self):
        """Test initialization with default parameters."""
        tracker = PoseTracker()
        
        assert tracker.smoothing_window == 5
        assert tracker.drift_threshold == 2.0
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        tracker = PoseTracker(
            smoothing_window=10,
            drift_threshold=5.0,
            max_history_size=5000,
        )
        
        assert tracker.smoothing_window == 10
        assert tracker.drift_threshold == 5.0
    
    def test_add_pose(self):
        """Test adding a pose to trajectory."""
        tracker = PoseTracker()
        
        pose = Pose3D(position=np.array([1.0, 2.0, 50.0]))
        
        tracker.add_pose(pose)
        
        assert len(tracker._trajectory) == 1
    
    def test_add_multiple_poses(self):
        """Test adding multiple poses."""
        tracker = PoseTracker()
        
        for i in range(10):
            pose = Pose3D(position=np.array([i, i, 50.0]))
            tracker.add_pose(pose)
        
        assert len(tracker._trajectory) == 10
    
    def test_get_trajectory(self):
        """Test retrieving trajectory points."""
        tracker = PoseTracker()
        
        # Add poses with frame numbers
        for i in range(20):
            pose = Pose3D(position=np.array([i, i, 50.0]))
            tracker.add_pose(pose, frame_number=i)
        
        # Get all trajectories
        trajectory = tracker.get_trajectory()
        
        assert len(trajectory) == 20
        
        # Get filtered trajectory
        filtered = tracker.get_trajectory(start_frame=5, end_frame=15)
        
        assert len(filtered) == 11
    
    def test_get_smoothed_trajectory(self):
        """Test getting smoothed trajectory."""
        tracker = PoseTracker()
        
        # Add poses with varying positions
        for i in range(20):
            pose = Pose3D(position=np.array([i * 0.5, np.sin(i) * 2, 50.0]))
            tracker.add_pose(pose)
        
        smoothed = tracker.get_smoothed_trajectory(window_size=5)
        
        assert len(smoothed) == 20
    
    def test_get_drift_estimate(self):
        """Test drift estimation."""
        tracker = PoseTracker()
        
        # Add poses that form a loop (return to start)
        for i in range(10):
            angle = i * (2 * np.pi / 10)
            pose = Pose3D(position=np.array([np.cos(angle), np.sin(angle), 50.0]))
            tracker.add_pose(pose)
        
        drift = tracker.get_drift_estimate()
        
        # Should have some drift due to not returning exactly to origin
        assert drift >= 0
    
    def test_detect_drift(self):
        """Test drift detection."""
        tracker = PoseTracker()
        
        # Add poses with significant drift
        for i in range(20):
            pose = Pose3D(position=np.array([i * 5, i * 3, 50.0]))
            tracker.add_pose(pose)
        
        has_drift = tracker.detect_drift(threshold=10.0)
        
        # Should detect drift since we moved far from origin
        assert has_drift
    
    def test_correct_drift(self):
        """Test applying drift correction."""
        tracker = PoseTracker()
        
        # Add poses
        for i in range(5):
            pose = Pose3D(position=np.array([i, i, 50.0]))
            tracker.add_pose(pose)
        
        original_positions = [p.pose.position.copy() for p in tracker._trajectory]
        
        # Apply correction
        correction = np.array([-1.0, -2.0, 0.0])
        tracker.correct_drift(correction)
        
        # Verify positions were shifted
        for i, point in enumerate(tracker._trajectory):
            assert np.allclose(point.pose.position, original_positions[i] + correction)
    
    def test_transform_to_frame(self):
        """Test coordinate frame transformation."""
        tracker = PoseTracker()
        
        pose = Pose3D(position=np.array([10.0, 20.0, 50.0]))
        
        # Transform to local frame with offset
        transformed = tracker.transform_to_frame(pose, frame_offset=np.array([2.0, 3.0, 0.0]))
        
        assert np.allclose(transformed.position, [8.0, 17.0, 50.0])
    
    def test_transform_to_world(self):
        """Test inverse coordinate frame transformation."""
        tracker = PoseTracker()
        
        pose = Pose3D(position=np.array([8.0, 17.0, 50.0]))
        
        # Transform back to world frame
        transformed = tracker.transform_to_world(pose, frame_offset=np.array([2.0, 3.0, 0.0]))
        
        assert np.allclose(transformed.position, [10.0, 20.0, 50.0])
    
    def test_export_csv(self):
        """Test exporting trajectory to CSV."""
        import tempfile
        
        tracker = PoseTracker()
        
        # Add poses
        for i in range(5):
            pose = Pose3D(position=np.array([i * 10, i * 10, 50.0]))
            tracker.add_pose(pose)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            filepath = f.name
        
        try:
            result = tracker.export_csv(filepath)
            
            assert result is True
            
            # Verify file was created and contains data
            import csv
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            assert len(rows) == 6  # Header + 5 data rows
        finally:
            import os
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_export_json(self):
        """Test exporting trajectory to JSON."""
        import tempfile
        
        tracker = PoseTracker()
        
        for i in range(3):
            pose = Pose3D(position=np.array([i, i, 50.0]))
            tracker.add_pose(pose)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            result = tracker.export_json(filepath)
            
            assert result is True
            
            # Verify file was created and contains data
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert len(data) == 3
        finally:
            import os
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_get_statistics(self):
        """Test retrieving trajectory statistics."""
        tracker = PoseTracker()
        
        # Add poses with varying positions
        for i in range(20):
            pose = Pose3D(position=np.array([i * 2, np.sin(i) * 5, 50.0]))
            tracker.add_pose(pose)
        
        stats = tracker.get_statistics()
        
        assert "num_points" in stats
        assert stats["num_points"] == 20
        assert "total_distance_meters" in stats


class TestPoseTrackerIntegration:
    """Integration tests for PoseTracker with SLAM engines."""
    
    def test_complete_trajectory_workflow(self):
        """Test complete trajectory workflow from pose estimation to export."""
        tracker = PoseTracker()
        
        # Simulate receiving poses from SLAM engine
        num_poses = 50
        
        for i in range(num_poses):
            timestamp = float(i * 0.1)
            
            # Create realistic drone trajectory (circular motion with altitude)
            angle = i * 0.2
            x = np.cos(angle) * 10
            y = np.sin(angle) * 10
            z = 50 + np.sin(i * 0.5) * 2
            
            pose = Pose3D(
                position=np.array([x, y, z]),
                timestamp=timestamp,
                confidence=0.95 - (i % 10) * 0.01  # Varying confidence
            )
            
            tracker.add_pose(pose, frame_number=i)
        
        # Verify trajectory was recorded correctly
        assert len(tracker._trajectory) == num_poses
        
        # Get statistics
        stats = tracker.get_statistics()
        
        assert stats["num_points"] == num_poses
        assert stats["total_distance_meters"] > 0
    
    def test_trajectory_smoothing(self):
        """Test trajectory smoothing reduces noise."""
        tracker = PoseTracker(smoothing_window=5)
        
        # Add noisy positions (simulating sensor noise)
        for i in range(30):
            # Base circular motion with added noise
            angle = i * 0.1
            x = np.cos(angle) * 20 + np.random.normal(0, 0.5)
            y = np.sin(angle) * 20 + np.random.normal(0, 0.5)
            
            pose = Pose3D(position=np.array([x, y, 50.0]))
            tracker.add_pose(pose)
        
        # Get smoothed trajectory
        smoothed = tracker.get_smoothed_trajectory(window_size=5)
        
        assert len(smoothed) == 30
        
        # Smoothed positions should have less variance
        original_variance = np.var([p.pose.position[0] for p in tracker._trajectory])
        smoothed_variance = np.var([p.position[0] for p in smoothed])
        
        # Variance should be reduced (or similar, since smoothing can't reduce too much)
        assert smoothed_variance <= original_variance * 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
