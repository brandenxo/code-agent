import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

from app.database import initialize_database, upsert_internal_benchmark
from app.main import API_KEY, BASE_URL, run_turn


MODELS = {
    "Nemotron": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "Laguna": "poolside/laguna-s-2.1:free",
    "North Mini": "cohere/north-mini-code:free",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "benchmarks" / "fixtures"
WORKSPACES_DIR = PROJECT_ROOT / "benchmarks" / "workspaces"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
TEST_COMMAND = "python -m pytest -q"
REQUEST_DELAY = 2.0
MAX_RETRIES = 5
RETRY_BACKOFF = 30.0


def task(task_id, name, category, prompt, fixture, test_command=TEST_COMMAND,
         expected_strings=None):
    return {
        "id": task_id,
        "name": name,
        "category": category,
        "prompt": prompt,
        "fixture": fixture,
        "test_command": test_command,
        "expected_strings": expected_strings or [],
    }


TASKS = [
    task("understanding-01", "Identify timeout configuration", "code_understanding",
         "Inspect the files and explain the default timeout and the environment variable that overrides it. Do not modify files.",
         "understanding_01", None, ["30", "AGENT_TIMEOUT"]),
    task("understanding-02", "Trace an order total", "code_understanding",
         "Inspect all relevant files. What numeric total does sample_order() produce, and why? Do not modify files.",
         "understanding_02", None, ["18.0", "discount"]),
    task("understanding-03", "Find valid job transitions", "code_understanding",
         "Read the project and list the valid status transition path from a new job through completion. Do not modify files.",
         "understanding_03", None, ["pending", "running", "complete"]),
    task("debugging-01", "Fix an off-by-one error", "debugging",
         "Fix the off-by-one bug in ranges.py, then run the tests.", "debugging_01"),
    task("debugging-02", "Fix empty-list handling", "debugging",
         "Fix stats.py so empty input is handled as documented, then run the tests.", "debugging_02"),
    task("debugging-03", "Fix inventory updates", "debugging",
         "Diagnose and fix the dictionary update bug in inventory.py. Run the tests.", "debugging_03"),
    task("feature-01", "Implement average", "feature_implementation",
         "Implement the TODO in averages.py according to its docstring. Run the tests.", "feature_01"),
    task("feature-02", "Add username validation", "feature_implementation",
         "Implement validate_username() according to its docstring. Run the tests.", "feature_02"),
    task("feature-03", "Add catalog search", "feature_implementation",
         "Implement Catalog.search() according to its docstring. Run the tests.", "feature_03"),
    task("refactoring-01", "Extract email normalization", "refactoring",
         "Refactor the duplicated email normalization into one helper and make both call sites consistent. Run the tests.",
         "refactoring_01"),
    task("refactoring-02", "Unify discount logic", "refactoring",
         "Refactor the duplicated discount calculations into one helper while fixing their inconsistent behavior. Run the tests.",
         "refactoring_02"),
    task("refactoring-03", "Unify display-name formatting", "refactoring",
         "Remove duplicated name-formatting logic with a shared helper and make both outputs consistent. Run the tests.",
         "refactoring_03"),
    task("testing-01", "Write calculator tests", "testing",
         "Create tests/test_calculator.py using pytest. Cover normal division and division by zero, then run the tests.",
         "testing_01"),
    task("testing-02", "Write slug tests", "testing",
         "Create tests/test_slug.py using pytest. Cover words, punctuation, and empty input, then run the tests.",
         "testing_02"),
    task("testing-03", "Write chunking tests", "testing",
         "Create tests/test_chunks.py using pytest. Cover even chunks, a final partial chunk, and invalid size, then run the tests.",
         "testing_03"),
    task("tool-use-01", "Find and implement a TODO", "multi_step_tool_use",
         "Inspect the project, find the unimplemented TODO, implement it, and run the full test suite.",
         "tool_use_01"),
    task("tool-use-02", "Diagnose and repair a failing suite", "multi_step_tool_use",
         "Run the tests, diagnose the failure, fix the production code, and rerun the tests to verify the repair.",
         "tool_use_02"),
    task("tool-use-03", "Coordinate a configuration rename", "multi_step_tool_use",
         "Inspect the multiple modules and replace the old timeout_seconds setting with request_timeout everywhere needed. Run the tests.",
         "tool_use_03"),
]


def prepare_workspace(benchmark_task):
    fixture = FIXTURES_DIR / benchmark_task["fixture"]
    if not fixture.is_dir():
        raise FileNotFoundError(f"Missing fixture: {fixture}")

    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(
        prefix=f'{benchmark_task["id"]}-', dir=WORKSPACES_DIR
    ))
    shutil.copytree(fixture, workspace, dirs_exist_ok=True)
    return workspace


