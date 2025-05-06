#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError


def log(message, timestamp_mode=False, end="\n", flush=False):
    """
    Log a message with an optional timestamp.
    
    Args:
        message (str): The message to log
        timestamp_mode (bool): Whether to include a timestamp
        end (str): String appended after the last character of message
        flush (bool): Whether to force a flush of the output
    """
    if timestamp_mode:
        current_time = datetime.datetime.now().isoformat(timespec='milliseconds')
        print(f"[{current_time}] {message}", end=end, flush=flush)
    else:
        print(message, end=end, flush=flush)        


def invoke_bedrock_converse_stream(prompt, model_id, timestamp_mode=False):
    """
    Invokes the Bedrock converseStream API with Claude v3.7 model using system prompt for tool use.

    Args:
        prompt (str): The user prompt to send to the model
        model_id (str): The model ID to use
        timestamp_mode (bool): Whether to print timestamps for each event

    Returns:
        str: The full response text
    """
    # Initialize Bedrock Runtime client
    bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-west-2")

    # Define the system prompt for fs_write tool
    system_prompt = """You have access to a set of tools that are executed upon the user's approval. You can use one tool per message.

# Tool Use Formatting

Tool use is formatted using XML-style tags. The tool name is enclosed in opening and closing tags, and each parameter is similarly enclosed within its own set of tags. Here's the structure:

<tool_name>
<parameter1_name>value1</parameter1_name>
<parameter2_name>value2</parameter2_name>
...
</tool_name>

# Available Tools

## fs_write
Description: A tool for creating and editing files
Parameters:
- command: (required) The commands to run. Allowed options are: `create`, `str_replace`, `insert`, `append`.
- path: (required) Absolute path to file or directory, e.g. `/tmp/file.py` or `/tmp`.
- file_text: (required for create) The content of the file to be created.
- old_str: (required for str_replace) The string in `path` to replace.
- new_str: (required for str_replace/insert/append) The new string to use.
- insert_line: (required for insert) The line number after which to insert the new string.

Usage:
<fs_write>
<command>create</command>
<path>/tmp/example.txt</path>
<file_text>This is the content of the file.</file_text>
</fs_write>

# Tool Use Guidelines

1. Choose the most appropriate tool based on the task.
2. Formulate your tool use using the XML format specified for the tool.
3. Wait for confirmation after each tool use before proceeding.
"""

    # Prepare request body
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        # Prepare API call parameters
        api_params = {
            "modelId": model_id,
            "messages": messages,
            "system": [{"text": system_prompt}],
        }

        # Call the converseStream API
        response = bedrock_runtime.converse_stream(**api_params)

        # Process the streaming response
        print("Streaming response from Claude v3.7 (System Prompt):")
        print("-" * 50)

        full_response = ""
        current_text = ""
        tool_use = {}
        
        # Track the assistant's response to include in the messages array
        assistant_message = {"role": "assistant", "content": []}
        current_content_block = None

        for event in response.get("stream"):
            # Print timestamp if timestamp mode is enabled

            if "messageStart" in event:
                log(f"[Message started with role: {event['messageStart']['role']}]", timestamp_mode)

            elif "contentBlockStart" in event:
                block_start = event["contentBlockStart"]["start"]
                if "toolUse" in block_start:
                    tool = block_start["toolUse"]
                    tool_use = {"toolUseId": tool["toolUseId"], "name": tool["name"], "input": ""}
                    log(f"[Tool Use Started: {tool['name']} (ID: {tool['toolUseId']})]", timestamp_mode)
                    
                    # Add the toolUse to the assistant's message
                    current_content_block = {"toolUse": {
                        "toolUseId": tool["toolUseId"],
                        "name": tool["name"],
                        "input": ""
                    }}

            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    text_chunk = delta["text"]
                    log(text_chunk, timestamp_mode, flush=False)
                    current_text += text_chunk
                    
                    # If this is the first text chunk, add a text block to the assistant's message
                    if not any(block.get("text", "") for block in assistant_message["content"]):
                        assistant_message["content"].append({"text": text_chunk})
                    else:
                        # Otherwise, append to the existing text block
                        for block in assistant_message["content"]:
                            if "text" in block:
                                block["text"] += text_chunk
                                break
                                
                elif "toolUse" in delta and "input" in delta["toolUse"]:
                    tool_use["input"] += delta["toolUse"]["input"]
                    log(f"[Tool input: {delta['toolUse']['input']}] ", timestamp_mode, flush=True)
                    
                    # Update the toolUse in the assistant's message
                    if current_content_block and "toolUse" in current_content_block:
                        current_content_block["toolUse"]["input"] += delta["toolUse"]["input"]

            elif "contentBlockStop" in event:
                if tool_use and "input" in tool_use and tool_use["input"]:
                    # Parse the tool input as XML
                    try:
                        # Extract command and parameters from XML-style input
                        import re
                        
                        # Extract command
                        command_match = re.search(r'<command>(.*?)</command>', tool_use["input"])
                        command = command_match.group(1) if command_match else None
                        
                        # Extract path
                        path_match = re.search(r'<path>(.*?)</path>', tool_use["input"])
                        path = path_match.group(1) if path_match else None
                        
                        # Extract file_text (for create command)
                        file_text_match = re.search(r'<file_text>(.*?)</file_text>', tool_use["input"], re.DOTALL)
                        file_text = file_text_match.group(1) if file_text_match else None
                        
                        # Extract old_str (for str_replace command)
                        old_str_match = re.search(r'<old_str>(.*?)</old_str>', tool_use["input"], re.DOTALL)
                        old_str = old_str_match.group(1) if old_str_match else None
                        
                        # Extract new_str (for str_replace, insert, append commands)
                        new_str_match = re.search(r'<new_str>(.*?)</new_str>', tool_use["input"], re.DOTALL)
                        new_str = new_str_match.group(1) if new_str_match else None
                        
                        # Extract insert_line (for insert command)
                        insert_line_match = re.search(r'<insert_line>(.*?)</insert_line>', tool_use["input"])
                        insert_line = int(insert_line_match.group(1)) if insert_line_match else None
                        
                        # Create parameters dictionary based on command
                        parameters = {"command": command, "path": path}
                        
                        if command == "create" and file_text is not None:
                            parameters["file_text"] = file_text
                        elif command == "str_replace" and old_str is not None and new_str is not None:
                            parameters["old_str"] = old_str
                            parameters["new_str"] = new_str
                        elif command == "insert" and new_str is not None and insert_line is not None:
                            parameters["new_str"] = new_str
                            parameters["insert_line"] = insert_line
                        elif command == "append" and new_str is not None:
                            parameters["new_str"] = new_str
                        
                        log(f"[Tool parameters: {json.dumps(parameters)}]", timestamp_mode, flush=True)
                        
                        # Update the toolUse input in the assistant's message
                        if current_content_block and "toolUse" in current_content_block:
                            current_content_block["toolUse"]["input"] = parameters
                            # Add the complete toolUse block to the assistant's message
                            assistant_message["content"].append(current_content_block)
                            current_content_block = None

                        # Execute the fs_write tool
                        if tool_use["name"] == "fs_write":
                            tool_success = execute_fs_write(parameters, timestamp_mode)
                            
                            # Create tool result message based on success or failure
                            result_text = ""
                            if tool_success:
                                result_text = f"Tool execution completed successfully for {parameters['command']} operation on {parameters['path']}"
                            else:
                                result_text = f"Tool execution failed for {parameters['command']} operation on {parameters['path']}"
                                
                            # Send tool result back to the model
                            tool_result_message = {
                                "role": "user",
                                "content": [
                                    {
                                        "toolResult": {
                                            "toolUseId": tool_use["toolUseId"],
                                            "content": [
                                                {
                                                    "text": result_text
                                                }
                                            ],
                                        }
                                    }
                                ],
                            }

                            # Create a complete messages array with the assistant's response
                            tool_messages = [
                                {"role": "user", "content": [{"text": prompt}]},
                                assistant_message,
                                tool_result_message
                            ]

                            # Call the API again with the tool result
                            log(f"[Sending tool result back to the model...]", timestamp_mode)
                            try:
                                continue_response = bedrock_runtime.converse_stream(
                                    modelId=model_id,
                                    messages=tool_messages,
                                    system=system_prompt,
                                )

                                # Process the continued response
                                for continue_event in continue_response.get("stream"):
                                    # Print timestamp if timestamp mode is enabled
                                    continue_timestamp = ""
                                    if timestamp_mode:
                                        current_time = datetime.datetime.now().isoformat(timespec='milliseconds')
                                        continue_timestamp = f"[{current_time}] "
                                        
                                    if "contentBlockDelta" in continue_event:
                                        continue_delta = continue_event["contentBlockDelta"]["delta"]
                                        if "text" in continue_delta:
                                            continue_text = continue_delta["text"]
                                            log(continue_text, timestamp_mode, flush=True)
                                            full_response += continue_text
                            except ClientError as e:
                                log(f"\nError invoking Bedrock: {e}")
                                # Continue with the response we have so far

                    except Exception as e:
                        log(f"\n[Error: Failed to parse tool input: {e}]")

                    # Reset tool use
                    tool_use = {}
                else:
                    full_response += current_text
                    current_text = ""

            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "")
                log(f"[Message stopped. Reason: {stop_reason}]")

        print("\n" + "-" * 50)
        return full_response

    except ClientError as e:
        print(f"Error invoking Bedrock: {e}")
        return None


