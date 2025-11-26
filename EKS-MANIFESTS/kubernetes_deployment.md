# EKS Kubernetes Deployment with GPU Support

## �� Overview

This document describes the deployment of the vLLM inference application on Amazon EKS (Elastic Kubernetes Service) with NVIDIA GPU support. The deployment uses g4dn.xlarge instances with Tesla T4 GPUs for high-performance LLM inference.

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    EKS Cluster Architecture                  │
└─────────────────────────────────────────────────────────────┘

AWS EKS Control Plane (Managed by AWS)
├── API Server
├── etcd (State storage)
├── Scheduler
└── Controller Manager
        ↓
        ↓
Data Plane - Node Group: gpu-nodes
└── EC2 Instance: g4dn.xlarge
    ├── Instance Details:
    │   ├── vCPUs: 4
    │   ├── RAM: 16 GB
    │   ├── GPU: 1x NVIDIA Tesla T4 (16 GB VRAM)
    │   ├── Storage: 125 GB NVMe SSD
    │   └── Network: Up to 25 Gbps
    │
    ├── Kubernetes Components:
    │   ├── kubelet (node agent)
    │   ├── kube-proxy (network proxy)
    │   └── Container Runtime (containerd)
    │
    ├── NVIDIA Device Plugin DaemonSet
    │   └── Exposes GPU as allocatable resource
    │
    └── Pods:
        └── vllm-llama Pod
            ├── Container: vllm
            │   ├── Image: ECR llama-vllm:latest
            │   ├── Resources:
            │   │   ├── GPU: 1 (nvidia.com/gpu)
            │   │   ├── CPU: 2 cores (request), 3 cores (limit)
            │   │   └── Memory: 12Gi (request), 14Gi (limit)
            │   └── Environment:
            │       ├── S3_BUCKET
            │       ├── MODEL_PATH
            │       └── GPU_MEMORY_UTILIZATION
            │
            ├── Service Account: vllm-sa
            │   └── IAM Role (IRSA): vllm-s3-access-role
            │
            └── Volumes:
                └── emptyDir: /models (ephemeral storage)

        ↓
        ↓ Downloads model from
        ↓
    S3 Bucket
    └── llama-qlora-1763527961/
        └── llama-2-7b-merged-vllm/ (~13 GB)

        ↓
        ↓ Exposes via
        ↓
    LoadBalancer Service
    └── External IP: a50191ee...elb.amazonaws.com:8000
```

---

## 🖥️ GPU Instance Specifications

### **g4dn.xlarge Details**
```
┌────────────────────────────────────────────────────────┐
│              g4dn.xlarge Specifications                 │
├────────────────────────────────────────────────────────┤
│                                                        │
│  GPU:                                                  │
│  ├─ Model: NVIDIA Tesla T4                           │
│  ├─ Architecture: Turing                              │
│  ├─ CUDA Cores: 2,560                                │
│  ├─ Tensor Cores: 320                                 │
│  ├─ Memory: 16 GB GDDR6                              │
│  ├─ Memory Bandwidth: 320 GB/s                       │
│  └─ FP16 Performance: 65 TFLOPS                      │
│                                                        │
│  Compute:                                              │
│  ├─ vCPUs: 4 (Intel Xeon Cascade Lake)              │
│  ├─ RAM: 16 GB                                       │
│  ├─ Network: Up to 25 Gbps                           │
│  └─ Storage: 125 GB NVMe SSD                         │
│                                                        │
│  Cost:                                                 │
│  ├─ On-Demand: $0.526/hour (us-east-1)              │
│  ├─ Monthly (24/7): ~$380                            │
│  └─ Monthly (8hrs/day): ~$127                        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### **vCPU Quota Requirements**
```
Instance Type    vCPUs Required    Quota Code
─────────────────────────────────────────────────────────
g4dn.xlarge      4                L-DB2E81BA
g4dn.2xlarge     8                L-DB2E81BA
g4dn.4xlarge     16               L-DB2E81BA

Default Quota (New AWS Accounts): 0
Required Action: Request quota increase via AWS Service Quotas
Approval Time: 5-30 minutes (typically)
```

---

## 🚀 Prerequisites

