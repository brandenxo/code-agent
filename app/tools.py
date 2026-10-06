import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


BASH_TIMEOUT_SECONDS = 60

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


def _workspace_path(file_path, workspace_root):
    path = Path(file_path)

    if workspace_root is None:
        return path

    root = Path(workspace_root).resolve()
    resolved = (root / path).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PermissionError(
            f"Path must stay inside the benchmark workspace: {file_path}"
        ) from error

    return resolved


def _run_benchmark_command(command, workspace_root):
    allowed = re.fullmatch(
        r"(?:python|py)(?:\.exe)?\s+-m\s+(?:pytest|unittest)"
        r"[A-Za-z0-9_./\\:\s=-]*",
        command.strip(),
        flags=re.IGNORECASE,
    )

    if not allowed:
        return (
            "Exit code: 126\nSTDOUT:\n\nSTDERR:\n"
            "Benchmark Bash only permits python -m pytest or "
            "python -m unittest commands."
        )

    arguments = shlex.split(command, posix=os.name != "nt")
    arguments[0] = sys.executable

    try:
        result = subprocess.run(
            arguments,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _timeout_result()

    return (
        f"Exit code: {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def _timeout_result():
    return (
        "Exit code: 124\nSTDOUT:\n\nSTDERR:\n"
        f"Command timed out after {BASH_TIMEOUT_SECONDS} seconds."
    )


def execute_tool(tool_call, workspace_root=None):
    arguments = json.loads(tool_call.function.arguments)

    if tool_call.function.name == "Read":
        file_path = _workspace_path(arguments["file_path"], workspace_root)

        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
        
    elif tool_call.function.name == "Write":
        file_path = _workspace_path(arguments["file_path"], workspace_root)
        content = arguments["content"]

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        return "File written successfully."
    
    elif tool_call.function.name == "Bash":
        command = arguments["command"]

        if workspace_root is not None:
            return _run_benchmark_command(command, workspace_root)

        arguments = shlex.split(command, posix=os.name != "nt")
        if not arguments:
            raise ValueError("Bash command cannot be empty")

        try:
            result = subprocess.run(
                arguments,
                capture_output=True,
                text=True,
                timeout=BASH_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _timeout_result()

        return (
            f"Exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    else:
        raise RuntimeError(f"Unsupported tool: {tool_call.function.name}")