def execute_fs_write(parameters, timestamp_mode=False):
    """
    Execute the fs_write tool functionality.

    Args:
        parameters (dict): The parameters for the fs_write tool
        timestamp_mode (bool): Whether to print timestamps for each message
    """
    command = parameters.get("command")
    path = parameters.get("path")


    if not command or not path:
        log(f"[Tool Error: Missing required parameters]")
        return False

    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        if command == "create":
            file_text = parameters.get("file_text", "")
            with open(path, "w") as f:
                f.write(file_text)
            log(f"[Tool Result: File created at {path}]")
            return True

        elif command == "append":
            new_str = parameters.get("new_str", "")
            if not os.path.exists(path):
                log(f"[Tool Error: File {path} does not exist for append operation]")
                return False

            with open(path, "a") as f:
                # Add newline if file doesn't end with one
                if os.path.getsize(path) > 0:
                    with open(path, "r") as check_file:
                        check_file.seek(max(0, os.path.getsize(path) - 1))
                        last_char = check_file.read(1)
                        if last_char != "\n":
                            f.write("\n")
                f.write(new_str)
            log(f"[Tool Result: Content appended to {path}]")
            return True

        elif command == "str_replace":
            old_str = parameters.get("old_str")
            new_str = parameters.get("new_str")

            if not old_str or new_str is None:
                log(f"[Tool Error: Missing old_str or new_str for str_replace operation]")
                return False

            if not os.path.exists(path):
                log(f"[Tool Error: File {path} does not exist for str_replace operation]")
                return False

            with open(path, "r") as f:
                content = f.read()

            if old_str not in content:
                log(f"[Tool Error: old_str not found in {path}]")
                return False

            new_content = content.replace(old_str, new_str)
            with open(path, "w") as f:
                f.write(new_content)
            log(f"[Tool Result: String replaced in {path}]")
            return True

        elif command == "insert":
            new_str = parameters.get("new_str")
            insert_line = parameters.get("insert_line")

            if new_str is None or insert_line is None:
                log(f"[Tool Error: Missing new_str or insert_line for insert operation]")
                return False

            if not os.path.exists(path):
                log(f"[Tool Error: File {path} does not exist for insert operation]")
                return False

            with open(path, "r") as f:
                lines = f.readlines()

            if insert_line < 0 or insert_line > len(lines):
                log(f"[Tool Error: insert_line {insert_line} out of range for {path}]")
                return False

            lines.insert(insert_line, new_str + "\n")
            with open(path, "w") as f:
                f.writelines(lines)
            log(f"[Tool Result: Content inserted at line {insert_line} in {path}]")
            return True

        else:
            log(f"[Tool Error: Unknown command {command}]")
            return False

    except Exception as e:
        log(f"[Tool Error: {str(e)}]")
        return False


def main():
    """
    Main function to parse arguments and invoke the Bedrock converseStream API.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Invoke Bedrock converseStream API with Claude v3.7 using system prompt")
    parser.add_argument("prompt", nargs="*", help="Prompt to send to the model")
    parser.add_argument("--timestamp", "-t", action="store_true", help="Enable timestamp mode")
    parser.add_argument("--model", "-m", default="us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
                        help="Model ID to use")
    
    args = parser.parse_args()
    
    # Get the prompt
    if args.prompt:
        # If prompt is provided as command line argument
        prompt = " ".join(args.prompt)
    else:
        # Otherwise, ask for input
        prompt = input("Enter your prompt for Claude v3.7: ")

    # Invoke the API with the specified options
    response = invoke_bedrock_converse_stream(prompt, model_id=args.model, timestamp_mode=args.timestamp)
    print(f"Response size: {len(response)}")


if __name__ == "__main__":
    main()
