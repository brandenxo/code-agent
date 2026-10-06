from app import api
from app import database
from fastapi.testclient import TestClient


def _stub_chat_storage(monkeypatch):
    monkeypatch.setattr(api, "get_conversation", lambda chat_id: {"id": chat_id})
    monkeypatch.setattr(api, "get_messages", lambda chat_id: [])
    monkeypatch.setattr(api, "save_chat_turn", lambda *args, **kwargs: None)


def test_chat_persistence_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "api.db")
    database.initialize_database()
    client = TestClient(api.app)

    created = client.post("/chats")
    assert created.status_code == 200
    chat_id = created.json()["chat_id"]

    renamed = client.patch(f"/chats/{chat_id}", json={"title": "Saved chat"})
    assert renamed.status_code == 200
    assert client.get("/chats").json()[0]["title"] == "Saved chat"
    assert client.get(f"/chats/{chat_id}/messages").json() == []


def test_delete_chat_removes_conversation_and_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "delete-chat.db")
    database.initialize_database()
    database.create_conversation("delete-me", "Temporary chat")
    database.save_chat_turn(
        "delete-me", "Question", "Answer", database.SEEDED_MODELS[0][2]
    )
    client = TestClient(api.app)

    response = client.delete("/chats/delete-me")

    assert response.status_code == 200
    assert response.json() == {"chat_id": "delete-me", "deleted": True}
    assert database.get_conversation("delete-me") is None
    assert database.get_messages("delete-me") == []
    assert client.delete("/chats/delete-me").status_code == 404


def test_manual_model_is_passed_through(monkeypatch):
    _stub_chat_storage(monkeypatch)
    seen = {}

    def fake_run_turn(client, history, model, **kwargs):
        seen["model"] = model
        seen["fallback_model"] = kwargs["fallback_model"]
        return "done", model, 10, 0, []

    monkeypatch.setattr(api, "run_turn", fake_run_turn)
    requested = "cohere/north-mini-code:free"
    result = api.chat(api.ChatRequest(chat_id="chat-1", prompt="hello", model=requested))

    assert seen["model"] == requested
    assert seen["fallback_model"] is None
    assert result["requested_model"] == requested
    assert result["selected_model"] == requested
    assert result["routing_category"] is None
    assert result["routing_reason"] == "Model selected manually."
    assert result["fallback_used"] is False
    assert result["fallback_model"] is None
    assert result["fallback_reason"] is None


def test_general_auto_prompt_uses_openrouter_free(monkeypatch):
    _stub_chat_storage(monkeypatch)
    seen = {}

    def fake_run_turn(client, history, model, **kwargs):
        seen["model"] = model
        seen["fallback_model"] = kwargs["fallback_model"]
        return "Hello!", model, 10, 0, []

    monkeypatch.setattr(api, "run_turn", fake_run_turn)
    result = api.chat(api.ChatRequest(chat_id="chat-1", prompt="hello", model="auto"))
    assert seen["model"] == "openrouter/free"
    assert seen["fallback_model"] is None
    assert result["selected_model"] == "openrouter/free"
    assert result["routing_category"] == "general"
    assert result["routing_reason"] == (
        "General conversation uses OpenRouter's free automatic model selection."
    )


def test_general_and_manual_failures_are_not_given_a_fallback(monkeypatch):
    _stub_chat_storage(monkeypatch)
    calls = []

    def fail(client, history, model, **kwargs):
        calls.append((model, kwargs["fallback_model"]))
        raise RuntimeError("model request failed")

    monkeypatch.setattr(api, "run_turn", fail)
    client = TestClient(api.app)
    requests = [
        {"chat_id": "chat-1", "prompt": "hello", "model": "auto"},
        {
            "chat_id": "chat-1", "prompt": "Fix this Python bug",
            "model": "cohere/north-mini-code:free",
        },
    ]

    for request in requests:
        response = client.post("/chat", json=request)
        assert response.status_code == 502
        assert response.json() == {"detail": "Agent request failed."}

    assert calls == [
        ("openrouter/free", None),
        ("cohere/north-mini-code:free", None),
    ]


