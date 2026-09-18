# Contributing to Disaster Map

Thank you for your interest in contributing to the disaster-map project! This document provides guidelines for contributors of all skill levels.

## 🎯 How to Contribute

### Types of Contributions

| Type | Examples | Difficulty |
|------|----------|------------|
| **Bug Fixes** | Fix crashes, improve error handling | Easy |
| **Performance Improvements** | Optimize FPS, reduce latency | Medium |
| **Feature Development** | New SLAM algorithms, visualization features | Hard |
| **Documentation** | Improve guides, add examples | Easy |
| **Testing** | Write unit tests, performance benchmarks | Medium |

### Getting Started

1. **Fork the repository**  
   `git clone https://github.com/your-username/disaster-map.git`

2. **Create a feature branch**  
   ```bash
   git checkout -b feature/improve-slam-performance
   ```

3. **Make your changes**  
   Follow the coding standards in [AGENTS.md](./AGENTS.md)

4. **Run tests locally**  
   ```bash
   pytest tests/unit --cov=src
   ```

5. **Submit a Pull Request**  
   Use the template in `.github/PULL_REQUEST_TEMPLATE.md`

## 📋 Code of Conduct

### Our Pledge

We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

Examples of behavior that contributes to a positive environment:
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

Examples of unacceptable behavior include:
- The use of sexualized language or imagery
- Personal attacks
- Trolling or insulting/derogatory comments
- Public or private harassment
- Publishing others' private information

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team at `dev@disaster-map.org`. All complaints will be reviewed and investigated promptly.

## 📁 Project Structure Overview

```
disaster-map/
├── src/              # Source code
│   ├── core/         # Core SLAM engine integration
│   ├── streaming/    # RTMP/RTSP stream handling
│   ├── mapping/      # Map data management
│   └── visualization/# 3D visualization layer
├── tests/            # Test suite
├── docs/             # Documentation
└── config/           # Configuration files
```

## 🎨 Coding Standards

### General Guidelines

1. **Code Style**  
   - Python: Follow [PEP 8](https://pep8.org/) style guide
   - JavaScript: Use ESLint with Airbnb preset
   - C++: Follow Google C++ Style Guide

2. **Commit Messages**  
   Use conventional commits format:
   ```
   feat: Add new SLAM algorithm integration
   fix: Resolve RTSP stream timeout issue
   docs: Update quick start guide
   refactor: Improve memory management in map state
   test: Add unit tests for frame processor
   perf: Optimize point cloud rendering performance
   ```

3. **Pull Requests**  
   - Include a clear description of changes
   - Reference related issues (e.g., `Closes #123`)
   - Ensure all CI checks pass before merging
   - Request reviews from at least 2 maintainers

### Agent-Specific Guidelines

See [AGENTS.md](./AGENTS.md) for detailed coding standards by role:
- **Vision Agent**: C++/Python SLAM code
- **Backend Agent**: Data pipelines, APIs
- **Frontend Agent**: WebGL/React components
- **DevOps Agent**: Docker, CI/CD scripts
- **QA Agent**: Test infrastructure

## 🧪 Testing Requirements

All contributions must include appropriate tests:

| Contribution Type | Required Tests |
|-------------------|----------------|
| Bug fix | Unit test for the fix |
| New feature | Unit + integration tests |
| Performance improvement | Benchmark results included |
| Documentation | N/A (but verify existing docs) |

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_slam.py -v

# Run integration tests
pytest tests/integration/ -v
```

## 📚 Documentation

### Writing Documentation

1. **Location**: All documentation goes in `docs/` directory
2. **Format**: Markdown with code examples
3. **Style**: Clear, concise, and actionable

Example structure:
```markdown
# Quick Start Guide

## Prerequisites

- Python 3.10+
- Docker

## Installation

```bash
pip install disaster-map
```

## Usage

See the [full documentation](./docs/usage.md) for details.
```

### Documentation Checklist

- [ ] Code examples are tested and working
- [ ] Screenshots included where helpful
- [ ] Links to external resources verified
- [ ] No broken links or typos

## 🔄 Review Process

1. **Submission**  
   Submit your PR with a clear description of changes

2. **Automated Checks**  
   CI will run:
   - Unit tests
   - Integration tests
   - Code style checks (linting, formatting)
   - Security scanning

3. **Code Review**  
   Maintainers will review your code within 48 hours
   - Questions? Ask in PR comments
   - Changes requested? Make them promptly

4. **Merge**  
   Once approved, changes are merged to `main` branch

## 📊 Performance Guidelines

### SLAM Performance Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| FPS | ≥ 30 | Process sample video sequence |
| Latency | < 50ms | End-to-end frame processing time |
| Memory | ≤ 2GB | Monitor during long-running session |

### Visualization Performance Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| FPS | ≥ 60 | Browser performance tab |
| Render Time | < 16ms | GPU profiling tools |
| Memory | ≤ 512MB | Chrome DevTools memory panel |

## 🆘 Getting Help

### Resources

- **Documentation**: [Read the Docs](https://disaster-map.readthedocs.io)
- **GitHub Issues**: [Open an issue](https://github.com/your-org/disaster-map/issues)
- **Slack**: Join #disaster-map-dev for real-time help
- **Email**: dev@disaster-map.org

### Common Questions

**Q: How do I report a bug?**  
A: Use the GitHub issue template at `.github/ISSUE_TEMPLATE/bug_report.md`

**Q: Can I suggest a new feature?**  
A: Yes! Submit a feature request via GitHub Issues

**Q: Who should I contact for questions?**  
A: Start with GitHub Discussions, then Slack or email

## 📜 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License. See [LICENSE](./LICENSE) for details.

## 👏 Thank You!

Your contributions help make disaster-map better for everyone. Whether it's fixing a typo, improving performance, or adding new features, every contribution matters!