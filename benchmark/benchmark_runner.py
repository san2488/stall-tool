"""Core benchmark runner for measuring API latency."""
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class BenchmarkRunner:
    """Measures and records API latency metrics."""
    
    def __init__(self, api_type: str, output_file: str):
        self.api_type = api_type
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Request ID storage for CloudTrail queries
        self.request_ids_file = self.output_file.with_suffix('.request_ids.json')
        
        # Load existing request IDs data if file exists
        if self.request_ids_file.exists():
            with open(self.request_ids_file, 'r') as f:
                self.request_ids_data = json.load(f)
        else:
            self.request_ids_data = []
        
        # Initialize CSV if it doesn't exist
        if not self.output_file.exists():
            self._init_csv()
    
    def _init_csv(self):
        """Initialize CSV with headers."""
        with open(self.output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'api_type',
                'model_id',
                'task_id',
                'task_type',
                'first_token_ms',
                'stream_complete_ms',
                'total_task_ms',
                'max_turn_ms',
                'tool_calls_count',
                'turns_count',
                'total_bedrock_requests',
                'cross_region_requests',
                'status'
            ])
    
    def store_request_ids(self, task_id: str, request_ids: List[str]):
        """Store request IDs for a task separately from CSV."""
        self.request_ids_data.append({
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'request_ids': request_ids
        })
        
        # Save to JSON file
        with open(self.request_ids_file, 'w') as f:
            json.dump(self.request_ids_data, f, indent=2)
    
    def get_all_request_ids(self) -> List[str]:
        """Get all request IDs from stored data."""
        all_ids = []
        for entry in self.request_ids_data:
            all_ids.extend(entry['request_ids'])
        return all_ids
    
    def record_result(self, task_id: str, task_type: str, 
                     first_token_ms: float, stream_complete_ms: float,
                     total_task_ms: float, max_turn_ms: float,
                     tool_calls_count: int,                     turns_count: int = 1,
                     model_id: str = "unknown",
                     total_bedrock_requests: int = 0,
                     cross_region_requests: int = 0,
                     status: str = "success"):
        """Record a benchmark result to CSV."""
        with open(self.output_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.api_type,
                model_id,
                task_id,
                task_type,
                f"{first_token_ms:.2f}",
                f"{stream_complete_ms:.2f}",
                f"{total_task_ms:.2f}",
                f"{max_turn_ms:.2f}",
                tool_calls_count,
                turns_count,
                total_bedrock_requests,
                cross_region_requests,
                status
            ])


