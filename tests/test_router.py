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
        ("explain this Python function", "code_understanding"),
        ("fix this bug", "debugging"),
        ("write pytest tests", "testing"),
        ("update multiple files and run tests", "multi_step_tool_use"),
        ("write code to greet Jesica", "code_understanding"),
    ],
)
def test_classify_task(prompt, expected):
    assert router.classify_task(prompt) == expected


@pytest.mark.parametrize("prompt", [
    "hello", "hi", "how are you", "what can you do", "my name is jesica",
    "tell me a joke", "write a short paragraph", "summarize this sentence",
    "rewrite this text", "write me a short email", "explain photosynthesis",
    "build a good daily routine",
])
def test_general_prompts_bypass_benchmark_data_and_scoring(prompt, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("General prompts must not query or score benchmark data")

    for name in ("get_models", "get_internal_benchmarks", "get_external_benchmarks"):
        monkeypatch.setattr(router.database, name, forbidden)
    monkeypatch.setattr(router, "_internal_scores", forbidden)
    monkeypatch.setattr(router, "_external_scores", forbidden)

    assert router.select_model(prompt) == (
        "openrouter/free", "general", router.GENERAL_ROUTING_REASON,
    )


@pytest.mark.parametrize("category", router.TASK_CATEGORIES)
def test_coding_fallback_never_uses_openrouter_free(category, monkeypatch):
    monkeypatch.setattr(router.database, "get_models", lambda **kwargs: [])
    monkeypatch.setattr(router.database, "get_internal_benchmarks", lambda **kwargs: [])
    monkeypatch.setattr(router.database, "get_external_benchmarks", lambda: [])
    selection = router.select_model_for_category(category)
    assert selection["selected_model"] in router.SUPPORTED_MODELS
    assert selection["evidence_type"] == "fallback"


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
