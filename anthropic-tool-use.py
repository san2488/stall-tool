#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import time
import requests
import sseclient

# You'll need to set your Anthropic API key as an environment variable
# export ANTHROPIC_API_KEY=your_api_key_here

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


def invoke_anthropic_messages_stream(prompt, model_id, timestamp_mode=False):
    """
    Invokes the Anthropic Messages API with streaming and tool use support.

    Args:
        prompt (str): The user prompt to send to the model
        model_id (str): The model ID to use
        timestamp_mode (bool): Whether to print timestamps for each event

    Returns:
        str: The full response text
    """
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Define the input schema for the fs_write tool
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["create", "str_replace", "insert", "append"],
                "description": "The commands to run. Allowed options are: `create`, `str_replace`, `insert`, `append`.",
            },
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.",
            },
            "file_text": {
                "type": "string",
                "description": "Required parameter of `create` command, with the content of the file to be created.",
            },
            "old_str": {
                "type": "string",
                "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
            },
            "new_str": {
                "type": "string",
                "description": "Required parameter of `str_replace` command containing the new string. Required parameter of `insert` command containing the string to insert. Required parameter of `append` command containing the content to append to the file.",
            },
            "insert_line": {
                "type": "integer",
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
            },
        },
        "required": ["command", "path"],
    }
    
    # Define the fs_write tool
    fs_write_tool = {
        "name": "fs_write",
        "description": "A tool for creating and editing files\n * The `create` command will override the file at `path` if it already exists as a file, and otherwise create a new file\n * The `append` command will add content to the end of an existing file, automatically adding a newline if the file doesn't end with one. The file must exist.\n Notes for using the `str_replace` command:\n * The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!\n * If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique\n * The `new_str` parameter should contain the edited lines that should replace the `old_str`.",
        "input_schema": input_schema
    }

    # Prepare request body
    messages = [{"role": "user", "content": prompt}]

    try:
        # Prepare API call parameters
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream"
        }
        
        # # Try with the exact model ID format from Bedrock
        # if model_id == "claude-3-7-sonnet-20250219":
        #     log("Using model ID: claude-3-7-sonnet-20250219-v1:0", timestamp_mode)
        #     model_id = "claude-3-7-sonnet-20250219-v1:0"
        
        # # Try with the standard Anthropic model ID format
        # if ":" in model_id:
        #     log(f"Removing version suffix from model ID: {model_id}", timestamp_mode)
        #     model_id = model_id.split(":")[0]
            
        # # For debugging, try with a known working model ID
        # if model_id.startswith("claude-3-7"):
        #     log("Falling back to claude-3-sonnet-20240229 as a test", timestamp_mode)
        #     model_id = "claude-3-sonnet-20240229"
        
        data = {
            "model": model_id,
            "messages": messages,
            "tools": [fs_write_tool],
            "max_tokens": 4096,
            "stream": True
        }

        # Call the Messages API with streaming
        log("Streaming response from Claude:")
        log("-" * 50, timestamp_mode)
        
        # Debug: Print request details
        log(f"API URL: {api_url}", timestamp_mode)
        log(f"Headers: {json.dumps({k: v for k, v in headers.items() if k != 'x-api-key'})}", timestamp_mode)
        log(f"Request data: {json.dumps(data)}", timestamp_mode)
        
        # timeout doesn't seem to be working for the stream
        response = requests.post(api_url, headers=headers, json=data, stream=True, timeout=120)
        
        # Debug: Print response details if there's an error
        if response.status_code != 200:
            log(f"Error status code: {response.status_code}", timestamp_mode)
            log(f"Error response: {response.text}", timestamp_mode)
            
        response.raise_for_status()
        
        client = sseclient.SSEClient(response)
        
        full_response = ""
        current_text = ""
        tool_use = {}
        
        # Track the assistant's response to include in the messages array
        assistant_message = {"role": "assistant", "content": []}
        current_content_block = None

        for event in client.events():
            # Debug: Print raw event data
            # log(f"Raw event: {event.event} - Data: {event.data[:100] if event.data else 'None'}", timestamp_mode)
            
            # Parse the event data
            if not event.data:
                continue
                
            data = json.loads(event.data)
            event_type = data.get("type")
            
            if event_type == "message_start":
                log(f"[Message started with role: {data['message']['role']}]", timestamp_mode)
                
            elif event_type == "content_block_start":
                content_block = data.get("content_block", {})
                block_type = content_block.get("type")
                
                # log(f"[Content block start: {block_type}]", timestamp_mode)
                log(f"[Content block data: {json.dumps(content_block)}]", timestamp_mode)
                
                if block_type == "tool_use":
                    tool_use = {
                        "toolUseId": content_block["id"],
                        "name": content_block["name"],
                        "input": {}
                    }
                    log(f"[Tool Use Started: {content_block['name']} (ID: {content_block['id']})]", timestamp_mode)
                    # Start timing tool input generation
                    tool_start_time = time.time()
                    
                    # Add the toolUse to the assistant's message
                    current_content_block = {
                        "type": "tool_use",
                        "id": content_block["id"],
                        "name": content_block["name"],
                        "input": {}
                    }
                    
            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                delta_type = delta.get("type")
                
                if delta_type == "text_delta":
                    text_chunk = delta.get("text", "")
                    log(text_chunk, timestamp_mode, flush=True)
                    current_text += text_chunk
                    full_response += text_chunk
                    
                    # If this is the first text chunk, add a text block to the assistant's message
                    if not any(block.get("type") == "text" for block in assistant_message["content"]):
                        assistant_message["content"].append({"type": "text", "text": text_chunk})
                    else:
                        # Otherwise, append to the existing text block
                        for block in assistant_message["content"]:
                            if block.get("type") == "text":
                                block["text"] += text_chunk
                                break
                                
                elif delta_type == "input_json_delta":
                    # Handle incremental JSON for tool use
                    partial_json = delta.get("partial_json", "")
                    log(f"[Tool input part: {partial_json}]", timestamp_mode, flush=True)
                    
                    # Accumulate the partial JSON
                    if "input_json" not in tool_use:
                        tool_use["input_json"] = ""
                    tool_use["input_json"] += partial_json
                    
                    # Try to parse the accumulated JSON if it looks complete
                    if tool_use["input_json"].startswith("{") and tool_use["input_json"].endswith("}"):
                        try:
                            complete_json = json.loads(tool_use["input_json"])
                            tool_use["input"] = complete_json
                            log(f"[Complete tool input: {json.dumps(complete_json)}]", timestamp_mode, flush=True)
                            
                            # Update the toolUse in the assistant's message
                            if current_content_block and current_content_block["type"] == "tool_use":
                                current_content_block["input"] = complete_json
                        except json.JSONDecodeError:
                            # JSON is not complete yet, continue accumulating
                            pass
                                
                elif delta_type == "tool_use_delta":
                    # For Anthropic API, the input is sent as a complete JSON object, not incrementally
                    if "input" in delta:
                        input_delta = json.dumps(delta["input"])
                        log(f"[Tool input: {input_delta}] ", timestamp_mode, flush=True)
                        tool_use["input"] = delta["input"]
                        
                        # Update the toolUse in the assistant's message
                        if current_content_block and current_content_block["type"] == "tool_use":
                            current_content_block["input"] = delta["input"]
            
            elif event_type == "content_block_stop":
                log(f"[Content block stopped]", timestamp_mode)
                if tool_use and "input" in tool_use and tool_use["input"]:
                    # Calculate and log tool input generation time
                    tool_end_time = time.time()
                    tool_elapsed_time = tool_end_time - tool_start_time
                    log(f"[Tool input generation time: {tool_elapsed_time:.2f} seconds]", timestamp_mode, flush=True)
                    
                    # Add the complete toolUse block to the assistant's message
                    if current_content_block and current_content_block["type"] == "tool_use":
                        assistant_message["content"].append(current_content_block)
                        current_content_block = None
                    
                    log(f"[Tool parameters: {json.dumps(tool_use['input'])}]", timestamp_mode, flush=True)
                    
                    # Execute the fs_write tool
                    if tool_use["name"] == "fs_write":
                        tool_success = execute_fs_write(tool_use["input"], timestamp_mode)
                        
                        # Create tool result message based on success or failure
                        result_text = ""
                        if tool_success:
                            result_text = f"Tool execution completed successfully for {tool_use['input']['command']} operation on {tool_use['input']['path']}"
                        else:
                            result_text = f"Tool execution failed for {tool_use['input']['command']} operation on {tool_use['input']['path']}"
                            
                        # Send tool result back to the model
                        tool_result_message = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use["toolUseId"],
                                    "content": result_text
                                }
                            ]
                        }

                        # Create a complete messages array with the assistant's response
                        tool_messages = [
                            {"role": "user", "content": prompt},
                            assistant_message,
                            tool_result_message
                        ]

                        # Call the API again with the tool result
                        log(f"[Sending tool result back to the model...]", timestamp_mode)
                        try:
                            continue_data = {
                                "model": model_id,
                                "messages": tool_messages,
                                "tools": [fs_write_tool],
                                "max_tokens": 4096,
                                "stream": True
                            }
                            
                            continue_response = requests.post(api_url, headers=headers, json=continue_data, stream=True)
                            continue_response.raise_for_status()
                            
                            continue_client = sseclient.SSEClient(continue_response)
                            
                            # Process the continued response
                            for continue_event in continue_client.events():
                                if continue_event.event == "content_block_delta" and continue_event.data:
                                    continue_data = json.loads(continue_event.data)
                                    if continue_data["type"] == "text_delta":
                                        continue_text = continue_data["delta"]["text"]
                                        log(continue_text, timestamp_mode, flush=True)
                                        full_response += continue_text
                                        
                        except Exception as e:
                            log(f"\nError invoking Anthropic API: {e}")
                            # Continue with the response we have so far

                    # Reset tool use
                    tool_use = {}
                else:
                    full_response += current_text
                    current_text = ""

            elif event_type == "message_delta":
                delta = data.get("delta", {})
                stop_reason = delta.get("stop_reason")
                if stop_reason:
                    log(f"[Message delta with stop_reason: {stop_reason}]", timestamp_mode)
                
            elif event_type == "message_stop":
                log(f"[Message stopped]", timestamp_mode)
                # Add any remaining text to the full response
                if current_text:
                    full_response += current_text
                    current_text = ""

        log("-" * 50, timestamp_mode)
        return full_response

    except Exception as e:
        log(f"Error invoking Anthropic API: {e}")
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

    # Get timestamp if in timestamp mode
    timestamp = ""
    if timestamp_mode:
        current_time = datetime.datetime.now().isoformat(timespec='milliseconds')
        timestamp = f"[{current_time}] "

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
    Main function to parse arguments and invoke the Anthropic Messages API.
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Invoke Anthropic Messages API with Claude")
    parser.add_argument("prompt", nargs="*", help="Prompt to send to the model")
    parser.add_argument("--timestamp", "-t", action="store_true", help="Enable timestamp mode")
    parser.add_argument("--model", "-m", default="claude-3-7-sonnet-20250219", 
                        help="Model ID to use")
    
    args = parser.parse_args()
    
    # Get the prompt
    if args.prompt:
        # If prompt is provided as command line argument
        prompt = " ".join(args.prompt)
    else:
        # Otherwise, ask for input
        prompt = input("Enter your prompt for Claude: ")

    # Invoke the API with the specified options
    response = invoke_anthropic_messages_stream(prompt, model_id=args.model, timestamp_mode=args.timestamp)
    print(f"Response size: {len(response) if response else 0}")


if __name__ == "__main__":
    main()
