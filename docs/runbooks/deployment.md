# =============================================================================
# Disaster Map - Production Deployment Runbook
# Version: 1.0 | Last Updated: September 20, 2026
# =============================================================================

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Staging Deployment](#staging-deployment)
- [Production Deployment](#production-deployment)
- [Rollback Procedures](#rollback-procedures)
- [Post-Deployment Verification](#post-deployment-verification)

---

## Pre-Deployment Checklist

### Code Quality Gates (Automated via CI/CD)

| Check | Status | Action Required |
|-------|--------|-----------------|
| Linting passes | ✅ Pass | None |
| Unit test coverage ≥ 80% | ✅ Pass | None |
| Security scan (Trivy) - No CRITICAL/HIGH | ✅ Pass | None |
| Performance tests pass | ✅ Pass | None |

### Manual Verification

- [ ] Review pull request changes for critical bugs
- [ ] Verify all feature flags are properly configured
- [ ] Check database migration scripts are up to date
- [ ] Validate environment variables in deployment config
- [ ] Confirm monitoring dashboards show healthy metrics

---

## Staging Deployment

### Automated Deployment (GitHub Actions)

```yaml
# Triggered automatically on push to main branch
job: deploy-staging
  - Deploy disaster-map-backend v${{ github.sha }} to staging
  - Run integration tests against staging environment
  - Verify SLAM FPS ≥ 30 in load test
```

### Manual Staging Deployment

1. **Build the Docker image**
   ```bash
   docker build -t disaster-map-backend:staging \
     --build-arg BUILDKIT_INLINE_CACHE=1 \
     ./docker/
   ```

2. **Push to registry**
   ```bash
   docker push ghcr.io/disaster-map/backend:staging-${{ github.sha }}
   ```

3. **Update Kubernetes deployment** (if using K8s)
   ```bash
   kubectl set image deployment/disaster-map-backend \
     backend=ghcr.io/disaster-map/backend:staging-${{ github.sha }} \
     -n staging
   ```

4. **Verify deployment**
   ```bash
   kubectl rollout status deployment/disaster-map-backend -n staging
   kubectl get pods -l app=disaster-map-backend -n staging
   ```

---

## Production Deployment

### Release Process (Tagged Releases)

1. **Create release tag**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. **CI/CD triggers production deployment automatically**
   - Builds Docker image with version tag
   - Runs security scan (Trivy)
   - Deploys to production environment
   - Generates release notes in CHANGELOG.md

### Manual Production Deployment (Emergency Only)

> ⚠️ **WARNING**: Manual production deployments should only be used for emergency fixes. Always prefer the automated CI/CD pipeline.

1. **Verify current state**
   ```bash
   # Check running pods
   kubectl get pods -l app=disaster-map-backend -n production
   
   # Check recent logs
   kubectl logs -l app=disaster-map-backend -n production --tail=100
   
   # Verify metrics are healthy
   curl http://prometheus:9090/api/v1/query?query=up{job="disaster-map-backend"}
   ```

2. **Create emergency deployment**
   ```bash
   # Build and tag image
   docker build -t disaster-map-backend:emergency \
     --build-arg BUILDKIT_INLINE_CACHE=1 \
     ./docker/
   
   # Push to registry
   docker push ghcr.io/disaster-map/backend:emergency
   
   # Deploy with rollout strategy
   kubectl set image deployment/disaster-map-backend \
     backend=ghcr.io/disaster-map/backend:emergency \
     -n production --record
   ```

3. **Monitor deployment**
   ```bash
   # Watch pod status
   kubectl rollout status deployment/disaster-map-backend -n production --timeout=120s
   
   # Check for errors in logs
   kubectl logs -l app=disaster-map-backend -n production --tail=500 | grep -i error
   
   # Verify metrics
   curl http://grafana:3000/api/d/disaster-map-slam-monitoring?orgId=1
   ```

---

## Rollback Procedures

### Automatic Rollback (CI/CD)

If deployment fails or triggers alerts:

```yaml
# In CI/CD pipeline, add rollback step
- name: Auto-rollback on failure
  if: failure() && needs.deploy-production.status == 'completed'
  run: |
    kubectl rollout undo deployment/disaster-map-backend -n production
    echo "Rolled back to previous version"
```

### Manual Rollback

1. **Identify previous working image**
   ```bash
   # List all images for this deployment
   kubectl get pods -l app=disaster-map-backend -n production -o jsonpath='{.items[0].spec.containers[*].image}' | tr ' ' '\n' | sort -u
   
   # Find the previous version tag
   PREVIOUS_TAG="v1.0.0"  # Replace with actual previous version
   ```

2. **Execute rollback**
   ```bash
   kubectl rollout undo deployment/disaster-map-backend -n production
   kubectl set image deployment/disaster-map-backend \
     backend=ghcr.io/disaster-map/backend:${PREVIOUS_TAG} \
     -n production
   
   # Verify rollback completed
   kubectl rollout status deployment/disaster-map-backend -n production
   ```

3. **Validate rollback**
   ```bash
   # Check all pods are running
   kubectl get pods -l app=disaster-map-backend -n production
   
   # Verify metrics are back to normal
   curl http://prometheus:9090/api/v1/query?query=rate(frame_processed_total[1m])
   
   # Check for any lingering errors
   kubectl logs -l app=disaster-map-backend -n production --tail=200 | grep -i error
   ```

---

## Post-Deployment Verification

### Automated Checks (CI/CD)

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Health endpoint | `curl http://localhost:8000/health` | HTTP 200 OK |
| FPS metric | `rate(frame_processed_total[1m]) * 60` | ≥ 30 fps |
| Error rate | `sum(rate(error_total[1m])) / sum(rate(request_total[1m]))` | < 5% |
| Latency P95 | `histogram_quantile(0.95, rate(latency_seconds_bucket[1m]))` | < 200ms |

### Manual Verification Checklist

- [ ] All pods are running and healthy
- [ ] No critical alerts in monitoring dashboard
- [ ] SLAM FPS ≥ 30 fps under load
- [ ] Error rates within acceptable thresholds (< 5%)
- [ ] Latency P95 < 200ms
- [ ] Memory usage < 85% of limit
- [ ] No connection timeouts or drops

### Verification Commands

```bash
# Health check endpoint
curl -f http://disaster-map-backend:8000/health || echo "Health check failed"

# Check FPS metrics (via Prometheus)
curl 'http://prometheus:9090/api/v1/query?query=rate(frame_processed_total[1m])*60'

# Check error rates
curl 'http://prometheus:9090/api/v1/query?query=sum(rate(error_total[1m]))/sum(rate(request_total[1m]))*100'

# Verify active streams
curl 'http://disaster-map-backend:8000/metrics?include=active_streams'

# Check Grafana dashboard
open http://grafana:3000/d/disaster-map-slam-monitoring
```

---

## Deployment Timeline

| Phase | Duration | Owner |
|-------|----------|-------|
| Pre-deployment checks | 5 min | DevOps Engineer |
| Staging deployment | 2-5 min | Automated (CI/CD) |
| Staging verification | 10 min | QA Engineer |
| Production deployment | 2-5 min | Automated (CI/CD) |
| Post-deployment verification | 15 min | DevOps Engineer |

---

## Contact Information

| Role | Name | Email | Phone |
|------|------|-------|-------|
| On-call DevOps | TBD | oncall@disaster-map.io | +1-555-0123 |
| Lead Backend Engineer | TBD | backend-lead@disaster-map.io | +1-555-0124 |
| Infrastructure Manager | TBD | infra@disaster-map.io | +1-555-0125 |

---

## Related Documentation

- [Troubleshooting Guide](./troubleshooting.md)
- [Incident Response Procedures](./incident-response.md)
- [Disaster Recovery Plan](./disaster-recovery.md)
- [Monitoring Dashboard Setup](../monitoring/README.md)