def test_crashed_agent_does_not_persist_or_replay_failed_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "failed.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    database.save_chat_turn("chat-1", "Previous question", "Previous answer", "test/model")
    previous = [dict(row) for row in database.get_messages("chat-1")]
    previous_conversation = dict(database.get_conversation("chat-1"))
    failed_prompt = "Delete important.txt"

    def crash(client, history, model, **kwargs):
        assert [dict(row) for row in database.get_messages("chat-1")] == previous
        assert history == [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": failed_prompt},
        ]
        raise RuntimeError("provider unavailable: secret API key")

    monkeypatch.setattr(api, "run_turn", crash)
    response = TestClient(api.app).post(
        "/chat",
        json={"chat_id": "chat-1", "prompt": failed_prompt, "model": "auto"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Agent request failed."}
    assert [dict(row) for row in database.get_messages("chat-1")] == previous
    assert dict(database.get_conversation("chat-1")) == previous_conversation

    seen = {}

    def succeed(client, history, model, **kwargs):
        seen["history"] = list(history)
        return "Recovered", model, 5, 0, []

    monkeypatch.setattr(api, "run_turn", succeed)
    recovered = TestClient(api.app).post(
        "/chat",
        json={"chat_id": "chat-1", "prompt": "hello", "model": "auto"},
    )
    assert recovered.status_code == 200
    assert seen["history"] == [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
        {"role": "user", "content": "hello"},
    ]
    messages = database.get_messages("chat-1")
    assert [message["content"] for message in messages] == [
        "Previous question", "Previous answer", "hello", "Recovered",
    ]
    assert all(message["status"] == "completed" for message in messages)


def test_successful_turn_saves_both_messages_after_agent_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "success.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    selected = "cohere/north-mini-code:free"

    def succeed(client, history, model, **kwargs):
        assert database.get_messages("chat-1") == []
        assert history == [{"role": "user", "content": "New question"}]
        return "New answer", model, 15, 2, ["Reading file..."]

    monkeypatch.setattr(api, "run_turn", succeed)
    client = TestClient(api.app)
    response = client.post("/chat", json={
        "chat_id": "chat-1", "prompt": "New question", "model": selected,
    })

    assert response.status_code == 200
    result = response.json()
    assert result["response"] == "New answer"
    assert result["model"] == result["selected_model"] == selected
    assert result["requested_model"] == selected
    assert result["routing_category"] is None
    assert result["routing_reason"] == "Model selected manually."
    assert result["latency"] >= 0
    assert result["tokens"] == 15
    assert result["tool_calls"] == 2
    assert result["steps"] == ["Reading file..."]
    messages = client.get("/chats/chat-1/messages").json()
    assert [(row["role"], row["content"]) for row in messages] == [
        ("user", "New question"), ("assistant", "New answer"),
    ]
    assert messages[1]["model_id"] == selected
    assert all(row["status"] == "completed" for row in messages)


def test_assistant_insert_failure_rolls_back_entire_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "rollback.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    previous_conversation = dict(database.get_conversation("chat-1"))
    connection = database.get_connection()
    try:
        # Fail the second insert, after the user insert has already executed.
        connection.execute("""
            CREATE TRIGGER reject_assistant BEFORE INSERT ON messages
            WHEN NEW.role = 'assistant'
            BEGIN
                SELECT RAISE(ABORT, 'private database failure');
            END
        """)
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setattr(api, "run_turn", lambda client, history, model, **kwargs: (
        "Answer", model, 5, 0, [],
    ))

    response = TestClient(api.app).post("/chat", json={
        "chat_id": "chat-1", "prompt": "hello", "model": "auto",
    })
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to save chat response."}
    assert database.get_messages("chat-1") == []
    assert dict(database.get_conversation("chat-1")) == previous_conversation


def test_auto_resolves_before_run_turn(monkeypatch):
    _stub_chat_storage(monkeypatch)
    selected = "poolside/laguna-s-2.1:free"
    monkeypatch.setattr(
        api,
        "select_model",
        lambda prompt: (selected, "multi_step_tool_use", "Benchmark winner."),
    )
    seen = {}

    def fake_run_turn(client, history, model, **kwargs):
        seen["model"] = model
        seen["fallback_model"] = kwargs["fallback_model"]
        return "done", model, 10, 1, ["step"]

    monkeypatch.setattr(api, "run_turn", fake_run_turn)
    result = api.chat(api.ChatRequest(chat_id="chat-1", prompt="work", model="auto"))

    assert seen["model"] == selected
    assert seen["fallback_model"] == "openrouter/free"
    assert seen["model"] not in {"auto", "openrouter/free"}
    assert result["requested_model"] == "auto"
    assert result["selected_model"] == selected
    assert result["routing_category"] == "multi_step_tool_use"
