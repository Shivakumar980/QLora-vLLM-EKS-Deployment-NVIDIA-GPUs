# Metrics Guide

Complete reference for all metrics tracked in this deployment.

---

## Request Metrics

### `vllm_request_success_total`
**Type:** Counter (monotonically increasing)

**Description:** Total number of successfully completed inference requests since pod startup.

**Use Cases:**
- Calculate request rate: `rate(vllm_request_success_total[5m])`
- Total workload processed
- Success rate calculation

**Example Values:**
- `0` - No requests processed yet
- `369` - 369 successful requests completed
- Always increasing unless pod restarts

**Alerts:**
```yaml
# No requests in 5 minutes
- alert: NoRequests
  expr: rate(vllm_request_success_total[5m]) == 0
  for: 5m
```

---

### `vllm_request_failure_total`
**Type:** Counter

**Description:** Total number of failed inference requests.

**Common Failure Reasons:**
- Out of memory (GPU VRAM)
- Timeout (request took too long)
- Invalid input
- Model error/crash

**Use Cases:**
- Error rate: `rate(vllm_request_failure_total[5m])`
- Reliability monitoring
- Alert on failures

**Target:** < 1% of total requests

**Alerts:**
```yaml
# Failure rate > 5%
- alert: HighFailureRate
  expr: |
    rate(vllm_request_failure_total[5m]) / 
    (rate(vllm_request_success_total[5m]) + rate(vllm_request_failure_total[5m])) 
    > 0.05
  for: 2m
```

---

## Latency Metrics (Histograms)

### `vllm_request_latency_seconds`
**Type:** Histogram

**Description:** End-to-end request duration from receiving request to sending complete response.

**Buckets:** 0.005s, 0.01s, 0.025s, 0.05s, 0.075s, 0.1s, 0.25s, 0.5s, 0.75s, 1s, 2.5s, 5s, 7.5s, 10s, +Inf

**Components:**
- `_bucket{le="..."}` - Count of requests ≤ bucket value
- `_sum` - Total time spent on all requests
- `_count` - Total number of requests

**Queries:**
```promql
# Average latency
rate(vllm_request_latency_seconds_sum[5m]) / rate(vllm_request_latency_seconds_count[5m])

# p50 (median)
histogram_quantile(0.50, rate(vllm_request_latency_seconds_bucket[5m]))

# p95
histogram_quantile(0.95, rate(vllm_request_latency_seconds_bucket[5m]))

# p99
histogram_quantile(0.99, rate(vllm_request_latency_seconds_bucket[5m]))
```

**Interpretation:**
- **p50 < 3s:** Good user experience
- **p95 < 5s:** Acceptable for most use cases
- **p99 < 10s:** Prevents timeouts
- **p99 > 15s:** Users will experience timeouts

**What Impacts Latency:**
- Model size (larger = slower)
- Token length (more tokens = longer)
- GPU utilization (busy GPU = queuing)
- Concurrent requests (shared resources)

---

### `vllm_time_to_first_token_seconds`
**Type:** Histogram

**Description:** Time from request start until first token is generated.

**Why It Matters:**
- **User perception:** Users see "thinking..." for this duration
- **Streaming applications:** First token appears, then rest streams
- **Prompt processing:** Measures how fast prompt is encoded

**Target Values:**
- **p50:** 200-500ms (feels instant)
- **p95:** < 1s (acceptable)
- **p99:** < 2s (good enough)

**Queries:**
```promql
# TTFT percentiles
histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[5m]))
```

**High TTFT Causes:**
- Long prompts (many input tokens)
- GPU busy with other requests
- Model loading (cold start)
- KV cache full (eviction needed)

**Note:** In this deployment, TTFT measurement may not be accurate because we use synchronous `LLM` class which doesn't expose true first token timing.

---

## Token Metrics

### `vllm_generation_tokens_total`
**Type:** Counter

**Description:** Cumulative count of output tokens generated across all requests.

**Use Cases:**
- Calculate throughput: `rate(vllm_generation_tokens_total[5m])`
- Estimate GPU work
- Cost tracking (tokens generated = compute used)
- Compare to `vllm_prompt_tokens_total` for input/output ratio

**Typical Values:**
- Single request: 50-500 tokens
- Per second: 30-100 tokens (single GPU)
- Per hour: 100K-360K tokens

**Queries:**
```promql
# Tokens per second
rate(vllm_generation_tokens_total[5m])

# Average tokens per request
increase(vllm_generation_tokens_total[1h]) / increase(vllm_request_success_total[1h])
```

**Interpretation:**
- 30-50 tok/s: Good for 7B model on single GPU
- 100+ tok/s: Excellent (optimization or larger GPU)
- 200+ tok/s: Top tier (multiple GPUs or quantization)

---

### `vllm_prompt_tokens_total`
**Type:** Counter

**Description:** Cumulative count of input/prompt tokens processed.

**Use Cases:**
- Input load monitoring
- Calculate input/output ratio
- Estimate context usage

**Input/Output Ratio:**
```promql
# Output tokens per input token
rate(vllm_generation_tokens_total[5m]) / rate(vllm_prompt_tokens_total[5m])
```

**Typical Ratios:**
- **2-5:1** - Short answers, Q&A
- **10-20:1** - Normal conversations
- **50-100:1** - Long-form generation, summaries

**Your Deployment:** 39,999 / 2,294 = **17.4:1** (normal)

---

## Calculated Metrics

### Request Rate (RPS)
```promql
rate(vllm_request_success_total[5m])
```

**Description:** Requests per second over last 5 minutes.

**Use For:**
- Load monitoring
- Capacity planning
- Autoscaling triggers

