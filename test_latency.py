#!/usr/bin/env python3
"""Simple latency test for Bedrock vs Anthropic APIs."""
import time
import boto3
import requests
import os
import sys

def test_bedrock_latency():
    """Test Bedrock API first token latency."""
    print("Testing Bedrock API...")
    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    start = time.time()
    first_token = None
    
    response = client.converse_stream(
        modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        messages=[{"role": "user", "content": [{"text": "Say hello"}]}],
        inferenceConfig={"maxTokens": 100}
    )
    
    for event in response.get('stream'):
        if first_token is None:
            if 'contentBlockDelta' in event:
                first_token = time.time()
                break
    
    if first_token:
        latency = (first_token - start) * 1000
        print(f"  First token: {latency:.2f}ms")
        return latency
    return None

def test_anthropic_latency():
    """Test Anthropic API first token latency."""
    print("Testing Anthropic API...")
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  ANTHROPIC_API_KEY not set, skipping")
        return None
    
    start = time.time()
    first_token = None
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": api_key,
            "accept": "text/event-stream"
        },
        json={
            "model": "claude-sonnet-4-5-20250929",
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 100,
            "stream": True
        },
        stream=True
    )
    
    for line in response.iter_lines():
        if first_token is None and line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: ') and 'content_block_delta' in line_str:
                first_token = time.time()
                break
    
    if first_token:
        latency = (first_token - start) * 1000
        print(f"  First token: {latency:.2f}ms")
        return latency
    return None

if __name__ == '__main__':
    print("Running simple latency tests (15 runs each)...\n")
    
    bedrock_latencies = []
    anthropic_latencies = []
    
    for i in range(15):
        print(f"Run {i+1}/15:")
        
        bl = test_bedrock_latency()
        if bl:
            bedrock_latencies.append(bl)
        
        al = test_anthropic_latency()
        if al:
            anthropic_latencies.append(al)
        
        print()
    
    print("=" * 60)
    print("RESULTS:")
    print("=" * 60)
    
    if bedrock_latencies:
        avg_bedrock = sum(bedrock_latencies) / len(bedrock_latencies)
        print(f"Bedrock avg:   {avg_bedrock:.2f}ms")
    
    if anthropic_latencies:
        avg_anthropic = sum(anthropic_latencies) / len(anthropic_latencies)
        print(f"Anthropic avg: {avg_anthropic:.2f}ms")
    
    if bedrock_latencies and anthropic_latencies:
        diff = avg_bedrock - avg_anthropic
        pct = (diff / avg_anthropic) * 100
        print(f"Difference:    {diff:+.2f}ms ({pct:+.1f}%)")
        print(f"\nBenchmark showed: Bedrock ~2000ms, Anthropic ~1700ms")
