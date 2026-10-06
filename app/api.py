import time
import uuid

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

from app.database import (
    add_message,
    create_conversation,
    get_conversation,
    get_messages,
    initialize_database,
)
from app.main import API_KEY, BASE_URL, run_turn

app = FastAPI()

initialize_database()

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


class ChatRequest(BaseModel):
    chat_id: str
    prompt: str
    model: str


@app.post("/chats")
def create_chat():
    chat_id = str(uuid.uuid4())

    create_conversation(chat_id)

    return {
        "chat_id": chat_id
        }

@app.post("/chat")
def chat(request: ChatRequest):
    if get_conversation(request.chat_id) is None:
        return {
            "error": "Chat not found"
        }

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
        request.model,
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
    }