### **Required Tools**
```bash
# Check installed versions
eksctl version      # Should be 0.150.0+
kubectl version     # Should be 1.28.0+
aws --version       # Should be 2.0.0+
helm version        # Should be 3.0.0+ (for monitoring)

# Install if missing (macOS)
brew install eksctl kubectl awscli helm

# Install if missing (Linux)
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz"
tar -xzf eksctl_Linux_amd64.tar.gz -C /tmp && sudo mv /tmp/eksctl /usr/local/bin
```

### **AWS Configuration**
```bash
# Configure AWS credentials
aws configure
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region: us-east-1
# Default output format: json

# Verify account
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account: ${AWS_ACCOUNT_ID}"
```

---

## 📊 GPU Quota Increase

### **Step 1: Check Current Quota**
```bash
# Check "Running On-Demand G and VT instances" quota
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --region us-east-1 \
  --query 'Quota.Value' \
  --output text
```

**Expected Output:**
- New accounts: `0.0` (need to request increase)
- After approval: `4.0` or higher

---

### **Step 2: Request Quota Increase**

**Option A: AWS Console (Recommended)**

1. Navigate to: https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas/L-DB2E81BA
2. Click "Request quota increase"
3. Enter desired value: `4` (for g4dn.xlarge) or `8` (for g4dn.2xlarge)
4. Submit request

**Option B: AWS CLI**
```bash
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --desired-value 4.0 \
  --region us-east-1
```

**Approval Timeline:**
- Typical: 5-30 minutes
- Complex cases: 1-2 business days

---

### **Step 3: Verify Quota Increase**
```bash
# Check approved quota
aws service-quotas get-service-quota \
  --service-code ec2 \
  --quota-code L-DB2E81BA \
  --region us-east-1

# Should show: "Value": 4.0 or higher
```

---

## ☸️ EKS Cluster Creation

### **Step 1: Create Cluster with GPU Node Group**
```bash
# Create cluster configuration
eksctl create cluster \
  --name llama-vllm-cluster \
  --region us-east-1 \
  --nodegroup-name gpu-nodes \
  --node-type g4dn.xlarge \
  --nodes 1 \
  --nodes-min 1 \
  --nodes-max 1 \
  --managed

# Creation time: 15-20 minutes
```

**What this creates:**
```
AWS Resources Created:
├── EKS Cluster
│   ├── Control Plane (managed by AWS)
│   ├── VPC with public/private subnets
│   ├── Security Groups
│   └── IAM Role for cluster
│
└── Managed Node Group
    ├── Auto Scaling Group (1 instance)
    ├── Launch Template
    ├── IAM Instance Profile
    └── EC2 Instance (g4dn.xlarge)
        └── AMI: Amazon EKS optimized AL2023 with NVIDIA drivers
```

**CloudFormation Stacks Created:**
- `eksctl-llama-vllm-cluster-cluster` (Control plane)
- `eksctl-llama-vllm-cluster-nodegroup-gpu-nodes` (Node group)

---

### **Step 2: Verify Cluster**
```bash
# Check cluster status
eksctl get cluster --name llama-vllm-cluster --region us-east-1

# Expected output:
# NAME                 VERSION  STATUS   CREATED
# llama-vllm-cluster   1.32     ACTIVE   2025-11-24T10:15:00Z

# Update kubeconfig
aws eks update-kubeconfig \
  --name llama-vllm-cluster \
  --region us-east-1

# Verify kubectl access
kubectl get nodes

# Expected output:
# NAME                             STATUS   ROLES    AGE   VERSION
# ip-192-168-50-209.ec2.internal   Ready    <none>   5m    v1.32.9-eks-c39b1d0
```

---

### **Step 3: Verify Node Specifications**
```bash
# Get detailed node info
kubectl describe node | grep -A 20 "Capacity:"

# Expected output:
# Capacity:
#   cpu:                4
#   ephemeral-storage:  125034Mi
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             16054744Ki
#   nvidia.com/gpu:     0          ← Will be 1 after device plugin
#   pods:               29
```

---

## 🎮 NVIDIA Device Plugin Installation

The NVIDIA Device Plugin enables Kubernetes to discover and allocate GPUs as schedulable resources.

