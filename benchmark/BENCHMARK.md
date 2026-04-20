# Bedrock vs Anthropic API Latency Benchmark

This benchmark measures and compares latency performance between AWS Bedrock and Anthropic's direct API for Claude 3.7 Sonnet.

## Metrics Collected

1. **Time to First Token**: Latency from request start to first token received
2. **Stream Complete Time**: Total time for the streaming response to complete
3. **Total Task Time**: End-to-end time including all tool calls

## Benchmark Tasks

### 1. Summarize Task
- **Goal**: Measure baseline text generation latency
- **Input**: pets-workshop project
- **Expected**: 2-3 sentence summary with minimal/no tool use

### 2. File Edit Task
- **Goal**: Measure latency with file read/write operations
- **Input**: Python file requiring refactoring
- **Expected**: Tool calls to read file, modify, and write back

### 3. Project Task
- **Goal**: Measure latency with multiple file creation operations
- **Input**: Specification for 3-file CLI project
- **Expected**: Multiple tool calls to create files

## Setup

### Prerequisites
```bash
# Install dependencies
pip install boto3 botocore requests sseclient-py

# Set environment variables
export AWS_REGION=us-west-2
export ANTHROPIC_API_KEY=your_api_key_here
```

### Directory Structure
```
benchmark/
├── fixtures/
│   └── pets-workshop/      # Cloned test project
├── tasks/
│   └── task_definitions.json
├── results/
│   ├── bedrock_raw.csv
│   ├── anthropic_raw.csv
│   └── comparison_report.csv
├── benchmark_runner.py
├── mock_tools.py
├── benchmark_bedrock.py
├── benchmark_anthropic.py
└── analyze_results.py
```

## Running Benchmarks

### Run Individual Benchmarks

```bash
# Bedrock benchmark (5 runs per task by default)
python benchmark/benchmark_bedrock.py

# Anthropic benchmark
python benchmark/benchmark_anthropic.py

# Custom number of runs
python benchmark/benchmark_bedrock.py --runs 10
python benchmark/benchmark_anthropic.py --runs 10
```

### Run All Benchmarks
```bash
./benchmark/run_all_benchmarks.sh
```

### Analyze Results
```bash
python benchmark/analyze_results.py
```

## Output Format

### Raw Results CSV
Each benchmark produces a CSV with columns:
- `timestamp`: ISO format timestamp
- `api_type`: "bedrock" or "anthropic"
- `task_id`: Unique task identifier
- `task_type`: "summarize", "file_edit", or "project"
- `first_token_ms`: Time to first token in milliseconds
- `stream_complete_ms`: Time to complete stream in milliseconds
- `total_task_ms`: Total task time in milliseconds
- `tool_calls_count`: Number of tool calls made
- `status`: "success" or error message

### Comparison Report
The analysis script generates:
- `comparison_report.csv`: Side-by-side comparison of mean latencies
- `detailed_stats.json`: Full statistics including p95, p99, min, max

## Mock Tool Execution

Tool calls are mocked to exclude local execution time from measurements. The mock executor:
- Returns deterministic responses
- Simulates file operations without actual I/O
- Tracks call counts for metrics

## Interpreting Results

### Key Metrics
- **First Token**: Lower is better - indicates API responsiveness
- **Stream Complete**: Total streaming time - includes all token generation
- **Total Task**: End-to-end time - includes tool call overhead

### Comparison
- Positive diff means Bedrock is slower
- Negative diff means Bedrock is faster
- Percentage shows relative difference

## Troubleshooting

### Missing API Key
```
Error: ANTHROPIC_API_KEY environment variable not set
```
Solution: `export ANTHROPIC_API_KEY=your_key`

### AWS Credentials
Ensure AWS credentials are configured:
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

### Model Not Available
If you get model access errors, ensure you have access to:
- Bedrock: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- Anthropic: `claude-3-7-sonnet-20250219`
