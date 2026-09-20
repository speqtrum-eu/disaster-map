# Test Suite Documentation

## Overview

This test suite provides comprehensive testing infrastructure for the disaster-map project, including:

- **Unit Tests**: >90% coverage on critical modules (SLAM, streaming, visualization)
- **Integration Tests**: End-to-end pipeline validation
- **Performance Benchmarks**: FPS, latency, and memory metrics
- **Regression Testing**: Automated testing on every PR

## Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/e2e/            # End-to-end tests

# Run with coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
```

## Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_slam/           # SLAM algorithm tests
│   │   └── test_pose.py     # Pose estimation tests
│   ├── test_streaming/      # Streaming module tests
│   │   └── test_rtsp.py     # RTSP client tests
│   ├── test_visualization/  # Visualization tests
│   │   └── test_camera.py   # Camera controller tests
│   └── conftest.py          # Unit test fixtures
├── integration/             # Integration tests
│   ├── test_pipeline.py     # Complete pipeline tests
│   └── test_slam_integration.py  # SLAM integration tests
├── e2e/                     # End-to-end tests
│   └── test_visualization.py  # Full visualization workflow
├── fixtures/                # Test data and fixtures
├── conftest.py              # Global pytest configuration
└── README.md                 # This file
```

## Running Tests by Category

### Unit Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Specific test module
pytest tests/unit/test_slam/test_pose.py -v

# With coverage
pytest tests/unit/ --cov=src.core.slam --cov-report=term-missing
```

### Integration Tests

```bash
# All integration tests
pytest tests/integration/ -v --timeout=300

# Specific pipeline test
pytest tests/integration/test_pipeline.py -v
```

### Performance Benchmarks

```bash
# Run SLAM benchmarks
python scripts/benchmark-slam.py --iterations 100

# Run latency benchmarks
python scripts/benchmark-latency.py --iterations 20

# Compare multiple algorithms
python scripts/benchmark-slam.py --algorithm orb_slam2
python scripts/benchmark-slam.py --algorithm dvm_slam
```

## CI/CD Integration

Tests are automatically run on every push and pull request via GitHub Actions:

- **Linting**: Black, isort, flake8, mypy, ruff
- **Testing**: Unit, integration, e2e tests with coverage
- **Benchmarks**: Performance regression detection
- **Security**: Bandit security scan

## Coverage Requirements

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| SLAM Engine | >90% | Critical |
| Data Pipeline | >85% | High |
| Visualization Layer | >80% | Medium |
| Navigation System | >75% | Low |

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| FPS (SLAM) | ≥30 | TBD |
| End-to-End Latency | ≤50ms | TBD |
| Memory Usage | <2GB | TBD |
| Tracking Success Rate | ≥95% | TBD |

## Regression Testing

Regression tests are automatically run on every PR:

```bash
# Run regression test suite
pytest tests/regression/ -v --mark=regression

# Check for performance regressions (>5% degradation)
python scripts/check-regressions.py --threshold 0.05
```

## Test Data

Test data is located in `test_data/`:

```bash
ls test_data/
├── videos/          # Sample video files
└── point_clouds/    # Point cloud test data
```

## Contributing

1. Add tests for new features
2. Ensure >80% coverage on critical modules
3. Include performance benchmarks where applicable
4. Update this README with any changes

## License

This test suite is part of the disaster-map project and follows its license terms.
