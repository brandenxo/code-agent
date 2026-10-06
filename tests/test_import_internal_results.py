import json

from app import database
from app.import_internal_results import import_internal_results


def test_internal_result_import_is_idempotent_and_updates_reruns(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "import.db")
    results_path = tmp_path / "results.json"
    model_id = database.SEEDED_MODELS[0][2]
    completed = {
        "task_id": "debugging-01",
        "category": "debugging",
        "actual_model": model_id,
        "success": True,
        "latency": 3.0,
        "tokens": 100,
        "tool_calls": 2,
    }
    results_path.write_text(
        json.dumps([completed, {"task_id": "incomplete", "actual_model": ""}]),
        encoding="utf-8",
    )

    first = import_internal_results(results_path)
    second = import_internal_results(results_path)

    assert first == {"inserted": 1, "updated": 0, "unchanged": 0, "skipped": 1}
    assert second == {"inserted": 0, "updated": 0, "unchanged": 1, "skipped": 1}

    completed["latency"] = 2.5
    results_path.write_text(json.dumps([completed]), encoding="utf-8")
    third = import_internal_results(results_path)
    rows = database.get_internal_benchmarks(model_id=model_id)

    assert third == {"inserted": 0, "updated": 1, "unchanged": 0, "skipped": 0}
    assert len(rows) == 1
    assert rows[0]["latency"] == 2.5
