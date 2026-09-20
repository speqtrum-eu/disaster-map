# =============================================================================
# Disaster Map - Disaster Recovery Plan (DRP)
# Version: 1.0 | Last Updated: September 20, 2026
# =============================================================================

## Table of Contents

- [Recovery Objectives](#recovery-objectives)
- [Recovery Scenarios](#recovery-scenarios)
- [Recovery Procedures](#recovery-procedures)
- [Data Backup & Restore](#data-backup--restore)
- [Testing & Maintenance](#testing--maintenance)

---

## Recovery Objectives

### RTO (Recovery Time Objective)

| System | RTO | Description |
|--------|-----|-------------|
| SLAM Backend API | 15 minutes | Full service restoration |
| Database Layer | 30 minutes | Data availability restored |
| Redis Cache | 5 minutes | Cache layer restoration |
| Monitoring Stack | 10 minutes | Observability restored |

### RPO (Recovery Point Objective)

| System | RPO | Description |
|--------|-----|-------------|
| User Trajectories | 5 minutes | Maximum data loss acceptable |
| Map Data | 1 hour | Historical map data |
| Configuration | 0 minutes | Zero configuration loss |
| Logs & Metrics | 1 hour | Audit trail preservation |

---

## Recovery Scenarios

### Scenario 1: Complete Service Outage

**Trigger:** All backend services unavailable, no response to health checks

**Recovery Steps:**
```bash
# Phase 1: Assessment (0-5 min)
echo "=== DISASTER RECOVERY INITIATED ===" | tee /var/log/dr/recovery.log
date >> /var/log/dr/recovery.log

# Verify complete outage
curl -f http://disaster-map-backend:8000/health || echo "Backend unreachable"
kubectl get pods -l app=disaster-map-backend -n production

# Phase 2: Infrastructure Recovery (5-15 min)
# Restore compute resources if needed
kubectl apply -f kubernetes/deployment.yaml -n production

# Verify infrastructure is healthy
kubectl get nodes
kubectl get services -l app=disaster-map-backend

# Phase 3: Data Services Recovery (15-25 min)
# Restore database connections
kubectl rollout restart deployment/postgres -n production

# Restore cache layer
kubectl rollout restart deployment/redis -n production

# Phase 4: Application Recovery (25-35 min)
# Deploy latest stable version
PREVIOUS_TAG="v1.0.0"  # Replace with last known good version
kubectl set image deployment/disaster-map-backend \
  backend=ghcr.io/disaster-map/backend:${PREVIOUS_TAG} \
  -n production

# Verify application is running
kubectl rollout status deployment/disaster-map-backend -n production --timeout=120s

# Phase 5: Validation (35-45 min)
# Run automated health checks
./scripts/health-check.sh

# Notify stakeholders
curl -X POST https://hooks.slack.com/services/XXX \
  -H 'Content-Type: application/json' \
  -d '{"text":"Service restored at $(date)"}'
```

**Estimated Recovery Time:** 45 minutes

---

### Scenario 2: Database Corruption

**Trigger:** Database reports corruption, queries failing with errors

**Recovery Steps:**
```bash
# Phase 1: Isolate the Issue (0-5 min)
# Stop all writes to prevent further damage
kubectl scale deployment/disaster-map-backend --replicas=0 -n production

# Check database status
psql -c "SELECT pg_is_in_recovery();"

# Phase 2: Restore from Backup (5-15 min)
# Identify last good backup
BACKUP_DATE=$(date -d '1 hour ago' '+%Y-%m-%d')
BACKUP_FILE="/backups/postgres/${BACKUP_DATE}-dump.sql.gz"

# Restore database
gunzip -c ${BACKUP_FILE} | psql disaster_map

# Verify data integrity
psql -c "SELECT count(*) FROM trajectories LIMIT 10;"

# Phase 3: Resume Services (15-25 min)
kubectl scale deployment/disaster-map-backend --replicas=3 -n production

# Monitor for errors
watch -n 5 'curl http://prometheus:9090/api/v1/query?query=sum(rate(error_total[1m]))'

# Phase 4: Data Validation (25-35 min)
# Verify trajectory data is intact
psql -c "SELECT count(*) FROM trajectories WHERE created_at > NOW() - INTERVAL '1 hour';"

# Notify stakeholders
```

**Estimated Recovery Time:** 35 minutes

---

### Scenario 3: Redis Cache Failure

**Trigger:** High cache miss rates, slow response times

**Recovery Steps:**
```bash
# Phase 1: Quick Assessment (0-2 min)
# Check Redis status
kubectl exec -it redis-master-0 -n production -- redis-cli ping

# Monitor cache metrics
curl 'http://prometheus:9090/api/v1/query?query=redis_connected_clients'

# Phase 2: Restart Cache Layer (2-5 min)
kubectl rollout restart deployment/redis -n production

# Verify Redis is responding
kubectl exec -it redis-master-0 -n production -- redis-cli info stats | grep connected_clients

# Phase 3: Warm Cache (5-10 min)
./scripts/warm-cache.sh

# Monitor cache hit rates
curl 'http://prometheus:9090/api/v1/query?query=redis_hits_total/redis_commands_total'

# Phase 4: Performance Validation (10-15 min)
# Verify response times are back to normal
curl 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(latency_seconds_bucket[1m]))'
```

**Estimated Recovery Time:** 15 minutes

---

### Scenario 4: Network Partition / Connectivity Loss

**Trigger:** Services unable to communicate with each other

**Recovery Steps:**
```bash
# Phase 1: Diagnose Network Issues (0-5 min)
# Check network connectivity between pods
kubectl exec -it disaster-map-backend-xxx -n production -- ping -c 3 redis-master-0

# Check DNS resolution
nslookup redis-master.disaster-map.svc.cluster.local

# Verify firewall rules
iptables -L -v -n | grep ESTABLISHED

# Phase 2: Restore Connectivity (5-10 min)
# If using cloud provider, check VPC peering
aws ec2 describe-vpcs --filters "Name=vpc-id,Values=<vpc-id>"

# Restart network plugins if necessary
kubectl delete pod -l k8s-app=kube-proxy -n kube-system

# Phase 3: Verify Service Communication (10-15 min)
# Test all service endpoints
for service in backend redis postgres; do
  echo "Testing $service..."
  curl -f http://$service:port/health || echo "$service unreachable"
done

# Phase 4: Performance Testing (15-20 min)
# Run load test to verify full connectivity
locust -f tests/performance/locustfile.py --users=10 --run-time=60s
```

**Estimated Recovery Time:** 20 minutes

---

### Scenario 5: Security Breach / Malicious Activity

**Trigger:** Suspicious activity detected, unauthorized access attempts

**Recovery Steps:**
```bash
# Phase 1: Containment (0-5 min)
# Isolate affected systems immediately
kubectl drain disaster-map-backend -n production --ignore-daemonsets --delete-emptydir-data

# Block suspicious IPs at firewall level
iptables -A INPUT -s <suspicious_ip> -j DROP

# Preserve evidence for forensics
tar czf /evidence/incident-$(date +%Y%m%d-%H%M%S).tar.gz \
  /var/log/disaster-map/ \
  /var/lib/kubelet/pods/

# Phase 2: Investigation (5-15 min)
# Analyze logs for attack patterns
grep -i "error\|attack\|malicious" /var/log/disaster-map/*.log | tail -100

# Check for unauthorized changes
git log --since="1 hour ago" --oneline
kubectl get pods --show-labels

# Phase 3: Remediation (15-30 min)
# Rotate all credentials and secrets
./scripts/rotate-secrets.sh

# Update security policies
kubectl apply -f kubernetes/security-policies.yaml -n production

# Rebuild affected components from clean images
docker build --no-cache -t disaster-map-backend:clean .
docker push ghcr.io/disaster-map/backend:clean

# Phase 4: Recovery (30-60 min)
# Deploy cleaned version
kubectl set image deployment/disaster-map-backend \
  backend=ghcr.io/disaster-map/backend:clean \
  -n production

# Monitor for suspicious activity
watch -n 5 'curl http://prometheus:9090/api/v1/query?query=sum(rate(error_total[1m]))'

# Phase 5: Post-Incident Review (Within 24 hours)
# Document all actions taken
# Conduct security audit
# Update incident response procedures
```

**Estimated Recovery Time:** 60 minutes + investigation time

---

## Data Backup & Restore

### Backup Schedule

| Data Type | Frequency | Retention | Storage Location |
|-----------|-----------|-----------|------------------|
| User Trajectories | Every 5 min | 30 days | S3 Glacier |
| Map Tiles | Daily | 90 days | S3 Standard-IA |
| Database Dump | Hourly | 7 days | GCS Coldline |
| Configuration | Real-time | Permanent | Git Repository |
| Logs & Metrics | Continuous | 14 days | Cloud Logging |

### Backup Verification

```bash
# Verify backup integrity (daily)
./scripts/verify-backups.sh

# Test restore procedure (weekly)
./scripts/test-restore.sh

# Generate backup report (monthly)
./scripts/generate-backup-report.sh > backup-report-$(date +%Y%m).txt
```

### Restore Procedures

#### Full Database Restore

```bash
#!/bin/bash
# scripts/restore-database.sh

set -e

BACKUP_FILE="${1:-latest}"
TARGET_DATABASE="disaster_map"

echo "=== Starting Database Restore ==="
echo "Backup file: $BACKUP_FILE"
echo "Target database: $TARGET_DATABASE"

# Stop all writes
kubectl scale deployment/disaster-map-backend --replicas=0 -n production

# Create new database for restore (safety measure)
psql -c "DROP DATABASE IF EXISTS disaster_map_restore;"
psql -c "CREATE DATABASE disaster_map_restore;"

# Restore from backup
gunzip -c "/backups/postgres/${BACKUP_FILE}.sql.gz" | psql disaster_map_restore

# Verify data integrity
psql -c "SELECT count(*) FROM trajectories LIMIT 10;"

# Switch to restored database
psql -c "ALTER DATABASE disaster_map_restore RENAME TO disaster_map;"

# Restart application
kubectl scale deployment/disaster-map-backend --replicas=3 -n production

echo "=== Database Restore Complete ==="
```

#### Point-in-Time Recovery (PITR)

```bash
#!/bin/bash
# scripts/pitr-restore.sh

set -e

TARGET_TIMESTAMP="${1:-$(date -d '1 hour ago' '+%Y-%m-%dT%H:%M:%S')}"

echo "=== Starting Point-in-Time Recovery ==="
echo "Target timestamp: $TARGET_TIMESTAMP"

# Use pg_basebackup for continuous backup recovery
pg_basebackup -D /tmp/pg_backup -Ft -z -Xs -P

# Restore to new cluster
psql -c "CREATE DATABASE disaster_map_pitr;"
gunzip -c "/tmp/pg_backup/base/*00000*" | psql disaster_map_pitr

# Verify recovery point
psql -c "SELECT now();"

# Switch application to recovered database
kubectl set env deployment/disaster-map-backend \
  POSTGRES_URL="postgresql://user:pass@postgres:5432/disaster_map_pitr" \
  -n production

echo "=== PITR Recovery Complete ==="
```

---

## Testing & Maintenance

### DRP Testing Schedule

| Test Type | Frequency | Owner | Duration |
|-----------|-----------|-------|----------|
| Tabletop Exercise | Monthly | Engineering Manager | 1 hour |
| Partial Failover Test | Quarterly | DevOps Team | 2 hours |
| Full Disaster Recovery | Annually | All Teams | 4-8 hours |
| Backup Verification | Weekly | DevOps Engineer | 30 min |

### Testing Procedures

#### Tabletop Exercise (Monthly)

```markdown
# Agenda:
1. Review recent incidents and lessons learned
2. Walk through recovery scenarios
3. Identify gaps in procedures
4. Update runbooks as needed
5. Assign action items for improvements
```

#### Partial Failover Test (Quarterly)

**Objective:** Verify ability to fail over to backup systems

**Steps:**
1. Notify stakeholders of test window
2. Execute controlled failover to secondary database
3. Monitor application performance
4. Verify data consistency
5. Restore primary system
6. Document results and lessons learned

#### Full Disaster Recovery (Annually)

**Objective:** Complete end-to-end disaster recovery validation

**Steps:**
1. Schedule maintenance window with stakeholders
2. Execute full DRP procedures in staging environment
3. Measure actual RTO/RPO against objectives
4. Validate all backup restoration procedures
5. Conduct post-test review meeting
6. Update DRP based on findings

### Maintenance Tasks

| Task | Frequency | Owner | Notes |
|------|-----------|-------|-------|
| Review and update runbooks | Monthly | DevOps Engineer | Incorporate lessons learned |
| Test backup restoration scripts | Weekly | DevOps Engineer | Automated testing in CI/CD |
| Validate monitoring alerts | Bi-weekly | SRE Team | Ensure alert thresholds are appropriate |
| Review DRP documentation | Quarterly | Engineering Manager | Keep procedures current |
| Update contact information | As needed | All Teams | Ensure on-call rotation is accurate |

---

## Contact Information

### Disaster Recovery Team

| Role | Name | Email | Phone | On-Call |
|------|------|-------|-------|---------|
| DRP Owner | TBD | drp-owner@disaster-map.io | +1-555-0200 | Rotating |
| Database Admin | TBD | dba@disaster-map.io | +1-555-0201 | On-call |
| Network Engineer | TBD | network@disaster-map.io | +1-555-0202 | On-call |
| Security Lead | TBD | security@disaster-map.io | +1-555-0203 | On-call |

### External Contacts

| Provider | Service | Contact | Phone |
|----------|---------|---------|-------|
| Cloud Provider | Support | support@cloud-provider.com | 800-XXX-XXXX |
| Backup Storage | Technical Support | backup-support@storage-provider.com | +1-555-0300 |
| Monitoring Service | Enterprise Support | enterprise@monitoring-service.com | +1-555-0400 |

---

## Related Documentation

- [Incident Response Procedures](./incident-response.md)
- [Deployment Runbook](./deployment.md)
- [Troubleshooting Guide](../troubleshooting/common-issues.md)
- [Monitoring Dashboard Setup](../monitoring/README.md)
