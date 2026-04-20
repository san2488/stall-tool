#!/usr/bin/env python3
import argparse
import json
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def create_large_context():
    """Create a large context to exceed 1024 token threshold for caching."""
    context = """
You are an expert software engineer with deep knowledge of distributed systems, cloud architecture, and modern development practices. 

Here's a comprehensive overview of microservices architecture patterns:

1. Service Discovery: Services need to find and communicate with each other. Common patterns include:
   - Client-side discovery (Eureka, Consul)
   - Server-side discovery (AWS ELB, Kubernetes Services)
   - Service mesh (Istio, Linkerd)

2. Configuration Management: Centralized configuration for distributed services:
   - Spring Cloud Config
   - AWS Parameter Store
   - Kubernetes ConfigMaps and Secrets
   - HashiCorp Vault for sensitive data

3. Circuit Breaker Pattern: Prevents cascading failures:
   - Netflix Hystrix (deprecated but influential)
   - Resilience4j
   - AWS App Mesh circuit breakers

4. API Gateway Patterns: Single entry point for client requests:
   - Request routing and composition
   - Authentication and authorization
   - Rate limiting and throttling
   - Request/response transformation

5. Data Management Patterns:
   - Database per service
   - Shared databases (anti-pattern but sometimes necessary)
   - Event sourcing
   - CQRS (Command Query Responsibility Segregation)

6. Communication Patterns:
   - Synchronous: REST, GraphQL, gRPC
   - Asynchronous: Message queues, event streaming
   - Hybrid approaches

7. Deployment Patterns:
   - Blue-green deployments
   - Canary releases
   - Rolling updates
   - Feature flags

8. Monitoring and Observability:
   - Distributed tracing (Jaeger, Zipkin)
   - Centralized logging (ELK stack, Fluentd)
   - Metrics collection (Prometheus, CloudWatch)
   - Health checks and service monitoring

9. Security Patterns:
   - OAuth 2.0 and OpenID Connect
   - JWT tokens
   - mTLS for service-to-service communication
   - Zero-trust networking

10. Testing Strategies:
    - Contract testing (Pact)
    - Integration testing
    - End-to-end testing
    - Chaos engineering

This context provides the foundation for discussing complex architectural decisions and trade-offs in modern distributed systems.
"""
    return context


def create_system_prompt():
    """Create a comprehensive system prompt to help reach 1024+ tokens."""
    return """You are Claude, an AI assistant created by Anthropic. You are a helpful, harmless, and honest AI assistant. You are knowledgeable about a wide range of topics including science, technology, history, literature, arts, current events, and many other subjects. You can help with analysis, writing, math, coding, creative tasks, and answering questions.

Key principles for your responses:
- Be helpful and try to answer questions accurately and thoroughly
- Be honest about what you do and don't know - if you're uncertain about something, say so
- Be harmless - don't provide information that could be used to harm people
- Be respectful and considerate in all interactions
- Provide clear, well-structured responses that directly address what the user is asking
- When appropriate, ask clarifying questions to better understand what the user needs
- For technical topics, explain concepts clearly and provide examples when helpful
- For creative tasks, be imaginative while staying grounded in the user's requirements
- Always strive to be accurate and cite sources when making factual claims
- Respect intellectual property and don't reproduce copyrighted content verbatim
- Be concise when brevity is preferred, but thorough when detail is needed
- Adapt your communication style to match the context and user's apparent expertise level

You have broad knowledge but are not connected to the internet and your knowledge has a cutoff date. You cannot browse the web, access real-time information, or learn from conversations. Each conversation starts fresh without memory of previous interactions.

When helping with code, provide working examples and explain the logic. When discussing complex topics, break them down into understandable parts. When asked for opinions, you can share perspectives while noting they are subjective. Always prioritize being genuinely helpful while maintaining appropriate boundaries.

Additional guidelines for technical discussions:
- When discussing software architecture, consider scalability, maintainability, and performance implications
- For programming questions, provide code examples in the requested language with clear explanations
- When explaining algorithms, include time and space complexity analysis where relevant
- For system design questions, consider trade-offs between different approaches
- When discussing databases, consider ACID properties, consistency models, and performance characteristics
- For security topics, emphasize best practices and common vulnerabilities to avoid
- When explaining networking concepts, include protocol details and real-world applications
- For cloud computing discussions, consider cost implications and service limitations
- When discussing data structures, explain when to use each type and their performance characteristics
- For machine learning topics, explain both theoretical concepts and practical implementation considerations

Communication style guidelines:
- Use clear, professional language appropriate for the technical level of the question
- Provide step-by-step explanations for complex procedures
- Include relevant examples and analogies to clarify difficult concepts
- Structure responses with clear headings and bullet points when appropriate
- Acknowledge limitations and suggest alternative approaches when applicable
- Encourage best practices and industry standards in all recommendations
- Be patient and thorough in explanations, assuming the user wants to understand the underlying concepts
- Provide additional resources or suggest further reading when helpful
- Always double-check technical accuracy and provide corrections if needed
- Maintain a helpful and encouraging tone throughout all interactions"""


