# Docker Image Build Pipeline with AWS CodeBuild

## 📋 Overview

This document describes the automated Docker image build pipeline for the vLLM inference application. The pipeline uses AWS CodeBuild to build x86_64 CUDA-enabled images and push them to Amazon ECR.

---

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                  Docker Build Pipeline                       │
└─────────────────────────────────────────────────────────────┘

Local Development
├── app.py                     (FastAPI application)
├── download_model.py          (S3 model loader)
├── Dockerfile                 (Container definition)
└── buildspec.yml              (CodeBuild instructions)
        ↓
        ↓ aws s3 cp
        ↓
S3 Build Bucket
├── s3://docker-build-temp-{timestamp}/
    ├── app.py
    ├── download_model.py
    ├── Dockerfile
    └── buildspec.yml
        ↓
        ↓ CodeBuild triggers
        ↓
AWS CodeBuild
├── Standard:7.0 (x86_64)
├── BUILD_GENERAL1_LARGE
├── Privileged Mode (Docker-in-Docker)
└── Build Process:
    ├── 1. Login to Docker Hub    (avoid rate limits)
    ├── 2. Login to ECR            (push destination)
    ├── 3. Docker build            (8-10 minutes)
    └── 4. Docker push             (2-3 minutes)
        ↓
        ↓
Amazon ECR
└── 533267109039.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest
    ├── Size: ~7.7 GB
    ├── Base: NVIDIA CUDA 12.1.0
    └── Ready for EKS deployment
```

---

## 📁 Project Files

### 1. **Dockerfile**

**Location:** `~/llama-vllm-deploy/Dockerfile`
```dockerfile
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# Prevents interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install Python packages in stages (dependency resolution)
# Stage 1: Core ML libraries
RUN pip3 install --no-cache-dir \
    "numpy<2" \
    torch==2.1.0 \
    transformers==4.36.0

# Stage 2: vLLM inference engine
RUN pip3 install --no-cache-dir \
    vllm==0.2.7

# Stage 3: Application dependencies
RUN pip3 install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    boto3==1.34.0 \
    prometheus-client==0.19.0

# Set working directory
WORKDIR /app

# Copy application code
COPY app.py /app/
COPY download_model.py /app/

# Expose FastAPI port
EXPOSE 8000

# Start application
CMD ["python3", "app.py"]
```

**Key Components:**
- **Base Image:** `nvidia/cuda:12.1.0-devel-ubuntu22.04` (includes CUDA runtime and development tools)
- **Python Version:** 3.10
- **vLLM Version:** 0.2.7 (optimized inference engine)
- **Image Size:** ~7.7 GB
- **Build Time:** 8-10 minutes

---

### 2. **app.py**

**Location:** `~/llama-vllm-deploy/app.py`

FastAPI application with:
- **vLLM Integration:** High-performance inference with PagedAttention
- **S3 Model Loading:** Automatic model download from S3 on startup
- **Prometheus Metrics:** Request count, latency, tokens generated
- **Health Checks:** `/health` endpoint for Kubernetes probes
- **REST API:** `/generate` endpoint for text generation

**Key Features:**
```python
# Environment Configuration
MODEL_PATH = os.getenv("MODEL_PATH", "/models/llama-2-7b-merged-vllm")
S3_BUCKET = os.getenv("S3_BUCKET")
MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", "512"))
GPU_MEMORY_UTILIZATION = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.95"))

# vLLM Initialization
llm_engine = LLM(
    model=MODEL_PATH,
    max_model_len=MAX_MODEL_LEN,
    tensor_parallel_size=1,
    gpu_memory_utilization=GPU_MEMORY_UTILIZATION,
    trust_remote_code=True
)

# Prometheus Metrics
REQUEST_COUNT = Counter('vllm_requests_total', 'Total requests', ['status'])
REQUEST_LATENCY = Histogram('vllm_request_latency_seconds', 'Request latency')
TOKENS_GENERATED = Counter('vllm_tokens_generated_total', 'Tokens generated')
```

---

### 3. **download_model.py**

**Location:** `~/llama-vllm-deploy/download_model.py`

S3 model downloader that:
- Downloads model files from S3 bucket on pod startup
- Uses boto3 with IAM role authentication (no hardcoded credentials)
- Handles paginated S3 object listings
- Creates local directory structure
```python
# Configuration from environment
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "llama-2-7b-merged-vllm")
LOCAL_MODEL_PATH = os.getenv("MODEL_PATH", "/models/llama-2-7b-merged-vllm")

