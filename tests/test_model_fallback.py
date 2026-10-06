import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import api, database
from app import main


PRIMARY_MODEL = "cohere/north-mini-code:free"
FALLBACK_MODEL = "openrouter/free"


class ModelHTTPError(Exception):
    def __init__(self, status_code, message="provider error"):
        super().__init__(message)
        self.status_code = status_code


class SequenceCompletions:
    def __init__(self, events):
        self.events = list(events)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({
            "model": kwargs["model"],
            "messages": list(kwargs["messages"]),
        })
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


def client_with(*events):
    completions = SequenceCompletions(events)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


def completion(content, model=PRIMARY_MODEL, tool_calls=None, tokens=5):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    return SimpleNamespace(
        usage=SimpleNamespace(total_tokens=tokens),
        choices=[SimpleNamespace(message=message)],
        model=model,
    )


def no_choices(tokens=0):
    return SimpleNamespace(
        usage=SimpleNamespace(total_tokens=tokens), choices=[], model=PRIMARY_MODEL
    )


def run_with_fallback(client, history=None, **kwargs):
    state = {}
    result = main.run_turn(
        client,
        history or [{"role": "user", "content": "Fix this Python bug"}],
        PRIMARY_MODEL,
        fallback_model=FALLBACK_MODEL,
        fallback_state=state,
        **kwargs,
    )
    return result, state


def test_primary_success_does_not_use_fallback():
    client, calls = client_with(completion("Fixed"))

    result, state = run_with_fallback(client)

    assert result[:4] == ("Fixed", PRIMARY_MODEL, 5, 0)
    assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL]
    assert state == {
        "fallback_used": False, "fallback_model": None, "fallback_reason": None,
    }


@pytest.mark.parametrize("status_code", [429, 503])
def test_retryable_status_switches_once_to_openrouter_free(status_code):
    client, calls = client_with(
        ModelHTTPError(status_code),
        completion("Recovered", model="provider/fallback-model:free", tokens=7),
    )

    result, state = run_with_fallback(client)

    assert result[:4] == ("Recovered", "provider/fallback-model:free", 7, 0)
    assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL, FALLBACK_MODEL]
    assert state["fallback_used"] is True
    assert state["fallback_model"] == FALLBACK_MODEL
    assert state["fallback_reason"].startswith("Primary model")


def test_no_choices_uses_fallback_and_keeps_reported_usage():
    client, calls = client_with(
        no_choices(tokens=3),
        completion("Recovered", model="provider/fallback-model:free", tokens=7),
    )

    result, state = run_with_fallback(client)

    assert result[0] == "Recovered"
    assert result[2] == 10
    assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL, FALLBACK_MODEL]
    assert state["fallback_used"] is True
    assert "no available response" in state["fallback_reason"]


def test_tool_path_error_stays_on_primary_model(monkeypatch):
    tool_call = SimpleNamespace(
        id="read-1",
        function=SimpleNamespace(
            name="Read", arguments=json.dumps({"file_path": "outside.txt"})
        ),
    )
    client, calls = client_with(
        completion(None, tool_calls=[tool_call]),
        completion("I could not read that path", tokens=4),
    )
    monkeypatch.setattr(
        main, "execute_tool",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("workspace restriction")),
    )

    result, state = run_with_fallback(client)

    assert result[0] == "I could not read that path"
    assert result[3] == 1
    assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL, PRIMARY_MODEL]
    assert calls.calls[1]["messages"][-1]["content"].startswith("Tool error:")
    assert state["fallback_used"] is False


def test_write_runs_once_when_later_completion_uses_fallback(monkeypatch):
    tool_call = SimpleNamespace(
        id="write-1",
        function=SimpleNamespace(
            name="Write",
            arguments=json.dumps({"file_path": "result.txt", "content": "done"}),
        ),
    )
    client, calls = client_with(
        completion(None, tool_calls=[tool_call], tokens=4),
        ModelHTTPError(429, "rate limit"),
        completion("Finished", model="provider/fallback-model:free", tokens=6),
    )
    executions = []

    def execute_once(received_call, workspace_root=None):
        executions.append(received_call.id)
        return "File written successfully."

    monkeypatch.setattr(main, "execute_tool", execute_once)
    result, state = run_with_fallback(client)

    assert result[0] == "Finished"
    assert result[2] == 10
    assert result[3] == 1
    assert executions == ["write-1"]
    assert [call["model"] for call in calls.calls] == [
        PRIMARY_MODEL, PRIMARY_MODEL, FALLBACK_MODEL,
    ]
    fallback_history = calls.calls[-1]["messages"]
    assert fallback_history[-1] == {
        "role": "tool", "tool_call_id": "write-1",
        "content": "File written successfully.",
    }
    assert state["fallback_used"] is True


