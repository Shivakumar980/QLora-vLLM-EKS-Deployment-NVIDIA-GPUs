import os
import subprocess
import asyncio
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from vllm import LLM, SamplingParams
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
import uvicorn
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

# Configuration from environment variables
MODEL_PATH = os.getenv("MODEL_PATH", "/models/llama-2-7b-merged-vllm")
MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", "2048"))
TENSOR_PARALLEL_SIZE = int(os.getenv("TENSOR_PARALLEL_SIZE", "1"))
S3_BUCKET = os.getenv("S3_BUCKET")

# Download model before starting FastAPI
if not os.path.exists(MODEL_PATH):
    if S3_BUCKET:
        print(f"📥 Model not found locally. Downloading from S3...")
        subprocess.run(["python3", "/app/download_model.py"], check=True)
        print("✅ Model downloaded successfully!")
    else:
        print("⚠️  Warning: MODEL_PATH doesn't exist and S3_BUCKET not set")

app = FastAPI(title="vLLM Inference API")

# Global LLM engine
llm_engine = None

# Prometheus metrics
REQUEST_COUNTER = Counter('vllm_request_success_total', 'Total successful requests')
REQUEST_FAILURE = Counter('vllm_request_failure_total', 'Total failed requests')
LATENCY_HISTOGRAM = Histogram('vllm_request_latency_seconds', 'Request latency in seconds')
TTFT_HISTOGRAM = Histogram('vllm_time_to_first_token_seconds', 'Time to first token in seconds')
TOKENS_GENERATED = Counter('vllm_generation_tokens_total', 'Total tokens generated')
PROMPT_TOKENS = Counter('vllm_prompt_tokens_total', 'Total prompt tokens')
GPU_CACHE_USAGE = Gauge('vllm_gpu_cache_usage_perc', 'GPU cache usage percentage')

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = False

class GenerateResponse(BaseModel):
    generated_text: str
    tokens_generated: int

@app.on_event("startup")
async def startup_event():
    """Initialize vLLM engine on startup"""
    global llm_engine
    
    print(f"🚀 Loading model from {MODEL_PATH}...")
    
    # Initialize vLLM engine
    llm_engine = LLM(
        model=MODEL_PATH,
        max_model_len=MAX_MODEL_LEN,
        tensor_parallel_size=TENSOR_PARALLEL_SIZE,
        gpu_memory_utilization=0.9,
        trust_remote_code=True
    )
    
    print("✅ Model loaded successfully!")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if llm_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "model": MODEL_PATH}

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate text from prompt"""
    if llm_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    start_time = time.time()
    
    try:
        # Set sampling parameters
        sampling_params = SamplingParams(
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens
        )
        
        # Time to first token (approximate)
        ttft_start = time.time()
        
        # Generate
        outputs = llm_engine.generate([request.prompt], sampling_params)
        
        ttft = time.time() - ttft_start
        
        generated_text = outputs[0].outputs[0].text
        tokens_generated = len(outputs[0].outputs[0].token_ids)
        
        # Update metrics
        REQUEST_COUNTER.inc()
        LATENCY_HISTOGRAM.observe(time.time() - start_time)
        TTFT_HISTOGRAM.observe(ttft)
        TOKENS_GENERATED.inc(tokens_generated)
        PROMPT_TOKENS.inc(len(request.prompt.split()))  # Approximate
        
        return GenerateResponse(
            generated_text=generated_text,
            tokens_generated=tokens_generated
        )
    
    except Exception as e:
        REQUEST_FAILURE.inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)