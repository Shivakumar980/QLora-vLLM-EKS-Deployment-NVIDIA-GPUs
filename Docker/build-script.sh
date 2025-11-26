#!/bin/bash
exec > /tmp/build-log.txt 2>&1
cd /home/ec2-user
mkdir -p build
cd build
aws s3 cp s3://docker-build-temp-1763574912/ . --recursive
sudo docker build -t llama-vllm:latest .
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | sudo docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
sudo docker tag llama-vllm:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest
sudo docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/llama-vllm:latest
echo "BUILD COMPLETE" >> /tmp/build-status.txt