### **Step 1: Install Device Plugin**
```bash
# Install NVIDIA device plugin DaemonSet
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify DaemonSet
kubectl get daemonset -n kube-system | grep nvidia

# Expected output:
# NAME                           DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE
# nvidia-device-plugin-daemonset 1         1         1       1            1
```

---

### **Step 2: Verify GPU Detection**
```bash
# Check GPU as allocatable resource
kubectl get nodes -o json | jq '.items[].status.allocatable."nvidia.com/gpu"'

# Expected output: "1"

# Check GPU details
kubectl describe node | grep -A 10 "Allocatable:"

# Expected output:
# Allocatable:
#   cpu:                3920m
#   ephemeral-storage:  114868820671
#   hugepages-1Gi:      0
#   hugepages-2Mi:      0
#   memory:             14939480Ki
#   nvidia.com/gpu:     1          ← GPU now available!
#   pods:               29
```

---

### **Step 3: Check Device Plugin Logs**
```bash
# Get device plugin pod name
DEVICE_PLUGIN_POD=$(kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs -n kube-system ${DEVICE_PLUGIN_POD}

# Expected output:
# I1124 10:20:15.123456       1 main.go:154] Starting NVIDIA Device Plugin
# I1124 10:20:15.234567       1 main.go:165] Starting FS watcher.
# I1124 10:20:15.345678       1 main.go:172] Starting OS watcher.
# I1124 10:20:15.456789       1 main.go:186] Retreiving plugins.
# I1124 10:20:15.567890       1 main.go:196] Starting plugin server for 'nvidia.com/gpu'
```

---

## 🔐 IAM Configuration (IRSA)

### **What is IRSA?**

**IAM Roles for Service Accounts (IRSA)** allows Kubernetes service accounts to assume IAM roles without storing credentials in the pod.
```
Flow:
Pod (vllm-llama)
  └─> ServiceAccount (vllm-sa)
      └─> IAM Role (vllm-s3-access-role)
          └─> S3 Bucket Access
              └─> Download model files
```

---

### **Step 1: Associate OIDC Provider**
```bash
# Get OIDC provider ID
OIDC_ID=$(aws eks describe-cluster \
    --name llama-vllm-cluster \
    --region us-east-1 \
    --query "cluster.identity.oidc.issuer" \
    --output text | cut -d '/' -f 5)

echo "OIDC Provider ID: ${OIDC_ID}"

# Associate OIDC provider with cluster
eksctl utils associate-iam-oidc-provider \
  --cluster llama-vllm-cluster \
  --region us-east-1 \
  --approve

# Verify OIDC provider
aws iam list-open-id-connect-providers | grep ${OIDC_ID}
```

---

### **Step 2: Create IAM Role for Service Account**
```bash
# Get AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/${OIDC_ID}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.us-east-1.amazonaws.com/id/${OIDC_ID}:sub": "system:serviceaccount:vllm:vllm-sa",
          "oidc.eks.us-east-1.amazonaws.com/id/${OIDC_ID}:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create S3 access policy
cat > s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::llama-qlora-1763527961/*",
        "arn:aws:s3:::llama-qlora-1763527961"
      ]
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name vllm-s3-access-role \
  --assume-role-policy-document file://trust-policy.json

# Create S3 policy
aws iam create-policy \
  --policy-name vllm-s3-policy \
  --policy-document file://s3-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name vllm-s3-access-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/vllm-s3-policy

echo "IAM Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/vllm-s3-access-role"
```

---

## 📦 Application Deployment

### **Step 1: Create Kubernetes Manifests**
```bash
# Create manifests directory
mkdir -p ~/eks-manifests
cd ~/eks-manifests

# Create deployment manifest
cat > vllm-deployment.yaml << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: vllm
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vllm-sa
  namespace: vllm
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/vllm-s3-access-role
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-llama
  namespace: vllm
  labels:
    app: vllm-llama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-llama
  template:
    metadata:
      labels:
        app: vllm-llama
    spec:
      serviceAccountName: vllm-sa
      containers:
      - name: vllm
        image: ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
          protocol: TCP
        env:
        - name: MODEL_PATH
          value: "/models/llama-2-7b-merged-vllm"
        - name: S3_BUCKET
          value: "llama-qlora-1763527961"
        - name: S3_PREFIX
          value: "llama-2-7b-merged-vllm"
        - name: MAX_MODEL_LEN
          value: "512"
        - name: GPU_MEMORY_UTILIZATION
          value: "0.95"
        - name: TENSOR_PARALLEL_SIZE
          value: "1"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "12Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "14Gi"
            cpu: "3"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 300
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 300
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: vllm-service
  namespace: vllm
  labels:
    app: vllm-llama
spec:
  type: LoadBalancer
  selector:
    app: vllm-llama
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
    name: http
EOF
```