class TaskExecutor:
    """Executes benchmark tasks and measures timing."""
    
    def __init__(self, api_client, mock_tool_executor, benchmark_runner, model_id: str = "unknown"):
        self.api_client = api_client
        self.mock_tools = mock_tool_executor
        self.runner = benchmark_runner
        self.model_id = model_id
        
        # Timing state
        self.start_time = None
        self.first_token_time = None
        self.stream_end_time = None
        self.tool_calls_count = 0
        self.turns_count = 0
        
        # Conversation state
        self.messages = []
        self.pending_tool_uses = []
        self.stop_reason = None
        
        # Request tracking
        self.request_ids = []
    
    def execute_task(self, task_def: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task and record metrics."""
        self.mock_tools.reset()
        self._reset_timing()
        
        task_id = task_def['task_id']
        task_type = task_def['task_type']
        prompt = task_def['prompt']
        
        try:
            # Start timing
            self.start_time = time.time()
            
            # Initialize conversation with user message
            self.messages = [{"role": "user", "content": prompt}]
            
            # Conversation loop - continue until end_turn or max_tokens
            max_turns = 10  # Safety limit
            while self.turns_count < max_turns:
                self.turns_count += 1
                self.pending_tool_uses = []
                self.stop_reason = None
                self.turn_start_time = time.time()  # Mark turn start
                
                # Execute API call (implemented by subclass)
                self._execute_api_call(task_def)
                
                # Calculate turn duration
                turn_duration = (time.time() - self.turn_start_time) * 1000
                self.turn_durations.append(turn_duration)
                
                # Check stop reason
                if self.stop_reason == "tool_use":
                    # Process tool calls and continue conversation
                    if not self._process_tool_calls():
                        break
                elif self.stop_reason in ["end_turn", "max_tokens", "stop_sequence"]:
                    # Conversation complete
                    break
                else:
                    # Unknown stop reason, exit
                    break
            
            # Calculate metrics
            first_token_ms = (self.first_token_time - self.start_time) * 1000 if self.first_token_time else 0
            stream_complete_ms = (self.stream_end_time - self.start_time) * 1000 if self.stream_end_time else 0
            total_task_ms = (time.time() - self.start_time) * 1000
            max_turn_ms = max(self.turn_durations) if self.turn_durations else 0
            
            # Store request IDs separately
            self.runner.store_request_ids(task_id, self.request_ids)
            
            # Record result
            self.runner.record_result(
                task_id=task_id,
                task_type=task_type,
                first_token_ms=first_token_ms,
                stream_complete_ms=stream_complete_ms,
                total_task_ms=total_task_ms,
                max_turn_ms=max_turn_ms,
                tool_calls_count=self.tool_calls_count,
                turns_count=self.turns_count,
                model_id=self.model_id,
                total_bedrock_requests=len(self.request_ids),
                cross_region_requests=0,  # Will be updated by CloudTrail query
                status="success"
            )
            
            return {
                "status": "success",
                "first_token_ms": first_token_ms,
                "stream_complete_ms": stream_complete_ms,
                "total_task_ms": total_task_ms,
                "max_turn_ms": max_turn_ms,
                "turns_count": self.turns_count
            }
            
        except Exception as e:
            # Record error
            total_task_ms = (time.time() - self.start_time) * 1000
            max_turn_ms = max(self.turn_durations) if self.turn_durations else 0
            self.runner.record_result(
                task_id=task_id,
                task_type=task_type,
                first_token_ms=0,
                stream_complete_ms=0,
                total_task_ms=total_task_ms,
                max_turn_ms=max_turn_ms,
                tool_calls_count=self.tool_calls_count,
                turns_count=self.turns_count,
                model_id=self.model_id,
                total_bedrock_requests=len(self.request_ids),
                cross_region_requests=0,
                status=f"error: {str(e)}"
            )
            return {"status": "error", "message": str(e)}
    
    def _reset_timing(self):
        """Reset timing state."""
        self.start_time = None
        self.first_token_time = None
        self.stream_end_time = None
        self.tool_calls_count = 0
        self.turns_count = 0
        self.messages = []
        self.pending_tool_uses = []
        self.stop_reason = None
        self.turn_durations = []  # Track duration of each turn
        self.turn_start_time = None
        self.request_ids = []
    
    def _execute_api_call(self, task_def: Dict[str, Any]):
        """Execute API call - to be implemented by subclass."""
        raise NotImplementedError("Subclass must implement _execute_api_call")
    
    def _process_tool_calls(self) -> bool:
        """Process pending tool calls and add results to conversation.
        
        Returns:
            bool: True if tool calls were processed successfully, False otherwise
        """
        if not self.pending_tool_uses:
            return False
        
        # Execute each tool call with mock executor
        tool_results = []
        for tool_use in self.pending_tool_uses:
            tool_name = tool_use.get('name')
            tool_input = tool_use.get('input', {})
            tool_id = tool_use.get('id')
            
            # Execute mock tool
            result = self.mock_tools.execute(tool_name, tool_input)
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result.get('content', '')
            })
        
        # Add tool results to conversation (format depends on API)
        self._add_tool_results_to_conversation(tool_results)
        
        return True
    
    def _add_tool_results_to_conversation(self, tool_results):
        """Add tool results to conversation - to be implemented by subclass."""
        raise NotImplementedError("Subclass must implement _add_tool_results_to_conversation")
    
    def _mark_first_token(self):
        """Mark when first token is received."""
        if self.first_token_time is None:
            self.first_token_time = time.time()
    
    def _mark_stream_end(self):
        """Mark when stream completes."""
        self.stream_end_time = time.time()
    
    def _handle_tool_call(self, tool_name: str, tool_input: Dict[str, Any]):
        """Handle a tool call using mock executor."""
        self.tool_calls_count += 1
        return self.mock_tools.execute(tool_name, tool_input)
