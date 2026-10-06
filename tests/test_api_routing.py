from app import api
from app import database
from fastapi.testclient import TestClient


def _stub_chat_storage(monkeypatch):
    monkeypatch.setattr(api, "get_conversation", lambda chat_id: {"id": chat_id})
    monkeypatch.setattr(api, "get_messages", lambda chat_id: [])
    monkeypatch.setattr(api, "add_message", lambda *args, **kwargs: None)


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


def test_manual_model_is_passed_through(monkeypatch):
    _stub_chat_storage(monkeypatch)
    seen = {}

    def fake_run_turn(client, history, model):
        seen["model"] = model
        return "done", model, 10, 0, []

    monkeypatch.setattr(api, "run_turn", fake_run_turn)
    requested = "cohere/north-mini-code:free"
    result = api.chat(api.ChatRequest(chat_id="chat-1", prompt="hello", model=requested))

    assert seen["model"] == requested
    assert result["requested_model"] == requested
    assert result["selected_model"] == requested
    assert result["routing_category"] is None
    assert result["routing_reason"] == "Model selected manually."


def test_auto_resolves_before_run_turn(monkeypatch):
    _stub_chat_storage(monkeypatch)
    selected = "poolside/laguna-s-2.1:free"
    monkeypatch.setattr(
        api,
        "select_model",
        lambda prompt: (selected, "multi_step_tool_use", "Benchmark winner."),
    )
    seen = {}

    def fake_run_turn(client, history, model):
        seen["model"] = model
        return "done", model, 10, 1, ["step"]

    monkeypatch.setattr(api, "run_turn", fake_run_turn)
    result = api.chat(api.ChatRequest(chat_id="chat-1", prompt="work", model="auto"))

    assert seen["model"] == selected
    assert seen["model"] not in {"auto", "openrouter/free"}
    assert result["requested_model"] == "auto"
    assert result["selected_model"] == selected
    assert result["routing_category"] == "multi_step_tool_use"
