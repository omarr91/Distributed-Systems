import asyncio
import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from health_checker import start_health_checker
from scheduler import WorkerRegistry, create_default_registry


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("master")

REQUEST_TIMEOUT_SECONDS  = 300
MAX_RETRIES              = 10
RETRY_DELAY_SECONDS      = 3.0
MAX_CONCURRENT_REQUESTS  = 50   # queue excess requests instead of failing them

app = FastAPI(title="Distributed AI Master Node")
registry: WorkerRegistry = create_default_registry()
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


class TaskRequest(BaseModel):
    query: str


@app.on_event("startup")
async def startup() -> None:
    start_health_checker(registry)
    logger.info("Master node started with workers: %s", registry.snapshot())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/workers")
async def workers() -> dict[str, Any]:
    return {
        "scheduler": registry.scheduler_info(),
        "workers":   registry.snapshot(),
    }


@app.post("/query")
async def submit_query(request: TaskRequest) -> dict[str, Any]:
    async with _semaphore:
        return await dispatch_query(request.query)


async def dispatch_query(query: str) -> dict[str, Any]:
    payload        = {"query": query}
    failed_workers: set[str] = set()

    for attempt in range(1, MAX_RETRIES + 1):
        # reset failed workers when all have been tried so we keep retrying
        all_worker_names = set(registry.snapshot().keys())
        if failed_workers >= all_worker_names:
            logger.info("All workers tried, resetting and waiting %.1fs...", RETRY_DELAY_SECONDS)
            failed_workers.clear()
            await asyncio.sleep(RETRY_DELAY_SECONDS)

        selected_worker = registry.select_worker(exclude=failed_workers)

        if selected_worker is None:
            logger.warning(
                "No workers available on attempt %d/%d, retrying in %.1fs...",
                attempt, MAX_RETRIES, RETRY_DELAY_SECONDS
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            continue

        worker_url = registry.get_worker_url(selected_worker)
        registry.increment_load(selected_worker)
        logger.info(
            "Forwarding to %s at %s (attempt %d/%d)",
            selected_worker, worker_url, attempt, MAX_RETRIES
        )

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{worker_url}/query", json=payload)
            response.raise_for_status()
            worker_response = response.json()

            registry.record_success(selected_worker)
            return {
                "selected_worker": selected_worker,
                "worker_response": worker_response,
            }

        except Exception as exc:
            logger.warning(
                "Worker %s failed on attempt %d — %s: %s",
                selected_worker, attempt, type(exc).__name__, repr(exc)
            )
            registry.record_failure(selected_worker)
            failed_workers.add(selected_worker)
            await asyncio.sleep(RETRY_DELAY_SECONDS)

        finally:
            registry.decrement_load(selected_worker)

    raise HTTPException(status_code=503, detail="All workers failed after retries")