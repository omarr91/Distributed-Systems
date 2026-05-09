import asyncio
import logging

import requests

from Scheduler import WorkerRegistry


logger = logging.getLogger("master.health_checker")

HEALTH_CHECK_INTERVAL_SECONDS = 5
HEALTH_CHECK_TIMEOUT_SECONDS = 2


def start_health_checker(registry: WorkerRegistry) -> None:
    asyncio.create_task(_health_check_loop(registry))
    logger.info("Worker health checker started")


async def _health_check_loop(registry: WorkerRegistry) -> None:
    while True:
        await asyncio.gather(
            *[
                _check_worker(registry, worker_name, worker["url"])
                for worker_name, worker in registry.snapshot().items()
            ]
        )
        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)


async def _check_worker(registry: WorkerRegistry, worker_name: str, worker_url: str) -> None:
    try:
        response = await asyncio.to_thread(
            requests.get,
            f"{worker_url}/status",
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        status_payload = response.json()
        if status_payload.get("status") == "healthy":
            registry.update_worker_status(worker_name, status_payload)
        else:
            logger.warning("Worker %s returned unhealthy payload: %s", worker_name, status_payload)
            registry.mark_unhealthy(worker_name)
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Health check failed for %s: %s", worker_name, exc)
        registry.mark_unhealthy(worker_name)
