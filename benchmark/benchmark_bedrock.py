"""Bedrock API benchmark script."""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.benchmark_runner import BenchmarkRunner, TaskExecutor
from benchmark.mock_tools import MockToolExecutor
from benchmark.query_cloudtrail import CloudTrailQuerier


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
        
        # Extract request ID from response metadata
        request_id = response.get('ResponseMetadata', {}).get('RequestId')
        if request_id:
            self.request_ids.append(request_id)
        
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


def run_benchmark(num_runs: int = 5, query_cloudtrail: bool = True):
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
    
    # Track benchmark start time for CloudTrail query
    benchmark_start_time = datetime.now(timezone.utc)
    
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
    
    # Query CloudTrail to update cross-region information after all runs
    if query_cloudtrail:
        print("\n=== Querying CloudTrail for cross-region information ===")
        print("Waiting 30 seconds for CloudTrail event delivery...")
        import time
        time.sleep(30)
        _update_cross_region_info(runner.output_file, benchmark_start_time)


def _update_cross_region_info(csv_file: Path, start_time: datetime):
    """Update CSV with cross-region information from CloudTrail.
    
    Args:
        csv_file: Path to CSV file to update
        start_time: Benchmark start time for CloudTrail query
    """
    # Load request IDs from separate file
    request_ids_file = csv_file.with_suffix('.request_ids.json')
    if not request_ids_file.exists():
        print("No request IDs file found")
        return
    
    with open(request_ids_file, 'r') as f:
        request_ids_data = json.load(f)
    
    # Collect all unique request IDs
    all_request_ids = set()
    for entry in request_ids_data:
        all_request_ids.update(entry['request_ids'])
    
    if not all_request_ids:
        print("No request IDs found")
        return
    
    print(f"Found {len(all_request_ids)} unique request IDs")
    
    # Query CloudTrail
    querier = CloudTrailQuerier(region='us-east-1')
    cross_region_map = querier.query_request_ids(
        request_ids=list(all_request_ids),
        start_time=start_time,
        max_retries=3,
        retry_delay=60
    )
    
    # Read CSV and update cross-region information by matching with request_ids_data
    rows = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Match this CSV row with corresponding request IDs entry
            if i < len(request_ids_data):
                request_ids = request_ids_data[i]['request_ids']
                cross_region_count = sum(
                    1 for rid in request_ids 
                    if cross_region_map.get(rid, False)
                )
                row['cross_region_requests'] = str(cross_region_count)
            
            rows.append(row)
    
    # Write updated CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✓ Updated {csv_file} with cross-region information")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Bedrock API benchmark')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs per task')
    parser.add_argument('--no-cloudtrail', action='store_true', 
                       help='Skip CloudTrail query for cross-region detection')
    args = parser.parse_args()
    
    run_benchmark(args.runs, query_cloudtrail=not args.no_cloudtrail)