# Downloads ~13GB model (14 files)
# Time: 3-5 minutes on EKS with same-region S3
```

---

### 4. **buildspec.yml**

**Location:** `~/llama-vllm-deploy/buildspec.yml`

CodeBuild configuration file:
```yaml
version: 0.2
phases:
  pre_build:
    commands:
      # Login to Docker Hub (avoid rate limits)
      - echo Logging in to Docker Hub...
      - export DOCKERHUB_CREDS=$(aws secretsmanager get-secret-value --secret-id dockerhub-credentials --query SecretString --output text)
      - export DOCKERHUB_USER=$(echo $DOCKERHUB_CREDS | jq -r '.username')
      - export DOCKERHUB_PASS=$(echo $DOCKERHUB_CREDS | jq -r '.password')
      - echo $DOCKERHUB_PASS | docker login --username $DOCKERHUB_USER --password-stdin
      
      # Login to Amazon ECR
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
  
  build:
    commands:
      - echo Build started on `date`
      - docker build -t llama-vllm:latest .
      - docker tag llama-vllm:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/llama-vllm:latest
  
  post_build:
    commands:
      - echo Build completed on `date`
      - docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/llama-vllm:latest
```

**Build Phases:**
1. **PRE_BUILD:** Authenticate with Docker Hub and ECR
2. **BUILD:** Build and tag Docker image
3. **POST_BUILD:** Push to ECR

---

## 🚀 Setup Instructions

### **Step 1: Create S3 Bucket for Build Files**
```bash
# Set bucket name with timestamp
export BUILD_BUCKET="docker-build-temp-$(date +%s)"

# Create bucket
aws s3 mb s3://${BUILD_BUCKET} --region us-east-1

echo "Build bucket: ${BUILD_BUCKET}"
```

**Purpose:** Store Dockerfile, app.py, download_model.py, and buildspec.yml for CodeBuild access

---

### **Step 2: Create ECR Repository**
```bash
# Create repository for Docker images
aws ecr create-repository \
    --repository-name llama-vllm \
    --region us-east-1 \
    --image-scanning-configuration scanOnPush=true

# Get repository URI
export ECR_REPO=$(aws ecr describe-repositories \
    --repository-names llama-vllm \
    --region us-east-1 \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo "ECR Repository: ${ECR_REPO}"
```

**Output:**
```
533267109039.dkr.ecr.us-east-1.amazonaws.com/llama-vllm
```

---

### **Step 3: Create IAM Role for CodeBuild**
```bash
# Create trust policy
cat > codebuild-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name CodeBuildServiceRole \
  --assume-role-policy-document file://codebuild-trust-policy.json

# Attach managed policies
aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

**Permissions:**
- **ECR:** Push images to repository
- **S3:** Read build files
- **CloudWatch:** Write build logs
- **Secrets Manager:** Access Docker Hub credentials

---

### **Step 4: Store Docker Hub Credentials**
```bash
# Create Docker Hub access token at: https://hub.docker.com/settings/security
# Description: "codebuild-access", Permissions: "Read-only"

# Store in Secrets Manager
aws secretsmanager create-secret \
  --name dockerhub-credentials \
  --secret-string '{"username":"YOUR_DOCKERHUB_USERNAME","password":"YOUR_DOCKERHUB_TOKEN"}' \
  --region us-east-1
```

**Why?**
- Docker Hub has rate limits: 100 pulls/6 hours for unauthenticated users
- Authenticated users get 200 pulls/6 hours
- Prevents build failures from rate limiting

---

### **Step 5: Create CodeBuild Project**
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

cat > codebuild-project.json << EOF
{
  "name": "llama-vllm-build",
  "source": {
    "type": "S3",
    "location": "${BUILD_BUCKET}/"
  },
  "artifacts": {
    "type": "NO_ARTIFACTS"
  },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "BUILD_GENERAL1_LARGE",
    "privilegedMode": true,
    "environmentVariables": [
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "us-east-1"
      },
      {
        "name": "AWS_ACCOUNT_ID",
        "value": "${AWS_ACCOUNT_ID}"
      }
    ]
  },
  "serviceRole": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/CodeBuildServiceRole"
}
EOF

# Create project
aws codebuild create-project --cli-input-json file://codebuild-project.json
```

**Configuration:**
- **Compute:** BUILD_GENERAL1_LARGE (7 GB memory, 4 vCPUs)
- **Privileged Mode:** Required for Docker-in-Docker
- **Runtime:** aws/codebuild/standard:7.0 (includes Docker, Python, AWS CLI)

---

## 🔄 Build Process

### **Step 1: Upload Files to S3**
```bash
cd ~/llama-vllm-deploy

