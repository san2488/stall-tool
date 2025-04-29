#!/usr/bin/env python3
import json
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError


def invoke_bedrock_converse_stream(prompt, model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"):
    """
    Invokes the Bedrock converseStream API with Claude v3.7 model with tool use support.

    Args:
        prompt (str): The user prompt to send to the model
        model_id (str): The model ID to use

    Returns:
        None: Prints the streaming response to stdout
    """
    # Initialize Bedrock Runtime client
    bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-west-2")

    # Define the input schema for the fs_write tool
    inputSchema = {
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
    # Define the fsWrite tool schema
    fs_write_tool = {
        "toolSpec": {
            "name": "fs_write",
            "description": "A tool for creating and editing files\n * The `create` command will override the file at `path` if it already exists as a file, and otherwise create a new file\n * The `append` command will add content to the end of an existing file, automatically adding a newline if the file doesn't end with one. The file must exist.\n Notes for using the `str_replace` command:\n * The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!\n * If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique\n * The `new_str` parameter should contain the edited lines that should replace the `old_str`.",
            "inputSchema": {"json": inputSchema},
        }
    }

    # Prepare request body
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    try:
        # Prepare API call parameters
        api_params = {
            "modelId": model_id,
            "messages": messages,
            "toolConfig": {"tools": [fs_write_tool]},
        }

        # Call the converseStream API
        response = bedrock_runtime.converse_stream(**api_params)

        # Process the streaming response
        print("Streaming response from Claude v3.7:")
        print("-" * 50)

        full_response = ""
        current_text = ""
        tool_use = {}

        for event in response.get("stream"):
            if "messageStart" in event:
                print(f"[Message started with role: {event['messageStart']['role']}]")

            elif "contentBlockStart" in event:
                block_start = event["contentBlockStart"]["start"]
                if "toolUse" in block_start:
                    tool = block_start["toolUse"]
                    tool_use = {"toolUseId": tool["toolUseId"], "name": tool["name"], "input": ""}
                    print(f"\n[Tool Use Started: {tool['name']} (ID: {tool['toolUseId']})]")

            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    text_chunk = delta["text"]
                    print(text_chunk, end="", flush=True)
                    current_text += text_chunk
                elif "toolUse" in delta and "input" in delta["toolUse"]:
                    tool_use["input"] += delta["toolUse"]["input"]

            elif "contentBlockStop" in event:
                if tool_use and "input" in tool_use and tool_use["input"]:
                    # Parse the tool input as JSON
                    try:
                        tool_use["input"] = json.loads(tool_use["input"])
                        print(f"\n[Tool parameters: {json.dumps(tool_use['input'], indent=2)}]")

                        # Execute the fs_write tool
                        if tool_use["name"] == "fs_write":
                            execute_fs_write(tool_use["input"])

                            # Send tool result back to the model
                            tool_result_message = {
                                "role": "user",
                                "content": [
                                    {
                                        "toolResult": {
                                            "toolUseId": tool_use["toolUseId"],
                                            "content": [
                                                {
                                                    "text": f"Tool execution completed successfully for {tool_use['input']['command']} operation on {tool_use['input']['path']}"
                                                }
                                            ],
                                        }
                                    }
                                ],
                            }

                            # Add the tool result message to the messages list
                            messages.append(tool_result_message)

                            # Call the API again with the tool result
                            print("\n[Sending tool result back to the model...]")
                            continue_response = bedrock_runtime.converse_stream(
                                modelId=model_id,
                                messages=messages,
                                toolConfig={"tools": [fs_write_tool]},
                            )

                            # Process the continued response
                            for continue_event in continue_response.get("stream"):
                                if "contentBlockDelta" in continue_event:
                                    continue_delta = continue_event["contentBlockDelta"]["delta"]
                                    if "text" in continue_delta:
                                        continue_text = continue_delta["text"]
                                        print(continue_text, end="", flush=True)
                                        full_response += continue_text

                    except json.JSONDecodeError:
                        print(f"\n[Error: Failed to parse tool input as JSON]")

                    # Reset tool use
                    tool_use = {}
                else:
                    full_response += current_text
                    current_text = ""

            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "")
                print(f"\n[Message stopped. Reason: {stop_reason}]")

        print("\n" + "-" * 50)
        return full_response

    except ClientError as e:
        print(f"Error invoking Bedrock: {e}")
        return None


def execute_fs_write(parameters):
    """
    Execute the fs_write tool functionality.

    Args:
        parameters (dict): The parameters for the fs_write tool
    """
    command = parameters.get("command")
    path = parameters.get("path")

    if not command or not path:
        print(f"\n[Tool Error: Missing required parameters]")
        return

    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        if command == "create":
            file_text = parameters.get("file_text", "")
            with open(path, "w") as f:
                f.write(file_text)
            print(f"\n[Tool Result: File created at {path}]")

        elif command == "append":
            new_str = parameters.get("new_str", "")
            if not os.path.exists(path):
                print(f"\n[Tool Error: File {path} does not exist for append operation]")
                return

            with open(path, "a") as f:
                # Add newline if file doesn't end with one
                if os.path.getsize(path) > 0:
                    with open(path, "r") as check_file:
                        check_file.seek(max(0, os.path.getsize(path) - 1))
                        last_char = check_file.read(1)
                        if last_char != "\n":
                            f.write("\n")
                f.write(new_str)
            print(f"\n[Tool Result: Content appended to {path}]")

        elif command == "str_replace":
            old_str = parameters.get("old_str")
            new_str = parameters.get("new_str")

            if not old_str or new_str is None:
                print(f"\n[Tool Error: Missing old_str or new_str for str_replace operation]")
                return

            if not os.path.exists(path):
                print(f"\n[Tool Error: File {path} does not exist for str_replace operation]")
                return

            with open(path, "r") as f:
                content = f.read()

            if old_str not in content:
                print(f"\n[Tool Error: old_str not found in {path}]")
                return

            new_content = content.replace(old_str, new_str)
            with open(path, "w") as f:
                f.write(new_content)
            print(f"\n[Tool Result: String replaced in {path}]")

        elif command == "insert":
            new_str = parameters.get("new_str")
            insert_line = parameters.get("insert_line")

            if new_str is None or insert_line is None:
                print(f"\n[Tool Error: Missing new_str or insert_line for insert operation]")
                return

            if not os.path.exists(path):
                print(f"\n[Tool Error: File {path} does not exist for insert operation]")
                return

            with open(path, "r") as f:
                lines = f.readlines()

            if insert_line < 0 or insert_line > len(lines):
                print(f"\n[Tool Error: insert_line {insert_line} out of range for {path}]")
                return

            lines.insert(insert_line, new_str + "\n")
            with open(path, "w") as f:
                f.writelines(lines)
            print(f"\n[Tool Result: Content inserted at line {insert_line} in {path}]")

        else:
            print(f"\n[Tool Error: Unknown command {command}]")

    except Exception as e:
        print(f"\n[Tool Error: {str(e)}]")


def main():
    # Get the prompt
    if len(sys.argv) > 1:
        # If prompt is provided as command line argument
        prompt = " ".join(sys.argv[1:])
    else:
        # Otherwise, ask for input
        prompt = input("Enter your prompt for Claude v3.7: ")

    response = invoke_bedrock_converse_stream(prompt)
    print(f"Response: {response}")


if __name__ == "__main__":
    main()
