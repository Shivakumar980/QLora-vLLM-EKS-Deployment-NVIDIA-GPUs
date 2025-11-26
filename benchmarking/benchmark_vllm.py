import time
import json
import requests
from locust import HttpUser, task, between, events
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import random

# Prometheus metrics for benchmark
benchmark_requests = Counter('benchmark_requests_total', 'Total benchmark requests')
benchmark_success = Counter('benchmark_success_total', 'Successful benchmark requests')
benchmark_failure = Counter('benchmark_failure_total', 'Failed benchmark requests')
benchmark_latency = Histogram('benchmark_latency_seconds', 'Benchmark request latency')
benchmark_ttft = Histogram('benchmark_ttft_seconds', 'Benchmark time to first token')
benchmark_tps = Gauge('benchmark_tokens_per_second', 'Tokens generated per second')

class VLLMBenchmark(HttpUser):
    wait_time = between(0.5, 2)
    host = "http://afd773128eaee4367b07d28a1d7fa194-1360421433.us-east-1.elb.amazonaws.com:8000"
    
    # Diverse prompts for realistic testing
    prompts = [
        "Explain quantum computing in simple terms",
        "Write a short story about a robot learning to paint",
        "What are the key differences between supervised and unsupervised learning?",
        "Describe the process of photosynthesis",
        "How does blockchain technology work?",
        "What is the theory of relativity?",
        "Explain neural networks to a beginner",
        "What are the main causes of climate change?",
        "Describe the water cycle",
        "How do vaccines work?"
    ]
    
    @task(weight=10)
    def short_generation(self):
        """Test short text generation (50 tokens)"""
        self._generate_text(max_tokens=50, name="short_gen")
    
    @task(weight=5)
    def medium_generation(self):
        """Test medium text generation (150 tokens)"""
        self._generate_text(max_tokens=150, name="medium_gen")
    
    @task(weight=2)
    def long_generation(self):
        """Test long text generation (300 tokens)"""
        self._generate_text(max_tokens=300, name="long_gen")
    
    def _generate_text(self, max_tokens, name):
        prompt = random.choice(self.prompts)
        
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        start_time = time.time()
        benchmark_requests.inc()
        
        try:
            with self.client.post(
                "/generate",
                json=payload,
                catch_response=True,
                name=name,
                timeout=60
            ) as response:
                end_time = time.time()
                latency = end_time - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    tokens = result.get("tokens_generated", 0)
                    
                    benchmark_success.inc()
                    benchmark_latency.observe(latency)
                    
                    if tokens > 0 and latency > 0:
                        tps = tokens / latency
                        benchmark_tps.set(tps)
                        # Approximate TTFT (not exact but gives indication)
                        ttft = latency / tokens if tokens > 0 else latency
                        benchmark_ttft.observe(ttft)
                    
                    response.success()
                    print(f"✅ {name}: {tokens} tokens in {latency:.2f}s ({tokens/latency:.1f} tok/s)")
                else:
                    benchmark_failure.inc()
                    response.failure(f"Status {response.status_code}")
                    print(f"❌ {name}: Failed with status {response.status_code}")
                    
        except Exception as e:
            benchmark_failure.inc()
            print(f"❌ {name}: Exception - {e}")

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Start Prometheus metrics server for benchmark metrics"""
    start_http_server(8089)
    print("�� Benchmark metrics available at http://localhost:8089")

if __name__ == "__main__":
    print("Run with: locust -f benchmark_vllm.py")