**Manifest Components:**
```
Resources Created:
├── Namespace: vllm
│   └── Isolation for vLLM resources
│
├── ServiceAccount: vllm-sa
│   └── Linked to IAM role via annotation
│
├── Deployment: vllm-llama
│   ├── Replicas: 1
│   ├── Container Image: From ECR
│   ├── Resource Requests:
│   │   ├── GPU: 1 (nvidia.com/gpu)
│   │   ├── CPU: 2 cores
│   │   └── Memory: 12Gi
│   ├── Resource Limits:
│   │   ├── GPU: 1
│   │   ├── CPU: 3 cores
│   │   └── Memory: 14Gi
│   └── Probes:
│       ├── Liveness: /health (300s delay)
│       └── Readiness: /health (300s delay)
│
└── Service: vllm-service
    ├── Type: LoadBalancer
    ├── Port: 8000
    └── Creates: AWS ELB
```

---

### **Step 2: Apply Manifests**
```bash
# Deploy application
kubectl apply -f vllm-deployment.yaml

# Expected output:
# namespace/vllm created
# serviceaccount/vllm-sa created
# deployment.apps/vllm-llama created
# service/vllm-service created
```

---

### **Step 3: Monitor Pod Creation**
```bash
# Watch pod status
kubectl get pods -n vllm -w

# Pod lifecycle:
# NAME                          READY   STATUS    AGE
# vllm-llama-xxx               0/1     Pending   0s      ← Scheduling
# vllm-llama-xxx               0/1     Pending   5s      ← Waiting for node
# vllm-llama-xxx               0/1     ContainerCreating   10s  ← Pulling image
# vllm-llama-xxx               1/1     Running   3m      ← Downloading model from S3
# vllm-llama-xxx               1/1     Running   7m      ← Model loaded, ready!
```

**Timeline:**
```
Phase                 Duration    Description
──────────────────────────────────────────────────────────
Pending               5-30s       Kubernetes scheduling
ContainerCreating     2-3min      Pulling 7.7GB image from ECR
Running (not ready)   3-5min      Downloading 13GB model from S3
Running (ready)       -           vLLM initialized, serving
──────────────────────────────────────────────────────────
Total Cold Start:     6-9 minutes
```

---

### **Step 4: View Pod Logs**
```bash
# Get pod name
export POD_NAME=$(kubectl get pods -n vllm -l app=vllm-llama -o jsonpath='{.items[0].metadata.name}')

# Follow logs
kubectl logs -f -n vllm ${POD_NAME}

# Expected log output:
# ==========
# == CUDA ==
# ==========
# CUDA Version 12.1.0
# ...
# 📥 Model not found locally. Downloading from S3...
# 📥 Downloading model from s3://llama-qlora-1763527961/llama-2-7b-merged-vllm...
#   Downloading: llama-2-7b-merged-vllm/config.json
#   Downloading: llama-2-7b-merged-vllm/model-00001-of-00007.safetensors
#   ...
# ✅ Downloaded 14 files to /models/llama-2-7b-merged-vllm
# ✅ Model downloaded successfully!
# INFO:     Started server process [1]
# INFO:     Waiting for application startup.
# 🚀 Loading model from /models/llama-2-7b-merged-vllm...
# INFO: Initializing an LLM engine with config: model='/models/llama-2-7b-merged-vllm', max_seq_len=512...
# INFO: # GPU blocks: 10, # CPU blocks: 512
# ✅ Model loaded successfully!
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### **Step 5: Get LoadBalancer URL**
```bash
# Wait for LoadBalancer provisioning (2-3 minutes)
kubectl get svc -n vllm -w

# Expected output:
# NAME            TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
# vllm-service    LoadBalancer   10.100.xxx.xxx  <pending>     8000:31234/TCP   30s
# vllm-service    LoadBalancer   10.100.xxx.xxx  a5019xxx...   8000:31234/TCP   2m

