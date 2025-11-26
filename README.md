## 1. High-Level AWS Infrastructure Overview
```mermaid
graph TB
    %% Styling
    classDef awsService fill:#FF9900,stroke:#232F3E,stroke-width:3px,color:#232F3E
    classDef k8sService fill:#326CE5,stroke:#fff,stroke-width:2px,color:#fff
    classDef storage fill:#569A31,stroke:#fff,stroke-width:2px,color:#fff
    classDef compute fill:#EC7211,stroke:#fff,stroke-width:2px,color:#fff
    classDef monitoring fill:#146EB4,stroke:#fff,stroke-width:2px,color:#fff
    classDef user fill:#DD344C,stroke:#fff,stroke-width:3px,color:#fff
    
    %% Users
    USER[External Users<br/>Web/CLI/API Clients]:::user
    
    %% AWS Services Layer
    subgraph AWS["AWS Cloud (us-east-1)"]
        direction TB
        
        %% Storage Services
        subgraph STORAGE["Storage Services"]
            S3_MODEL[(S3 Bucket<br/>Model Storage<br/>13 GB)]:::storage
            S3_BUILD[(S3 Bucket<br/>Build Files)]:::storage
            ECR[(Amazon ECR<br/>Container Registry<br/>7.7 GB Image)]:::storage
        end
        
        %% Security Services
        subgraph SECURITY["Security & Secrets"]
            SM[Secrets Manager<br/>Docker Hub Creds]:::awsService
            IAM[IAM Roles<br/>IRSA + CodeBuild]:::awsService
            OIDC[OIDC Provider<br/>EKS Integration]:::awsService
        end
        
        %% Build Pipeline
        subgraph BUILD["CI/CD Pipeline"]
            CB[AWS CodeBuild<br/>Docker Build<br/>x86_64]:::awsService
        end
        
        %% EKS Cluster
        subgraph EKS_CLUSTER["Amazon EKS Cluster"]
            direction TB
            
            CP[Control Plane<br/>Managed by AWS<br/>$72/month]:::k8sService
            
            subgraph VPC["VPC (192.168.0.0/16)"]
                direction TB
                
                subgraph NODE["GPU Node: g4dn.xlarge"]
                    direction TB
                    GPU_HW[Hardware<br/>4 vCPUs, 16GB RAM<br/>Tesla T4 16GB GPU<br/>$380/month]:::compute
                    
                    subgraph K8S_PODS["Kubernetes Pods"]
                        direction LR
                        
                        subgraph NS_VLLM["Namespace: vllm"]
                            VLLM_POD[vLLM Pod<br/>Llama-2-7B Inference<br/>GPU: 1, CPU: 2-3, Mem: 12-14Gi]:::k8sService
                        end
                        
                        subgraph NS_MON["Namespace: monitoring"]
                            PROM[Prometheus<br/>Metrics Collection<br/>30s scrape]:::monitoring
                            GRAF[Grafana<br/>Visualization<br/>Dashboards]:::monitoring
                        end
                    end
                    
                    NVIDIA[NVIDIA Device Plugin<br/>GPU Scheduler]:::k8sService
                end
                
                LB_VLLM[Load Balancer<br/>vLLM Service<br/>Port 8000]:::awsService
                LB_PROM[Load Balancer<br/>Prometheus<br/>Port 9090]:::awsService
                LB_GRAF[Load Balancer<br/>Grafana<br/>Port 80]:::awsService
            end
        end
    end
    
    %% Data Flows
    USER ==>|HTTP Requests| LB_VLLM
    USER ==>|View Metrics| LB_GRAF
    USER ==>|Query Metrics| LB_PROM
    
    S3_BUILD -->|Source Files| CB
    SM -->|Docker Creds| CB
    CB ==>|Push Image| ECR
    
    ECR ==>|Pull Image| VLLM_POD
    S3_MODEL ==>|Download Model<br/>IRSA Auth| VLLM_POD
    IAM -->|Provide Permissions| VLLM_POD
    OIDC -->|Trust Relationship| IAM
    
    CP -->|Manages| NODE
    GPU_HW -->|Hosts| K8S_PODS
    NVIDIA -->|Exposes GPU| VLLM_POD
    
    VLLM_POD -->|Expose Metrics| PROM
    PROM -->|Data Source| GRAF
    
    VLLM_POD -->|Service| LB_VLLM
    PROM -->|Service| LB_PROM
    GRAF -->|Service| LB_GRAF
```