def score_tests(command, workspace):
    arguments = command.split()
    arguments[0] = sys.executable
    completed = subprocess.run(
        arguments, cwd=workspace, capture_output=True, text=True, timeout=120
    )
    output = completed.stdout + "\n" + completed.stderr
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) errors?", output)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    failed += int(error_match.group(1)) if error_match else 0
    if completed.returncode and failed == 0:
        failed = 1
    return completed.returncode == 0 and passed > 0, passed, failed


def score_response(response, expected_strings):
    response_lower = response.lower()
    passed = sum(value.lower() in response_lower for value in expected_strings)
    return passed == len(expected_strings), passed, len(expected_strings) - passed


def save_results(results):
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")


def load_results():
    if not RESULTS_PATH.exists():
        return []

    try:
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid results file: {RESULTS_PATH}") from error

    if not isinstance(results, list):
        raise RuntimeError(f"Results file must contain a JSON list: {RESULTS_PATH}")
    return results


def copy_result_to_database(result):
    """Idempotently copy one completed JSON benchmark result into SQLite."""
    if not result.get("actual_model"):
        raise ValueError("Only completed benchmark results can be copied")

    initialize_database()
    row_id, _ = upsert_internal_benchmark(
        model_id=result["actual_model"],
        task_id=result["task_id"],
        category=result["category"],
        success=result["success"],
        latency=result.get("latency"),
        tokens=result.get("tokens"),
        tool_calls=result.get("tool_calls"),
    )
    return row_id


def result_key(result):
    return result["task_id"], result["requested_model"]


def upsert_result(results, new_result):
    key = result_key(new_result)
    results[:] = [result for result in results if result_key(result) != key]
    results.append(new_result)


def is_rate_limited(result):
    response = result["response"].lower()
    return "rate limit" in response or "error code: 429" in response


