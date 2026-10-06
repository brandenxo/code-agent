"""Deterministic prompt classification and benchmark-driven model routing."""

from collections import defaultdict
from statistics import mean

from app import database


SUPPORTED_MODELS = (
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "cohere/north-mini-code:free",
)

MODEL_NAMES = {
    "nvidia/nemotron-3-ultra-550b-a55b:free": "Nemotron 3 Ultra",
    "poolside/laguna-s-2.1:free": "Laguna S 2.1",
    "cohere/north-mini-code:free": "North Mini Code",
}

TASK_CATEGORIES = (
    "code_understanding", "debugging", "feature_implementation",
    "refactoring", "testing", "multi_step_tool_use",
)

# Ordered from most specific to most general.
CATEGORY_PHRASES = (
    (
        "multi_step_tool_use",
        (
            "multiple files", "across files", "run tests and fix",
            "find and implement", "diagnose and repair", "update everywhere",
            "coordinated change",
        ),
    ),
    (
        "debugging",
        ("fix bug", "broken", "crash", "error", "exception", "failing", "diagnose"),
    ),
    ("testing", ("test", "pytest", "unittest", "coverage", "write tests")),
    (
        "refactoring",
        ("refactor", "clean up", "duplicate", "simplify", "reorganize", "rename"),
    ),
    (
        "feature_implementation",
        ("implement", "add feature", "create function", "add method", "build", "support"),
    ),
    (
        "code_understanding",
        ("explain", "what does", "how does", "understand", "inspect", "summarize code"),
    ),
)

FALLBACK_MODELS = {
    "testing": "cohere/north-mini-code:free",
    "feature_implementation": "cohere/north-mini-code:free",
    "refactoring": "poolside/laguna-s-2.1:free",
    "multi_step_tool_use": "poolside/laguna-s-2.1:free",
    "debugging": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "code_understanding": "nvidia/nemotron-3-ultra-550b-a55b:free",
}


def classify_task(prompt):
    """Classify a prompt using readable, deterministic phrase matching."""
    normalized_prompt = " ".join(prompt.lower().split())
    for category, phrases in CATEGORY_PHRASES:
        if any(phrase in normalized_prompt for phrase in phrases):
            return category
    return "code_understanding"


def _normalize(values, lower_is_better=False):
    """Return min-max normalized values, treating equal values as equally strong."""
    if not values:
        return {}
    lowest, highest = min(values.values()), max(values.values())
    if lowest == highest:
        return {key: 1.0 for key in values}
    normalized = {
        key: (value - lowest) / (highest - lowest)
        for key, value in values.items()
    }
    if lower_is_better:
        return {key: 1.0 - value for key, value in normalized.items()}
    return normalized


def _internal_scores(rows, model_ids):
    grouped = defaultdict(list)
    for row in rows:
        if row["model_id"] in model_ids:
            grouped[row["model_id"]].append(row)

    correctness = {
        model_id: mean(row["success"] for row in model_rows)
        for model_id, model_rows in grouped.items()
    }
    metric_averages = {}
    for metric in ("latency", "tokens", "tool_calls"):
        metric_averages[metric] = {
            model_id: mean(
                row[metric] for row in model_rows if row[metric] is not None
            )
            for model_id, model_rows in grouped.items()
            if any(row[metric] is not None for row in model_rows)
        }

    latency = _normalize(metric_averages["latency"], lower_is_better=True)
    tokens = _normalize(metric_averages["tokens"], lower_is_better=True)
    tools = _normalize(metric_averages["tool_calls"], lower_is_better=True)
    return {
        model_id: (
            0.60 * correctness[model_id]
            + 0.15 * latency.get(model_id, 0.5)
            + 0.15 * tokens.get(model_id, 0.5)
            + 0.10 * tools.get(model_id, 0.5)
        )
        for model_id in grouped
    }


def _external_scores(rows, model_ids):
    """Normalize each public benchmark separately before averaging it."""
    raw_scores = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["model_id"] in model_ids:
            raw_scores[row["benchmark_name"]][row["model_id"]].append(row["score"])

    normalized_by_model = defaultdict(list)
    for benchmark_rows in raw_scores.values():
        benchmark_values = {
            model_id: mean(scores)
            for model_id, scores in benchmark_rows.items()
        }
        for model_id, score in _normalize(benchmark_values).items():
            normalized_by_model[model_id].append(score)
    return {
        model_id: mean(scores)
        for model_id, scores in normalized_by_model.items()
    }


def _fallback(category):
    model_id = FALLBACK_MODELS[category]
    reason = (
        f"No usable benchmark data was available, so the {category} fallback "
        f"selected {MODEL_NAMES[model_id]}."
    )
    return model_id, category, reason


def select_model(prompt):
    """Return ``(model_id, task_category, routing_reason)`` for a prompt."""
    category = classify_task(prompt)
    selection = select_model_for_category(category)
    return selection["selected_model"], category, selection["reason"]


def select_model_for_category(category):
    """Use the same routing decision for chat and the comparison dashboard."""
    if category not in TASK_CATEGORIES:
        raise ValueError(f"Unknown task category: {category}")
    try:
        active_models = {
            row["model_id"] for row in database.get_models(active_only=True)
        }
        model_ids = [model for model in SUPPORTED_MODELS if model in active_models]
        if not model_ids:
            model_ids = list(SUPPORTED_MODELS)
        internal_rows = database.get_internal_benchmarks(category=category)
        external_rows = database.get_external_benchmarks()
    except Exception:
        # Routing must remain available during first-run database setup failures.
        return _fallback_selection(category)

    internal = _internal_scores(internal_rows, model_ids)
    external = _external_scores(external_rows, model_ids)
    if not internal and not external:
        return _fallback_selection(category)

    evidence_target = max(1, len(model_ids) * 3)
    internal_confidence = min(1.0, len(internal_rows) / evidence_target)
    internal_weight = 0.70 * internal_confidence
    external_weight = 1.0 - internal_weight

    # If only one evidence source exists, let it carry the decision by itself.
    if not internal:
        internal_weight, external_weight = 0.0, 1.0
    elif not external:
        internal_weight, external_weight = 1.0, 0.0

    scores = {
        model_id: (
            internal_weight * internal.get(model_id, 0.5)
            + external_weight * external.get(model_id, 0.5)
        )
        for model_id in model_ids
    }
    selected = max(model_ids, key=lambda model_id: (scores[model_id], -model_ids.index(model_id)))
    sources = []
    if internal:
        sources.append("internal")
    if external:
        sources.append("external")
    reason = (
        f"{MODEL_NAMES[selected]} had the strongest normalized score for "
        f"{category} using {' and '.join(sources)} benchmark evidence."
    )
    return {
        "selected_model": selected,
        "display_name": MODEL_NAMES[selected],
        "reason": reason,
        "evidence_type": "benchmark",
    }


def _fallback_selection(category):
    selected, _, reason = _fallback(category)
    return {
        "selected_model": selected,
        "display_name": MODEL_NAMES[selected],
        "reason": reason,
        "evidence_type": "fallback",
    }
