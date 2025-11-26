# Quick Start Guide

Get your vLLM deployment running in 30 minutes!

## Prerequisites Checklist

- [ ] AWS CLI configured
- [ ] kubectl installed
- [ ] eksctl installed  
- [ ] Helm installed
- [ ] AWS GPU quota (8 vCPUs for G instances)
- [ ] S3 bucket with model files
- [ ] ECR repository with Docker image

---

## 5-Step Deployment

### Step 1: Create EKS Cluster (10 min)
```bash
# GPU node
eksctl create cluster \
  --name llama-vllm-cluster \
  --region us-east-1 \
  --nodegroup-name gpu-nodes-g5 \
  --node-type g5.xlarge \
  --nodes 1 \
  --managed

# Monitoring node
eksctl create nodegroup \
  --cluster llama-vllm-cluster \
  --name monitoring-nodes \
  --node-type t3.medium \
  --nodes 1 \
  --managed \
  --node-labels workload=monitoring
```

### Step 2: Install NVIDIA Plugin (1 min)
```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

### Step 3: Configure IAM (5 min)
```bash
# Enable OIDC
eksctl utils associate-iam-oidc-provider \
  --cluster llama-vllm-cluster \
  --approve

# Get OIDC ID
OIDC_ID=$(aws eks describe-cluster \
  --name llama-vllm-cluster \
  --query 'cluster.identity.oidc.issuer' \
  --output text | sed 's|https://oidc.eks.us-east-1.amazonaws.com/id/||')

# Create IAM role (update trust-policy.json with your OIDC_ID first)
# Then apply deployment
```

### Step 4: Deploy vLLM (5 min)
```bash
kubectl apply -f EKS-MANIFESTS/vllm-deployment.yaml

# Watch it start
kubectl get pods -n vllm -w

# Wait for "Model loaded successfully!" in logs
kubectl logs -n vllm -l app=vllm-llama -f
```

### Step 5: Install Monitoring (5 min)
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values monitoring/prometheus-values.yaml

# Apply ServiceMonitor
kubectl apply -f monitoring/vllm-servicemonitor.yaml

# Fix service
kubectl label svc -n vllm vllm-service app=vllm-llama
kubectl patch svc -n vllm vllm-service --type='json' -p='[
  {"op": "replace", "path": "/spec/ports/0/name", "value": "http"}
]'
```

---

## Verify Everything Works
```bash
# 1. Get endpoint
kubectl get svc -n vllm vllm-service
export VLLM_ENDPOINT="http://<EXTERNAL-IP>:8000"

# 2. Test health
curl $VLLM_ENDPOINT/health

# 3. Generate text
curl -X POST $VLLM_ENDPOINT/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how are you?", "max_tokens": 50}'

# 4. Check metrics
curl $VLLM_ENDPOINT/metrics | grep vllm_request_success_total

# 5. Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open http://localhost:3000 (admin/admin123)

# 6. Run benchmark
cd benchmarking
./simple_benchmark.sh
```

---

## Next Steps

1. Import Grafana dashboard (`monitoring/vllm-dashboard.json`)
2. Run comprehensive benchmark with Locust
3. Review performance metrics
4. Set up alerting rules
5. Configure autoscaling

---

## Common Issues

**Pod stuck in Pending?**
```bash
kubectl describe pod -n vllm <pod-name>
# Usually: insufficient CPU or GPU not available
```

**No metrics in Grafana?**
```bash
# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Visit http://localhost:9090/targets
```

**LoadBalancer stuck?**
```bash
kubectl describe svc -n vllm vllm-service
# Check events for errors
```

---

## Support

- Full documentation: `README.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Metrics guide: `docs/METRICS_GUIDE.md`

---

**Total time:** ~30 minutes  
**Cost:** ~$0.50 for setup + $1.00/hour running
