import asyncio
import logging

import httpx

from scheduler import WorkerRegistry


logger = logging.getLogger("master.health_checker")

#HEALTH_CHECK_INTERVAL_SECONDS = 15   # less frequent — workers are doing heavy work
HEALTH_CHECK_TIMEOUT_SECONDS  = 5    # more generous timeout
UNHEALTHY_THRESHOLD           = 5    # consecutive failures before marking unhealthy
HEALTHY_THRESHOLD             = 1    # one success to mark healthy again

# Track consecutive failures per worker
_failure_counts: dict[str, int] = {}


def start_health_checker(registry: WorkerRegistry) -> None:
    asyncio.create_task(_health_check_loop(registry))
    logger.info("Worker health checker started")


async def _health_check_loop(registry: WorkerRegistry) -> None:
    async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
        await asyncio.gather(
            *[
                _check_worker(client, registry, worker_name, worker["url"])
                for worker_name, worker in registry.snapshot().items()
            ]
        )

async def _check_worker(
    client: httpx.AsyncClient,
    registry: WorkerRegistry,
    worker_name: str,
    worker_url: str,
) -> None:
    global _failure_counts
    if worker_name not in _failure_counts:
        _failure_counts[worker_name] = 0

    try:
        response = await client.get(f"{worker_url}/status")
        response.raise_for_status()
        status_payload = response.json()

        if status_payload.get("status") == "healthy":
            # Reset failure count on success
            _failure_counts[worker_name] = 0
            registry.update_worker_status(worker_name, status_payload)
            # Re-mark healthy if it was marked unhealthy before
            registry.mark_healthy(worker_name)
        else:
            logger.warning(
                "Worker %s returned unhealthy payload: %s", worker_name, status_payload
            )
            _failure_counts[worker_name] += 1
            if _failure_counts[worker_name] >= UNHEALTHY_THRESHOLD:
                registry.mark_unhealthy(worker_name)

    except Exception as exc:
        _failure_counts[worker_name] += 1
        failures = _failure_counts[worker_name]
        logger.warning(
            "Health check failed for %s (%d/%d): %s",
            worker_name, failures, UNHEALTHY_THRESHOLD, exc
        )
        # Only mark unhealthy after consecutive failures
        if failures >= UNHEALTHY_THRESHOLD:
            registry.mark_unhealthy(worker_name)