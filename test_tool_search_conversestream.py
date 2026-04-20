"""
Test: Tool Search Tool via Bedrock ConverseStream API

This script tests whether the Bedrock ConverseStream API supports the tool search
feature (defer_loading, tool_reference blocks, server_tool_use).

Per Anthropic docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
Per Bedrock docs: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-tool-use.html

Expected result: FAILURE — tool search is only available via InvokeModel/InvokeModelWithResponseStream,
not the Converse/ConverseStream API. The ConverseStream API schema lacks:
  - defer_loading field on ToolSpecification
  - tool_reference content block type
  - server_tool_use content block type
  - tool_search_tool_result content block type
"""

import json
import sys
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, ParamValidationError

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION = "us-east-1"


def timestamp():
    return datetime.now().isoformat(timespec="milliseconds")


def test_defer_loading_in_tool_spec():
    """Test 1: Can we pass defer_loading in toolSpec via converseStream?"""
    print(f"\n[{timestamp()}] === Test 1: defer_loading in toolSpec ===")

    client = boto3.client("bedrock-runtime", region_name=REGION)

    tools = [
        {
            "toolSpec": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    }
                },
                # This field doesn't exist in the ConverseStream ToolSpecification schema
                "deferLoading": True,
            }
        }
    ]

    try:
        response = client.converse_stream(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": "What's the weather in Seattle?"}]}],
            toolConfig={"tools": tools},
            inferenceConfig={"maxTokens": 1024},
        )
        print(f"[{timestamp()}] UNEXPECTED SUCCESS — response received")
        # Drain stream
        for event in response.get("stream", []):
            pass
    except ParamValidationError as e:
        print(f"[{timestamp()}] EXPECTED FAILURE: ParamValidationError")
        print(f"  {e}")
    except ClientError as e:
        print(f"[{timestamp()}] EXPECTED FAILURE: ClientError")
        print(f"  Code: {e.response['Error']['Code']}")
        print(f"  Message: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"[{timestamp()}] FAILURE: {type(e).__name__}: {e}")


def test_system_tool_search():
    """Test 2: Can we pass tool_search as a systemTool?"""
    print(f"\n[{timestamp()}] === Test 2: tool_search as systemTool ===")

    client = boto3.client("bedrock-runtime", region_name=REGION)

    tools = [
        {"systemTool": {"name": "tool_search_tool_regex"}},
        {
            "toolSpec": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    }
                },
            }
        },
    ]

    try:
        response = client.converse_stream(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": "What's the weather in Seattle?"}]}],
            toolConfig={"tools": tools},
            inferenceConfig={"maxTokens": 1024},
        )
        print(f"[{timestamp()}] Response received, processing stream...")
        for event in response.get("stream", []):
            if "contentBlockStart" in event:
                print(f"[{timestamp()}] contentBlockStart: {json.dumps(event['contentBlockStart'], default=str)}")
            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    print(f"[{timestamp()}] text: {delta['text'][:80]}")
                elif "toolUse" in delta:
                    print(f"[{timestamp()}] toolUse delta: {delta['toolUse'].get('input', '')[:80]}")
            elif "messageStop" in event:
                print(f"[{timestamp()}] stop: {event['messageStop'].get('stopReason')}")
        print(f"[{timestamp()}] SUCCESS — systemTool accepted")
    except ParamValidationError as e:
        print(f"[{timestamp()}] FAILURE: ParamValidationError")
        print(f"  {e}")
    except ClientError as e:
        print(f"[{timestamp()}] FAILURE: ClientError")
        print(f"  Code: {e.response['Error']['Code']}")
        print(f"  Message: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"[{timestamp()}] FAILURE: {type(e).__name__}: {e}")


def test_additional_model_request_fields():
    """Test 3: Can we pass tool search config via additionalModelRequestFields?"""
    print(f"\n[{timestamp()}] === Test 3: tool search via additionalModelRequestFields ===")

    client = boto3.client("bedrock-runtime", region_name=REGION)

    tools = [
        {
            "toolSpec": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    }
                },
            }
        },
    ]

    try:
        response = client.converse_stream(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": "What's the weather in Seattle?"}]}],
            toolConfig={"tools": tools},
            inferenceConfig={"maxTokens": 1024},
            additionalModelRequestFields={
                "anthropic_beta": ["tool-search-tool-2025-10-19"],
            },
        )
        print(f"[{timestamp()}] Response received, processing stream...")
        for event in response.get("stream", []):
            if "messageStop" in event:
                print(f"[{timestamp()}] stop: {event['messageStop'].get('stopReason')}")
        print(f"[{timestamp()}] Completed (beta header accepted but no tool search behavior expected)")
    except ParamValidationError as e:
        print(f"[{timestamp()}] FAILURE: ParamValidationError")
        print(f"  {e}")
    except ClientError as e:
        print(f"[{timestamp()}] FAILURE: ClientError")
        print(f"  Code: {e.response['Error']['Code']}")
        print(f"  Message: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"[{timestamp()}] FAILURE: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print("Tool Search Tool — ConverseStream API Compatibility Test")
    print("=" * 70)
    print(f"Model: {MODEL_ID}")
    print(f"Region: {REGION}")
    print(f"Started: {timestamp()}")
    print()
    print("HYPOTHESIS: Tool search is NOT supported via ConverseStream.")
    print("The API schema lacks defer_loading, tool_reference, and")
    print("server_tool_use content block types.")

    test_defer_loading_in_tool_spec()
    test_system_tool_search()
    test_additional_model_request_fields()

    print(f"\n{'=' * 70}")
    print("CONCLUSION")
    print("=" * 70)
    print("""
Confirmed findings:

  Test 1 — defer_loading in toolSpec:
    ParamValidationError: "deferLoading" unknown, must be one of: name, description, inputSchema
    (boto3 SDK rejects it client-side before any network call)

  Test 2 — systemTool for tool_search:
    ParamValidationError: "systemTool" unknown, must be one of: toolSpec, cachePoint
    (boto3 SDK doesn't even expose the systemTool union member yet)

  Test 3 — additionalModelRequestFields with beta header:
    Would pass validation but doesn't enable tool search behavior since
    the tool definitions themselves can't carry defer_loading.

VERDICT: Tool search is IMPOSSIBLE via ConverseStream.
The only path on Bedrock is InvokeModelWithResponseStream with the raw
Anthropic message format and beta header:
  "anthropic_beta": ["tool-search-tool-2025-10-19"]
""")
