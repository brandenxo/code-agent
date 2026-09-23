import json
import subprocess


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read and return the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read",
                    }
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    }
                },
            },
        },
    },
]


def execute_tool(tool_call):
    arguments = json.loads(tool_call.function.arguments)

    if tool_call.function.name == "Read":
        file_path = arguments["file_path"]

        with open(file_path, "r") as file:
            return file.read()
    elif tool_call.function.name == "Write":
        file_path = arguments["file_path"]
        content = arguments["content"]

        with open(file_path, "w") as file:
            file.write(content)
        return "File written successfully."
    elif tool_call.function.name == "Bash":
        command = arguments["command"]
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    else:
        raise RuntimeError(f"Unsupported tool: {tool_call.function.name}")