## 2. Docker Build & ECR Pipeline Flow

``` mermaid
sequenceDiagram
    participant Dev as Developer
    participant Local as Local Machine
    participant S3 as S3 Bucket<br/>(Build Files)
    participant CB as AWS CodeBuild
    participant DH as Docker Hub
    participant SM as Secrets Manager
    participant ECR as Amazon ECR
    
    Note over Dev,ECR: Docker Image Build Pipeline
    
    Dev->>Local: 1. Modify code<br/>(app.py, Dockerfile)
    Local->>Local: 2. Test locally (optional)
    
    Local->>S3: 3. Upload files<br/>aws s3 cp *.py *.yml
    Note over S3: Stores:<br/>- Dockerfile<br/>- app.py<br/>- download_model.py<br/>- buildspec.yml
    
    Dev->>CB: 4. Trigger build<br/>aws codebuild start-build
    
    rect rgb(240, 240, 240)
        Note over CB: CodeBuild Process (12 min)
        
        CB->>S3: 5. Download source files
        S3-->>CB: Return files
        
        CB->>SM: 6. Get Docker Hub credentials
        SM-->>CB: Return credentials
        
        CB->>DH: 7. docker login (avoid rate limit)
        DH-->>CB: Authenticated
        
        CB->>ECR: 8. docker login (ECR)
        ECR-->>CB: Authenticated
        
        CB->>CB: 9. docker build<br/>(8-10 min)
        Note over CB: Build Steps:<br/>- Pull NVIDIA CUDA base<br/>- Install Python packages<br/>- Copy application code
        
        CB->>CB: 10. docker tag<br/>llama-vllm:latest
        
        CB->>ECR: 11. docker push<br/>(2-3 min, 7.7 GB)
        ECR-->>CB: Push complete
    end
    
    CB-->>Dev: 12. Build status: SUCCEEDED
    
    Dev->>ECR: 13. Verify image
    ECR-->>Dev: Image details:<br/>Size: 7.7 GB<br/>Tag: latest<br/>Digest: sha256:...
```

## 3. EKS Cluster & Pod Deployment Flow
```mermaid
sequenceDiagram
    participant Admin as Cluster Admin
    participant eksctl as eksctl CLI
    participant AWS as AWS API
    participant EKS as EKS Control Plane
    participant Node as GPU Node<br/>(g4dn.xlarge)
    participant ECR as Amazon ECR
    participant S3 as S3 Bucket<br/>(Model Storage)
    participant Pod as vLLM Pod
    participant LB as Load Balancer
    
    Note over Admin,LB: EKS Cluster Creation & Deployment
    
    rect rgb(230, 230, 250)
        Note over Admin,Node: Cluster Setup (15-20 min)
        
        Admin->>AWS: 1. Request GPU quota increase<br/>(4 vCPUs)
        AWS-->>Admin: Quota approved
        
        Admin->>eksctl: 2. eksctl create cluster<br/>--node-type g4dn.xlarge
        eksctl->>AWS: Create CloudFormation stacks
        
        AWS->>EKS: 3. Provision control plane
        EKS-->>AWS: Control plane ready
        
        AWS->>Node: 4. Launch EC2 instance<br/>(g4dn.xlarge)
        Note over Node: Install:<br/>- kubelet<br/>- Container runtime<br/>- NVIDIA drivers
        Node-->>EKS: 5. Node joins cluster
        
        eksctl-->>Admin: Cluster created ✓
    end
    
    rect rgb(240, 255, 240)
        Note over Admin,Node: NVIDIA GPU Setup
        
        Admin->>EKS: 6. Install NVIDIA device plugin
        EKS->>Node: Deploy DaemonSet
        Node->>Node: 7. Detect GPU<br/>nvidia.com/gpu: 1
        Node-->>EKS: GPU advertised
    end
    
    rect rgb(255, 240, 240)
        Note over Admin,LB: IAM & IRSA Setup
        
        Admin->>AWS: 8. Associate OIDC provider
        AWS-->>Admin: OIDC provider created
        
        Admin->>AWS: 9. Create IAM role<br/>(vllm-s3-access-role)
        AWS-->>Admin: Role created with S3 policy
    end
    
    rect rgb(240, 248, 255)
        Note over Admin,LB: Application Deployment (6-9 min)
        
        Admin->>EKS: 10. kubectl apply deployment
        EKS->>Node: Schedule pod
        
        Node->>ECR: 11. Pull image<br/>(2-3 min)
        ECR-->>Node: Image layers (7.7 GB)
        
        Node->>Pod: 12. Start container
        Pod->>Pod: 13. Run download_model.py
        
        Pod->>S3: 14. Download model<br/>via IRSA (3-5 min)
        Note over Pod,S3: Uses IAM role<br/>No credentials in pod
        S3-->>Pod: Model files (13 GB)
        
        Pod->>Pod: 15. Initialize vLLM<br/>(1-2 min)
        Note over Pod: Load model to GPU<br/>Initialize FastAPI
        
        Pod-->>EKS: 16. Pod ready ✓
        
        EKS->>AWS: 17. Provision LoadBalancer
        AWS->>LB: Create ELB
        LB-->>EKS: LoadBalancer ready
        
        EKS-->>Admin: Deployment complete ✓<br/>URL: a50191ee...elb.amazonaws.com:8000
    end
```

