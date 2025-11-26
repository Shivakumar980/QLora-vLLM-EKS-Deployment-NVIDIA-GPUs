# Troubleshooting Guide

## Quick Diagnostics

Run these commands to gather information:
```bash
# Check all resources
kubectl get all -n vllm
kubectl get all -n monitoring

# Check events
kubectl get events -n vllm --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n vllm -l app=vllm-llama --tail=100

# Check node status
kubectl describe nodes
```

---

## Issue: Pod Won't Start

### Symptoms
- Pod stuck in `Pending`, `ContainerCreating`, or `CrashLoopBackOff`

### Diagnosis
```bash
kubectl describe pod -n vllm <pod-name>
kubectl logs -n vllm <pod-name>
```

### Solutions

**Insufficient CPU/Memory:**
```bash
# Check resource usage
kubectl top nodes

# Reduce resource requests in deployment
# Edit vllm-deployment.yaml: reduce cpu from "3" to "2"
```

**Image Pull Errors:**
```bash
# Verify image exists in ECR
aws ecr describe-images --repository-name llama-vllm --region us-east-1

# Check image pull secrets
kubectl get sa -n vllm vllm-sa -o yaml
```

**S3 Access Denied:**
```bash
# Verify IAM role annotation
kubectl describe sa -n vllm vllm-sa

# Test S3 access from pod
kubectl exec -it -n vllm <pod-name> -- aws s3 ls s3://your-bucket/
```

---

## Issue: No Metrics in Grafana

### Symptoms
- Grafana shows "No data"
- Empty graphs despite sending requests

### Diagnosis
```bash
# Check if Prometheus is scraping
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Visit http://localhost:9090/targets
# Look for vllm-metrics

# Check ServiceMonitor
kubectl get servicemonitor -n monitoring vllm-metrics -o yaml

# Test metrics endpoint directly
curl http://<LOAD_BALANCER>:8000/metrics
```

### Solutions

**ServiceMonitor not found:**
```bash
kubectl apply -f monitoring/vllm-servicemonitor.yaml
```

**Service missing labels:**
```bash
kubectl label svc -n vllm vllm-service app=vllm-llama
```

**Port not named:**
```bash
kubectl patch svc -n vllm vllm-service --type='json' -p='[
  {"op": "replace", "path": "/spec/ports/0/name", "value": "http"}
]'
```

**Wrong namespace selector:**
```yaml
# ServiceMonitor must have:
namespaceSelector:
  matchNames:
  - vllm  # Must match namespace where vLLM is deployed
```

---

## Issue: High Latency

### Symptoms
- Requests taking >10 seconds
- Timeouts

### Diagnosis
```bash
# Check metrics
curl http://<LOAD_BALANCER>:8000/metrics | grep latency

# Check GPU utilization
kubectl exec -it -n vllm <pod-name> -- nvidia-smi

# Check concurrent requests
# Look at Grafana "Estimated Concurrent Requests" panel
```

### Solutions

**GPU Memory Full:**
- Reduce `MAX_MODEL_LEN` in deployment (2048 → 1024)
- Lower `gpu_memory_utilization` in app.py (0.9 → 0.8)

**Too Many Concurrent Requests:**
- Scale horizontally (add more pods)
- Implement request queuing
- Add rate limiting

**Network Issues:**
- Check LoadBalancer health
- Verify security groups allow traffic
- Test from within cluster: `kubectl run -it --rm debug --image=busybox -- wget -O- http://vllm-service.vllm:8000/health`

---

## Issue: Out of Memory (OOM)

### Symptoms
- Pod crashes with exit code 137
- Logs show CUDA OOM errors

### Diagnosis
```bash
# Check GPU memory
kubectl exec -it -n vllm <pod-name> -- nvidia-smi

# Check pod resource limits
kubectl describe pod -n vllm <pod-name> | grep -A 5 Limits
```

### Solutions

1. **Reduce model context:**
```yaml
   env:
   - name: MAX_MODEL_LEN
     value: "1024"  # Reduced from 2048
```

2. **Lower GPU memory utilization:**
```python
   # In app.py
   gpu_memory_utilization=0.85  # Instead of 0.9
```

3. **Use quantized model:**
   - INT8: Saves ~50% memory
   - INT4: Saves ~75% memory

4. **Upgrade GPU:**
   - Switch from g5.xlarge (24GB) to g5.2xlarge or larger