# Upload all build files
aws s3 cp Dockerfile s3://${BUILD_BUCKET}/ --region us-east-1
aws s3 cp app.py s3://${BUILD_BUCKET}/ --region us-east-1
aws s3 cp download_model.py s3://${BUILD_BUCKET}/ --region us-east-1
aws s3 cp buildspec.yml s3://${BUILD_BUCKET}/ --region us-east-1

# Verify upload
aws s3 ls s3://${BUILD_BUCKET}/
```

**Expected Output:**
```
2025-11-24 12:00:00       1234 Dockerfile
2025-11-24 12:00:01       3456 app.py
2025-11-24 12:00:02       2345 download_model.py
2025-11-24 12:00:03        789 buildspec.yml
```

---

### **Step 2: Trigger Build**
```bash
# Start build
aws codebuild start-build --project-name llama-vllm-build

# Output includes build ID:
# "id": "llama-vllm-build:abc123def456..."
```

---

### **Step 3: Monitor Build**
```bash
# Get latest build ID
export BUILD_ID=$(aws codebuild list-builds-for-project \
    --project-name llama-vllm-build \
    --query 'ids[0]' \
    --output text)

# Check status
aws codebuild batch-get-builds \
  --ids ${BUILD_ID} \
  --query "builds[0].[buildStatus,currentPhase]" \
  --output table

# Continuous monitoring
while true; do
  clear
  echo "=== Build Status ==="
  aws codebuild batch-get-builds --ids ${BUILD_ID} \
    --query "builds[0].[buildStatus,currentPhase]" --output table
  echo ""
  date
  sleep 15
done
```

**Build Timeline:**
```
Phase               Duration    Description
──────────────────────────────────────────────────────────
QUEUED              10-30s      Waiting for builder
PROVISIONING        30-60s      Starting build environment
DOWNLOAD_SOURCE     10-20s      Downloading from S3
PRE_BUILD           30s         Docker Hub + ECR login
BUILD               8-10min     Docker build process
POST_BUILD          2-3min      Push image to ECR
COMPLETED           -           Build finished
──────────────────────────────────────────────────────────
Total Time:         ~12-15 minutes
```

---

### **Step 4: View Build Logs**
```bash
# Get CloudWatch log stream
aws logs get-log-events \
  --log-group-name /aws/codebuild/llama-vllm-build \
  --log-stream-name ${BUILD_ID#*:} \
  --limit 100 \
  --region us-east-1 \
  | jq -r '.events[].message'

# Or view in console
echo "https://console.aws.amazon.com/codesuite/codebuild/projects/llama-vllm-build/history?region=us-east-1"
```

---

### **Step 5: Verify Image in ECR**
```bash
# List images
aws ecr describe-images \
  --repository-name llama-vllm \
  --region us-east-1

# Check latest image
aws ecr describe-images \
  --repository-name llama-vllm \
  --region us-east-1 \
  --query 'imageDetails[0].[imageTags,imageSizeInBytes,imagePushedAt]' \
  --output table
```

**Expected Output:**
```
------------------------------------------------------------
|                    DescribeImages                        |
+------------------+-------------------+--------------------+
|  latest          |  7724555583      |  2025-11-24T05:15  |
+------------------+-------------------+--------------------+
    (Tag)              (~7.7 GB)         (Timestamp)
```

---

## 🔁 Updating the Image

### **Quick Update Process**
```bash
# 1. Modify code locally
cd ~/llama-vllm-deploy
# Edit app.py, Dockerfile, etc.

# 2. Upload to S3
aws s3 cp app.py s3://${BUILD_BUCKET}/
aws s3 cp Dockerfile s3://${BUILD_BUCKET}/  # if modified

# 3. Trigger new build
aws codebuild start-build --project-name llama-vllm-build

# 4. Monitor build
export BUILD_ID=$(aws codebuild list-builds-for-project --project-name llama-vllm-build --query 'ids[0]' --output text)
aws codebuild batch-get-builds --ids ${BUILD_ID} --query "builds[0].[buildStatus,currentPhase]" --output table

# 5. Verify new image
aws ecr describe-images --repository-name llama-vllm --region us-east-1 --query 'imageDetails[0].imagePushedAt'
```

---

## 🐛 Troubleshooting

### **Issue 1: Build Fails with Docker Hub Rate Limit**

**Error:**
```
ERROR: toomanyrequests: You have reached your pull rate limit
```

**Solution:**
```bash
# Verify Docker Hub credentials in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id dockerhub-credentials \
  --query SecretString \
  --output text

# Update if needed
aws secretsmanager update-secret \
  --secret-id dockerhub-credentials \
  --secret-string '{"username":"NEW_USER","password":"NEW_TOKEN"}'
```

---

### **Issue 2: Build Fails with Dependency Error**

**Error:**
```
ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/...
```

**Solution:**
```bash
# Check Dockerfile for version conflicts
# Install packages in stages (torch first, then vLLM, then others)
# Pin numpy version: "numpy<2"
```

---

### **Issue 3: CodeBuild Permission Denied**

**Error:**
```
AccessDeniedException: User is not authorized to perform: codebuild:StartBuild
```

**Solution:**
```bash
# Check IAM role has correct permissions
aws iam get-role --role-name CodeBuildServiceRole

# Re-attach policies if needed
aws iam attach-role-policy \
  --role-name CodeBuildServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
```

---

### **Issue 4: Image Not Updating in EKS**

**Problem:** Kubernetes caching old `:latest` image

**Solution:**
```bash
# Option 1: Set imagePullPolicy to Always
kubectl patch deployment vllm-llama -n vllm -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"vllm","imagePullPolicy":"Always"}]}}}}'

