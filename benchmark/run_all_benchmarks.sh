#!/bin/bash
set -e

echo "=========================================="
echo "Running Bedrock vs Anthropic Benchmarks"
echo "=========================================="

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable not set"
    exit 1
fi

# Default number of runs
RUNS=${1:-5}

echo ""
echo "Configuration:"
echo "  Runs per task: $RUNS"
echo ""

# Run Bedrock benchmark
echo "=========================================="
echo "1. Running Bedrock Benchmark"
echo "=========================================="
python benchmark/benchmark_bedrock.py --runs $RUNS

echo ""
echo "=========================================="
echo "2. Running Anthropic Benchmark"
echo "=========================================="
python benchmark/benchmark_anthropic.py --runs $RUNS

echo ""
echo "=========================================="
echo "3. Analyzing Results"
echo "=========================================="
python benchmark/analyze_results.py

echo ""
echo "=========================================="
echo "✓ All benchmarks complete!"
echo "=========================================="
echo ""
echo "Results:"
echo "  - benchmark/results/bedrock_raw.csv"
echo "  - benchmark/results/anthropic_raw.csv"
echo "  - benchmark/results/comparison_report.csv"
echo "  - benchmark/results/detailed_stats.json"
echo ""