# Save LoadBalancer URL
export LB_URL=$(kubectl get svc -n vllm vllm-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "LoadBalancer URL: http://${LB_URL}:8000"
```

---

## 🧪 Testing the Deployment

### **Health Check**
```bash
# Test health endpoint
curl http://${LB_URL}:8000/health

# Expected response:
# {"status":"healthy","model":"/models/llama-2-7b-merged-vllm"}
```

---

### **Text Generation**
```bash
# Test inference
curl -X POST http://${LB_URL}:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in simple terms:",
    "max_tokens": 100,
    "temperature": 0.7
  }'

# Expected response:
# {
#   "generated_text": "Quantum computing is a revolutionary...",
#   "tokens_generated": 87
# }
```

---

### **Prometheus Metrics**
```bash
# View metrics
curl http://${LB_URL}:8000/metrics

# Sample output:
# vllm_requests_total{status="success"} 15.0
# vllm_request_latency_seconds_sum 45.2
# vllm_request_latency_seconds_count 15.0
# vllm_tokens_generated_total 1234.0
# vllm_active_requests 0.0
# vllm_model_loaded 1.0
```

---

## 🔍 Monitoring & Debugging

### **Check Pod Status**
```bash
# Get pod details
kubectl describe pod -n vllm ${POD_NAME}

# Check resource allocation
kubectl describe pod -n vllm ${POD_NAME} | grep -A 10 "Limits:"

# Expected output:
#   Limits:
#     cpu:             3
#     memory:          14Gi
#     nvidia.com/gpu:  1
#   Requests:
#     cpu:             2
#     memory:          12Gi
#     nvidia.com/gpu:  1
```

---

### **Check GPU Usage**
```bash
# Exec into pod
kubectl exec -it -n vllm ${POD_NAME} -- nvidia-smi

# Expected output:
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 525.60.13    Driver Version: 525.60.13    CUDA Version: 12.1   |
# |-------------------------------+----------------------+----------------------+
# | GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
# | Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
# |===============================+======================+======================|
# |   0  Tesla T4            Off  | 00000000:00:1E.0 Off |                    0 |
# | N/A   45C    P0    28W /  70W |  12456MiB / 15360MiB |     75%      Default |
# +-------------------------------+----------------------+----------------------+

# Watch GPU usage in real-time
kubectl exec -it -n vllm ${POD_NAME} -- watch -n 1 nvidia-smi
```

---

### **View Events**
```bash
# Check cluster events
kubectl get events -n vllm --sort-by='.lastTimestamp'

# Check pod events
kubectl describe pod -n vllm ${POD_NAME} | grep -A 20 "Events:"
```

---

## 🐛 Troubleshooting

### **Issue 1: Pod Stuck in Pending**

**Symptoms:**
```bash
kubectl get pods -n vllm
# NAME                 READY   STATUS    RESTARTS   AGE
# vllm-llama-xxx      0/1     Pending   0          5m
```

**Diagnosis:**
```bash
kubectl describe pod -n vllm ${POD_NAME} | grep -A 10 "Events:"
```

**Common Causes & Solutions:**

**A. Insufficient CPU**
```
Error: "0/1 nodes are available: 1 Insufficient cpu."

Solution:
kubectl patch deployment vllm-llama -n vllm --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "1"}
]'
```

**B. Insufficient GPU**
```
Error: "0/1 nodes are available: 1 Insufficient nvidia.com/gpu."

Solution 1: Check NVIDIA device plugin
kubectl get daemonset -n kube-system nvidia-device-plugin-daemonset

Solution 2: Reinstall device plugin
kubectl delete -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

**C. Node Not Ready**
```
Error: "0/1 nodes are available: 1 node(s) had untolerated taint."

Solution: Check node status
kubectl get nodes
kubectl describe node | grep -A 5 "Taints:"
```

---

### **Issue 2: Pod CrashLoopBackOff**

**Symptoms:**
```bash
kubectl get pods -n vllm
# NAME                 READY   STATUS             RESTARTS   AGE
# vllm-llama-xxx      0/1     CrashLoopBackOff   3          5m
```

