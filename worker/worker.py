import asyncio
import os
import random
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, root_validator


app = FastAPI(title="Simulated GPU Worker")

WORKER_NAME = os.getenv("WORKER_NAME", "worker")
MIN_PROCESSING_SECONDS = float(os.getenv("MIN_PROCESSING_SECONDS", "1"))
MAX_PROCESSING_SECONDS = float(os.getenv("MAX_PROCESSING_SECONDS", "3"))
active_requests = 0
completed_requests = 0
load_lock = asyncio.Lock()


class InferRequest(BaseModel):
    prompt: str | None = None
    query: str | None = None

    @root_validator(pre=True)
    def require_prompt_or_query(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("prompt") and values.get("query"):
            values["prompt"] = values["query"]
        if not values.get("prompt"):
            raise ValueError("prompt or query is required")
        return values


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/status")
async def status() -> dict[str, Any]:
    async with load_lock:
        return {
            "worker": WORKER_NAME,
            "status": "healthy",
            "active_requests": active_requests,
            "completed_requests": completed_requests,
        }


@app.post("/infer")
async def infer(request: InferRequest) -> dict[str, Any]:
    return await process_task(request.prompt)


@app.post("/tasks")
async def create_task(request: InferRequest) -> dict[str, Any]:
    return await process_task(request.prompt)


@app.post("/query")
async def submit_query(request: InferRequest) -> dict[str, Any]:
    return await process_task(request.prompt)


async def process_task(prompt: str) -> dict[str, Any]:
    global active_requests, completed_requests

    async with load_lock:
        active_requests += 1

    processing_time = random.uniform(MIN_PROCESSING_SECONDS, MAX_PROCESSING_SECONDS)
    try:
        await asyncio.sleep(processing_time)

        return {
            "worker": WORKER_NAME,
            "processing_time": round(processing_time, 2),
            "result": f"Processed: {prompt}",
        }
    finally:
        async with load_lock:
            active_requests = max(0, active_requests - 1)
            completed_requests += 1
