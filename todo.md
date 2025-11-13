# TODO: Bedrock vs Anthropic 1P API Latency Benchmark

## Section 1: Infrastructure & Data Setup
**Goal**: Prepare benchmark framework and test data
- [x] Create benchmark directory structure (`/benchmark/`)
- [x] Clone pets-workshop repo to `/benchmark/fixtures/pets-workshop/`
- [x] Create fixture generator script that prepares:
  - Project summary text (for Summarize task)
  - Sample file content (for File Edit task)
  - Project spec (for Project Task)
- [x] Define task definitions in JSON/YAML with:
  - Task ID, type, input data, expected tool calls
  - Example: `{"task_id": "summarize_1", "type": "summarize", "project_path": "..."}`
- [x] Create mock tool executor that simulates tool responses without actual execution
  - Mock `fs_read`, `fs_write`, `file_list` operations
  - Return deterministic responses

## Section 2: Benchmark Framework
**Goal**: Build core measurement infrastructure
- [x] Create `BenchmarkRunner` class that:
  - Accepts API client (Bedrock or Anthropic)
  - Tracks: `start_time`, `first_token_time`, `stream_end_time`
  - Records raw timing data to CSV
- [x] Create CSV schema with columns:
  - `timestamp, api_type, task_id, task_type, first_token_ms, stream_complete_ms, total_task_ms, tool_calls_count, status`
- [x] Create task executor that:
  - Loads task definition
  - Sends to API
  - Intercepts tool requests → calls mock executor
  - Records all timings

## Section 3: Bedrock Benchmark Script
**Goal**: Measure Bedrock API latency
- [x] Create `benchmark_bedrock.py` that:
  - Initializes Bedrock client
  - Loads all 3 task types
  - Runs each task N times (e.g., 5 runs)
  - Writes raw timings to `results/bedrock_raw.csv`
- [x] Handle streaming events to capture first token time
- [x] Mock tool execution (don't actually call tools)

## Section 4: Anthropic 1P Benchmark Script
**Goal**: Measure Anthropic API latency
- [x] Create `benchmark_anthropic.py` that:
  - Initializes Anthropic client
  - Loads all 3 task types
  - Runs each task N times (e.g., 5 runs)
  - Writes raw timings to `results/anthropic_raw.csv`
- [x] Handle streaming events to capture first token time
- [x] Mock tool execution (don't actually call tools)

## Section 5: Task Definitions
**Goal**: Define the 3 benchmark tasks
- [x] **Summarize Task**: 
  - Input: pets-workshop project path
  - Prompt: "Summarize this project in 2-3 sentences"
  - Expected: Text response (no tools needed, or minimal)
- [x] **File Edit Task**:
  - Input: Sample Python file
  - Prompt: "Refactor this function to use list comprehension"
  - Expected: Tool calls to read file, write modified version
- [x] **Project Task**:
  - Input: Project spec (e.g., "Create a simple CLI tool with 3 files")
  - Prompt: "Create the following files: main.py, config.py, utils.py"
  - Expected: Multiple tool calls to create files

## Section 6: Analysis & Reporting Script
**Goal**: Aggregate and compare raw data
- [x] Create `analyze_results.py` that:
  - Reads `bedrock_raw.csv` and `anthropic_raw.csv`
  - Computes per-task statistics:
    - Mean, median, p95, p99 for each metric
    - Comparison table (Bedrock vs Anthropic)
  - Outputs to `results/comparison_report.csv` or JSON
- [x] Generate summary statistics by task type

## Section 7: Documentation & Execution Guide
**Goal**: Make benchmark reproducible
- [x] Create `BENCHMARK.md` with:
  - Setup instructions (install deps, clone fixtures)
  - How to run individual benchmarks
  - How to run analysis
  - Expected output format
- [x] Create `run_all_benchmarks.sh` that:
  - Runs both benchmark scripts
  - Runs analysis
  - Outputs summary

---

## Execution Order
1. **Section 1** → Prepare data
2. **Section 2** → Build framework
3. **Sections 3 & 4** → Can run in parallel (independent scripts)
4. **Section 5** → Define tasks (can be done during Section 2)
5. **Section 6** → Analysis (after Sections 3 & 4 complete)
6. **Section 7** → Documentation (final)

Each section is independent and can be completed/tested separately.

---

## Section 8: Multi-Turn Agentic Conversation Support
**Goal**: Enable benchmarks to handle multiple tool calls in a conversation loop

### Current Limitation
- Benchmark only processes single API response per task
- Stops after first tool call when `stopReason: tool_use`
- Project task only creates 1 file instead of 3 because conversation doesn't continue

### Tasks
- [x] Modify `TaskExecutor._execute_api_call()` to support conversation loop:
  - Check `stopReason` after each response
  - If `stopReason == "tool_use"`, continue conversation
  - If `stopReason == "end_turn"` or `"max_tokens"`, stop
- [x] Implement conversation history tracking:
  - Store messages array with user/assistant turns
  - Append tool results as new messages
- [x] Update Bedrock executor to:
  - Parse tool use requests from response
  - Call mock tool executor
  - Format tool results for next API call
  - Continue loop until completion
- [x] Update Anthropic executor to:
  - Parse tool use requests from SSE stream
  - Call mock tool executor  
  - Format tool results for next API call
  - Continue loop until completion
- [x] Update metrics tracking:
  - Track total conversation time (all turns)
  - Track per-turn latency
  - Track total tool calls across all turns
  - Add `turns_count` column to CSV
- [x] Update task definitions:
  - Keep explicit "create 3 files" prompt for project task
  - Verify all 3 files get created in multi-turn mode
- [x] Test with project task to verify 3 tool calls occur
- [ ] Update documentation with multi-turn behavior

## Section 9: Analysis Script Testing
**Goal**: Verify analysis scripts work with collected benchmark data

### Tasks
- [ ] Run both Bedrock and Anthropic benchmarks with multiple runs (5+)
- [ ] Test `analyze_results.py` on collected data
- [ ] Verify comparison report generation
- [ ] Verify summary statistics are correct
- [ ] Test with edge cases (errors, missing data)
- [ ] Update analysis script if needed for new CSV columns (model_id, turns_count)
