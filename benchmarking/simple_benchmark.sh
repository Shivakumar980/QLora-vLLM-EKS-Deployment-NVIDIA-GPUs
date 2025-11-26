#!/bin/bash

echo "🚀 Running Simple vLLM Benchmark"
echo "================================"
echo ""

ENDPOINT="http://afd773128eaee4367b07d28a1d7fa194-1360421433.us-east-1.elb.amazonaws.com:8000"

# Test different token lengths
for tokens in 50 100 200; do
  echo "Testing with max_tokens=$tokens"
  
  for i in {1..5}; do
    start=$(date +%s.%N)
    
    response=$(curl -s -X POST "$ENDPOINT/generate" \
      -H "Content-Type: application/json" \
      -d "{
        \"prompt\": \"Explain artificial intelligence in detail\",
        \"max_tokens\": $tokens,
        \"temperature\": 0.7
      }")
    
    end=$(date +%s.%N)
    latency=$(echo "$end - $start" | bc)
    
    tokens_generated=$(echo $response | jq -r '.tokens_generated // 0')
    
    if [ "$tokens_generated" != "0" ]; then
      tps=$(echo "scale=2; $tokens_generated / $latency" | bc)
      echo "  Request $i: ${latency}s, $tokens_generated tokens, ${tps} tok/s"
    else
      echo "  Request $i: FAILED"
    fi
    
    sleep 1
  done
  
  echo ""
done

echo "✅ Benchmark complete! Check Grafana for visualization"
