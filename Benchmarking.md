# vLLM Benchmarking and Performance Monitoring

This document provides detailed benchmarking results and performance metrics for the vLLM deployment, captured using Grafana dashboards with Prometheus as the data source.

## Grafana Monitoring Dashboard Overview

The following Grafana dashboards visualize real-time performance metrics from the vLLM inference server deployed on AWS EKS with GPU support. These metrics are crucial for understanding system performance, resource utilization, and identifying potential bottlenecks.

---

## 1. Request Rate and Throughput Metrics

<img width="468" height="264" alt="Image" src="https://github.com/user-attachments/assets/de75c870-99c8-468a-b2b7-ad1db2a37b96" />

### Overview
This dashboard panel displays the **request rate** metrics for the vLLM inference server, showing how many requests are being processed over time.

### Key Metrics Visualized:
- **Requests Per Second (RPS)**: The rate at which the vLLM server is handling incoming inference requests
- **Time-series data**: Shows request patterns and peaks over the monitoring period
- **Throughput trends**: Indicates the system's ability to handle concurrent requests

---

## 2. GPU Utilization and Memory Metrics

<img width="468" height="265" alt="Image" src="https://github.com/user-attachments/assets/3470e283-96f5-4892-9cbe-a31f96ae0421" />

### Overview
This panel tracks **GPU resource utilization**, including compute usage and memory consumption, which are critical for LLM inference workloads.

### Key Metrics Visualized:
- **GPU Utilization (%)**: Percentage of GPU compute being used
- **GPU Memory Usage**: VRAM consumption by the loaded model and inference operations
- **Memory Bandwidth**: Data transfer rates to/from GPU memory
- **Thermal and Power metrics**: Optional monitoring of GPU temperature and power consumption
---

## 3. Response Time and Latency Distribution

<img width="468" height="257" alt="Image" src="https://github.com/user-attachments/assets/d3399d67-2971-428f-9278-0cc36a7e7859" />

### Overview
This dashboard visualizes **inference latency metrics**, showing how quickly the vLLM server responds to requests.

### Key Metrics Visualized:
- **P50 (Median) Latency**: Typical response time for 50% of requests
- **P95 Latency**: Response time for 95% of requests (excluding outliers)
- **P99 Latency**: Worst-case latency for 99% of requests
- **Average Response Time**: Mean latency across all requests
- **Time to First Token (TTFT)**: Critical metric for streaming responses
- **Tokens Per Second**: Generation speed of the model


---

## Benchmarking Configuration

### System Specifications:
- **Model**: Llama-2-7B with QLoRA fine-tuning
- **GPU**: NVIDIA GPU (type based on AWS instance)
- **vLLM Version**: Latest stable release
- **Kubernetes**: AWS EKS cluster with GPU node pool
- **Monitoring Stack**: Prometheus + Grafana

### Test Parameters:
- **Concurrent Users**: Variable load testing from 1 to N users
- **Request Pattern**: Mixed prompt lengths and generation parameters
- **Duration**: Sustained load over monitoring period
- **Metrics Collection**: 15-second scrape interval

---


