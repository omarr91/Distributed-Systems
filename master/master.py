import logging
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from HealthChecker import start_health_checker
from Scheduler import WorkerRegistry, create_default_registry


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("master")

REQUEST_TIMEOUT_SECONDS = 30

app = FastAPI(title="Distributed AI Master Node")
registry: WorkerRegistry = create_default_registry()


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
    return registry.snapshot()


@app.post("/query")
async def submit_query(request: TaskRequest) -> dict[str, Any]:
    return await dispatch_query(request.query)


async def dispatch_query(query: str) -> dict[str, Any]:
    payload = {"query": query}
    failed_workers: set[str] = set()

    while True:
        selected_worker = registry.select_least_loaded(exclude=failed_workers)
        if selected_worker is None:
            logger.warning("No healthy workers available for request")
            raise HTTPException(status_code=503, detail="No healthy workers available")

        worker_url = registry.get_worker_url(selected_worker)
        registry.increment_load(selected_worker)
        logger.info("Forwarding task to %s at %s", selected_worker, worker_url)

        try:
            response = await run_in_threadpool(
                requests.post,
                f"{worker_url}/query",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            worker_response = response.json()

            return {
                "selected_worker": selected_worker,
                "worker_response": worker_response,
            }
        except (requests.RequestException, ValueError) as exc:
            logger.exception("Worker %s failed during inference: %s", selected_worker, exc)
            registry.mark_unhealthy(selected_worker)
            failed_workers.add(selected_worker)
        finally:
            registry.decrement_load(selected_worker)
