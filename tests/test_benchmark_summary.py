import pytest
from fastapi.testclient import TestClient

from app import api, database
from app.router import TASK_CATEGORIES, select_model_for_category


@pytest.fixture
def summary_client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "summary.db")
    database.initialize_database()
    # Any accidental agent execution during a summary request fails locally.
    def forbidden(*args, **kwargs):
        pytest.fail("Benchmark summary must not run the agent")
    monkeypatch.setattr(api, "run_turn", forbidden)
    return TestClient(api.app)


def test_summary_counts_averages_external_and_routing(summary_client):
    model_id = database.SEEDED_MODELS[0][2]
    database.add_internal_benchmark(model_id, "first", "debugging", True, 10, 100, 2)
    database.add_internal_benchmark(model_id, "second", "debugging", False, 20, 300, 4)
    database.add_internal_benchmark(model_id, "third", "testing", True, 30, 500, 6)
    database.add_external_benchmark(
        model_id, "Published test fixture", 55.0, "Fixture publisher",
        "https://example.test/results", "2026-01-01",
    )

    response = summary_client.get("/benchmarks/summary")
    assert response.status_code == 200
    data = response.json()
    assert {model["model_id"] for model in data["models"]} == {
        model[2] for model in database.SEEDED_MODELS
    }
    model = next(model for model in data["models"] if model["model_id"] == model_id)
    assert model["display_name"] == "Nemotron 3 Ultra"
    assert model["provider"] == "NVIDIA"
    assert model["internal"] == {
        "runs": 3, "success_rate": pytest.approx(2 / 3),
        "avg_latency": 20, "avg_tokens": 300, "avg_tool_calls": 4,
    }
    assert model["categories"]["debugging"] == {
        "runs": 2, "success_rate": 0.5,
        "avg_latency": 15, "avg_tokens": 200, "avg_tool_calls": 3,
    }
    assert model["external"] == [{
        "benchmark_name": "Published test fixture", "score": 55.0,
        "source": "Fixture publisher", "source_url": "https://example.test/results",
        "published_date": "2026-01-01",
    }]
    assert set(data["routing"]) == set(TASK_CATEGORIES)
    for category in TASK_CATEGORIES:
        assert data["routing"][category] == select_model_for_category(category)
        assert data["routing"][category]["evidence_type"] == "benchmark"


def test_summary_missing_data_and_inactive_models(summary_client):
    model_id = database.SEEDED_MODELS[0][2]
    connection = database.get_connection()
    try:
        connection.execute("UPDATE models SET active = 0 WHERE model_id = ?", (model_id,))
        connection.commit()
    finally:
        connection.close()

    response = summary_client.get("/benchmarks/summary")
    assert response.status_code == 200
    data = response.json()
    assert len(data["models"]) == 2
    assert model_id not in {model["model_id"] for model in data["models"]}
    for model in data["models"]:
        assert model["internal"]["runs"] == 0
        assert model["internal"]["success_rate"] is None
        assert model["internal"]["avg_latency"] is None
        assert model["internal"]["avg_tokens"] is None
        assert model["internal"]["avg_tool_calls"] is None
        assert set(model["categories"]) == set(TASK_CATEGORIES)
        assert model["external"] == []
    assert all(row["evidence_type"] == "fallback" for row in data["routing"].values())