## 4. Model Inference Request Flow
```mermaid
sequenceDiagram
    participant User as User/Client
    participant LB as AWS Load Balancer
    participant SVC as Kubernetes Service
    participant POD as vLLM Pod
    participant API as FastAPI Server
    participant VLLM as vLLM Engine
    participant GPU as Tesla T4 GPU
    participant PROM as Prometheus
    
    Note over User,PROM: Text Generation Request Flow
    
    User->>LB: 1. POST /generate<br/>{"prompt": "...", "max_tokens": 100}
    LB->>SVC: 2. Forward to service:8000
    SVC->>POD: 3. Route to healthy pod
    
    POD->>API: 4. FastAPI endpoint
    
    rect rgb(255, 250, 240)
        Note over API,GPU: Inference Pipeline
        
        API->>API: 5. Increment metrics<br/>REQUEST_COUNT++<br/>ACTIVE_REQUESTS++
        
        API->>VLLM: 6. Call vLLM engine<br/>SamplingParams(temp=0.7, top_p=0.9)
        
        VLLM->>GPU: 7. Load tokens to GPU
        Note over GPU: Tensor Operations:<br/>- Attention computation<br/>- Token generation<br/>- KV cache management
        
        loop Token Generation
            GPU->>GPU: 8. Generate token<br/>(~40-60ms per token)
            GPU->>VLLM: Return token
            VLLM->>VLLM: Update KV cache
        end
        
        GPU-->>VLLM: 9. Complete sequence<br/>(87 tokens, ~4 sec)
        
        VLLM-->>API: 10. Generated text
        
        API->>API: 11. Record metrics<br/>REQUEST_LATENCY.observe(4.2s)<br/>TOKENS_GENERATED += 87<br/>ACTIVE_REQUESTS--
    end
    
    API-->>POD: 12. Response object
    POD-->>SVC: 13. HTTP 200 OK
    SVC-->>LB: 14. Forward response
    LB-->>User: 15. JSON response<br/>{"generated_text": "...", "tokens_generated": 87}
    
    Note over PROM: Scrape Metrics Every 30s
    PROM->>POD: 16. GET /metrics
    POD-->>PROM: 17. Prometheus metrics<br/>vllm_requests_total{status="success"} 1<br/>vllm_request_latency_seconds 4.2<br/>vllm_tokens_generated_total 87
```