# Option 2: Use image digest instead of :latest
IMAGE_DIGEST=$(aws ecr describe-images --repository-name llama-vllm --query 'imageDetails[0].imageDigest' --output text)
kubectl set image deployment/vllm-llama vllm=${ECR_REPO}@${IMAGE_DIGEST} -n vllm
```

---

## 📊 Build Metrics
```
┌────────────────────────────────────────────────────────┐
│              Build Performance Metrics                  │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Average Build Time:      12 minutes                  │
│  Image Size:              7.7 GB                      │
│  Layers:                  15 layers                   │
│  Build Cost:              ~$0.05 per build           │
│                                                        │
│  Breakdown:                                            │
│  ├─ Base Image Pull:      2 min                      │
│  ├─ System Packages:      1 min                      │
│  ├─ Python Packages:      8 min                      │
│  ├─ Copy Application:     <1 sec                     │
│  └─ Push to ECR:          2 min                      │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 💰 Cost Analysis
```
Component               Cost per Build    Monthly (10 builds)
────────────────────────────────────────────────────────────
CodeBuild (Large)       $0.05            $0.50
S3 Storage (build)      $0.01            $0.01
ECR Storage (7.7GB)     $0.77            $0.77
Data Transfer           $0.10            $1.00
────────────────────────────────────────────────────────────
Total:                  $0.93            $2.28
```

---

## 🔐 Security Best Practices

1. **No Hardcoded Credentials**
   - Docker Hub credentials in Secrets Manager
   - IAM roles for S3/ECR access
   - No API keys in Dockerfile or code

2. **Image Scanning**
   - ECR scan on push enabled
   - Checks for CVEs in dependencies

3. **Least Privilege IAM**
   - CodeBuild role has minimal permissions
   - Separate roles for build vs runtime

4. **Private Repositories**
   - ECR repository not publicly accessible
   - S3 bucket not public

---

## 📚 References

- [AWS CodeBuild Documentation](https://docs.aws.amazon.com/codebuild/)
- [Amazon ECR User Guide](https://docs.aws.amazon.com/ecr/)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [NVIDIA CUDA Container Images](https://hub.docker.com/r/nvidia/cuda)

---

## 📝 Quick Reference Commands
```bash
# Upload files to S3
aws s3 sync ~/llama-vllm-deploy/ s3://${BUILD_BUCKET}/ --exclude "*" --include "*.py" --include "Dockerfile" --include "buildspec.yml"

# Start build
aws codebuild start-build --project-name llama-vllm-build

# Check status
aws codebuild batch-get-builds --ids $(aws codebuild list-builds-for-project --project-name llama-vllm-build --query 'ids[0]' --output text) --query "builds[0].[buildStatus,currentPhase]" --output table

# List images
aws ecr list-images --repository-name llama-vllm --region us-east-1

# Delete old images (keep last 5)
aws ecr batch-delete-image --repository-name llama-vllm --image-ids $(aws ecr list-images --repository-name llama-vllm --query 'imageIds[5:]' --output json)
```

---

**Next:** See [EKS-DEPLOYMENT.md](./EKS-DEPLOYMENT.md) for Kubernetes deployment instructions.
