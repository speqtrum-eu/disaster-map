# =============================================================================
# Disaster Map - Troubleshooting Guide
# Common Issues and Solutions for Production Systems
# =============================================================================

## Table of Contents

- [SLAM Performance Issues](#slam-performance-issues)
- [Connection & Streaming Problems](#connection--streaming-problems)
- [Memory & Resource Issues](#memory--resource-issues)
- [Network & Latency Problems](#network--latency-problems)
- [Database & Cache Issues](#database--cache-issues)
- [Deployment & Infrastructure](#deployment--infrastructure)

---

## SLAM Performance Issues

### Issue: Low FPS (< 30 fps)

**Symptoms:**
- Dashboard shows FPS below 30
- Video feed appears choppy
- Tracking drift increases rapidly

**Root Causes:**
1. CPU overload from feature extraction
2. Insufficient keyframe density
3. High-resolution video streams
4. Memory pressure causing GC pauses

**Diagnosis Commands:**
```bash
# Check CPU utilization
kubectl top pods -l app=disaster-map-backend

# Monitor FPS metrics in Prometheus
curl 'http://prometheus:9090/api/v1/query?query=rate(frame_processed_total[1m])*60'

# Check memory pressure
docker stats disaster-map-backend --no-stream
```

**Solutions:**

| Solution | Impact | When to Apply |
|----------|--------|---------------|
| Reduce video resolution | High | Immediate relief |
| Increase CPU allocation | Medium | If CPU > 80% |
| Adjust keyframe interval | Low | Fine-tuning |
| Enable GPU acceleration | High | Long-term optimization |

**Configuration Changes:**
```yaml
# In config/slam.yaml, reduce resolution:
video_resolution:
  width: 640    # Default: 1280
  height: 480   # Default: 720

# Increase keyframe interval (lower density):
keyframe_interval: 5.0  # Seconds between keyframes
```

---

### Issue: High Latency (> 200ms)

**Symptoms:**
- Processing delays visible in video feed
- Real-time tracking feels laggy
- P95 latency exceeds threshold

**Root Causes:**
1. I/O bottlenecks from disk operations
2. Network latency between services
3. Database query timeouts
4. Redis cache misses

**Diagnosis Commands:**
```bash
# Check end-to-end latency
curl -w "@http://disaster-map-backend:8000/metrics/latency" http://localhost:8000/api/health

# Monitor database queries
psql -c "SELECT now() - pg_last_xact_replay_timestamp()"

# Check Redis hit rate
redis-cli INFO stats | grep hits
```

**Solutions:**
1. Enable query caching for frequently accessed map data
2. Optimize database indexes on trajectory tables
3. Use connection pooling for Redis
4. Consider SSD storage for video frames

---

### Issue: Tracking Loss / Drift

**Symptoms:**
- Map diverges from actual position
- Features disappear suddenly
- Loop closure fails repeatedly

**Root Causes:**
1. Low-texture environments
2. Rapid camera motion
3. Lighting changes
4. Feature tracking saturation

**Solutions:**
```python
# In src/core/slam/base_slam.py, adjust parameters:

def configure_tracking(self):
    # Increase feature matching threshold for challenging conditions
    self.matcher_params = cv.DMatchMatcherParams()
    self.matcher_params.crossCheck = False
    
    # Enable IMU data fusion if available
    self.enable_imu_fusion = True
    
    # Adjust relocalization sensitivity
    self.relocalization_threshold = 0.5  # Lower for more aggressive relocalization
```

---

## Connection & Streaming Problems

### Issue: RTSP/RTMP Stream Disconnections

**Symptoms:**
- Video feed drops intermittently
- "Connection lost" errors in logs
- High reconnection rate

**Root Causes:**
1. Network instability
2. Firewall blocking ports
3. Buffer overflow on network devices
4. Client timeout settings too aggressive

**Diagnosis Commands:**
```bash
# Check active connections
netstat -an | grep ESTABLISHED | wc -l

# Monitor reconnection attempts
grep "reconnect" /var/log/disaster-map/*.log | tail -100

# Check network latency to stream source
ping -c 5 <stream_source_ip>
```

**Solutions:**
```python
# In src/streaming/rtsp_client.py, adjust settings:

class RTSPClient:
    def __init__(self):
        self.reconnect_delay = 2.0  # Exponential backoff base
        self.max_retries = 5
        self.buffer_size = 1024 * 1024  # 1MB buffer
        
    def connect(self, url: str) -> bool:
        """Connect with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self._establish_connection(url)
            except ConnectionError as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.reconnect_delay * (2 ** attempt))
```

---

### Issue: High Connection Count (> 10 concurrent streams)

**Symptoms:**
- System becomes unresponsive under load
- Memory usage spikes
- Request timeouts increase

**Root Causes:**
1. No connection pooling
2. Resource leaks in stream handlers
3. Missing timeout configurations

**Solutions:**
```python
# In src/data_pipeline/memory_manager.py, implement connection pool:

from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def stream_connection_pool(max_size=10):
    """Connection pool for RTSP streams"""
    connections = []
    
    try:
        # Acquire a connection from pool
        conn = await get_available_connection()
        yield conn
    finally:
        # Return connection to pool or close if exhausted
        if len(connections) < max_size:
            await return_to_pool(conn)
        else:
            await close_connection(conn)

# In src/streaming/frame_extractor.py, add timeout handling:

class FrameExtractor:
    def __init__(self):
        self.timeout = 30.0  # Seconds
    
    async def extract_frame(self, stream_url: str) -> np.ndarray:
        """Extract frame with timeout"""
        try:
            return await asyncio.wait_for(
                self._extract_frame_internal(stream_url),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            LOG_ERROR(f"Frame extraction timed out after {self.timeout}s")
            raise
```

---

## Memory & Resource Issues

### Issue: High Memory Usage (> 85%)

**Symptoms:**
- OOM kills in production
- Slow response times due to GC pauses
- Map data not loading properly

**Root Causes:**
1. Unbounded data structures (e.g., queues)
2. Memory leaks in long-running processes
3. Large point clouds loaded into memory
4. Insufficient cache eviction policies

**Diagnosis Commands:**
```bash
# Check memory usage over time
watch -n 1 'docker stats disaster-map-backend --no-stream'

# Profile Python memory usage
py-spy record -o profile.svg -- python src/main.py &

# Check for memory leaks with valgrind (development only)
valgrind --leak-check=full python src/main.py
```

**Solutions:**
```python
# In src/data_pipeline/memory_manager.py, implement bounded queues:

from collections import deque
import threading

class BoundedQueue:
    """Thread-safe bounded queue with automatic eviction"""
    
    def __init__(self, maxsize=1024):
        self.queue = deque(maxlen=maxsize)
        self.lock = threading.Lock()
    
    def put(self, item):
        with self.lock:
            if len(self.queue) >= self.maxsize:
                # Evict oldest items (LRU policy)
                evicted_items = list(self.queue)[:self.maxsize // 2]
                for item in evicted_items:
                    self._cleanup(item)
            
            self.queue.append(item)
    
    def get(self, timeout=None):
        with self.lock:
            if not self.queue:
                return None
            
            # Return most recent items first (MRU policy)
            return self.queue.pop()
```

---

### Issue: CPU Spikes (> 90%)

**Symptoms:**
- Intermittent performance degradation
- High latency during peak hours
- System becomes unresponsive under load

**Root Causes:**
1. Inefficient algorithms (O(n²) complexity)
2. Missing async processing for I/O operations
3. CPU-bound tasks blocking event loop
4. No request rate limiting

**Solutions:**
```python
# Use async/await for non-blocking I/O
import asyncio

async def process_stream(stream_url: str):
    """Process stream with async I/O"""
    async with rtsp_client.connect(stream_url) as client:
        while True:
            # Non-blocking frame extraction
            frame = await client.receive_frame(timeout=0.1)
            
            # Process in background thread pool for CPU-intensive tasks
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: extract_features(frame.image)
            )
            
            yield result

# Implement request rate limiting
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/track")
@limiter.limit("100 per minute")  # Rate limit to 100 requests/min
async def track_pose(request: Request):
    return {"pose": {...}}
```

---

## Network & Latency Problems

### Issue: High Network Latency (> 50ms)

**Symptoms:**
- Slow video feed startup
- Delayed pose updates in visualization
- Timeouts on external API calls

**Root Causes:**
1. Suboptimal network routing
2. Packet loss or congestion
3. DNS resolution delays
4. SSL/TLS handshake overhead

**Diagnosis Commands:**
```bash
# Test network latency to key services
ping -c 5 <backend_service>
traceroute <stream_source_ip>

# Check for packet loss
mtr -n --report <backend_service>

# Monitor DNS resolution time
time nslookup <service_name>
```

**Solutions:**
1. Use CDN for static assets and map tiles
2. Implement connection keep-alive for persistent connections
3. Pre-warm SSL sessions for frequently accessed endpoints
4. Use HTTP/2 or WebSocket for real-time data streams

---

### Issue: Connection Timeouts

**Symptoms:**
- "Connection timed out" errors in logs
- Intermittent failures on high load
- Slow response times under stress

**Root Causes:**
1. TCP connection limits reached
2. Firewall dropping idle connections
3. Load balancer timeout settings too short
4. Database connection pool exhausted

**Solutions:**
```python
# In src/utils/logging.py, add timeout monitoring:

import time
from contextlib import contextmanager

@contextmanager
def timed_operation(operation_name: str):
    """Context manager for timing operations"""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 5000:  # Alert on operations > 5s
            LOG_WARNING(f"Slow operation: {operation_name} took {elapsed_ms:.0f}ms")

# Usage in code:
with timed_operation("database_query"):
    result = db.query("SELECT * FROM trajectories WHERE ...")
```

---

## Database & Cache Issues

### Issue: Database Connection Pool Exhaustion

**Symptoms:**
- "Too many connections" errors
- Slow queries due to connection wait times
- Occasional query timeouts

**Root Causes:**
1. Connection pool size too small
2. Long-running transactions holding connections
3. Missing connection cleanup on errors
4. No connection timeout configuration

**Solutions:**
```python
# In src/data_pipeline/incremental_mapper.py, configure pool:

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def get_database_connection():
    """Create database connection with proper pooling"""
    engine = create_engine(
        "postgresql://user:password@localhost/disaster_map",
        poolclass=QueuePool,
        pool_size=20,           # Number of connections to keep open
        max_overflow=10,        # Additional connections on demand
        pool_pre_ping=True,     # Check connection before use
        pool_recycle=3600,      # Recycle connections after 1 hour
        connect_args={"connect_timeout": 10},  # Connection timeout
    )
    return engine

# Implement proper cleanup in context managers:
from contextlib import contextmanager

@contextmanager
def database_transaction():
    """Context manager for database transactions"""
    conn = None
    try:
        with engine.begin() as conn:
            yield conn
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        # Ensure connection is returned to pool
        pass  # Context manager handles this automatically
```

---

### Issue: Redis Cache Misses

**Symptoms:**
- Slow response times on repeated requests
- High memory usage in application
- Occasional cache stampede

**Root Causes:**
1. Cache key design issues (too many unique keys)
2. Missing TTL on cached data
3. No cache warming strategy
4. Memory eviction policy not configured

**Solutions:**
```python
# In src/data_pipeline/memory_manager.py, implement smart caching:

import redis
from functools import wraps
import time

class SmartCache:
    def __init__(self, host='localhost', port=6379):
        self.redis = redis.Redis(host=host, port=port, decode_responses=True)
        self.default_ttl = 300  # 5 minutes
    
    def get(self, key: str, default=None):
        """Get value with TTL check"""
        try:
            value = self.redis.get(key)
            if value is not None:
                return json.loads(value)
            return default
        except redis.RedisError as e:
            LOG_ERROR(f"Redis get error: {e}")
            return default
    
    def set(self, key: str, value, ttl=None):
        """Set value with automatic TTL"""
        try:
            self.redis.setex(
                key, 
                ttl or self.default_ttl, 
                json.dumps(value)
            )
        except redis.RedisError as e:
            LOG_ERROR(f"Redis set error: {e}")
    
    def get_with_ttl(self, key: str):
        """Get value with TTL"""
        try:
            return self.redis.ttl(key)
        except redis.RedisError as e:
            LOG_ERROR(f"Redis TTL error: {e}")
            return -1

# Use cache warming for frequently accessed data:
def warm_cache():
    """Pre-populate cache with hot data"""
    hot_keys = [
        "map_tiles:layer_0",
        "trajectory_stats:daily",
        "system_metrics:hourly"
    ]
    
    for key in hot_keys:
        value = get_data_from_source(key)
        smart_cache.set(key, value, ttl=3600)  # 1 hour TTL
```

---

## Deployment & Infrastructure Issues

### Issue: Pod Not Starting / CrashLoopBackOff

**Symptoms:**
- Kubernetes pod repeatedly crashing
- "CrashLoopBackOff" status in deployment
- No logs or empty log output

**Root Causes:**
1. Missing environment variables
2. Port binding issues
3. Health check failures
4. Resource limits too restrictive

**Diagnosis Commands:**
```bash
# Check pod events
kubectl describe pod <pod_name> -n production

# View last container logs
kubectl logs <pod_name> -c main --previous

# Check resource usage
kubectl top pods -l app=disaster-map-backend

# Verify health checks
curl http://<pod_ip>:8000/health
```

**Solutions:**
```yaml
# In Kubernetes deployment, ensure proper configuration:

apiVersion: apps/v1
kind: Deployment
metadata:
  name: disaster-map-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: disaster-map-backend
  template:
    metadata:
      labels:
        app: disaster-map-backend
    spec:
      containers:
      - name: backend
        image: ghcr.io/disaster-map/backend:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: REDIS_URL
          value: "redis://cache:6379"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

### Issue: Slow Startup Time (> 60 seconds)

**Symptoms:**
- Long pod startup times
- Delayed service availability after deployment
- High resource usage during startup

**Root Causes:**
1. Large dependencies being installed at runtime
2. Database migrations running on every start
3. Cache warming taking too long
4. Missing pre-warming strategies

**Solutions:**
```python
# In src/main.py, optimize startup:

import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def app_lifespan(app):
    """Optimized application lifespan for fast startup"""
    # Pre-load critical data before accepting requests
    await preload_critical_data()
    
    yield
    
    # Cleanup on shutdown
    await cleanup_resources()

def preload_critical_data():
    """Load essential data during startup"""
    tasks = [
        load_map_config(),      # Fast, cached
        initialize_database(),  # Quick migrations only
        warm_cache(),           # Pre-populate hot keys
    ]
    
    return asyncio.gather(*tasks)

# Use lazy loading for non-critical components:
from functools import lru_cache

@lru_cache(maxsize=128)
def get_trajectory_stats(trajectory_id):
    """Cache trajectory statistics to avoid repeated queries"""
    # Query database here
    pass
```

---

## Quick Reference Commands

### Health Checks
```bash
# Application health
curl http://localhost:8000/health

# Prometheus metrics
curl 'http://prometheus:9090/api/v1/query?query=up'

# Grafana dashboard status
curl -X POST "http://grafana:3000/api/datasources/proxy/1" \
  -H "Content-Type: application/json" \
  -d '{"name":"Prometheus","type":"prometheus"}'
```

### Monitoring Queries (PromQL)
```promql
# FPS rate
rate(frame_processed_total[1m]) * 60

# Error rate
sum(rate(error_total{status=~"5.."}[1m])) / sum(rate(request_total[1m])) * 100

# P95 latency
histogram_quantile(0.95, rate(latency_seconds_bucket[1m]))

# Active streams
disaster_map_active_streams

# Memory usage
process_resident_memory_bytes / container_spec_memory_limit_bytes * 100
```

### Log Aggregation (ELK Stack)
```bash
# Search for errors in last hour
curl "http://elasticsearch:9200/_search?query={\"from\":-3600,\"size\":1000}" \
  -H 'Content-Type: application/json'

# Filter by severity
grep "ERROR\|CRITICAL" /var/log/disaster-map/*.log | tail -100
```

---

## Escalation Matrix

| Issue Severity | Response Time | Escalation Path |
|----------------|---------------|-----------------|
| Critical (Service Down) | < 5 min | On-call → Team Lead → CTO |
| High (Degraded Performance) | < 15 min | DevOps Engineer → Backend Lead |
| Medium (Minor Issues) | < 1 hour | Any team member |
| Low (Feature Requests) | Next sprint | Product Owner |

---

## Related Documentation

- [Deployment Runbook](./runbooks/deployment.md)
- [Incident Response Procedures](./incident-response.md)
- [Monitoring Dashboard Guide](../monitoring/README.md)
- [Performance Tuning Guide](../performance/README.md)