---

## Issue: Prometheus Not Starting

### Symptoms
- Prometheus pod stuck in `Pending`

### Diagnosis
```bash
kubectl describe pod -n monitoring -l app.kubernetes.io/name=prometheus

# Check PVCs
kubectl get pvc -n monitoring
```

### Solutions

**Missing EBS CSI Driver:**
```bash
# Install EBS CSI driver
eksctl create addon \
  --cluster llama-vllm-cluster \
  --name aws-ebs-csi-driver \
  --region us-east-1
```

**No storage class:**
```bash
# Verify storage class exists
kubectl get storageclass

# Should see: gp2 or gp3
```

**Insufficient resources on monitoring node:**
```bash
# Check if t3.medium node is full
kubectl top nodes

# Solution: Create larger monitoring node or reduce Prometheus resources
```

---

## Issue: LoadBalancer Stuck in Pending

### Symptoms
- `kubectl get svc -n vllm` shows `<pending>` for EXTERNAL-IP

### Diagnosis
```bash
# Check service events
kubectl describe svc -n vllm vllm-service

# Check AWS Load Balancer Controller
kubectl get pods -n kube-system | grep aws-load-balancer
```

### Solutions

**No available subnets:**
- Verify VPC has public subnets with available IPs
- Check subnet tags for EKS compatibility

**Service account issues:**
- Ensure AWS Load Balancer Controller is installed
- Verify IAM permissions

**Security group blocking:**
- Check security groups allow inbound traffic on port 8000

---

## Issue: Locust Connection Errors

### Symptoms
- Locust shows high failure rate
- Connection refused/timeout errors

### Diagnosis
```bash
# Test endpoint manually
curl -v http://<LOAD_BALANCER>:8000/health

# Check if pod is accepting connections
kubectl port-forward -n vllm svc/vllm-service 8000:8000
curl http://localhost:8000/health
```

### Solutions

**LoadBalancer not ready:**
```bash
# Wait for EXTERNAL-IP to appear
kubectl get svc -n vllm vllm-service -w
```

**Pod not ready:**
```bash
# Check pod status
kubectl get pods -n vllm

# If not ready, check logs
kubectl logs -n vllm -l app=vllm-llama
```

**Firewall/Security group:**
- Verify security groups allow traffic
- Check AWS Network ACLs
- Verify no corporate firewall blocking

---

## Useful Debug Commands
```bash
# Interactive shell in pod
kubectl exec -it -n vllm <pod-name> -- /bin/bash

# Check GPU
nvidia-smi

# Check Python packages
pip list | grep vllm

# Test local connection
curl http://localhost:8000/health

# Check environment variables
env | grep -E "MODEL|S3|MAX"

# View full pod spec
kubectl get pod -n vllm <pod-name> -o yaml

# Get all events
kubectl get events --all-namespaces --sort-by='.lastTimestamp'

# Check resource quotas
kubectl describe resourcequota -n vllm
```

---

## Performance Tuning

### If throughput is lower than expected:

1. **Check GPU utilization:**
```bash
   kubectl exec -it -n vllm <pod-name> -- watch -n 1 nvidia-smi
```
   - Target: 80-95% GPU utilization
   - If low: Increase batch size or concurrent requests

2. **Adjust vLLM parameters:**
   - `max_num_seqs`: Max batch size
   - `max_num_batched_tokens`: Batch token limit
   - `gpu_memory_utilization`: Memory fraction

3. **Use quantization:**
   - INT8: ~1.5-2x faster, minimal quality loss
   - INT4: ~2-3x faster, slight quality loss

4. **Enable tensor parallelism** (if multiple GPUs):
```yaml
   env:
   - name: TENSOR_PARALLEL_SIZE
     value: "2"  # For 2 GPUs
```

---

## Getting Help

If you're still stuck:

1. **Check logs thoroughly:**
```bash
   kubectl logs -n vllm -l app=vllm-llama --tail=500 > logs.txt
```

2. **Gather cluster info:**
```bash
   kubectl cluster-info dump > cluster-dump.txt
```

3. **Check GitHub Issues:**
   - [vLLM Issues](https://github.com/vllm-project/vllm/issues)
   - [EKS Issues](https://github.com/aws/containers-roadmap/issues)

4. **Community Support:**
   - vLLM Discord
   - AWS EKS Forums
   - Stack Overflow (tag: vllm, eks, kubernetes)