def run_one(client, benchmark_task, requested_model):
    workspace = prepare_workspace(benchmark_task)
    started = time.perf_counter()
    try:
        files = sorted(
            str(path.relative_to(workspace)).replace("\\", "/")
            for path in workspace.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        instructions = [
            benchmark_task["prompt"],
            "All paths are relative to an isolated workspace.",
            f"Workspace files: {', '.join(files)}.",
        ]
        if benchmark_task["test_command"]:
            instructions.append(
                f'Use Bash only for this test command: {benchmark_task["test_command"]}.'
            )
        history = [{"role": "user", "content": "\n".join(instructions)}]
        response, actual_model, tokens, tool_calls, steps = run_turn(
            client, history, requested_model, workspace_root=workspace
        )
        latency = round(time.perf_counter() - started, 2)
        if benchmark_task["test_command"]:
            success, tests_passed, tests_failed = score_tests(
                benchmark_task["test_command"], workspace
            )
        else:
            success, tests_passed, tests_failed = score_response(
                response, benchmark_task["expected_strings"]
            )

        return {
            "task_id": benchmark_task["id"],
            "task_name": benchmark_task["name"],
            "category": benchmark_task["category"],
            "requested_model": requested_model,
            "actual_model": actual_model,
            "success": success,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "latency": latency,
            "tokens": tokens,
            "tool_calls": tool_calls,
            "steps": steps,
            "response": response,
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def print_summary(results):
    print("\nOVERALL")
    print(f'{"MODEL":<14} {"PASSED":>6} {"TOTAL":>6} {"SUCCESS %":>10} '
          f'{"AVG LATENCY":>12} {"AVG TOKENS":>11} {"AVG TOOLS":>9}')
    for label, model in MODELS.items():
        rows = [row for row in results if row["requested_model"] == model]
        total = len(rows)
        passed = sum(row["success"] for row in rows)
        print(
            f"{label:<14} {passed:>6} {total:>6} "
            f"{(100 * passed / total if total else 0):>9.1f}% "
            f"{(sum(row['latency'] for row in rows) / total if total else 0):>11.2f}s "
            f"{(sum(row['tokens'] for row in rows) / total if total else 0):>11.1f} "
            f"{(sum(row['tool_calls'] for row in rows) / total if total else 0):>9.1f}"
        )

    grouped = defaultdict(list)
    for row in results:
        grouped[row["category"]].append(row)
    for category in dict.fromkeys(item["category"] for item in TASKS):
        print(f"\n{category.replace('_', ' ').upper()}")
        for label, model in MODELS.items():
            rows = [row for row in grouped[category] if row["requested_model"] == model]
            print(f"{label}: {sum(row['success'] for row in rows)}/{len(rows)}")


def error_result(benchmark_task, model, error, latency):
    return {
        "task_id": benchmark_task["id"],
        "task_name": benchmark_task["name"],
        "category": benchmark_task["category"],
        "requested_model": model,
        "actual_model": "",
        "success": False,
        "tests_passed": 0,
        "tests_failed": 1,
        "latency": latency,
        "tokens": 0,
        "tool_calls": 0,
        "steps": [],
        "response": f"Benchmark error: {error}",
    }


def parse_rerun_pairs(arguments):
    """Turn --rerun task-id:model-label arguments into benchmark keys."""
    labels = {label.lower(): model for label, model in MODELS.items()}
    pairs = set()
    for value in arguments:
        try:
            task_id, label = value.rsplit(":", 1)
        except ValueError as error:
            raise ValueError(
                f"Invalid --rerun value {value!r}; use task-id:model-label."
            ) from error
        if task_id not in {item["id"] for item in TASKS}:
            raise ValueError(f"Unknown benchmark task: {task_id}")
        model = labels.get(label.lower())
        if model is None:
            raise ValueError(
                f"Unknown model label: {label}. Use one of: {', '.join(MODELS)}"
            )
        pairs.add((task_id, model))
    return pairs


def run_benchmark(rerun_pairs=None):
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    results = load_results()
    completed = {
        result_key(result)
        for result in results
        if result.get("actual_model")
    }
    if completed:
        print(f"Resuming: {len(completed)} completed runs will be skipped.")
    if rerun_pairs:
        print(f"Targeted rerun: {len(rerun_pairs)} selected run(s).")

    for benchmark_task in TASKS:
        print(f'\n[{benchmark_task["id"]}] {benchmark_task["name"]}')
        for label, model in MODELS.items():
            key = benchmark_task["id"], model
            if rerun_pairs is not None and key not in rerun_pairs:
                continue
            if key in completed and (rerun_pairs is None or key not in rerun_pairs):
                print(f"  Skipping {label}: already completed.")
                continue

            print(f"  Running {label}...", end="", flush=True)
            for attempt in range(MAX_RETRIES + 1):
                started = time.perf_counter()
                try:
                    result = run_one(client, benchmark_task, model)
                except Exception as error:
                    result = error_result(
                        benchmark_task, model, error, round(time.perf_counter() - started, 2)
                    )
                if not is_rate_limited(result) or attempt == MAX_RETRIES:
                    break
                wait = RETRY_BACKOFF * (attempt + 1)
                print(f" rate limited, retrying in {wait:.0f}s...", end="", flush=True)
                time.sleep(wait)

            upsert_result(results, result)
            save_results(results)
            print(" PASS" if result["success"] else " FAIL")
            if result.get("success"):
                completed.add(key)
            if is_rate_limited(result):
                print("Rate limit reached after retries. Stopping without attempting more runs.")
                print_summary(results)
                print(f"\nRaw results saved to {RESULTS_PATH}")
                return

            time.sleep(REQUEST_DELAY)

    print_summary(results)
    print(f"\nRaw results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    rerun_pairs = parse_rerun_pairs(
        argument.split("=", 1)[1]
        for argument in sys.argv[1:]
        if argument.startswith("--rerun=")
    )
    unknown_arguments = [
        argument for argument in sys.argv[1:]
        if not argument.startswith("--rerun=")
    ]
    if unknown_arguments:
        raise ValueError(f"Unknown argument(s): {', '.join(unknown_arguments)}")
    run_benchmark(rerun_pairs=rerun_pairs or None)