**Diagnosis:**
```bash
# Check current logs
kubectl logs -n vllm ${POD_NAME}

# Check previous crash logs
kubectl logs -n vllm ${POD_NAME} --previous
```

**Common Causes:**

**A. S3 Permission Error**
```
Error: "botocore.exceptions.NoCredentialsError: Unable to locate credentials"

Solution:
1. Verify OIDC provider: eksctl utils associate-iam-oidc-provider --cluster llama-vllm-cluster --approve
2. Check ServiceAccount annotation: kubectl get sa vllm-sa -n vllm -o yaml
3. Verify IAM role exists: aws iam get-role --role-name vllm-s3-access-role
4. Check IAM policy: aws iam list-attached-role-policies --role-name vllm-s3-access-role
```

**B. GPU Memory Error**
```
Error: "ValueError: The model's max seq len (512) is larger than the maximum number of tokens that can be stored in KV cache (160)"

Solution:
kubectl set env deployment/vllm-llama -n vllm MAX_MODEL_LEN=256
kubectl set env deployment/vllm-llama -n vllm GPU_MEMORY_UTILIZATION=0.98
```

**C. Image Pull Error**
```
Error: "Failed to pull image: authorization failed"

Solution:
# Verify ECR permissions
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Check image exists
aws ecr describe-images --repository-name llama-vllm --region us-east-1
```

---

### **Issue 3: LoadBalancer Stuck in Pending**

**Symptoms:**
```bash
kubectl get svc -n vllm
# NAME            TYPE           EXTERNAL-IP   PORT(S)          AGE
# vllm-service    LoadBalancer   <pending>     8000:31234/TCP   10m
```

**Solution:**
```bash
# Wait 3-5 minutes for AWS to provision ELB
# Check service events
kubectl describe svc -n vllm vllm-service

# If still pending after 10 minutes, check VPC configuration
aws ec2 describe-vpcs --filters "Name=tag:alpha.eksctl.io/cluster-name,Values=llama-vllm-cluster"

# Verify subnets have required tags
aws ec2 describe-subnets --filters "Name=vpc-id,Values=YOUR_VPC_ID" --query 'Subnets[*].[SubnetId,Tags]'
```

---

## 📊 Resource Utilization

### **Expected Resource Usage**
```
┌────────────────────────────────────────────────────────┐
│           Pod Resource Consumption                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  GPU:                                                  │
│  ├─ Utilization: 70-90% (during inference)           │
│  ├─ Memory Used: 10-12 GB / 16 GB                    │
│  └─ Memory Util: ~75%                                 │
│                                                        │
│  CPU:                                                  │
│  ├─ Used: 1.5-2.5 cores (of 3 limit)                │
│  └─ Utilization: 50-80%                              │
│                                                        │
│  Memory (RAM):                                         │
│  ├─ Used: 8-10 GB (of 14 GB limit)                  │
│  └─ Utilization: ~70%                                 │
│                                                        │
│  Network:                                              │
│  ├─ Ingress: 1-5 KB/s (requests)                    │
│  └─ Egress: 10-50 KB/s (responses)                  │
│                                                        │
│  Storage:                                              │
│  ├─ Model: 13 GB (downloaded to emptyDir)           │
│  └─ Container: 7.7 GB (image layers)                 │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### **Check Current Usage**
```bash
# Pod resource usage
kubectl top pod -n vllm

# Expected output:
# NAME                          CPU(cores)   MEMORY(bytes)
# vllm-llama-xxx               2000m        10000Mi

# Node resource usage
kubectl top node

# Expected output:
# NAME                             CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# ip-192-168-50-209.ec2.internal   2500m        62%    12000Mi         75%
```

---

## 🔄 Scaling Operations

### **Manual Scaling**
```bash
# Scale up replicas
kubectl scale deployment vllm-llama -n vllm --replicas=2

# Note: Limited by GPU availability (1 GPU per node, 1 node in cluster)
# For true scaling, add more nodes:
eksctl scale nodegroup --cluster llama-vllm-cluster --name gpu-nodes --nodes 2 --region us-east-1
```

---

### **Update Deployment**
```bash
# Update environment variable
kubectl set env deployment/vllm-llama -n vllm MAX_MODEL_LEN=256

