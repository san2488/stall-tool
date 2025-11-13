"""Bedrock API benchmark script."""
import json
import sys
from pathlib import Path

import boto3

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.benchmark_runner import BenchmarkRunner, TaskExecutor
from benchmark.mock_tools import MockToolExecutor


class BedrockTaskExecutor(TaskExecutor):
    """Bedrock-specific task executor."""
    
    MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    
    def __init__(self, api_client, mock_tool_executor, benchmark_runner):
        super().__init__(api_client, mock_tool_executor, benchmark_runner, self.MODEL_ID)
        self.current_assistant_content = []
    
    def _execute_api_call(self, task_def: dict):
        """Execute Bedrock API call with streaming."""
        # Reset assistant content for this turn
        self.current_assistant_content = []
        
        # Convert messages to Bedrock format
        bedrock_messages = []
        for msg in self.messages:
            if isinstance(msg['content'], str):
                bedrock_messages.append({
                    "role": msg['role'],
                    "content": [{"text": msg['content']}]
                })
            elif isinstance(msg['content'], list):
                # Already in correct format or contains tool results
                bedrock_messages.append(msg)
        
        # Define tools
        tools = [{
            "toolSpec": {
                "name": "fs_write",
                "description": "Write content to a file",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "file_text": {"type": "string"}
                        },
                        "required": ["path", "file_text"]
                    }
                }
            }
        }, {
            "toolSpec": {
                "name": "fs_read",
                "description": "Read content from a file",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        },
                        "required": ["path"]
                    }
                }
            }
        }]
        
        # Make streaming request
        response = self.api_client.converse_stream(
            modelId=self.MODEL_ID,
            messages=bedrock_messages,
            toolConfig={"tools": tools},
            inferenceConfig={"maxTokens": 4096}
        )
        
        # Process stream
        stream = response.get('stream')
        if stream:
            for event in stream:
                self._process_event(event)
        
        self._mark_stream_end()
        
        # Add assistant message to conversation
        self.messages.append({
            "role": "assistant",
            "content": self.current_assistant_content
        })
    
    def _process_event(self, event: dict):
        """Process a single stream event."""
        if 'messageStart' in event:
            pass
        
        elif 'contentBlockStart' in event:
            # Check if this is a tool use block
            block = event['contentBlockStart']['start']
            if 'toolUse' in block:
                tool_name = block['toolUse'].get('name', 'unknown')
                tool_id = block['toolUse'].get('toolUseId', 'unknown')
                print(f"[TOOL CALL #{self.tool_calls_count + 1}] {tool_name} (ID: {tool_id})")
                self.tool_calls_count += 1
                self._mark_first_token()
                
                # Track tool use for conversation
                self.current_tool_use = {
                    "toolUse": {
                        "toolUseId": tool_id,
                        "name": tool_name,
                        "input": {}
                    }
                }
            elif 'text' in block:
                # Text content block
                self.current_text_block = {"text": ""}
        
        elif 'contentBlockDelta' in event:
            delta = event['contentBlockDelta']['delta']
            
            if 'text' in delta:
                self._mark_first_token()
                # Accumulate text
                if hasattr(self, 'current_text_block'):
                    self.current_text_block["text"] += delta['text']
            
            elif 'toolUse' in delta:
                self._mark_first_token()
                # Accumulate tool input
                if hasattr(self, 'current_tool_use'):
                    input_json = delta['toolUse'].get('input', '')
                    if input_json:
                        # Parse and merge JSON input
                        try:
                            import json
                            parsed = json.loads(input_json)
                            self.current_tool_use['toolUse']['input'].update(parsed)
                        except:
                            pass
        
        elif 'contentBlockStop' in event:
            # Finalize current content block
            if hasattr(self, 'current_tool_use'):
                self.current_assistant_content.append(self.current_tool_use)
                # Add to pending tool uses
                self.pending_tool_uses.append({
                    "id": self.current_tool_use['toolUse']['toolUseId'],
                    "name": self.current_tool_use['toolUse']['name'],
                    "input": self.current_tool_use['toolUse']['input']
                })
                delattr(self, 'current_tool_use')
            elif hasattr(self, 'current_text_block'):
                self.current_assistant_content.append(self.current_text_block)
                delattr(self, 'current_text_block')
        
        elif 'messageStop' in event:
            self.stop_reason = event['messageStop'].get('stopReason', 'unknown')
            print(f"[MESSAGE STOPPED] Reason: {self.stop_reason}")
        
        elif 'metadata' in event:
            pass
    
    def _add_tool_results_to_conversation(self, tool_results):
        """Add tool results to conversation in Bedrock format."""
        # Bedrock expects tool results in user message with specific format
        content = []
        for result in tool_results:
            content.append({
                "toolResult": {
                    "toolUseId": result['tool_use_id'],
                    "content": [{"text": result['content']}]
                }
            })
        
        self.messages.append({
            "role": "user",
            "content": content
        })


def run_benchmark(num_runs: int = 5):
    """Run Bedrock benchmark."""
    print("Starting Bedrock API benchmark...")
    
    # Initialize components
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    mock_tools = MockToolExecutor()
    runner = BenchmarkRunner('bedrock', 'benchmark/results/bedrock_raw.csv')
    executor = BedrockTaskExecutor(bedrock, mock_tools, runner)
    
    # Load tasks
    tasks_file = Path('benchmark/tasks/task_definitions.json')
    with open(tasks_file) as f:
        tasks = json.load(f)
    
    # Run each task multiple times
    for run_num in range(1, num_runs + 1):
        print(f"\n=== Run {run_num}/{num_runs} ===")
        
        for task in tasks:
            task_id = task['task_id']
            print(f"Executing {task_id}...", end=' ')
            
            result = executor.execute_task(task)
            
            if result['status'] == 'success':
                print(f"✓ ({result['total_task_ms']:.0f}ms)")
            else:
                print(f"✗ {result.get('message', 'Unknown error')}")
    
    print(f"\n✓ Benchmark complete. Results saved to {runner.output_file}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Bedrock API benchmark')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs per task')
    args = parser.parse_args()
    
    run_benchmark(args.runs)
