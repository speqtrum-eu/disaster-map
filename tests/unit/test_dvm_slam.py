"""Unit Tests for DVM-SLAM Integration."""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from src.core.slam.dvm_slam import (
    DVM_SLAEngine, 
    DVMConfig,
    DVMNode,
    DVMConsensusState,
    MultiAgentSLAMManager,
)


class TestDVMNode:
    """Tests for DVMNode data class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        node = DVMNode(id="test_node")
        
        assert node.id == "test_node"
        assert np.allclose(node.position, [0.0, 0.0, 0.0])
        assert node.orientation is None
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        position = np.array([10.5, -20.3, 45.7])
        orientation = np.array([0.98, 0.06, 0.02, 0.0])
        
        node = DVMNode(
            id="node_1",
            position=position,
            orientation=orientation,
        )
        
        assert np.allclose(node.position, position)
        assert np.allclose(node.orientation, orientation)


class TestDVMConsensusState:
    """Tests for DVMConsensusState data class."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        state = DVMConsensusState()
        
        assert state.num_nodes == 0
        assert state.consensus_reached is False
        assert state.iterations == 0
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        state = DVMConsensusState(
            num_nodes=5,
            consensus_reached=True,
            iterations=12,
        )
        
        assert state.num_nodes == 5
        assert state.consensus_reached is True


class TestDVMConfig:
    """Tests for DVMConfig data class."""
    
    def test_initialization_default(self):
        """Test default configuration values."""
        config = DVMConfig()
        
        assert config.node_id == "node_0"
        assert config.consensus_interval == 1.0
        assert config.max_neighbors == 8
    
    def test_initialization_with_values(self):
        """Test initialization with custom values."""
        config = DVMConfig(
            node_id="drone_A",
            consensus_interval=2.0,
            max_neighbors=12,
        )
        
        assert config.node_id == "drone_A"
        assert config.consensus_interval == 2.0


