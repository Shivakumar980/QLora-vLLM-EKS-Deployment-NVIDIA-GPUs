# QLoRA Fine-Tuning with vLLM Deployment on AWS EKS backed by NVIDIA GPUs

A complete end-to-end MLOps pipeline for fine-tuning Llama-2-7B using QLoRA (Quantized Low-Rank Adaptation) and deploying it on AWS EKS with vLLM for production-grade, high-performance inference.

## 🎯 Project Overview

This project demonstrates a production-ready workflow that includes:

- **QLoRA Fine-Tuning**: Memory-efficient 4-bit quantization fine-tuning of Llama-2-7B
- **Containerization**: Docker-based packaging with optimized build process
- **Cloud Deployment**: Kubernetes deployment on AWS EKS with GPU support
- **CI/CD Pipeline**: Automated builds using AWS CodeBuild
- **Monitoring**: Production-grade observability with Prometheus and Grafana
- **Performance Benchmarking**: Comprehensive testing and metrics collection

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   QLoRA Model   │────▶│  Docker Image    │────▶│   AWS ECR       │
│   Fine-Tuning   │     │  (vLLM Server)   │     │   Registry      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
                        ┌──────────────────────────────────────────┐
                        │         AWS EKS Cluster                  │
                        │  ┌────────────┐      ┌────────────┐     │
                        │  │   vLLM     │      │ Prometheus │     │
                        │  │    Pod     │◄─────│  Monitoring│     │
                        │  └────────────┘      └────────────┘     │
                        │         │                    │           │
                        │         ▼                    ▼           │
                        │  ┌────────────┐      ┌────────────┐     │
                        │  │   NVIDIA   │      │  Grafana   │     │
                        │  │ GPU Device │      │ Dashboard  │     │
                        │  └────────────┘      └────────────┘     │
                        └──────────────────────────────────────────┘
```

## ✨ Key Features

- **Memory-Efficient Training**: QLoRA enables fine-tuning 7B models on consumer GPUs
- **High-Performance Inference**: vLLM with PagedAttention for optimized token generation
- **GPU Acceleration**: NVIDIA device plugin for Kubernetes GPU scheduling
- **Auto-Scaling**: Kubernetes HPA for dynamic scaling based on load
- **Production Monitoring**: Real-time metrics, dashboards, and alerting
- **Comprehensive Documentation**: Detailed guides for setup, troubleshooting, and operations

## 📁 Project Structure

```
QLora-vLLM-EKS-Deployment/
├── Docker/                              # Container build configuration
│   ├── Dockerfile                       # Multi-stage Docker build
│   ├── app.py                          # vLLM FastAPI server application
│   ├── download_model.py               # Model download utility
│   ├── build-script.sh                 # Local Docker build script
│   ├── full-build-userdata.sh          # EC2 build automation
│   ├── user-data.sh                    # EC2 instance initialization
│   ├── buildspec.yml                   # AWS CodeBuild specification
│   ├── codebuild-project.json          # CodeBuild project config
│   ├── codebuild-trust-policy.json     # CodeBuild IAM trust policy
│   ├── ec2-trust-policy.json           # EC2 IAM trust policy
│   ├── vllm-servicemonitor.yaml        # Prometheus metrics collection
│   ├── DockerBuild.md                  # Build documentation
│   └── Readme.mdyy                     # Additional notes
│
├── EKS-MANIFESTS/                      # Kubernetes deployment files
│   ├── vllm-deployment.yaml            # Main vLLM deployment manifest
│   ├── nvidia-device-plugin.yml        # GPU device plugin
│   ├── prometheus-servicemonitor.yaml  # Prometheus metrics collection
│   ├── kubernetes_deployment.md        # Deployment guide
│   ├── s3-policy.json                  # S3 access policy
│   └── trust-policy.json               # IAM trust policy
│
├── monitoring/                          # Observability stack
│   ├── prometheus-values.yaml          # Prometheus Helm values
│   ├── vllm-dashboard.json             # Grafana dashboard config
│   ├── vllm-servicemonitor.yaml        # vLLM metrics scraping
│   ├── vLLM Performance Metrics Copy-*.json  # Dashboard backup
│   ├── README.md                       # Monitoring setup guide
│   └── STRUCTURE.md                    # Monitoring architecture
│
├── benchmarking/                        # Performance testing
│   ├── benchmark_vllm.py               # Comprehensive benchmark suite
│   ├── simple_benchmark.sh             # Quick benchmark script
│   ├── requirements.txt                # Benchmark dependencies
│   └── results/                        # Benchmark results (HTML reports)
│       └── benchmark_*.html            # Timestamped benchmark reports
│
├── docs/                                # Documentation
│   ├── QUICKSTART.md                   # Quick start guide
│   ├── TROUBLESHOOTING.md              # Common issues and solutions
│   └── METRICS_GUIDE.md                # Metrics documentation
│
├── backup/                              # Backup and recovery
│   ├── eks-backup.txt                  # EKS cluster backup
│   ├── cluster-backup.json             # Cluster configuration
│   └── cleanup-log.txt                 # Cleanup operations log
│
└── README.md                            # This file
```

## 🚀 Quick Start

### Prerequisites

**Local Development:**
- Python 3.8+
- Docker 20.10+
- AWS CLI v2
- kubectl 1.28+
- Helm 3.x

**AWS Resources:**
- AWS Account with appropriate IAM permissions
- EKS cluster (1.28+)
- ECR repository
- EC2 GPU instances (g5.xlarge, g5.2xlarge, or higher)
- S3 bucket for model storage

**Required Quotas:**
- Running On-Demand G instances (minimum 8 vCPUs)
- EKS cluster capacity

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/Shivakumar980/QLora-vLLM-EKS-Deployment.git
cd QLora-vLLM-EKS-Deployment
```

#### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your Secret Access Key
# Set default region (e.g., us-east-1)
```

#### 3. Set Environment Variables

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPOSITORY=vllm-llama2-qlora
export EKS_CLUSTER_NAME=llm-inference-cluster
```

## 🐳 Docker Build and Push

### Option 1: Local Build

```bash
cd Docker

# Build the Docker image
./build-script.sh

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag vllm-server:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
```

### Option 2: AWS CodeBuild (Automated)

```bash
# Create ECR repository
aws ecr create-repository --repository-name $ECR_REPOSITORY

# Create CodeBuild project
aws codebuild create-project --cli-input-json file://Docker/codebuild-project.json

# Start build
aws codebuild start-build --project-name vllm-docker-build
```

### Option 3: EC2 Instance Build

```bash
# Launch EC2 instance with user data script
aws ec2 run-instances \
    --image-id ami-xxxxxxxxx \
    --instance-type t3.xlarge \
    --user-data file://Docker/full-build-userdata.sh \
    --iam-instance-profile Name=CodeBuildServiceRole
```

For detailed build instructions, see [Docker/DockerBuild.md](Docker/DockerBuild.md)

## ☸️ EKS Deployment

### 1. Create EKS Cluster

```bash
# Using eksctl
eksctl create cluster \
    --name $EKS_CLUSTER_NAME \
    --region $AWS_REGION \
    --nodegroup-name gpu-nodes \
    --node-type g5.xlarge \
    --nodes 2 \
    --nodes-min 1 \
    --nodes-max 4 \
    --managed

# Update kubeconfig
aws eks update-kubeconfig --name $EKS_CLUSTER_NAME --region $AWS_REGION
```

### 2. Install NVIDIA Device Plugin

```bash
cd EKS-MANIFESTS

# Deploy NVIDIA device plugin for GPU support
kubectl apply -f nvidia-device-plugin.yml

# Verify GPU nodes
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

### 3. Deploy vLLM Application

```bash
# Update the image URI in vllm-deployment.yaml
export IMAGE_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
sed -i "s|IMAGE_URI_PLACEHOLDER|$IMAGE_URI|g" vllm-deployment.yaml

# Apply the deployment
kubectl apply -f vllm-deployment.yaml

# Check deployment status
kubectl get pods -l app=vllm-server
kubectl logs -f deployment/vllm-deployment
```

### 4. Expose the Service

```bash
# Get the LoadBalancer URL
kubectl get svc vllm-service

# Wait for LoadBalancer to provision (may take 2-3 minutes)
export LB_URL=$(kubectl get svc vllm-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "vLLM Endpoint: http://$LB_URL:8000"
```

For complete deployment guide, see [EKS-MANIFESTS/kubernetes_deployment.md](EKS-MANIFESTS/kubernetes_deployment.md)

## 🧪 Testing the Deployment

### Health Check

```bash
curl http://$LB_URL:8000/health
# Expected: {"status": "healthy"}
```

### Simple Inference Test

```bash
curl -X POST http://$LB_URL:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "meta-llama/Llama-2-7b-hf",
        "prompt": "Explain machine learning in simple terms:",
        "max_tokens": 100,
        "temperature": 0.7
    }'
