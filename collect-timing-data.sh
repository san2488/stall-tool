#!/bin/bash

# Script to collect timing data for fs_write tool instructions
# Runs the Python scripts for 1k and 5k inputs and extracts timing information

# Set up variables
CSV_FILE="tool_timing_data.csv"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# Create CSV header if it doesn't exist
if [ ! -f "$CSV_FILE" ]; then
    echo "timestamp,implementation,input_size,tool_time_seconds,actual_chars" > "$CSV_FILE"
fi

# Function to run a test and extract timing information
run_test() {
    local implementation=$1
    local size=$2
    local command=$3
    
    echo "Running $implementation with ${size}k input..."
    
    # Remove any existing test file
    rm -f /tmp/lorem-ipsum.txt
    
    # Run the command and capture output
    output=$(eval "$command")
    
    # Extract timing information using grep to get just the number
    timing=$(echo "$output" | grep -o "\[Tool input generation time: [0-9.]\+ seconds\]" | grep -o "[0-9][0-9.]*")
    
    # Get actual character count if the file exists
    actual_chars=0
    if [ -f "/tmp/lorem-ipsum.txt" ]; then
        actual_chars=$(wc -m < /tmp/lorem-ipsum.txt | tr -d ' ')
    fi
    
    if [ -n "$timing" ]; then
        echo "  Tool time: $timing seconds"
        echo "  Actual characters: $actual_chars"
        # Append to CSV
        echo "$TIMESTAMP,$implementation,${size}k,$timing,$actual_chars" >> "$CSV_FILE"
    else
        echo "  Failed to extract timing information"
    fi
}

# Activate virtual environment
source .venv/bin/activate

# Run Bedrock implementation tests
run_test "bedrock-tool-spec" "1" "python bedrock-tool-use-stalling.py --timestamp 'write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"
run_test "bedrock-tool-spec" "5" "python bedrock-tool-use-stalling.py --timestamp 'write 5000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"
run_test "bedrock-tool-spec" "10" "python bedrock-tool-use-stalling.py --timestamp 'write 10000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"

# Run Anthropic implementation tests
# DO NOT WORK. Some issue with the client which times out before the response is received. Haven't bothered debugging yet.
# run_test "anthropic" "1" "python anthropic-tool-use.py --timestamp 'write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"
# run_test "anthropic" "5" "python anthropic-tool-use.py --timestamp 'write 5000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"

# Run System Prompt implementation tests
run_test "system-prompt" "1" "python system-prompt-tool-use.py --timestamp 'write 1000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"
run_test "system-prompt" "5" "python system-prompt-tool-use.py --timestamp 'write 5000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"
run_test "system-prompt" "10" "python system-prompt-tool-use.py --timestamp 'write 10000 characters of lorem ipsum filler text to /tmp/lorem-ipsum.txt'"

echo "All tests completed. Results saved to $CSV_FILE"
echo "Summary of collected data:"
echo "------------------------"
cat "$CSV_FILE"