# Update image
kubectl set image deployment/vllm-llama vllm=${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:v2 -n vllm

# Restart deployment (pulls latest image)
kubectl rollout restart deployment vllm-llama -n vllm

# Check rollout status
kubectl rollout status deployment/vllm-llama -n vllm
```

---

## 💰 Cost Analysis
```
┌────────────────────────────────────────────────────────┐
│              Monthly Cost Breakdown                     │
├────────────────────────────────────────────────────────┤
│                                                        │
│  EKS Control Plane:      $72.00/month                 │
│  g4dn.xlarge (24/7):     $380.00/month                │
│  EBS Storage (125GB):    $12.50/month                 │
│  LoadBalancer:           $16.20/month                 │
│  Data Transfer:          ~$5.00/month                 │
│  ──────────────────────────────────────                │
│  Total (24/7):           $485.70/month                │
│                                                        │
│  With 8hrs/day usage:                                  │
│  g4dn.xlarge:            $127.00/month                │
│  Total (8hrs/day):       $232.70/month                │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 🧹 Cleanup

### **Delete Deployment**
```bash
# Delete application
kubectl delete -f vllm-deployment.yaml

# Or delete namespace (removes all resources)
kubectl delete namespace vllm
```

---

### **Delete Cluster**
```bash
# Delete entire cluster (including node group)
eksctl delete cluster --name llama-vllm-cluster --region us-east-1

# This deletes:
# - EKS control plane
# - Node group
# - EC2 instances
# - VPC (if created by eksctl)
# - Security groups
# - IAM roles
# - LoadBalancers

# Deletion time: 10-15 minutes
```

---

### **Delete IAM Resources**
```bash
# Detach policy from role
aws iam detach-role-policy \
  --role-name vllm-s3-access-role \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/vllm-s3-policy

# Delete role
aws iam delete-role --role-name vllm-s3-access-role

# Delete policy
aws iam delete-policy --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/vllm-s3-policy
```

---

## 📚 Kubernetes Commands Reference

### **Cluster Operations**
```bash
# Get cluster info
kubectl cluster-info

# Get cluster version
kubectl version --short

# View cluster nodes
kubectl get nodes -o wide

# Describe node
kubectl describe node <node-name>
```

---

### **Pod Operations**
```bash
# List pods
kubectl get pods -n vllm

# Watch pods
kubectl get pods -n vllm -w

# Describe pod
kubectl describe pod -n vllm <pod-name>

# Get pod logs
kubectl logs -n vllm <pod-name>

# Follow logs
kubectl logs -f -n vllm <pod-name>

# Previous logs (after crash)
kubectl logs -n vllm <pod-name> --previous

# Exec into pod
kubectl exec -it -n vllm <pod-name> -- /bin/bash

# Port forward
kubectl port-forward -n vllm <pod-name> 8000:8000
```

---

### **Service Operations**
```bash
# List services
kubectl get svc -n vllm

# Describe service
kubectl describe svc -n vllm vllm-service

# Get LoadBalancer URL
kubectl get svc -n vllm vllm-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

---

### **Deployment Operations**
```bash
# Get deployments
kubectl get deployment -n vllm

# Describe deployment
kubectl describe deployment -n vllm vllm-llama

# Scale deployment
kubectl scale deployment vllm-llama -n vllm --replicas=2

# Restart deployment
kubectl rollout restart deployment vllm-llama -n vllm

# Check rollout status
kubectl rollout status deployment vllm-llama -n vllm

# View rollout history
kubectl rollout history deployment vllm-llama -n vllm

# Rollback deployment
kubectl rollout undo deployment vllm-llama -n vllm
```

---

### **Resource Monitoring**
```bash
# Pod resource usage
kubectl top pod -n vllm

# Node resource usage
kubectl top node

# Get events
kubectl get events -n vllm --sort-by='.lastTimestamp'

# Watch events
kubectl get events -n vllm --watch
```

---

## 📖 Additional Resources

- [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes GPU Support](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [IAM Roles for Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [vLLM Documentation](https://docs.vllm.ai/)

---

**Previous:** See [DOCKER-BUILD.md](./DOCKER-BUILD.md) for Docker image build instructions.

**Next:** See [MONITORING.md](./MONITORING.md) for Prometheus + Grafana setup.