```

### Chat Completion Test

```bash
curl -X POST http://$LB_URL:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "meta-llama/Llama-2-7b-hf",
        "messages": [
            {"role": "user", "content": "What is quantum computing?"}
        ],
        "max_tokens": 150
    }'
```

## 📊 Monitoring and Observability

### Deploy Prometheus Stack

```bash
cd monitoring

# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus and Grafana
helm install prometheus prometheus-community/kube-prometheus-stack \
    -f prometheus-values.yaml \
    -n monitoring --create-namespace

# Apply vLLM ServiceMonitor
kubectl apply -f vllm-servicemonitor.yaml
```

### Access Grafana Dashboard

```bash
# Port forward to Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Open browser: http://localhost:3000
# Default credentials: admin / prom-operator
```

### Import vLLM Dashboard

1. Navigate to Dashboards → Import
2. Upload `monitoring/vllm-dashboard.json`
3. Select Prometheus data source
4. Click Import

### Key Metrics Monitored

- **Request Metrics**: Request rate, latency (p50, p95, p99), error rate
- **Token Metrics**: Tokens per second, generation speed
- **GPU Metrics**: Utilization, memory usage, temperature
- **System Metrics**: CPU, memory, network I/O
- **vLLM Specific**: KV cache usage, batch size, queue depth

For detailed monitoring setup, see [monitoring/README.md](monitoring/README.md)

## ⚡ Performance Benchmarking

### Run Comprehensive Benchmark

```bash
cd benchmarking

# Install dependencies
pip install -r requirements.txt

# Run benchmark suite
python benchmark_vllm.py \
    --endpoint http://$LB_URL:8000 \
    --model meta-llama/Llama-2-7b-hf \
    --num-requests 1000 \
    --concurrent-requests 10 \
    --prompt-length 512 \
    --max-tokens 128

# Results will be saved to results/benchmark_TIMESTAMP.html
```

### Quick Benchmark

```bash
# Simple throughput test
./simple_benchmark.sh http://$LB_URL:8000
```

### Expected Performance (g5.xlarge)

| Metric | Value |
|--------|-------|
| Throughput | 800-1200 tokens/sec |
| Latency (P50) | 45-80ms |
| Latency (P95) | 150-250ms |
| Latency (P99) | 300-450ms |
| GPU Memory Usage | ~14GB |
| Concurrent Requests | 10-15 optimal |

## 🔧 Troubleshooting

### Common Issues

#### 1. Pod Stuck in Pending State

**Symptom**: Pod remains in `Pending` status
```bash
kubectl describe pod <pod-name>
```

**Solutions**:
- Check GPU node availability: `kubectl get nodes -l node.kubernetes.io/instance-type`
- Verify NVIDIA device plugin: `kubectl get pods -n kube-system | grep nvidia`
- Check resource quotas: `kubectl describe resourcequota`

#### 2. Out of Memory (OOM) Errors

**Symptom**: Pod crashes with OOM
```bash
kubectl logs <pod-name> --previous
```

**Solutions**:
- Reduce `max_model_len` in deployment
- Use smaller batch size
- Upgrade to larger GPU instance (g5.2xlarge)

#### 3. Docker Build Failures

**Symptom**: Build fails during layer creation

**Solutions**:
```bash
# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1
docker build -t vllm-server:latest .

# Check disk space
df -h
```

#### 4. Image Pull Errors

**Symptom**: `ErrImagePull` or `ImagePullBackOff`

**Solutions**:
```bash
# Verify ECR authentication
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Check IAM permissions for EKS nodes
aws iam get-role-policy --role-name <node-role> --policy-name ECRAccess
```

#### 5. GPU Not Detected

**Symptom**: vLLM logs show "No GPU available"

**Solutions**:
```bash
# Reinstall NVIDIA device plugin
kubectl delete -f nvidia-device-plugin.yml
kubectl apply -f nvidia-device-plugin.yml