## 5. Monitoring Stack Architecture
```mermaid
graph TB
    %% Styling
    classDef vllmNode fill:#3b82f6,stroke:#1e40af,stroke-width:2px,color:#fff
    classDef promNode fill:#E6522C,stroke:#b91c1c,stroke-width:2px,color:#fff
    classDef grafNode fill:#F46800,stroke:#d97706,stroke-width:2px,color:#fff
    classDef alertNode fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
    classDef userNode fill:#8b5cf6,stroke:#6d28d9,stroke-width:3px,color:#fff
    
    USER[DevOps Team<br/>Monitoring Dashboard]:::userNode
    
    subgraph EKS["EKS Cluster"]
        direction TB
        
        subgraph NS_VLLM["Namespace: vllm"]
            VLLM[vLLM Pod<br/>FastAPI + Prometheus Client]:::vllmNode
            VLLM_SVC[Service: vllm-metrics<br/>Port 8000]:::vllmNode
        end
        
        subgraph NS_MON["Namespace: monitoring"]
            direction TB
            
            subgraph PROM_STACK["Prometheus Stack"]
                SM[ServiceMonitor<br/>Target: vllm-metrics<br/>Interval: 30s]:::promNode
                PROM[Prometheus Server<br/>Time-Series DB<br/>Retention: 15 days]:::promNode
                AM[AlertManager<br/>Alert Routing<br/>Slack/Email/PagerDuty]:::alertNode
            end
            
            GRAF[Grafana<br/>Visualization<br/>Dashboards & Panels]:::grafNode
            
            PROM_SVC[Service: Prometheus<br/>LoadBalancer:9090]:::promNode
            GRAF_SVC[Service: Grafana<br/>LoadBalancer:80]:::grafNode
        end
    end
    
    %% Metrics Flow
    VLLM -->|Expose /metrics| VLLM_SVC
    SM -->|Scrape every 30s| VLLM_SVC
    SM -->|Send metrics| PROM
    
    PROM -->|Evaluate rules| AM
    AM -->|Fire alerts| USER
    
    PROM -->|Data source| GRAF
    GRAF -->|Query PromQL| PROM
    
    %% External Access
    PROM -->|Expose| PROM_SVC
    GRAF -->|Expose| GRAF_SVC
    
    PROM_SVC -->|HTTP:9090| USER
    GRAF_SVC -->|HTTP:80| USER
    
    %% Metrics Details
    VLLM -.->|Metrics| METRICS[Prometheus Metrics:<br/>• vllm_requests_total<br/>• vllm_request_latency_seconds<br/>• vllm_tokens_generated_total<br/>• vllm_active_requests<br/>• vllm_model_loaded]:::promNode

```

## 6.Detailed pod Architecture
```mermaid
graph LR
    %% Styling
    classDef containerNode fill:#326CE5,stroke:#fff,stroke-width:2px,color:#fff
    classDef volumeNode fill:#569A31,stroke:#fff,stroke-width:2px,color:#fff
    classDef resourceNode fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E
    classDef configNode fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff
    
    subgraph POD["Pod: vllm-llama-xxxxxxxxxx"]
        direction TB
        
        subgraph META["Pod Metadata"]
            LABELS[Labels:<br/>app: vllm-llama]:::configNode
            SA[ServiceAccount:<br/>vllm-sa<br/>IAM Role: vllm-s3-access-role]:::configNode
        end
        
        subgraph CONTAINER["Container: vllm"]
            direction TB
            
            IMAGE[Image:<br/>533267109039.dkr.ecr<br/>.us-east-1.amazonaws.com<br/>/llama-vllm:latest]:::containerNode
            
            ENV[Environment Variables:<br/>• MODEL_PATH=/models/llama-2-7b-merged-vllm<br/>• S3_BUCKET=llama-qlora-1763527961<br/>• S3_PREFIX=llama-2-7b-merged-vllm<br/>• MAX_MODEL_LEN=512<br/>• GPU_MEMORY_UTILIZATION=0.95<br/>• TENSOR_PARALLEL_SIZE=1]:::configNode
            
            PORTS[Ports:<br/>8000/TCP]:::configNode
            
            subgraph APP_STACK["Application Stack"]
                DOWNLOAD[download_model.py<br/>S3 Model Loader]:::containerNode
                FASTAPI[FastAPI Server<br/>Port 8000]:::containerNode
                VLLM_ENG[vLLM Engine<br/>Inference Optimization]:::containerNode
                MODEL[Llama-2-7B Model<br/>QLoRA Fine-Tuned<br/>~10 GB in GPU Memory]:::containerNode
            end
            
            PROBES[Health Probes:<br/>• Liveness: GET /health<br/>• Readiness: GET /health<br/>  InitialDelay: 300s]:::configNode
        end
        
        subgraph RESOURCES["Resources"]
            REQ[Requests:<br/>• nvidia.com/gpu: 1<br/>• cpu: 2 cores<br/>• memory: 12 Gi]:::resourceNode
            LIM[Limits:<br/>• nvidia.com/gpu: 1<br/>• cpu: 3 cores<br/>• memory: 14 Gi]:::resourceNode
        end
        
        subgraph VOLUMES["Volumes"]
            EMPTY[emptyDir: /models<br/>Ephemeral Storage<br/>~13 GB Model Files]:::volumeNode
        end
    end
    
    subgraph GPU_HW["Hardware"]
        GPU[NVIDIA Tesla T4<br/>16 GB VRAM<br/>Utilization: 75-90%<br/>Memory Used: 10-12 GB]:::resourceNode
    end
    
    %% Connections
    IMAGE --> APP_STACK
    ENV --> APP_STACK
    DOWNLOAD --> FASTAPI
    FASTAPI --> VLLM_ENG
    VLLM_ENG --> MODEL
    MODEL --> GPU
    
    SA -.->|IRSA| DOWNLOAD
    EMPTY -.->|Mount| MODEL
    REQ --> GPU
    LIM --> GPU
```

