import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from app.database import (
    add_message,
    create_conversation,
    get_conversation,
    get_conversations,
    get_messages,
    get_models,
    get_internal_benchmarks,
    get_external_benchmarks,
    summarize_internal_benchmarks,
    initialize_database,
    update_conversation_title,
)
from app.main import API_KEY, BASE_URL, run_turn
from app.router import TASK_CATEGORIES, select_model, select_model_for_category

app = FastAPI()

initialize_database()

client = OpenAI(
    api_key=API_KEY or "not-configured",
    base_url=BASE_URL,
)


class ChatRequest(BaseModel):
    chat_id: str
    prompt: str
    model: str


class ChatTitleRequest(BaseModel):
    title: str


@app.post("/chats")
def create_chat():
    chat_id = str(uuid.uuid4())

    create_conversation(chat_id)

    return {"chat_id": chat_id}


@app.get("/chats")
def list_chats():
    return [dict(conversation) for conversation in get_conversations()]


@app.get("/chats/{chat_id}/messages")
def list_chat_messages(chat_id: str):
    if get_conversation(chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return [dict(message) for message in get_messages(chat_id)]


@app.patch("/chats/{chat_id}")
def rename_chat(chat_id: str, request: ChatTitleRequest):
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if not update_conversation_title(chat_id, title[:80]):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"chat_id": chat_id, "title": title[:80]}

@app.post("/chat")
def chat(request: ChatRequest):
    if get_conversation(request.chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    requested_model = request.model
    if requested_model == "auto":
        selected_model, routing_category, routing_reason = select_model(request.prompt)
    else:
        selected_model = requested_model
        routing_category = None
        routing_reason = "Model selected manually."

    stored_messages = get_messages(request.chat_id)
    conversation_history = [
        {"role": message["role"], "content": message["content"]}
        for message in stored_messages
    ]

    add_message(request.chat_id, "user", request.prompt)
    conversation_history.append({"role": "user", "content": request.prompt})

    start = time.perf_counter()

    reply, actual_model, tokens, tool_count, steps = run_turn(
        client,
        conversation_history,
        selected_model,
    )

    end = time.perf_counter()

    add_message(request.chat_id, "assistant", reply, actual_model)
    
    return {
        "response": reply,
        "model": actual_model,
        "latency": round(end - start, 2),
        "tokens": tokens,
        "tool_calls": tool_count,
        "steps": steps,
        "routing_category": routing_category,
        "routing_reason": routing_reason,
        "requested_model": requested_model,
        "selected_model": selected_model,
    }


@app.get("/benchmarks/summary")
def benchmark_summary():
    internal_rows = get_internal_benchmarks()
    external_rows = get_external_benchmarks()
    models = []
    for model in get_models(active_only=True):
        rows = [row for row in internal_rows if row["model_id"] == model["model_id"]]
        models.append({
            "model_id": model["model_id"],
            "display_name": model["name"],
            "provider": model["provider"],
            "internal": summarize_internal_benchmarks(rows),
            "categories": {
                category: summarize_internal_benchmarks(
                    [row for row in rows if row["category"] == category]
                )
                for category in TASK_CATEGORIES
            },
            "external": [
                {key: row[key] for key in (
                    "benchmark_name", "score", "source", "source_url", "published_date"
                )}
                for row in external_rows if row["model_id"] == model["model_id"]
            ],
        })
    return {
        "models": models,
        "routing": {
            category: select_model_for_category(category)
            for category in TASK_CATEGORIES
        },
    }


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
