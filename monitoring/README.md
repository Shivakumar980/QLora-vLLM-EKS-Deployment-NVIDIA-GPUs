# vLLM Deployment on AWS EKS with Monitoring & Benchmarking

Production-ready deployment of Llama-2-7B using vLLM on AWS EKS with comprehensive monitoring using Prometheus and Grafana.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Infrastructure Setup](#infrastructure-setup)
- [Monitoring Stack](#monitoring-stack)
- [Benchmarking](#benchmarking)
- [Performance Results](#performance-results)
- [Troubleshooting](#troubleshooting)
- [Cost Estimation](#cost-estimation)

---

## 🎯 Overview

This project demonstrates a complete production deployment of a Large Language Model (LLM) inference system with:

- **Model:** Llama-2-7B (QLoRA fine-tuned)
- **Inference Engine:** vLLM (high-performance serving)
- **Infrastructure:** AWS EKS with GPU nodes
- **Monitoring:** Prometheus + Grafana
- **Benchmarking:** Locust load testing

### Key Features

✅ Scalable GPU-based inference  
✅ Real-time performance monitoring  
✅ Comprehensive benchmarking tools  
✅ Production-ready observability  
✅ 100% success rate at 32.6 tokens/sec  

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                         AWS EKS Cluster                      │
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  GPU Node Group  │         │ Monitoring Nodes │          │
│  │  (g5.xlarge)     │         │  (t3.medium)     │          │
│  │                  │         │                  │          │
│  │  ┌────────────┐  │         │  ┌────────────┐ │          │
│  │  │   vLLM     │  │         │  │ Prometheus │ │          │
│  │  │  Llama-2-7B│◄─┼─────────┼──┤  (scraper) │ │          │
│  │  │            │  │         │  └────────────┘ │          │
│  │  │ + FastAPI  │  │         │                  │          │
│  │  │ + Metrics  │  │         │  ┌────────────┐ │          │
│  │  └────────────┘  │         │  │  Grafana   │ │          │
│  │        ▲         │         │  │ (dashboard)│ │          │
│  └────────┼─────────┘         │  └────────────┘ │          │
│           │                   └──────────────────┘          │
│           │                                                  │
└───────────┼──────────────────────────────────────────────────┘
            │
            │ LoadBalancer
            ▼
    ┌──────────────┐
    │   Internet   │
    │    Users     │
    └──────────────┘
```

### Component Details

| Component | Specification | Purpose |
|-----------|--------------|---------|
| **GPU Node** | g5.xlarge (A10G 24GB VRAM) | Model inference |
| **Monitoring Node** | t3.medium | Prometheus & Grafana |
| **Model** | Llama-2-7B (FP16, ~13GB) | Text generation |
| **Inference Engine** | vLLM v0.2.7 | High-performance serving |
| **API** | FastAPI + Uvicorn | REST endpoints |
| **Storage** | S3 (model) + EBS (runtime) | Persistent storage |

---

## 📦 Prerequisites

### Required Tools
```bash
# AWS CLI
aws --version  # >= 2.x

# kubectl
kubectl version --client  # >= 1.28

# eksctl
eksctl version  # >= 0.150

# Helm
helm version  # >= 3.12

# Docker (for building images)
docker --version  # >= 24.x

# Python (for benchmarking)
python3 --version  # >= 3.10
```

### AWS Requirements

- AWS Account with appropriate permissions
- AWS CLI configured (`aws configure`)
- VPC quota: 8 vCPUs for G instances
- S3 bucket with model files
- ECR repository for Docker images

### Check GPU Quota
```bash
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --region us-east-1 \
  --query 'Quota.[QuotaName,Value]' \
  --output table
```

Required: At least 4 vCPUs for g5.xlarge

---

## 🚀 Infrastructure Setup

### 1. Create EKS Cluster with GPU Node
```bash
# Create cluster with GPU node group
eksctl create cluster \
  --name llama-vllm-cluster \
  --region us-east-1 \
  --nodegroup-name gpu-nodes-g5 \
  --node-type g5.xlarge \
  --nodes 1 \
  --nodes-min 1 \
  --nodes-max 1 \
  --managed

# Update kubeconfig
aws eks update-kubeconfig --name llama-vllm-cluster --region us-east-1
```

**Note:** g5.xlarge provides:
- 4 vCPUs, 16GB RAM
- 1x NVIDIA A10G GPU (24GB VRAM)
- ~$1.00/hour

### 2. Add Monitoring Node Group
```bash
# Create separate node group for monitoring
eksctl create nodegroup \
  --cluster llama-vllm-cluster \
  --region us-east-1 \
  --name monitoring-nodes \
  --node-type t3.medium \
  --nodes 1 \
  --nodes-min 1 \
  --nodes-max 1 \
  --managed \
  --node-labels workload=monitoring
```

### 3. Install NVIDIA Device Plugin
```bash
# Install NVIDIA plugin for GPU support
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify GPU is detected
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
# Output: "1"
```

### 4. Configure IAM for S3 Access
```bash
# Enable OIDC provider
eksctl utils associate-iam-oidc-provider \
  --cluster llama-vllm-cluster \
  --region us-east-1 \
  --approve

# Get OIDC ID
OIDC_ID=$(aws eks describe-cluster \
  --name llama-vllm-cluster \
  --region us-east-1 \
  --query 'cluster.identity.oidc.issuer' \
  --output text | sed 's|https://oidc.eks.us-east-1.amazonaws.com/id/||')

echo "OIDC ID: $OIDC_ID"
```

Create IAM role and policy (see `iam-policy.json` and `trust-policy.json` in repo).

### 5. Deploy vLLM Application
```bash
# Apply deployment manifests
kubectl apply -f EKS-MANIFESTS/vllm-deployment.yaml

# Check deployment
kubectl get pods -n vllm
kubectl logs -n vllm -l app=vllm-llama -f
```

Wait for:
- Model download from S3 (~5-10 min for 12.6GB)
- Model loading into GPU (~2-3 min)
- "✅ Model loaded successfully!"

### 6. Get LoadBalancer Endpoint
```bash
kubectl get svc -n vllm vllm-service

# Save the EXTERNAL-IP for later use
export VLLM_ENDPOINT="http://<EXTERNAL-IP>:8000"
```

### 7. Test the Deployment
```bash
# Health check
curl $VLLM_ENDPOINT/health

# Generate text
curl -X POST $VLLM_ENDPOINT/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is artificial intelligence?",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

---

## 📊 Monitoring Stack

### Architecture
```
Prometheus (scrapes metrics every 15s)
     ↓
vLLM /metrics endpoint (Prometheus format)
     ↓
Grafana (visualizes data)
```

### 1. Install Prometheus + Grafana
```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values monitoring/prometheus-values.yaml
```

**Installation includes:**
- Prometheus (metrics collection & storage)
- Grafana (visualization dashboards)
- Alertmanager (alerting)
- Node Exporter (node metrics)
- Kube State Metrics (K8s object metrics)

### 2. Configure ServiceMonitor for vLLM
```bash
# Apply ServiceMonitor to tell Prometheus where to scrape
kubectl apply -f monitoring/vllm-servicemonitor.yaml

# Verify ServiceMonitor is created
kubectl get servicemonitor -n monitoring vllm-metrics
```

### 3. Add Port Name to Service

vLLM service needs a named port for ServiceMonitor to work:
```bash
# Patch service to add port name
kubectl patch svc -n vllm vllm-service --type='json' -p='[
  {
    "op": "replace",
    "path": "/spec/ports/0",
    "value": {
      "name": "http",
      "port": 8000,
      "protocol": "TCP",
      "targetPort": 8000
    }
  }
]'

# Add app label
kubectl label svc -n vllm vllm-service app=vllm-llama
```

### 4. Access Grafana
```bash
# Get Grafana admin password
kubectl get secret --namespace monitoring prometheus-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode
echo

# Port-forward Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

Open browser: **http://localhost:3000**
- Username: `admin`
- Password: (from command above)

### 5. Import vLLM Dashboard

1. In Grafana, go to **Dashboards** → **New** → **Import**
2. Click **Upload JSON file**
3. Select `monitoring/vllm-dashboard.json`
4. Click **Import**

### 6. Verify Prometheus is Scraping
```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Open: **http://localhost:9090/targets**

Look for `serviceMonitor/monitoring/vllm-metrics/0` - should show **State: UP**

---

## 🔬 Benchmarking

### Available Metrics

Your deployment tracks these metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `vllm_request_success_total` | Counter | Total successful requests |
| `vllm_request_failure_total` | Counter | Total failed requests |
| `vllm_request_latency_seconds` | Histogram | End-to-end request latency |
| `vllm_time_to_first_token_seconds` | Histogram | Time until first token |
| `vllm_generation_tokens_total` | Counter | Total output tokens generated |
| `vllm_prompt_tokens_total` | Counter | Total input tokens processed |

### Benchmarking Tools

Two options available:

#### Option 1: Simple Bash Script (Quick Test)
```bash
cd benchmarking

# Run simple benchmark
./simple_benchmark.sh
```

Sends 15 requests with varying token lengths (50, 100, 200) and reports:
- Latency per request
- Tokens generated
- Tokens per second

#### Option 2: Locust Load Testing (Comprehensive)
```bash
# Install dependencies
pip install locust prometheus-client requests

# Start Locust with web UI
locust -f benchmark_vllm.py
```

Then:
1. Open **http://localhost:8089**
2. Configure test:
   - Users: 10
   - Spawn rate: 2
   - Host: (pre-configured)
3. Click **Start swarming**
4. Watch metrics in real-time on Grafana

**Or run headless:**
```bash
locust -f benchmark_vllm.py \
  --headless \
  --users 10 \
  --spawn-rate 2 \
  --run-time 5m \
  --html results/benchmark_$(date +%Y%m%d_%H%M%S).html
```

### Benchmark Scenarios

The Locust script includes three scenarios:

1. **Short Generation** (50 tokens) - 10x weight
   - Simulates quick questions/answers
   
2. **Medium Generation** (150 tokens) - 5x weight
   - Typical conversation responses
   
3. **Long Generation** (300 tokens) - 2x weight
   - Detailed explanations, summaries

### Interpreting Results

**Good Performance Indicators:**
- ✅ Success rate > 99%
- ✅ p95 latency < 5 seconds
- ✅ Throughput > 30 tokens/sec
- ✅ No request failures

**Warning Signs:**
- ⚠️ Latency increasing over time
- ⚠️ Success rate dropping
- ⚠️ Throughput declining

---

## 📈 Performance Results

### Test Configuration

- **Model:** Llama-2-7B (FP16)
- **GPU:** NVIDIA A10G (24GB VRAM)
- **Instance:** AWS g5.xlarge
- **Load:** 10 concurrent users
- **Duration:** 5 minutes
- **Total Requests:** 369

### Results Summary

| Metric | Value | Status |
|--------|-------|--------|
| **Total Requests** | 369 | ✅ |
| **Success Rate** | 100% | ✅ Excellent |
| **Failure Rate** | 0% | ✅ Perfect |
| **Total Tokens Generated** | 39,999 | ✅ |
| **Average Tokens/Request** | 108.4 | ✅ Normal |
| **Overall Throughput** | 32.6 tokens/sec | ✅ Good |
| **Average Latency** | 3.32 seconds | ✅ Acceptable |
| **p50 Latency** | < 2.5s | ✅ Good |
| **p95 Latency** | < 5.0s | ✅ Good |
| **p99 Latency** | < 7.5s | ✅ Acceptable |

### Performance Analysis

**Strengths:**
- 🎯 100% reliability (no failures)
- 🚀 Consistent performance under load
- 💪 Handles 10 concurrent users smoothly
- ⚡ Good token generation speed

**Optimization Opportunities:**
- TTFT could be lower with streaming
- Batch processing could improve throughput
- Quantization (INT8/INT4) would increase speed

### Comparison Benchmarks

| Setup | Throughput | Latency (p95) | Notes |
|-------|-----------|---------------|-------|
| **This deployment** | 32.6 tok/s | < 5s | FP16, single GPU |
| Llama-2-7B + vLLM (A100) | 80-120 tok/s | < 2s | Larger GPU |
| Llama-2-7B + INT8 | 50-70 tok/s | < 3s | Quantized |
| Llama-2-13B (A10G) | 18-25 tok/s | < 8s | Larger model |

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. Pod Stuck in Pending

**Symptom:** `kubectl get pods -n vllm` shows `Pending`

**Check:**
```bash
kubectl describe pod -n vllm <pod-name> | grep Events -A 10
```

**Common causes:**
- Insufficient CPU/Memory
- No GPU available
- Node not ready

**Solution:**
```bash
# Check node resources
kubectl describe nodes

# Verify GPU is available
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

#### 2. Prometheus Not Scraping vLLM

**Symptom:** No data in Grafana, metrics show "No data"

**Check:**
```bash
# Verify ServiceMonitor exists
kubectl get servicemonitor -n monitoring vllm-metrics

# Check service has correct labels
kubectl get svc -n vllm vllm-service --show-labels

# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

**Solution:**
```bash
# Ensure service has app label and named port
kubectl label svc -n vllm vllm-service app=vllm-llama

kubectl patch svc -n vllm vllm-service --type='json' -p='[
  {"op": "replace", "path": "/spec/ports/0/name", "value": "http"}
]'
```

#### 3. Model Download Fails

**Symptom:** Pod logs show S3 access errors

**Check:**
```bash
# Verify IAM role is attached
kubectl describe sa -n vllm vllm-sa | grep Annotations

# Test S3 access from pod
kubectl exec -it -n vllm <pod-name> -- aws s3 ls s3://your-bucket/
```

**Solution:**
- Verify IAM role has S3 permissions
- Check OIDC provider is configured
- Ensure trust policy has correct OIDC ID

#### 4. Out of Memory (OOM)

**Symptom:** Pod crashes, logs show memory errors

**Check:**
```bash
# Check GPU memory
kubectl exec -it -n vllm <pod-name> -- nvidia-smi
```

**Solution:**
- Reduce `max_model_len` in deployment
- Lower `gpu_memory_utilization` in app.py
- Use quantized model (INT8/INT4)
- Upgrade to larger GPU (g5.2xlarge, g5.4xlarge)

#### 5. High Latency

**Symptom:** Requests taking >10 seconds

**Possible causes:**
- GPU cache full
- Too many concurrent requests
- Network issues

**Check:**
```bash
# Monitor pod logs
kubectl logs -n vllm -l app=vllm-llama -f

# Check metrics
curl $VLLM_ENDPOINT/metrics | grep vllm_request_latency
```

**Solution:**
- Scale horizontally (add more pods)
- Optimize batch size
- Use async inference

---

## 💰 Cost Estimation

### AWS Infrastructure Costs (us-east-1)

| Resource | Specification | Hourly | Monthly (730hrs) |
|----------|--------------|--------|------------------|
| **GPU Node** | g5.xlarge | $1.006 | $734.38 |
| **Monitoring Node** | t3.medium | $0.0416 | $30.37 |
| **LoadBalancer** | NLB | $0.0225 | $16.43 |
| **EBS Storage** | 50GB gp3 | - | $4.00 |
| **Data Transfer** | First 100GB free | - | $0-90 |
| **S3 Storage** | 15GB model | - | $0.35 |
| | | **Total:** | **~$785/month** |

### Cost Optimization Strategies

1. **Use Spot Instances** for GPU nodes (50-70% savings)
```bash
   eksctl create nodegroup --spot
```

2. **Auto-scaling** - Scale to zero during off-hours
```bash
   # Set min nodes to 0
   eksctl scale nodegroup --nodes-min=0
```

3. **Reserved Instances** - 1-year commitment saves 30-40%

4. **Smaller instances** for dev/test
   - g4dn.xlarge ($0.526/hr) for testing
   - Switch to g5 for production

### Performance vs Cost

| Instance | vCPU | VRAM | Throughput | Cost/Hour | Cost/1M Tokens |
|----------|------|------|------------|-----------|----------------|
| g4dn.xlarge | 4 | 16GB | ~25 tok/s | $0.526 | $5.84 |
| **g5.xlarge** | 4 | 24GB | ~33 tok/s | $1.006 | **$8.47** |
| g5.2xlarge | 8 | 24GB | ~35 tok/s | $1.212 | $9.63 |
| g5.4xlarge | 16 | 24GB | ~38 tok/s | $1.624 | $11.89 |

**Best value:** g5.xlarge for production workloads

---

## 📚 Additional Resources

### Documentation

- [vLLM Documentation](https://docs.vllm.ai/)
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [Grafana Tutorials](https://grafana.com/tutorials/)

### Related Projects

- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/)
- [NVIDIA Triton](https://github.com/triton-inference-server)

### Community

- [vLLM Discord](https://discord.gg/vllm)
- [EKS Community](https://github.com/aws/containers-roadmap)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 👤 Author

**Your Name**
- GitHub: [@yourusername](https://github.com/yourusername)
- LinkedIn: [Your Profile](https://linkedin.com/in/yourprofile)

---

## 🙏 Acknowledgments

- vLLM team for the excellent inference engine
- NVIDIA for GPU support and CUDA toolkit
- Prometheus & Grafana communities
- AWS EKS team for Kubernetes service

---

## 📝 Changelog

### v1.0.0 (2025-11-26)
- Initial release
- Llama-2-7B deployment on g5.xlarge
- Prometheus + Grafana monitoring
- Locust benchmarking suite
- Comprehensive documentation

---

**⭐ If you find this project helpful, please star it on GitHub!**