class TestDVM_SLAEngine:
    """Tests for DVM_SLAEngine class."""
    
    def test_initialization_default(self):
        """Test engine initialization with default config."""
        engine = DVM_SLAEngine()
        
        assert not engine.initialized
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        config = DVMConfig(
            node_id="test_drone",
            consensus_interval=0.5,
        )
        
        engine = DVM_SLAEngine(config)
        
        assert engine.config.node_id == "test_drone"
    
    def test_initialization_success(self):
        """Test successful initialization."""
        config = DVMConfig(node_id="drone_A")
        engine = DVM_SLAEngine(config)
        
        result = engine.initialize()
        
        assert result is True
        assert engine.initialized
    
    def test_initialization_missing_node_id(self):
        """Test initialization failure when node_id not set."""
        config = DVMConfig(node_id="")  # Empty node_id
        
        with pytest.raises(ValueError, match="node_id must be set"):
            engine = DVM_SLAEngine(config)
            engine.initialize()
    
    def test_process_frame_fallback(self):
        """Test frame processing in fallback mode."""
        config = DVMConfig(node_id="test_node")
        engine = DVM_SLAEngine(config)
        
        # Initialize first
        engine.initialize()
        
        # Create mock frame data
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        timestamp = 123.456
        
        pose = engine.process_frame(frame, timestamp)
        
        assert pose.timestamp == timestamp
    
    def test_add_neighbor(self):
        """Test adding a neighbor node."""
        config = DVMConfig(node_id="node_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        position = np.array([10.0, 20.0, 50.0])
        
        result = engine.add_neighbor("node_B", position)
        
        assert result is True
    
    def test_remove_neighbor(self):
        """Test removing a neighbor node."""
        config = DVMConfig(node_id="node_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        # Add and remove neighbor
        engine.add_neighbor("node_B", np.array([10.0, 20.0, 50.0]))
        result = engine.remove_neighbor("node_B")
        
        assert result is True
    
    def test_remove_nonexistent_neighbor(self):
        """Test removing a non-existent neighbor."""
        config = DVMConfig(node_id="node_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        result = engine.remove_neighbor("nonexistent_node")
        
        assert result is False
    
    def test_reset_clears_state(self):
        """Test that reset clears all internal state."""
        config = DVMConfig(node_id="test_node")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        # Add some simulated data
        engine._neighbors["node_B"] = Mock()
        engine._consensus_state.iterations = 5
        
        assert len(engine._neighbors) == 1
        assert engine._consensus_state.iterations == 5
        
        # Reset should clear everything
        engine.reset()
        
        assert len(engine._neighbors) == 0
    
    def test_get_network_state(self):
        """Test retrieving network state."""
        config = DVMConfig(node_id="node_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        # Add a neighbor
        engine.add_neighbor("node_B", np.array([10.0, 20.0, 50.0]))
        
        state = engine.get_network_state()
        
        assert "node_id" in state
        assert state["node_id"] == "node_A"


class TestMultiAgentSLAMManager:
    """Tests for MultiAgentSLAMManager class."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = MultiAgentSLAMManager()
        
        assert len(manager._agents) == 0
    
    def test_register_agent(self):
        """Test registering a new agent."""
        config = DVMConfig(node_id="agent_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        manager = MultiAgentSLAMManager()
        
        result = manager.register_agent(engine)
        
        assert result is True
        assert len(manager._agents) == 1
    
    def test_register_duplicate_agent(self):
        """Test registering duplicate agent."""
        config = DVMConfig(node_id="agent_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        manager = MultiAgentSLAMManager()
        
        # Register twice should fail on second attempt
        result1 = manager.register_agent(engine)
        result2 = manager.register_agent(engine)
        
        assert result1 is True
        assert result2 is False
    
    def test_unregister_agent(self):
        """Test unregistering an agent."""
        config = DVMConfig(node_id="agent_A")
        engine = DVM_SLAEngine(config)
        engine.initialize()
        
        manager = MultiAgentSLAMManager()
        manager.register_agent(engine)
        
        result = manager.unregister_agent("agent_A")
        
        assert result is True
        assert len(manager._agents) == 0
    
    def test_get_fused_pose(self):
        """Test getting fused pose from multiple agents."""
        config_a = DVMConfig(node_id="agent_A")
        engine_a = DVM_SLAEngine(config_a)
        engine_a.initialize()
        
        config_b = DVMConfig(node_id="agent_B")
        engine_b = DVM_SLAEngine(config_b)
        engine_b.initialize()
        
        manager = MultiAgentSLAMManager()
        manager.register_agent(engine_a)
        manager.register_agent(engine_b)
        
        # Add poses to history
        pose_a = PoseEstimate(position=np.array([1.0, 2.0, 50.0]))
        pose_b = PoseEstimate(position=np.array([1.1, 2.1, 50.1]))
        
        engine_a._pose_history.append(pose_a)
        engine_b._pose_history.append(pose_b)
        
        fused_pose = manager.get_fused_pose()
        
        # Should return average pose
        assert fused_pose is not None
    
    def test_run_consensus_round(self):
        """Test running a consensus round."""
        config_a = DVMConfig(node_id="agent_A")
        engine_a = DVM_SLAEngine(config_a)
        engine_a.initialize()
        
        manager = MultiAgentSLAMManager()
        manager.register_agent(engine_a)
        
        # Need at least 2 agents for consensus
        result = manager.run_consensus_round()
        
        assert result is False  # Only one agent
    
    def test_get_fleet_status(self):
        """Test retrieving fleet status."""
        config_a = DVMConfig(node_id="agent_A")
        engine_a = DVM_SLAEngine(config_a)
        engine_a.initialize()
        
        manager = MultiAgentSLAMManager()
        manager.register_agent(engine_a)
        
        status = manager.get_fleet_status()
        
        assert "total_agents" in status
        assert status["total_agents"] == 1


# Integration tests with mock data
class TestDVMIntegration:
    """Integration tests for DVM-SLAM components."""
    
    def test_multi_agent_workflow(self):
        """Test complete multi-agent workflow simulation."""
        # Create multiple agents
        agents = []
        configs = [
            DVMConfig(node_id=f"drone_{i}") 
            for i in range(3)
        ]
        
        for config in configs:
            engine = DVM_SLAEngine(config)
            engine.initialize()
            agents.append(engine)
        
        # Create manager and register all agents
        manager = MultiAgentSLAMManager()
        
        for agent in agents:
            manager.register_agent(agent)
        
        assert len(manager._agents) == 3
        
        # Simulate processing frames across agents
        for i in range(5):
            timestamp = float(i * 0.1)
            
            for agent in agents:
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                pose = agent.process_frame(frame, timestamp)
                
                # Verify pose was computed
                assert pose.timestamp == timestamp
        
        # Get fused pose from all agents
        fused_pose = manager.get_fused_pose()
        
        assert fused_pose is not None
    
    def test_consensus_across_agents(self):
        """Test consensus operation across multiple agents."""
        # Create 3 agents with positions forming a triangle
        configs = [
            DVMConfig(node_id="node_A"),
            DVMConfig(node_id="node_B"),
            DVMConfig(node_id="node_C"),
        ]
        
        agents = []
        for config in configs:
            engine = DVM_SLAEngine(config)
            engine.initialize()
            
            # Set initial positions
            if config.node_id == "node_A":
                position = np.array([0.0, 0.0, 50.0])
            elif config.node_id == "node_B":
                position = np.array([10.0, 0.0, 50.0])
            else:
                position = np.array([5.0, 8.66, 50.0])  # Equilateral triangle
            
            engine._update_node_position(position)
            agents.append(engine)
        
        manager = MultiAgentSLAMManager()
        
        for agent in agents:
            manager.register_agent(agent)
        
        assert len(manager._agents) == 3
        
        # Run consensus round
        result = manager.run_consensus_round()
        
        # Should succeed with multiple agents
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
