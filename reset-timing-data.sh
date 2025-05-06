#!/bin/bash

# Script to reset the timing data CSV file
# This creates a fresh CSV file with just the header

CSV_FILE="tool_timing_data.csv"

# Create CSV header
echo "timestamp,implementation,input_size,tool_time_seconds" > "$CSV_FILE"

echo "Timing data has been reset. $CSV_FILE now contains only the header."
