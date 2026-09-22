# Code Review Checklist

## Overview

This document provides a comprehensive code review checklist for the Disaster Map project. All pull requests should be reviewed against these criteria.

---

## Documentation Standards

### Required Documentation

- [ ] **README Updates**: If new features are added, update `README.md` with usage instructions
- [ ] **API Documentation**: Update OpenAPI spec in `docs/api/openapi.yaml` for any API changes
- [ ] **Type Definitions**: Add TypeScript definitions to `src/types/index.d.ts` for new types

### Code Comments

- [ ] Functions have descriptive names that indicate their purpose
- [ ] Complex logic includes inline comments explaining the "why" not just the "what"
- [ ] Public APIs are documented with docstrings or JSDoc comments
- [ ] TODO/FIXME comments include issue references when possible

---

## Code Quality Standards

### Naming Conventions

| Language | Convention | Example |
|----------|------------|---------|
| Python | snake_case for functions/variables, PascalCase for classes | `process_frame()`, `FrameProcessor` |
| JavaScript/TypeScript | camelCase for variables/functions, PascalCase for components/classes | `handleError()`, `PointCloudComponent` |

### Code Style

- [ ] Follow project-specific linting rules (ESLint/Prettier)
- [ ] Use consistent indentation (2 spaces recommended)
- [ ] Maximum line length: 100 characters
- [ ] No trailing whitespace
- [ ] Blank lines between logical sections

---

## Performance Requirements

### SLAM Processing

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| FPS | ≥ 30 fps | Benchmark with `benchmark/performance_benchmark.py` |
| Latency | ≤ 50ms end-to-end | Measure from frame capture to pose output |
| Memory | < 2GB peak usage | Monitor during extended operation |

### Web Viewer

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| FPS | ≥ 60 fps on modern hardware | Browser DevTools Performance tab |
| Load Time | < 5 seconds initial load | Lighthouse audit |
| Memory | Stable under interaction | Monitor during navigation |

### Data Processing

- [ ] Large datasets use streaming/chunking where possible
- [ ] Database queries include appropriate indexes
- [ ] API responses are paginated for large result sets
- [ ] File uploads support progress indicators

---

## Testing Requirements

### Unit Tests

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| SLAM Engine | > 90% | Critical |
| Data Pipeline | > 85% | High |
| Visualization Layer | > 80% | Medium |
| Navigation System | > 75% | Low |

**Test Requirements:**
- [ ] All public functions have unit tests
- [ ] Edge cases are tested (empty input, invalid data)
- [ ] Error conditions produce appropriate exceptions/messages
- [ ] Tests run in < 30 seconds total execution time

### Integration Tests

- [ ] API endpoints return expected responses for valid/invalid inputs
- [ ] Data flows correctly through the processing pipeline
- [ ] External services (database, storage) are mocked appropriately
- [ ] Error handling works end-to-end

### E2E Tests

- [ ] Critical user workflows are tested with Playwright
- [ ] Performance benchmarks pass under load
- [ ] Cross-browser compatibility verified (Chrome, Firefox, Safari)

---

## Security Standards

### Authentication & Authorization

- [ ] API endpoints require authentication where appropriate
- [ ] JWT tokens are validated and have proper expiration
- [ ] Sensitive data is encrypted at rest and in transit
- [ ] No hardcoded credentials or secrets in code

### Input Validation

- [ ] All user inputs are sanitized before processing
- [ ] File uploads are validated for type and size limits
- [ ] SQL injection prevention through parameterized queries
- [ ] XSS prevention through output encoding

---

## Architecture Standards

### Code Organization

```
src/
├── core/              # Core SLAM algorithms
├── data_pipeline/     # Video processing pipeline
├── streaming/         # Real-time communication
├── visualization/     # 3D rendering and display
└── utils/             # Helper functions
```

- [ ] Each module has a single responsibility
- [ ] Dependencies are minimized and well-documented
- [ ] Configuration is externalized (not hardcoded)
- [ ] Error handling is consistent across modules

### API Design

- [ ] RESTful endpoints follow standard conventions
- [ ] Response formats are consistent (JSON with error handling)
- [ ] Versioning strategy is in place for breaking changes
- [ ] Rate limiting is implemented for public APIs

---

## Code Review Process

### Before Submitting a PR

1. **Self-Review Checklist**
   - [ ] Code follows project standards
   - [ ] All tests pass locally
   - [ ] Documentation is updated
   - [ ] No console.log or debug statements remain

2. **Required Changes**
   - [ ] Address all feedback from previous reviews
   - [ ] Include meaningful commit messages
   - [ ] Link related issues in PR description

### Reviewer Responsibilities

1. **First Pass: Code Quality**
   - Check for code style violations
   - Verify naming conventions
   - Ensure proper error handling

2. **Second Pass: Functionality**
   - Test the changes locally if possible
   - Verify tests cover new functionality
   - Check performance impact

3. **Third Pass: Architecture & Security**
   - Review for architectural consistency
   - Identify potential security issues
   - Ensure scalability considerations

### Approval Criteria

A PR can be merged when:
- All required checks pass (CI, linting, tests)
- At least one maintainer approves the changes
- No critical or high-priority issues remain open
- Documentation is complete and accurate

---

## Common Issues to Watch For

| Issue | Severity | Example |
|-------|----------|---------|
| Memory leaks | Critical | Unreleased geometries in viewer |
| Race conditions | High | Concurrent frame processing without locks |
| Hardcoded values | Medium | Magic numbers, hardcoded paths |
| Missing error handling | Medium | Silent failures on invalid input |
| Inconsistent logging | Low | Mixed log levels, missing context |

---

## Resources

- [Project Style Guide](./STYLE_GUIDE.md) - Detailed coding standards
- [API Documentation](../docs/api/openapi.yaml) - API specifications
- [Architecture Overview](../docs/architecture.md) - System design
- [Performance Benchmarks](../benchmarks/performance_benchmark.py) - Testing tools

---

## Contact

For questions about code review or contributing:
- **Email:** support@disaster-map.local
- **Slack:** #code-review channel
- **GitHub Issues:** https://github.com/disaster-map/issues