def invoke_multi_turn_conversation(model_id, region):
    """
    Test caching with a multi-turn conversation that exceeds 1024 tokens.
    """
    # Initialize Bedrock Runtime client
    config = Config(read_timeout=300)
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=region, config=config)
    
    # Create large context and system prompt
    large_context = create_large_context()
    system_prompt = create_system_prompt()
    
    # Initialize conversation with system prompt and user message with cache point
    system_prompt_with_cache = [
        {"text": system_prompt},
        {"cachePoint": {"type": "default"}}
    ]
    
    messages = [
        {
            "role": "user", 
            "content": [
                {"text": f"{large_context}\n\nBased on this context, what are the key considerations for implementing a microservices architecture?"},
                {"cachePoint": {"type": "default"}}
            ]
        }
    ]
    
    print("=== TURN 1: Initial request with large context ===")
    
    try:
        # First API call - should create cache
        response1 = bedrock_runtime.converse(
            modelId=model_id,
            system=system_prompt_with_cache,
            messages=messages,
            inferenceConfig={"maxTokens": 500}
        )
        
        # Extract text from response
        content = response1['output']['message']['content'][0]
        if 'text' in content:
            response_text = content['text']
        else:
            response_text = str(content)
            
        print(f"Response: {response_text[:200]}...")
        print(f"Stop reason: {response1['stopReason']}")
        
        # Print usage information
        usage = response1.get('usage', {})
        print(f"Input tokens: {usage.get('inputTokens', 0)}")
        print(f"Output tokens: {usage.get('outputTokens', 0)}")
        print(f"Total tokens: {usage.get('totalTokens', 0)}")
        
        # Check for cache information
        if 'cacheCreationInputTokens' in usage:
            print(f"Cache creation input tokens: {usage['cacheCreationInputTokens']}")
        if 'cacheReadInputTokens' in usage:
            print(f"Cache read input tokens: {usage['cacheReadInputTokens']}")
            
        print("\n" + "="*60 + "\n")
        
        # Add assistant response to conversation
        messages.append(response1['output']['message'])
        
        # Add second user message
        messages.append({
            "role": "user",
            "content": [{"text": "Can you elaborate on the circuit breaker pattern and provide a code example?"}]
        })
        
        print("=== TURN 2: Follow-up question (should use cache) ===")
        
        # Second API call - should use cache
        response2 = bedrock_runtime.converse(
            modelId=model_id,
            system=system_prompt_with_cache,
            messages=messages,
            inferenceConfig={"maxTokens": 500}
        )
        
        # Extract text from response
        content2 = response2['output']['message']['content'][0]
        if 'text' in content2:
            response_text2 = content2['text']
        else:
            response_text2 = str(content2)
            
        print(f"Response: {response_text2[:200]}...")
        print(f"Stop reason: {response2['stopReason']}")
        
        # Print usage information
        usage2 = response2.get('usage', {})
        print(f"Input tokens: {usage2.get('inputTokens', 0)}")
        print(f"Output tokens: {usage2.get('outputTokens', 0)}")
        print(f"Total tokens: {usage2.get('totalTokens', 0)}")
        
        # Check for cache information
        if 'cacheCreationInputTokens' in usage2:
            print(f"Cache creation input tokens: {usage2['cacheCreationInputTokens']}")
        if 'cacheReadInputTokens' in usage2:
            print(f"Cache read input tokens: {usage2['cacheReadInputTokens']}")
            
        print("\n" + "="*60 + "\n")
        
        # Add assistant response and third user message
        messages.append(response2['output']['message'])
        messages.append({
            "role": "user",
            "content": [{"text": "What about API gateway patterns? How do they fit into the overall architecture?"}]
        })
        
        print("=== TURN 3: Another follow-up (should also use cache) ===")
        
        # Third API call - should also use cache
        response3 = bedrock_runtime.converse(
            modelId=model_id,
            system=system_prompt_with_cache,
            messages=messages,
            inferenceConfig={"maxTokens": 500}
        )
        
        # Extract text from response
        content3 = response3['output']['message']['content'][0]
        if 'text' in content3:
            response_text3 = content3['text']
        else:
            response_text3 = str(content3)
            
        print(f"Response: {response_text3[:200]}...")
        print(f"Stop reason: {response3['stopReason']}")
        
        # Print usage information
        usage3 = response3.get('usage', {})
        print(f"Input tokens: {usage3.get('inputTokens', 0)}")
        print(f"Output tokens: {usage3.get('outputTokens', 0)}")
        print(f"Total tokens: {usage3.get('totalTokens', 0)}")
        
        # Check for cache information
        if 'cacheCreationInputTokens' in usage3:
            print(f"Cache creation input tokens: {usage3['cacheCreationInputTokens']}")
        if 'cacheReadInputTokens' in usage3:
            print(f"Cache read input tokens: {usage3['cacheReadInputTokens']}")
            
        print("\n=== CACHE ANALYSIS ===")
        print("Turn 1: Should show cache creation")
        print("Turn 2: Should show cache read")
        print("Turn 3: Should show cache read")
        
    except ClientError as e:
        print(f"Error invoking Bedrock: {e}")
        return None


def main():
    """
    Main function to test caching behavior.
    """
    parser = argparse.ArgumentParser(description="Test Bedrock prompt caching")
    parser.add_argument("--model", "-m", default="anthropic.claude-sonnet-4-20250514-v1:0", help="Model ID to use")
    parser.add_argument("--region", "-r", default="us-east-1", help="AWS region to use")
    args = parser.parse_args()
    
    print(f"Testing caching with model: {args.model} in region: {args.region}")
    invoke_multi_turn_conversation(args.model, args.region)


if __name__ == "__main__":
    main()
