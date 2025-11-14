# Benchmark Verification: Bedrock vs Anthropic

This document verifies that both benchmarks run identical tasks under identical conditions.

## ✅ Verified: Same Task Definitions

Both benchmarks load from the same file:
- **File**: `benchmark/tasks/task_definitions.json`
- **Tasks**: 
  - `summarize_1`: Summarize pets-workshop project
  - `file_edit_1`: Refactor validate_gender method
  - `project_1`: Create 3 Python files for CLI calculator

**Code Location:**
- Bedrock: `benchmark/benchmark_bedrock.py:194`
- Anthropic: `benchmark/benchmark_anthropic.py:209`

```python
tasks_file = Path('benchmark/tasks/task_definitions.json')
with open(tasks_file) as f:
    tasks = json.load(f)
```

## ✅ Verified: Same Tool Definitions

Both benchmarks define identical tools with the same schemas:

### fs_write Tool
- **Name**: `fs_write`
- **Description**: "Write content to a file"
- **Parameters**: `path` (string), `file_text` (string)
- **Required**: Both parameters

### fs_read Tool
- **Name**: `fs_read`
- **Description**: "Read content from a file"
- **Parameters**: `path` (string)
- **Required**: `path`

**Code Location:**
- Bedrock: `benchmark/benchmark_bedrock.py:42-62`
- Anthropic: `benchmark/benchmark_anthropic.py:43-63`

**Format Difference (API-specific):**
- Bedrock uses `toolSpec` with nested `inputSchema.json`
- Anthropic uses flat `input_schema`
- Both represent the same tool schema

## ✅ Verified: Same Mock Tool Executor

Both benchmarks use the same `MockToolExecutor` class:
- **File**: `benchmark/mock_tools.py`
- **Behavior**: Returns deterministic mock responses
- **No actual file I/O**: Simulates tool execution

**Code Location:**
- Bedrock: `benchmark/benchmark_bedrock.py:189`
- Anthropic: `benchmark/benchmark_anthropic.py:205`

```python
mock_tools = MockToolExecutor()
```

## ✅ Verified: Same Inference Configuration

Both benchmarks use identical inference settings:
- **max_tokens**: 4096
- **streaming**: Enabled
- **Model**: Claude Sonnet 4.5 (same model, different IDs)
  - Bedrock: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
  - Anthropic: `claude-sonnet-4-5-20250929`

## ✅ Verified: Same Timing Methodology

Both benchmarks use the same `TaskExecutor` base class:
- **File**: `benchmark/benchmark_runner.py`
- **Metrics**:
  - `first_token_ms`: Time to first token (any content)
  - `stream_complete_ms`: Time until stream ends
  - `total_task_ms`: Total time including all turns
  - `tool_calls_count`: Total tool calls across all turns
  - `turns_count`: Number of conversation turns

**Timing Logic:**
```python
def _mark_first_token(self):
    if self.first_token_time is None:
        self.first_token_time = time.time()
```

## ✅ Verified: Same Multi-Turn Conversation Logic

Both benchmarks use identical conversation loop:
- Continue on `stopReason == "tool_use"`
- Stop on `stopReason == "end_turn"` or `"max_tokens"`
- Process tool results and add to conversation
- Maximum 10 turns per task

**Code Location:**
- Base class: `benchmark/benchmark_runner.py:60-90`

## 🔍 Key Differences (Expected)

### 1. API Format Differences
- **Bedrock**: Uses AWS SDK with `converse_stream()` API
- **Anthropic**: Uses REST API with SSE streaming

### 2. Event Processing
- **Bedrock**: Processes `contentBlockDelta` events
- **Anthropic**: Processes SSE `content_block_delta` events
- Both extract the same information (text, tool use)

### 3. Tool Result Format
- **Bedrock**: Uses `toolResult` with nested structure
- **Anthropic**: Uses `tool_result` with flat structure
- Both convey the same information

## ✅ Conclusion

The benchmarks are **functionally identical**:
- ✅ Same tasks and prompts
- ✅ Same tool definitions (semantically)
- ✅ Same mock tool responses
- ✅ Same timing methodology
- ✅ Same multi-turn conversation logic
- ✅ Same inference configuration

**Any performance differences are attributable to the APIs themselves, not the benchmark implementation.**

## Verification Commands

```bash
# Verify both use same task file
grep -n "task_definitions.json" benchmark/benchmark_*.py

# Verify both use same mock tools
grep -n "MockToolExecutor" benchmark/benchmark_*.py

# Verify both use same base class
grep -n "class.*TaskExecutor" benchmark/benchmark_*.py

# Compare tool definitions
diff <(grep -A 20 "Define tools" benchmark/benchmark_bedrock.py) \
     <(grep -A 20 "Define tools" benchmark/benchmark_anthropic.py)
```
