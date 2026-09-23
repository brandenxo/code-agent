# code-agent

A small terminal AI coding assistant. It runs a chat loop against an
OpenAI-compatible API (via [OpenRouter](https://openrouter.ai)) and gives the
model a handful of tools — `Read`, `Write`, and `Bash` — so it can read files,
write files, and run shell commands on your behalf.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Create an [OpenRouter](https://openrouter.ai) account and API key.
3. Set the required environment variable:

   ```sh
   export OPENROUTER_API_KEY="sk-or-..."
   ```

## Run

```sh
uv run -m app.main
```

This starts an interactive prompt. Type a message and press enter; the
assistant will respond and, if needed, call its tools to read/write files or
run commands in the current directory. Type `exit` or `quit` to end the
session.

## Project layout

- `app/main.py` — the chat loop and REPL entry point.
- `app/tools.py` — tool definitions (schemas for the model) and their
  execution (`execute_tool`).
