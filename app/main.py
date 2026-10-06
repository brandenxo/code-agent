import os
import sys
import json
import time

from app.tools import TOOLS, execute_tool
from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    default="https://openrouter.ai/api/v1",
)
MODEL = os.getenv(
    "OPENROUTER_MODEL",
    default="openrouter/free",
)

DEFAULT_MAX_TOOL_CALLS = 12
DEFAULT_MAX_RUNTIME_SECONDS = 120
DEFAULT_MAX_TOTAL_TOKENS = None


def _limit_result(conversation_history, message, model, tokens, tool_count, steps):
    conversation_history.append({"role": "assistant", "content": message})
    return message, model, tokens, tool_count, steps


def run_turn(
    client,
    conversation_history,
    model,
    workspace_root=None,
    max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
    max_runtime_seconds=DEFAULT_MAX_RUNTIME_SECONDS,
    max_total_tokens=DEFAULT_MAX_TOTAL_TOKENS,
):
    total_tokens, tool_count = 0, 0
    steps = []
    started = time.perf_counter()
    while True:
        if time.perf_counter() - started >= max_runtime_seconds:
            return _limit_result(
                conversation_history,
                "Agent stopped safely after reaching the runtime limit.",
                model,
                total_tokens,
                tool_count,
                steps,
            )

        chat = client.chat.completions.create(
            model=model,
            messages=conversation_history,
            tools=TOOLS,
        )
        if chat.usage:
            total_tokens += chat.usage.total_tokens
    
        if not chat.choices:
            raise RuntimeError("No choices in response")

        message = chat.choices[0].message
        actual_model = chat.model or model

        if (
            max_total_tokens is not None
            and total_tokens >= max_total_tokens
            and message.tool_calls
        ):
            return _limit_result(
                conversation_history,
                "Agent stopped safely after reaching the token limit.",
                actual_model,
                total_tokens,
                tool_count,
                steps,
            )

        pending_tool_calls = len(message.tool_calls or [])
        if message.tool_calls and tool_count + pending_tool_calls > max_tool_calls:
            return _limit_result(
                conversation_history,
                "Agent stopped safely after reaching the tool-call limit.",
                actual_model,
                total_tokens,
                tool_count,
                steps,
            )

        conversation_history.append(message)

        if not message.tool_calls:
            return (
                message.content or "",
                actual_model,
                total_tokens,
                tool_count,
                steps,
                )

        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments)
            tool_name = tool_call.function.name

            if tool_name == "Read":
                steps.append(
                    f"Reading {arguments['file_path']}..."
                )

            elif tool_name == "Write":
                steps.append(
                    f"Writing {arguments['file_path']}..."
                )

            elif tool_name == "Bash":
                steps.append(
                    f"Running {arguments['command']}..."
                )

            try:
                result = execute_tool(tool_call, workspace_root=workspace_root)
            except (OSError, PermissionError, ValueError) as error:
                result = f"Tool error: {error}"

            conversation_history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

            tool_count += 1


def run_agent(prompt):
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )

    conversation_history = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    return run_turn(client, conversation_history, MODEL)


def main():
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
    )

    conversation_history = []

    while True:
        try:
            user_input = input("> ")
        except EOFError:
            break

        if user_input.strip().lower() in ("exit", "quit"):
            break

        conversation_history.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        reply, model, tokens, tool_count, steps = run_turn(
            client,
            conversation_history,
            MODEL,
        )

        sys.stdout.write(reply + "\n")


if __name__ == "__main__":
    main()
