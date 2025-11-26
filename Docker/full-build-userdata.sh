#!/bin/bash
exec > /var/log/docker-build.log 2>&1
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Wait for Docker
sleep 10

# Download files
cd /home/ec2-user
mkdir -p build
cd build
aws s3 cp s3://docker-build-temp-1763574912/ . --recursive --exclude "build-script.sh"

# Build
docker build -t llama-vllm:latest .

# Get account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag llama-vllm:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest

# Mark complete
echo "BUILD COMPLETE" > /tmp/build-complete.txt
