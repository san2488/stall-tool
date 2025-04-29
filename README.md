# Bedrock Tool Use with Claude v3.7

This repository demonstrates how to use Amazon Bedrock's Claude v3.7 model with tool calling capabilities through the converseStream API.

## Files

- `bedrock-tool-use-stalling.py`: A Python script that invokes the Bedrock converseStream API with Claude v3.7 and tool use support

## Overview

This project shows how to properly implement tool use with Claude v3.7 through the Bedrock API. The implementation handles the streaming response correctly and processes tool use requests according to the API specifications.

## Key Features

- Proper handling of the converseStream API with Claude v3.7
- Correct implementation of tool definitions and schemas
- Processing of streaming responses with tool use events
- Execution of tools and sending results back to the model
- Optional timestamp mode for debugging and tracking response timing

## Setup and Usage

### Using uv (Python package manager)

This project uses `uv` for dependency management and virtual environments.

```bash
# Setup the project
make setup

# Run the main script with no arguments
make run

# Run with a simple "hello world" prompt
make run-hello-world

# Run with a prompt that triggers tool use (create a Fibonacci generator)
make run-hello-world-tool

# Run with timestamp mode enabled
make run-with-timestamp

# Format code
make format

# Clean up
make clean
```

### Manual Setup

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Run the script
source .venv/bin/activate
python bedrock-tool-use-stalling.py "Your prompt here"

# Run with timestamp mode enabled
python bedrock-tool-use-stalling.py --timestamp "Your prompt here"
```

## Command Line Options

The script supports the following command line options:

- `--timestamp` or `-t`: Enable timestamp mode to display ISO-format timestamps for each event in the stream
- `--model` or `-m`: Specify a different model ID (default: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`)

Example:
```bash
python bedrock-tool-use-stalling.py --timestamp --model "us.anthropic.claude-3-7-sonnet-20250219-v1:0" "Your prompt here"
```

## Tool Use Implementation

The script implements the `fs_write` tool that allows Claude v3.7 to:
- Create new files
- Append content to existing files
- Replace content in files
- Insert content at specific lines

This enables the model to generate code, configuration files, or any text content and save it directly to the filesystem.

## Example Prompts

Here are some example prompts you can try:

1. "Write a Python script that calculates the first 10 prime numbers and save it to prime_calculator.py"
2. "Create a simple HTML webpage with a form and save it to index.html"
3. "Generate a basic React component that displays a counter and save it to Counter.jsx"

## Requirements

- Python 3.8+
- AWS credentials with Bedrock access configured
- Boto3 with Bedrock support

## Notes

- Make sure your AWS credentials have the necessary permissions to access Bedrock
- The Claude v3.7 model is used in this example, but other models that support tool use can also be used
- The region is set to us-west-2 by default, change it if your Bedrock endpoint is in a different region
