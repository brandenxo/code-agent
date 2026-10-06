"""Import locally measured benchmark JSON results into SQLite."""

import json
import sys
from pathlib import Path

from app.database import initialize_database, upsert_internal_benchmark


DEFAULT_RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
REQUIRED_FIELDS = {"task_id", "category", "success"}


def load_results(results_path):
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Results file not found: {results_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in results file: {results_path}") from error

    if not isinstance(results, list):
        raise ValueError("Benchmark results must be a JSON list")
    return results


def import_internal_results(results_path=DEFAULT_RESULTS_PATH):
    """Import completed results and return counts by import action."""
    results_path = Path(results_path)
    results = load_results(results_path)
    initialize_database()
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError(f"Result at index {index} must be an object")
        if not result.get("actual_model"):
            counts["skipped"] += 1
            continue

        missing = REQUIRED_FIELDS.difference(result)
        if missing:
            fields = ", ".join(sorted(missing))
            raise ValueError(f"Completed result at index {index} is missing: {fields}")

        _, action = upsert_internal_benchmark(
            model_id=result["actual_model"],
            task_id=result["task_id"],
            category=result["category"],
            success=result["success"],
            latency=result.get("latency"),
            tokens=result.get("tokens"),
            tool_calls=result.get("tool_calls"),
            run_date=result.get("run_date"),
        )
        counts[action] += 1

    return counts


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) > 1:
        raise ValueError("Usage: python -m app.import_internal_results [results.json]")
    results_path = Path(arguments[0]) if arguments else DEFAULT_RESULTS_PATH
    counts = import_internal_results(results_path)
    print(
        "Internal benchmark import complete: "
        f"{counts['inserted']} inserted, {counts['updated']} updated, "
        f"{counts['unchanged']} unchanged, {counts['skipped']} incomplete skipped."
    )


if __name__ == "__main__":
    main()
