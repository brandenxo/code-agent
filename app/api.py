import time
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

from app.main import run_agent
from app.main import API_KEY, BASE_URL, run_turn
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

conversations = {}
class ChatRequest(BaseModel):
    chat_id: str
    prompt: str

@app.post("/chats")
def create_chat():
    chat_id = str(uuid.uuid4())

    conversations[chat_id] = []

    return {
        "chat_id": chat_id
        }

@app.post("/chat")
def chat(request: ChatRequest):
    conversation_history = conversations.get(request.chat_id)

    if conversation_history is None:
        return {
            "error": "Chat not found"
        }

    conversation_history.append(
        {
            "role": "user",
            "content": request.prompt,
        }
    )

    start = time.perf_counter()

    reply, model, tokens, tool_count = run_turn(
        client,
        conversation_history,
    )

    end = time.perf_counter()
    
    return {
        "response": reply,
        "model": model,
        "latency": round(end - start, 2),
        "tokens": tokens,
        "tool_calls": tool_count,
    }