# Verify GPU allocation
kubectl describe node <gpu-node-name> | grep nvidia.com/gpu
```

For comprehensive troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## 📖 Documentation

- **[Quick Start Guide](docs/QUICKSTART.md)**: Get up and running in 15 minutes
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)**: Solutions to common problems
- **[Metrics Guide](docs/METRICS_GUIDE.md)**: Understanding monitoring metrics
- **[Docker Build Guide](Docker/DockerBuild.md)**: Detailed container build instructions
- **[Kubernetes Deployment](EKS-MANIFESTS/kubernetes_deployment.md)**: EKS deployment details
- **[Monitoring Architecture](monitoring/STRUCTURE.md)**: Observability stack overview

## 🎯 Best Practices

### Security

- Use IAM roles for service accounts (IRSA) instead of access keys
- Enable encryption at rest for EBS volumes
- Use private subnets for worker nodes
- Implement network policies for pod-to-pod communication
- Regularly update base images and dependencies

### Performance Optimization

- **Batch Size**: Tune based on GPU memory and latency requirements
- **Max Model Length**: Balance between context size and throughput
- **Tensor Parallelism**: Use for models >13B parameters
- **KV Cache**: Enable for improved throughput on repeated requests
- **GPU Memory**: Set `--gpu-memory-utilization 0.9` for optimal usage

### Cost Optimization

- Use Spot instances for non-critical workloads (can save 70-90%)
- Implement Cluster Autoscaler for dynamic scaling
- Right-size GPU instances based on workload
- Use mixed instance types in node groups
- Monitor idle resources with CloudWatch

### Operational Excellence

- Implement proper logging with CloudWatch or ELK
- Set up alerting for critical metrics
- Use GitOps (ArgoCD/FluxCD) for deployment automation
- Maintain separate dev/staging/prod environments
- Regular backup of cluster state and configurations

## 🔄 CI/CD Pipeline

The project includes AWS CodeBuild integration for automated builds:

1. **Source Stage**: Code pushed to GitHub
2. **Build Stage**: CodeBuild triggered
   - Downloads base model
   - Builds Docker image
   - Runs security scanning
3. **Push Stage**: Image pushed to ECR
4. **Deploy Stage**: Updates EKS deployment

See [Docker/buildspec.yml](Docker/buildspec.yml) for build configuration.

## 🧹 Cleanup

### Delete Kubernetes Resources

```bash
kubectl delete -f EKS-MANIFESTS/vllm-deployment.yaml
kubectl delete -f EKS-MANIFESTS/nvidia-device-plugin.yml
helm uninstall prometheus -n monitoring
kubectl delete namespace monitoring
```

### Delete EKS Cluster

```bash
eksctl delete cluster --name $EKS_CLUSTER_NAME --region $AWS_REGION
```

### Delete ECR Repository

```bash
aws ecr delete-repository --repository-name $ECR_REPOSITORY --force
```

### Delete CodeBuild Project

```bash
aws codebuild delete-project --name vllm-docker-build
```

## 📊 Project Metrics

- **Model**: Llama-2-7B (Fine-tuned with QLoRA)
- **Quantization**: 4-bit (bitsandbytes)
- **Inference Engine**: vLLM 0.4.x
- **Container Size**: ~8-10 GB
- **Cold Start Time**: 60-90 seconds
- **GPU Memory**: 14-16 GB (g5.xlarge)

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Meta AI** for the Llama-2 model
- **Tim Dettmers** for QLoRA and bitsandbytes
- **vLLM Team** for the inference engine
- **NVIDIA** for CUDA and GPU support
- **AWS** for EKS and cloud infrastructure
- **Hugging Face** for model hosting and transformers library

## 📚 References

### Documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [QLoRA Paper (Arxiv)](https://arxiv.org/abs/2305.14314)
- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes GPU Guide](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [Prometheus Operator](https://prometheus-operator.dev/)

### Related Technologies
- [Hugging Face Transformers](https://github.com/huggingface/transformers)
- [PEFT (Parameter-Efficient Fine-Tuning)](https://github.com/huggingface/peft)
- [bitsandbytes](https://github.com/TimDettmers/bitsandbytes)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)

## 📧 Contact

**Shivakumar** - [@Shivakumar980](https://github.com/Shivakumar980)

Project Link: [https://github.com/Shivakumar980/QLora-vLLM-EKS-Deployment](https://github.com/Shivakumar980/QLora-vLLM-EKS-Deployment)

## 🌟 Star History

If you find this project helpful, please consider giving it a ⭐!

---

**Built with ❤️ for the ML/MLOps community**
