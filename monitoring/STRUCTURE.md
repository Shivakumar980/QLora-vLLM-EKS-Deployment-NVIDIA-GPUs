# Project Structure
```
llama-vllm-deploy/
├── README.md                          # Main documentation (this file)
├── STRUCTURE.md                       # Project structure overview
│
├── app/                               # vLLM Application
│   ├── Dockerfile                     # Container image definition
│   ├── app.py                         # FastAPI application with metrics
│   └── download_model.py              # S3 model downloader script
│
├── EKS-MANIFESTS/                     # Kubernetes Deployment Files
│   ├── vllm-deployment.yaml           # vLLM deployment, service, namespace
│   └── nvidia-device-plugin.yaml      # NVIDIA GPU device plugin
│
├── monitoring/                        # Monitoring Stack
│   ├── README.md                      # Monitoring setup guide
│   ├── prometheus-values.yaml         # Helm values for Prometheus
│   ├── vllm-servicemonitor.yaml       # Prometheus ServiceMonitor config
│   └── vllm-dashboard.json            # Grafana dashboard (import this)
│
├── benchmarking/                      # Load Testing & Benchmarking
│   ├── benchmark_vllm.py              # Locust load testing script
│   ├── simple_benchmark.sh            # Quick bash benchmark
│   ├── requirements.txt               # Python dependencies
│   └── results/                       # Benchmark results directory
│       └── .gitkeep
│
├── iam/                               # AWS IAM Configurations
│   ├── s3-policy.json                 # S3 access policy
│   └── trust-policy.json              # OIDC trust relationship
│
└── docs/                              # Additional Documentation
    ├── TROUBLESHOOTING.md             # Common issues and solutions
    ├── COST_ANALYSIS.md               # Detailed cost breakdown
    └── METRICS_GUIDE.md               # Metrics explanation
```

## File Descriptions

### Application Layer

**`app/Dockerfile`**
- Base: NVIDIA CUDA 12.1.0
- Installs: vLLM, FastAPI, Prometheus client
- Exposes: Port 8000

**`app/app.py`**
- FastAPI server with vLLM integration
- Endpoints: `/health`, `/generate`, `/metrics`
- Tracks: Request latency, TTFT, token counts

**`app/download_model.py`**
- Downloads model from S3 at startup
- Validates file integrity
- Progress reporting

### Kubernetes Manifests

**`EKS-MANIFESTS/vllm-deployment.yaml`**
```yaml
Components:
  - Namespace: vllm
  - ServiceAccount: vllm-sa (with IAM role annotation)
  - Deployment: vllm-llama
    - Replicas: 1
    - Resources: 3 CPU, 12Gi RAM, 1 GPU
    - Image: ECR image
    - Env vars: MODEL_PATH, S3_BUCKET, MAX_MODEL_LEN
  - Service: vllm-service (LoadBalancer type)
```

### Monitoring Configuration

**`monitoring/prometheus-values.yaml`**
- Prometheus retention: 7 days
- Storage: 10Gi
- Node selector: workload=monitoring
- Grafana admin password: admin123 (change this!)

**`monitoring/vllm-servicemonitor.yaml`**
- Scrape interval: 15 seconds
- Scrape timeout: 10 seconds
- Target: vllm-service in vllm namespace
- Port: http (port 8000)

**`monitoring/vllm-dashboard.json`**
Grafana dashboard with 13+ panels:
- Request metrics (rate, total, success/failure)
- Latency distributions (p50, p95, p99)
- Token throughput
- TTFT percentiles

### Benchmarking Tools

**`benchmarking/benchmark_vllm.py`**
- Locust-based load testing
- 3 scenarios: short (50 tok), medium (150 tok), long (300 tok)
- Weighted distribution: 10:5:2
- Exports Prometheus metrics on port 8089
- Diverse prompts for realistic testing

**`benchmarking/simple_benchmark.sh`**
- Bash script for quick tests
- Tests 50, 100, 200 token generations
- 5 requests per token length
- Calculates tokens/second
- Requires: curl, jq, bc

### IAM Policies

**`iam/s3-policy.json`**
```json
Permissions:
  - s3:GetObject
  - s3:ListBucket
Resource: llama-qlora-1763527961/*
```

**`iam/trust-policy.json`**
- OIDC federated identity
- ServiceAccount: system:serviceaccount:vllm:vllm-sa
- Replace OIDC_ID with your cluster's OIDC provider ID

---

## Quick Reference

### Essential Commands
```bash
# Deploy application
kubectl apply -f EKS-MANIFESTS/vllm-deployment.yaml

# Install monitoring
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values monitoring/prometheus-values.yaml

# Run benchmark
locust -f benchmarking/benchmark_vllm.py

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Check logs
kubectl logs -n vllm -l app=vllm-llama -f

# Get endpoint
kubectl get svc -n vllm vllm-service
```

### Important Endpoints

| Endpoint | Purpose | Access |
|----------|---------|--------|
| `/health` | Health check | External (LoadBalancer) |
| `/generate` | Text generation | External (LoadBalancer) |
| `/metrics` | Prometheus metrics | Internal (Prometheus) |
| Grafana | Dashboards | Port-forward 3000:80 |
| Prometheus | Metrics UI | Port-forward 9090:9090 |
| Locust | Load test UI | localhost:8089 |

---

## Configuration Variables

### Environment Variables (in deployment)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_PATH` | `/models/llama-2-7b-merged-vllm` | Local model path |
| `S3_BUCKET` | `llama-qlora-1763527961` | S3 bucket name |
| `S3_PREFIX` | `llama-2-7b-merged-vllm` | S3 object prefix |
| `MAX_MODEL_LEN` | `2048` | Maximum sequence length |
| `TENSOR_PARALLEL_SIZE` | `1` | Number of GPUs for tensor parallelism |

### Resource Requests

| Component | CPU | Memory | GPU |
|-----------|-----|--------|-----|
| vLLM Pod | 3 cores | 12Gi | 1 (NVIDIA) |
| Prometheus | 300m | 1Gi | 0 |
| Grafana | 50m | 128Mi | 0 |

---

## Metrics Reference

### Counter Metrics
- `vllm_request_success_total` - Successful requests
- `vllm_request_failure_total` - Failed requests
- `vllm_generation_tokens_total` - Output tokens
- `vllm_prompt_tokens_total` - Input tokens

### Histogram Metrics
- `vllm_request_latency_seconds` - Request duration
- `vllm_time_to_first_token_seconds` - TTFT

### Calculated Metrics
- Request rate: `rate(vllm_request_success_total[5m])`
- Token throughput: `rate(vllm_generation_tokens_total[5m])`
- Success rate: `success / (success + failure) * 100`
- Average latency: `sum / count`

---

## Next Steps After Setup

1. ✅ Verify all pods are running
2. ✅ Check Prometheus is scraping metrics
3. ✅ Import Grafana dashboard
4. ✅ Run simple benchmark
5. ✅ Run Locust load test
6. ✅ Review performance metrics
7. 🎯 Optimize based on results
8. 🎯 Set up alerting rules
9. 🎯 Configure autoscaling
10. 🎯 Production hardening
