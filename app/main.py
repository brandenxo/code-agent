import os
import sys

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


def run_turn(client, conversation_history):
    while True:
        chat = client.chat.completions.create(
            model=MODEL,
            messages=conversation_history,
            tools=TOOLS,
        )

        if not chat.choices:
            raise RuntimeError("No choices in response")

        message = chat.choices[0].message
        conversation_history.append(message)

        if not message.tool_calls:
            return message.content or ""

        for tool_call in message.tool_calls:
            result = execute_tool(tool_call)

            conversation_history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )


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

    return run_turn(client, conversation_history)


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

        reply = run_turn(
            client,
            conversation_history,
        )

        sys.stdout.write(reply + "\n")


if __name__ == "__main__":
    main()