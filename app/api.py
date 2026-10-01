import time

from fastapi import FastAPI
from pydantic import BaseModel

from app.main import run_agent


app = FastAPI()


class ChatRequest(BaseModel):
    prompt: str


@app.post("/chat")
def chat(request: ChatRequest):
    start = time.perf_counter()
    reply, model, tokens, tool_count = run_agent(request.prompt)

    end = time.perf_counter()

    return {
        "response": reply,
        "model": model,
        "latency": round(end - start, 2),
        "tokens": tokens,
        "tool_calls": tool_count
    }