def test_fallback_keeps_the_primary_turns_tool_budget(monkeypatch):
    first_tool = SimpleNamespace(
        id="write-1",
        function=SimpleNamespace(
            name="Write",
            arguments=json.dumps({"file_path": "result.txt", "content": "done"}),
        ),
    )
    second_tool = SimpleNamespace(
        id="delete-1",
        function=SimpleNamespace(
            name="Delete", arguments=json.dumps({"file_path": "result.txt"}),
        ),
    )
    client, calls = client_with(
        completion(None, tool_calls=[first_tool], tokens=4),
        ModelHTTPError(429, "rate limit"),
        completion(
            None,
            model="provider/fallback-model:free",
            tool_calls=[second_tool],
            tokens=6,
        ),
    )
    executions = []
    monkeypatch.setattr(
        main,
        "execute_tool",
        lambda tool_call, workspace_root=None: executions.append(tool_call.id) or "done",
    )

    result, state = run_with_fallback(client, max_tool_calls=1)

    assert result[0] == "Agent stopped safely after reaching the tool-call limit."
    assert result[2:4] == (10, 1)
    assert executions == ["write-1"]
    assert [call["model"] for call in calls.calls] == [
        PRIMARY_MODEL, PRIMARY_MODEL, FALLBACK_MODEL,
    ]
    assert state["fallback_used"] is True


def test_no_configured_fallback_means_no_retry():
    client, calls = client_with(ModelHTTPError(429, "rate limit"))

    with pytest.raises(ModelHTTPError):
        main.run_turn(
            client,
            [{"role": "user", "content": "hello"}],
            FALLBACK_MODEL,
        )

    assert [call["model"] for call in calls.calls] == [FALLBACK_MODEL]


def test_authentication_and_programming_errors_do_not_fallback():
    for error in (ModelHTTPError(401, "invalid API key"), RuntimeError("code bug")):
        client, calls = client_with(error)
        with pytest.raises(type(error)):
            run_with_fallback(client)
        assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL]


def test_primary_and_fallback_failure_returns_sanitized_error_without_persistence(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "fallback.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    client, calls = client_with(
        ModelHTTPError(429, "secret primary response"),
        ModelHTTPError(503, "secret fallback response"),
    )
    monkeypatch.setattr(api, "client", client)

    response = TestClient(api.app).post("/chat", json={
        "chat_id": "chat-1", "prompt": "Fix this Python bug", "model": "auto",
    })

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Primary model and OpenRouter fallback are currently unavailable. "
            "Please try again shortly."
        )
    }
    assert "secret" not in response.text
    assert database.get_messages("chat-1") == []
    assert calls.calls[-1]["model"] == FALLBACK_MODEL


def test_successful_api_fallback_reports_metadata_and_persists_turn(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "fallback-success.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    monkeypatch.setattr(
        api,
        "select_model",
        lambda prompt: (PRIMARY_MODEL, "debugging", "Benchmark winner."),
    )
    client, calls = client_with(
        ModelHTTPError(429, "rate limit"),
        completion("Recovered", model="provider/fallback-model:free", tokens=7),
    )
    monkeypatch.setattr(api, "client", client)

    response = TestClient(api.app).post("/chat", json={
        "chat_id": "chat-1", "prompt": "Fix this Python bug", "model": "auto",
    })

    assert response.status_code == 200
    result = response.json()
    assert result["requested_model"] == "auto"
    assert result["selected_model"] == PRIMARY_MODEL
    assert result["model"] == "provider/fallback-model:free"
    assert result["fallback_used"] is True
    assert result["fallback_model"] == FALLBACK_MODEL
    assert result["fallback_reason"] == "Primary model was rate limited."
    assert result["tokens"] == 7
    assert [call["model"] for call in calls.calls] == [PRIMARY_MODEL, FALLBACK_MODEL]
    messages = database.get_messages("chat-1")
    assert [(row["role"], row["content"]) for row in messages] == [
        ("user", "Fix this Python bug"), ("assistant", "Recovered"),
    ]
    assert messages[-1]["model_id"] == "provider/fallback-model:free"
