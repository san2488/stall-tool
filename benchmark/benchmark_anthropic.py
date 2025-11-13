"""Anthropic API benchmark script."""
import json
import os
import sys
from pathlib import Path

import requests
from sseclient import SSEClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.benchmark_runner import BenchmarkRunner, TaskExecutor
from benchmark.mock_tools import MockToolExecutor


class AnthropicTaskExecutor(TaskExecutor):
    """Anthropic-specific task executor."""
    
    def __init__(self, api_key, mock_tool_executor, benchmark_runner):
        # Create a simple client wrapper
        self.api_key = api_key
        super().__init__(None, mock_tool_executor, benchmark_runner)
        self.current_assistant_content = []
    
    def _execute_api_call(self, task_def: dict):
        """Execute Anthropic API call with streaming."""
        # Reset assistant content for this turn
        self.current_assistant_content = []
        
        url = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "accept": "text/event-stream"
        }
        
        # Define tools
        tools = [{
            "name": "fs_write",
            "description": "Write content to a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "file_text": {"type": "string"}
                },
                "required": ["path", "file_text"]
            }
        }, {
            "name": "fs_read",
            "description": "Read content from a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }]
        
        payload = {
            "model": "claude-3-7-sonnet-20250219",
            "messages": self.messages,
            "tools": tools,
            "max_tokens": 4096,
            "stream": True
        }
        
        # Make streaming request
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        # Process SSE stream
        client = SSEClient(response)
        for event in client.events():
            if event.data:
                self._process_event(event.data)
        
        self._mark_stream_end()
        
        # Add assistant message to conversation
        self.messages.append({
            "role": "assistant",
            "content": self.current_assistant_content
        })
    
    def _process_event(self, data: str):
        """Process a single SSE event."""
        if data == '[DONE]':
            return
        
        try:
            event_data = json.loads(data)
            event_type = event_data.get('type')
            
            if event_type == 'message_start':
                pass
            
            elif event_type == 'content_block_start':
                # Check if this is a tool use block
                block = event_data.get('content_block', {})
                if block.get('type') == 'tool_use':
                    self.tool_calls_count += 1
                    self._mark_first_token()
                    
                    # Track tool use for conversation
                    self.current_tool_use = {
                        "type": "tool_use",
                        "id": block.get('id'),
                        "name": block.get('name'),
                        "input": {}
                    }
                elif block.get('type') == 'text':
                    # Text content block
                    self.current_text_block = {"type": "text", "text": ""}
            
            elif event_type == 'content_block_delta':
                delta = event_data.get('delta', {})
                
                if delta.get('type') == 'text_delta':
                    self._mark_first_token()
                    # Accumulate text
                    if hasattr(self, 'current_text_block'):
                        self.current_text_block["text"] += delta.get('text', '')
                
                elif delta.get('type') == 'input_json_delta':
                    self._mark_first_token()
                    # Accumulate tool input
                    if hasattr(self, 'current_tool_use'):
                        partial_json = delta.get('partial_json', '')
                        if partial_json:
                            # Accumulate JSON string (will parse at end)
                            if 'input_json' not in self.current_tool_use:
                                self.current_tool_use['input_json'] = ''
                            self.current_tool_use['input_json'] += partial_json
            
            elif event_type == 'content_block_stop':
                # Finalize current content block
                if hasattr(self, 'current_tool_use'):
                    # Parse accumulated JSON
                    if 'input_json' in self.current_tool_use:
                        try:
                            self.current_tool_use['input'] = json.loads(self.current_tool_use['input_json'])
                            del self.current_tool_use['input_json']
                        except:
                            pass
                    
                    self.current_assistant_content.append(self.current_tool_use)
                    # Add to pending tool uses
                    self.pending_tool_uses.append({
                        "id": self.current_tool_use['id'],
                        "name": self.current_tool_use['name'],
                        "input": self.current_tool_use['input']
                    })
                    delattr(self, 'current_tool_use')
                elif hasattr(self, 'current_text_block'):
                    self.current_assistant_content.append(self.current_text_block)
                    delattr(self, 'current_text_block')
            
            elif event_type == 'message_delta':
                delta = event_data.get('delta', {})
                if 'stop_reason' in delta:
                    self.stop_reason = delta['stop_reason']
            
            elif event_type == 'message_stop':
                pass
        
        except json.JSONDecodeError:
            pass
    
    def _add_tool_results_to_conversation(self, tool_results):
        """Add tool results to conversation in Anthropic format."""
        # Anthropic expects tool results in user message
        content = []
        for result in tool_results:
            content.append({
                "type": "tool_result",
                "tool_use_id": result['tool_use_id'],
                "content": result['content']
            })
        
        self.messages.append({
            "role": "user",
            "content": content
        })


def run_benchmark(num_runs: int = 5):
    """Run Anthropic benchmark."""
    print("Starting Anthropic API benchmark...")
    
    # Get API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize components
    mock_tools = MockToolExecutor()
    runner = BenchmarkRunner('anthropic', 'benchmark/results/anthropic_raw.csv')
    executor = AnthropicTaskExecutor(api_key, mock_tools, runner)
    
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
    parser = argparse.ArgumentParser(description='Run Anthropic API benchmark')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs per task')
    args = parser.parse_args()
    
    run_benchmark(args.runs)
