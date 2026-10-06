# Code Agent

Code Agent is a small, readable coding assistant built with Python, FastAPI,
SQLite, and a vanilla HTML/CSS/JavaScript interface. It sends model requests
through OpenRouter, supports multi-step tool use, and keeps browser
conversations across restarts.

## Features

- Browser chat UI and interactive CLI
- Manual model selection or benchmark-informed automatic routing
- SQLite conversation and message persistence
- Read, Write, Delete, and direct subprocess-based Bash tools
- Tool-call and runtime safety limits
- Local benchmark harness with resumable JSON results
- Internal metrics for correctness, latency, tokens, and tool calls
- Separate storage for sourced public benchmark data

## Supported models

- NVIDIA Nemotron 3 Ultra (`nvidia/nemotron-3-ultra-550b-a55b:free`)
- Poolside Laguna S 2.1 (`poolside/laguna-s-2.1:free`)
- Cohere North Mini Code (`cohere/north-mini-code:free`)

These are currently OpenRouter free-tier model IDs. Availability and provider
limits are controlled by OpenRouter.

## Automatic routing

The browser's **Auto** option sends `auto` to this application, never to
OpenRouter. `app/router.py` classifies the prompt as code understanding,
debugging, feature implementation, refactoring, testing, or multi-step tool
use. It then compares active models using data in SQLite.

Non-coding requests, such as greetings, jokes, emails, or text rewriting, use
the `general` category and `openrouter/free` directly, without benchmark
scoring. Coding routes and their fallbacks use the three coding models above.

If an automatically selected coding model is temporarily unavailable, the
current agent turn switches once to `openrouter/free`. The fallback continues
from the existing tool history, so completed file or command operations are not
repeated. General prompts and manually selected models are not retried.

Internal benchmark evidence emphasizes correctness (60%), followed by latency
efficiency (15%), token efficiency (15%), and tool efficiency (10%). Public
benchmark scores are normalized within each benchmark before being used as a
supplemental prior. Internal evidence can carry up to 70% of the combined
decision; sparse internal evidence gives public data more influence. With no
usable data, the router uses explicit category-based fallbacks.

`internal_benchmarks` contains only measurements produced by this project's
benchmark harness. `external_benchmarks` is reserved for sourced published
results. Verified vendor-published scores and their source metadata are bundled
in `app/seed_benchmarks.py`. Seed them idempotently with:

```powershell
python -m app.seed_benchmarks
```

Import the benchmark harness's existing local results into SQLite with:

```powershell
python -m app.import_internal_results
```

The import is idempotent: unchanged model/task results are not duplicated, and
rerun results update their existing row.

## Project structure

```text
app/
  api.py                 FastAPI routes and frontend hosting
  benchmark.py           Local benchmark runner and result persistence
  database.py            SQLite schema and data helpers
  main.py                Agent loop, CLI, and execution limits
  router.py              Prompt classifier and model scoring
  seed_benchmarks.py     Verified public benchmark import list
  tools.py               Read, Write, Delete, and Bash implementations
  frontend/              Browser UI
benchmarks/fixtures/     Local benchmark tasks
tests/                   Free, local unit tests
```

## Setup

Requirements: Python 3.14+ and an OpenRouter account for model calls.

Using uv:

```powershell
uv sync
```

Or using pip:

```powershell
python -m pip install -e .
```

Set the API key before making chat or benchmark requests:

```powershell
$env:OPENROUTER_API_KEY="your-api-key"
```

On macOS or Linux, use `export OPENROUTER_API_KEY="your-api-key"`.

## Run

Start the API and its browser UI from the project root:

```powershell
python -m uvicorn app.api:app --reload
```

Then open <http://localhost:8000>. The frontend is served by FastAPI, so a
separate web server is not required.

Choose **Benchmarks** or open <http://localhost:8000/#benchmarks> to compare
internal model metrics, published external results, and current Auto picks.
The dashboard reads `GET /benchmarks/summary`; opening or refreshing it makes
no model requests and does not run benchmarks.

The CLI remains available:

```powershell
python -m app.main
```

`OPENROUTER_MODEL` optionally changes the CLI model. Browser model selection is
controlled by the dropdown and Auto router.

## Tests and benchmarks

Run all local unit tests without contacting OpenRouter:

```powershell
python -m pytest -q
```

The benchmark suite makes live model requests and may be rate-limited. Run it
only when you intentionally want those requests:

```powershell
python -m app.benchmark
```

Completed benchmark results are retained and skipped on later runs. Targeted
reruns use `--rerun=task-id:model-label`; see `app/benchmark.py` for labels.

## Current limitations

- Tool use has no human approval step, and Read/Write/Delete are not sandboxed during
  normal chat. Benchmark workspaces remain path-restricted.
- Bash starts one executable directly; shell pipelines, redirection, and other
  shell syntax are not interpreted.
- Responses do not stream, and long conversations are not summarized.
- There is no authentication, multi-user isolation, or deletion UI.
- Historical messages retain content and model ID, but not per-response latency,
  token counts, or Auto-routing explanations.
- External benchmark data must be verified and entered manually; no scraping is
  performed.
