import os
import sys
import json
import logging
import time

from app.tools import TOOLS, execute_tool
from openai import APIConnectionError, APITimeoutError, OpenAI


logger = logging.getLogger(__name__)

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


class ModelUnavailableError(RuntimeError):
    """A model/provider returned no usable completion."""


class ModelFallbackError(RuntimeError):
    """Both the primary model and its configured fallback were unavailable."""


def is_retryable_model_error(error):
    """Return whether a completion failed because its provider is unavailable."""
    if isinstance(error, (ModelUnavailableError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True

    status_code = getattr(error, "status_code", None)
    if status_code in {401, 403}:
        return False
    if status_code == 429 or (status_code is not None and 500 <= status_code <= 599):
        return True

    message = str(error).lower()
    if status_code == 402 and any(
        phrase in message for phrase in ("quota", "credit", "free limit", "free tier")
    ):
        return True
    return status_code is not None and any(
        phrase in message
        for phrase in (
            "provider overloaded",
            "provider unavailable",
            "temporarily unavailable",
            "no provider available",
            "no providers available",
            "free quota exhausted",
            "quota exhausted",
        )
    )


def model_fallback_reason(error):
    status_code = getattr(error, "status_code", None)
    message = str(error).lower()
    if status_code == 429 or "rate limit" in message or "quota" in message:
        return "Primary model was rate limited."
    if isinstance(error, (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError)):
        return "Primary model provider timed out."
    if isinstance(error, ModelUnavailableError):
        return "Primary model returned no available response."
    if status_code is not None and 500 <= status_code <= 599:
        return "Primary model provider was temporarily unavailable."
    return "Primary model was temporarily unavailable."


def call_model_with_fallback(
    client, conversation_history, model, fallback_model, fallback_state
):
    """Call one completion, switching models once without resetting turn state."""
    try:
        return client.chat.completions.create(
            model=model,
            messages=conversation_history,
            tools=TOOLS,
        ), model
    except Exception as error:
        can_fallback = (
            fallback_model
            and model != fallback_model
            and not fallback_state["fallback_used"]
            and is_retryable_model_error(error)
        )
        if not can_fallback:
            if fallback_state["fallback_used"] and is_retryable_model_error(error):
                raise ModelFallbackError(
                    "Primary model and OpenRouter fallback are currently unavailable. "
                    "Please try again shortly."
                ) from error
            raise

        fallback_state["fallback_used"] = True
        fallback_state["fallback_model"] = fallback_model
        fallback_state["fallback_reason"] = model_fallback_reason(error)
        logger.warning(
            "Model fallback activated: primary=%s fallback=%s error_type=%s status=%s",
            model,
            fallback_model,
            type(error).__name__,
            getattr(error, "status_code", None),
        )
        try:
            return client.chat.completions.create(
                model=fallback_model,
                messages=conversation_history,
                tools=TOOLS,
            ), fallback_model
        except Exception as fallback_error:
            if not is_retryable_model_error(fallback_error):
                raise
            raise ModelFallbackError(
                "Primary model and OpenRouter fallback are currently unavailable. "
                "Please try again shortly."
            ) from fallback_error


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
    fallback_model=None,
    fallback_state=None,
):
    total_tokens, tool_count = 0, 0
    steps = []
    started = time.perf_counter()
    active_model = model
    if fallback_state is None:
        fallback_state = {}
    fallback_state.update({
        "fallback_used": False,
        "fallback_model": None,
        "fallback_reason": None,
    })
    while True:
        if time.perf_counter() - started >= max_runtime_seconds:
            return _limit_result(
                conversation_history,
                "Agent stopped safely after reaching the runtime limit.",
                active_model,
                total_tokens,
                tool_count,
                steps,
            )

        chat, active_model = call_model_with_fallback(
            client,
            conversation_history,
            active_model,
            fallback_model,
            fallback_state,
        )
        if chat.usage:
            total_tokens += chat.usage.total_tokens
    
        if not chat.choices:
            no_choices = ModelUnavailableError("No choices in response")
            if (
                fallback_model
                and active_model != fallback_model
                and not fallback_state["fallback_used"]
            ):
                fallback_state["fallback_used"] = True
                fallback_state["fallback_model"] = fallback_model
                fallback_state["fallback_reason"] = model_fallback_reason(no_choices)
                active_model = fallback_model
                continue
            if fallback_state["fallback_used"]:
                raise ModelFallbackError(
                    "Primary model and OpenRouter fallback are currently unavailable. "
                    "Please try again shortly."
                ) from no_choices
            raise no_choices

        message = chat.choices[0].message
        actual_model = chat.model or active_model

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

            elif tool_name == "Delete":
                steps.append(
                    f"Deleting {arguments['file_path']}..."
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
