# Code Agent

A lightweight coding agent built in Python that can interact with a local project through LLM tool calling.

The agent maintains conversation history, decides when to use tools, executes those tools locally, and feeds the results back to the model until it produces a final response.

It currently runs as an interactive terminal application and uses OpenRouter for model access.

## Features

- Interactive terminal chat
- Persistent conversation history
- Multi-step agent loop
- LLM tool calling
- Read local files
- Create and overwrite files
- Execute shell commands
- Support multiple tool calls in a single model response
- Configurable OpenRouter model through environment variables

## How It Works

The agent follows a loop:

```text
User prompt
    ↓
LLM receives conversation history + available tools
    ↓
LLM either:
    ├── returns a final response
    │
    └── requests one or more tools
            ↓
        Python executes the tools
            ↓
        Tool results are added to conversation history
            ↓
        LLM is called again
```

The model does not directly read files or execute commands.

Instead, it returns structured tool requests. The Python runtime performs the requested operation, stores the result in the conversation history, and sends the updated conversation back to the model.

## Available Tools

### Read

Reads and returns the contents of a local file.

Example:

```text
> read README.md and explain what this project does
```

### Write

Creates or overwrites a file with generated content.

Example:

```text
> create hello.txt and write "hello world" inside it
```

### Bash

Executes a shell command and returns its output to the model.

Example:

```text
> use bash to list the files in this directory
```

> **Warning:** Bash commands are currently executed directly through the local shell. Additional approval and execution controls are planned.

## Project Structure

```text
app/
├── main.py
└── tools.py
```

### `main.py`

Handles:

- terminal input
- conversation history
- model requests
- the agent loop
- tool-call handling
- final responses

### `tools.py`

Contains:

- tool schemas sent to the model
- Read implementation
- Write implementation
- Bash implementation

## Tech Stack

- Python
- OpenAI Python SDK
- OpenRouter API
- JSON
- subprocess
- LLM tool calling

## Setup

### Requirements

- Python 3.14+
- OpenRouter account
- OpenRouter API key

Install the project:

```bash
pip install -e .
```

## Environment Variables

The application reads configuration from environment variables.

### Windows PowerShell

```powershell
$env:OPENROUTER_API_KEY="your-api-key"
```

Optional model override:

```powershell
$env:OPENROUTER_MODEL="openrouter/free"
```

### macOS / Linux

```bash
export OPENROUTER_API_KEY="your-api-key"
```

Optional model override:

```bash
export OPENROUTER_MODEL="openrouter/free"
```

API keys should never be committed to source control.

## Running the Agent

From the project root:

```bash
python -m app.main
```

The program starts an interactive terminal session:

```text
> say hello
Hello, how are you today?

> read README.md and summarize it
This project is a lightweight coding agent...

> exit
```

Use either:

```text
exit
```

or:

```text
quit
```

to close the program.

## Current Limitations

- Bash commands execute without user approval
- Shell execution is not sandboxed
- Bash commands do not currently have execution time limits
- Conversations are not persisted after the program exits
- The interface is terminal-only
- Long conversations are not yet summarized or truncated

## Planned Improvements

- Browser-based interface with FastAPI
- WebSocket communication
- Streaming model responses
- Human approval before potentially destructive tool execution
- Tool execution activity log
- Safer shell execution
- File change visualization
- Model switching and comparison metrics