**Typical Values:**
- **1-5 RPS:** Light load
- **10-20 RPS:** Medium load  
- **50+ RPS:** Heavy load (may need scaling)

---

### Token Throughput
```promql
rate(vllm_generation_tokens_total[5m])
```

**Description:** Tokens generated per second.

**Primary LLM Performance Metric:** Industry standard for comparing models/configs.

**Factors:**
- Model size (7B vs 13B vs 70B)
- GPU type (T4 vs A10G vs A100)
- Quantization (FP16 vs INT8 vs INT4)
- Batch size
- Context length

---

### Success Rate
```promql
rate(vllm_request_success_total[5m]) / 
(rate(vllm_request_success_total[5m]) + rate(vllm_request_failure_total[5m])) * 100
```

**Description:** Percentage of successful requests.

**SLA Targets:**
- **99%** (two nines): Acceptable
- **99.9%** (three nines): Good
- **99.99%** (four nines): Excellent

**Your Deployment:** 100% 🎉

---

### Estimated TPOT (Time Per Output Token)
```promql
rate(vllm_request_latency_seconds_sum[5m]) / rate(vllm_generation_tokens_total[5m])
```

**Description:** Average time to generate each token.

**Target:** 20-50ms per token for good performance

**Calculation:** Total time / Total tokens = Avg time per token

**Interpretation:**
- **< 20ms:** Excellent
- **20-50ms:** Good
- **50-100ms:** Acceptable
- **> 100ms:** Slow (needs optimization)

**Note:** This is an approximation. True TPOT requires streaming measurement.

---

## System Metrics

### `process_resident_memory_bytes`
**Description:** RAM used by Python process (not GPU memory).

**Your Value:** ~5.7GB / 16GB node = 36% (healthy)

**Monitor for:** Memory leaks (constantly increasing)

---

### `process_cpu_seconds_total`
**Description:** Total CPU time used by process.

**Low value is good:** Means GPU is doing most work, not CPU.

---

## Metric Relationships

### Performance Triangle
```
        Latency
           ↗  ↖
          /    \
         /      \
  Throughput ←→ Concurrency
```

- **↑ Concurrency** → **↑ Throughput** (to a point)
- **↑ Concurrency** → **↑ Latency** (resource contention)
- **↓ Latency** → **↑ User Satisfaction**

### Ideal State:
- High throughput
- Low latency  
- Moderate concurrency
- 100% success rate

---

## Dashboard Panels

### Panel 1: Total Requests (Stat)
```promql
vllm_request_success_total
```
Shows: Cumulative successful requests

---

### Panel 2: Request Rate (Time Series)
```promql
rate(vllm_request_success_total[5m])
```
Shows: Current load (requests/sec)

---

### Panel 3: Latency Distribution (Time Series)
```promql
histogram_quantile(0.50, rate(vllm_request_latency_seconds_bucket[5m]))
histogram_quantile(0.95, rate(vllm_request_latency_seconds_bucket[5m]))
histogram_quantile(0.99, rate(vllm_request_latency_seconds_bucket[5m]))
```
Shows: p50/p95/p99 latency over time

---

### Panel 4: Token Throughput (Time Series)
```promql
rate(vllm_generation_tokens_total[5m])
```
Shows: Tokens generated per second

---

### Panel 5: Success Rate (Gauge)
```promql
rate(vllm_request_success_total[5m]) / 
(rate(vllm_request_success_total[5m]) + rate(vllm_request_failure_total[5m])) * 100
```
Shows: Reliability as percentage

---

## Alerting Rules

### Critical Alerts
```yaml
groups:
- name: vllm_critical
  interval: 30s
  rules:
  
  # High failure rate
  - alert: HighFailureRate
    expr: |
      rate(vllm_request_failure_total[5m]) / 
      (rate(vllm_request_success_total[5m]) + rate(vllm_request_failure_total[5m])) 
      > 0.05
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High request failure rate"
      description: "{{ $value }}% of requests are failing"
  
  # High latency
  - alert: HighLatency
    expr: |
      histogram_quantile(0.95, rate(vllm_request_latency_seconds_bucket[5m])) > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High request latency"
      description: "P95 latency is {{ $value }}s"
  
  # No requests
  - alert: NoRequests
    expr: rate(vllm_request_success_total[5m]) == 0
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "No requests received"
      description: "No successful requests in last 10 minutes"
  
  # Low throughput
  - alert: LowThroughput
    expr: rate(vllm_generation_tokens_total[5m]) < 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Low token throughput"
      description: "Only {{ $value }} tokens/sec"
```

---

## Metric Collection Flow
```
vLLM Request
    ↓
FastAPI /generate endpoint
    ↓
Update Prometheus metrics
    ↓
/metrics endpoint (Prometheus format)
    ↓
Prometheus scrapes every 15s
    ↓
Stores in TSDB
    ↓
Grafana queries Prometheus
    ↓
Dashboard displays data
```

---

## Best Practices

1. **Monitor trends, not just current values**
   - Is latency increasing over time?
   - Is throughput declining?

2. **Use percentiles, not averages**
   - p95/p99 show worst-case user experience
   - Average hides outliers

3. **Set up alerts**
   - High failure rate
   - High latency
   - No traffic (possible outage)

4. **Correlate metrics**
   - High latency + high concurrency = overloaded
   - High failures + low GPU memory = OOM
   - Low throughput + low GPU util = CPU bottleneck

5. **Benchmark regularly**
   - Establish baseline
   - Detect regressions
   - Validate optimizations

---

## Further Reading

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Histogram vs Summary](https://prometheus.io/docs/practices/histograms/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)
- [vLLM Metrics](https://docs.vllm.ai/en/latest/serving/metrics.html)
