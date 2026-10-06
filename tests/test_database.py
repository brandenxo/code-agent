from app import database


def test_conversation_message_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    database.initialize_database()

    database.create_conversation("chat-1")
    database.add_message("chat-1", "user", "Hello")
    model_id = database.SEEDED_MODELS[0][2]
    database.add_message("chat-1", "assistant", "Hi", model_id)
    database.update_conversation_title("chat-1", "Greeting")

    conversations = database.get_conversations()
    messages = database.get_messages("chat-1")
    assert conversations[0]["title"] == "Greeting"
    assert [message["content"] for message in messages] == ["Hello", "Hi"]
    assert messages[1]["model_id"] == model_id
    assert messages[0]["status"] == "completed"


def test_message_status_can_be_updated(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "status.db")
    database.initialize_database()
    database.create_conversation("chat-1")
    message_id = database.add_message(
        "chat-1", "user", "Hello", status="pending"
    )

    assert database.update_message_status(message_id, "failed") is True
    assert database.get_messages("chat-1")[0]["status"] == "failed"


def test_external_benchmark_seeding_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    database.initialize_database()
    record = {
        "model_id": database.SEEDED_MODELS[0][2],
        "benchmark_name": "Verified Example",
        "score": 1.0,
        "source": "Test fixture",
        "source_url": "https://example.test/benchmark",
        "published_date": "2026-01-01",
    }

    assert database.seed_external_benchmarks([record]) == 1
    assert database.seed_external_benchmarks([record]) == 0
    assert len(database.get_external_benchmarks()) == 1
