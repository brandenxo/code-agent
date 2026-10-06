import pytest

from app import router


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Diagnose this failing exception", "debugging"),
        ("Write tests with pytest", "testing"),
        ("Refactor this duplicate code", "refactoring"),
        ("Implement a new function", "feature_implementation"),
        ("Explain how this code works", "code_understanding"),
        ("Run tests and fix the problem across files", "multi_step_tool_use"),
    ],
)
def test_classify_task(prompt, expected):
    assert router.classify_task(prompt) == expected


def test_fallback_when_benchmark_data_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        router.database,
        "get_models",
        lambda active_only=False: [
            {"model_id": model_id} for model_id in router.SUPPORTED_MODELS
        ],
    )
    monkeypatch.setattr(router.database, "get_internal_benchmarks", lambda **kwargs: [])
    monkeypatch.setattr(router.database, "get_external_benchmarks", lambda: [])

    model_id, category, reason = router.select_model("Refactor this module")

    assert model_id == "poolside/laguna-s-2.1:free"
    assert category == "refactoring"
    assert "No usable benchmark data" in reason


def test_internal_correctness_has_the_strongest_influence(monkeypatch):
    models = list(router.SUPPORTED_MODELS)
    monkeypatch.setattr(
        router.database,
        "get_models",
        lambda active_only=False: [{"model_id": model_id} for model_id in models],
    )
    rows = []
    for model_id, success, latency in (
        (models[0], 1, 20.0),
        (models[1], 0, 1.0),
        (models[2], 0, 2.0),
    ):
        rows.extend(
            {
                "model_id": model_id,
                "success": success,
                "latency": latency,
                "tokens": 100,
                "tool_calls": 1,
            }
            for _ in range(3)
        )
    monkeypatch.setattr(
        router.database, "get_internal_benchmarks", lambda **kwargs: rows
    )
    monkeypatch.setattr(router.database, "get_external_benchmarks", lambda: [])

    selected, category, _ = router.select_model("Fix bug in the parser")

    assert selected == models[0]
    assert category == "debugging"
