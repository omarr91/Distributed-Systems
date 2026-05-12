import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastapi import FastAPI
from pydantic import BaseModel, model_validator
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "facebook/opt-125m"  
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = None
model     = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model     = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
        device_map="auto"
    )
    print("Model ready.")
    yield
    del model, tokenizer

app = FastAPI(title="Simulated GPU Worker", lifespan=lifespan)

WORKER_NAME       = os.getenv("WORKER_NAME", "worker")
active_requests   = 0
completed_requests = 0
load_lock         = asyncio.Lock()


class InferRequest(BaseModel):
    prompt: str | None = None
    query:  str | None = None

    @model_validator(mode="before")
    @classmethod
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
            "worker":              WORKER_NAME,
            "status":              "healthy",
            "active_requests":     active_requests,
            "completed_requests":  completed_requests,
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

    started_at = time.perf_counter()
    try:
        model_response  = await asyncio.to_thread(run_inference, prompt)
        processing_time = time.perf_counter() - started_at
        return {
            "worker":          WORKER_NAME,
            "model":           MODEL_NAME,
            "processing_time": round(processing_time, 2),
            "result":          model_response,
        }
    finally:
        async with load_lock:
            active_requests    = max(0, active_requests - 1)
            completed_requests += 1


def run_inference(prompt: str, max_new_tokens: int = 32) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )

    new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)