## 7.Complete Data Flow Timeline

```mermaid
gantt
    title vLLM Deployment Timeline (Cold Start)
    dateFormat X
    axisFormat %M:%S
    
    section Build Phase
    Upload to S3           :done, s1, 0, 30s
    CodeBuild Queue        :done, s2, after s1, 30s
    Docker Build           :done, s3, after s2, 600s
    Push to ECR            :done, s4, after s3, 180s
    
    section Cluster Setup
    Request GPU Quota      :done, c1, 0, 1800s
    eksctl Create Cluster  :done, c2, after c1, 1200s
    Install NVIDIA Plugin  :done, c3, after c2, 60s
    Configure IRSA         :done, c4, after c3, 120s
    
    section Deployment
    Apply Manifests        :active, d1, after c4, 10s
    Schedule Pod           :active, d2, after d1, 30s
    Pull Image from ECR    :active, d3, after d2, 180s
    Download Model from S3 :active, d4, after d3, 300s
    Initialize vLLM        :active, d5, after d4, 120s
    Server Ready           :milestone, after d5, 0
    
    section First Request
    User Request           :crit, r1, after d5, 5s
    Generate Response      :crit, r2, after r1, 4s
    Return to User         :milestone, after r2, 0
```

## 8. Benchmarked vLLM Metrics Overview

```mermaid
graph TB
    %% Styling
    classDef latencyNode fill:#3b82f6,stroke:#1e40af,stroke-width:2px,color:#fff
    classDef throughputNode fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
    classDef resourceNode fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff
    classDef qualityNode fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff
    
    BENCH[vLLM Benchmark<br/>g4dn.xlarge + Tesla T4]
    
    BENCH --> LATENCY[Latency Metrics]:::latencyNode
    BENCH --> THROUGHPUT[Throughput Metrics]:::throughputNode
    BENCH --> RESOURCES[Resource Utilization]:::resourceNode
    BENCH --> QUALITY[Quality Metrics]:::qualityNode
    
    LATENCY --> L1[Time to First Token<br/>TTFT: 100-200ms]:::latencyNode
    LATENCY --> L2[Per Token Latency<br/>40-60ms/token]:::latencyNode
    LATENCY --> L3[Total Request Time<br/>4-6 sec for 100 tokens]:::latencyNode
    LATENCY --> L4[P50 Latency: 200ms<br/>P95 Latency: 500ms<br/>P99 Latency: 2.3s]:::latencyNode
    
    THROUGHPUT --> T1[Tokens per Second<br/>15-25 tok/s]:::throughputNode
    THROUGHPUT --> T2[Requests per Second<br/>0.3-0.5 req/s]:::throughputNode
    THROUGHPUT --> T3[Concurrent Requests<br/>Max: 2-4]:::throughputNode
    THROUGHPUT --> T4[Batch Size<br/>8-16 concurrent]:::throughputNode
    
    RESOURCES --> R1[GPU Utilization<br/>70-90%]:::resourceNode
    RESOURCES --> R2[GPU Memory<br/>10-12 GB / 16 GB]:::resourceNode
    RESOURCES --> R3[CPU Usage<br/>1.5-2.5 cores / 4]:::resourceNode
    RESOURCES --> R4[RAM Usage<br/>8-10 GB / 16 GB]:::resourceNode
    
    QUALITY --> Q1[Context Window<br/>512 tokens]:::qualityNode
    QUALITY --> Q2[Model Size<br/>7B parameters, 4-bit]:::qualityNode
    QUALITY --> Q3[Cold Start<br/>6-9 minutes]:::qualityNode
    QUALITY --> Q4[Warm Inference<br/>~10 seconds]:::qualityNode
```
