import copy
import logging
import threading
from typing import Any


logger = logging.getLogger("master.scheduler")


DEFAULT_WORKERS: dict[str, dict[str, Any]] = {
    "worker1": {
        "url": "http://localhost:8001",
        "active_requests": 0,
        "worker_active_requests": 0,
        "completed_requests": 0,
        "healthy": True,
    },
    "worker2": {
        "url": "http://localhost:8002",
        "active_requests": 0,
        "worker_active_requests": 0,
        "completed_requests": 0,
        "healthy": True,
    },
    "worker3": {
        "url": "http://localhost:8003",
        "active_requests": 0,
        "worker_active_requests": 0,
        "completed_requests": 0,
        "healthy": True,
    },
    "worker4": {
        "url": "http://localhost:8004",
        "active_requests": 0,
        "worker_active_requests": 0,
        "completed_requests": 0,
        "healthy": True,
    },
    "worker5": {
        "url": "http://localhost:8005",
        "active_requests": 0,
        "worker_active_requests": 0,
        "completed_requests": 0,
        "healthy": True,
    },
}


class WorkerRegistry:
    def __init__(self, workers: dict[str, dict[str, Any]]) -> None:
        self._workers = copy.deepcopy(workers)
        self._lock = threading.RLock()

    def select_least_loaded(self, exclude: set[str] | None = None) -> str | None:
        exclude = exclude or set()
        with self._lock:
            healthy_workers = [
                name
                for name, worker in self._workers.items()
                if worker["healthy"] and name not in exclude
            ]

            if not healthy_workers:
                return None

            # Load-aware scheduling: prefer real worker-reported load, while accounting
            # for this master's in-flight requests between status refreshes.
            selected = min(
                healthy_workers,
                key=lambda name: self._effective_load(name),
            )
            logger.debug("Selected worker %s from candidates %s", selected, healthy_workers)
            return selected

    def get_worker_url(self, worker_name: str) -> str:
        with self._lock:
            return self._workers[worker_name]["url"]

    def increment_load(self, worker_name: str) -> None:
        with self._lock:
            self._workers[worker_name]["active_requests"] += 1
            logger.debug(
                "Incremented %s load to %s",
                worker_name,
                self._workers[worker_name]["active_requests"],
            )

    def decrement_load(self, worker_name: str) -> None:
        with self._lock:
            self._workers[worker_name]["active_requests"] = max(
                0,
                self._workers[worker_name]["active_requests"] - 1,
            )
            logger.debug(
                "Decremented %s load to %s",
                worker_name,
                self._workers[worker_name]["active_requests"],
            )

    def mark_healthy(self, worker_name: str) -> None:
        self._set_health(worker_name, True)

    def mark_unhealthy(self, worker_name: str) -> None:
        self._set_health(worker_name, False)

    def update_worker_status(self, worker_name: str, status: dict[str, Any]) -> None:
        with self._lock:
            self._workers[worker_name]["healthy"] = status.get("status") == "healthy"
            self._workers[worker_name]["worker_active_requests"] = int(
                status.get("active_requests", 0)
            )
            self._workers[worker_name]["completed_requests"] = int(
                status.get("completed_requests", 0)
            )

    def _set_health(self, worker_name: str, healthy: bool) -> None:
        with self._lock:
            if self._workers[worker_name]["healthy"] != healthy:
                state = "healthy" if healthy else "unhealthy"
                logger.warning("Marking worker %s as %s", worker_name, state)
            self._workers[worker_name]["healthy"] = healthy

    def _effective_load(self, worker_name: str) -> int:
        worker = self._workers[worker_name]
        return max(worker["active_requests"], worker["worker_active_requests"])

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            snapshot = copy.deepcopy(self._workers)
            for worker_name, worker in snapshot.items():
                worker["effective_load"] = self._effective_load(worker_name)
            return snapshot


def create_default_registry() -> WorkerRegistry:
    return WorkerRegistry(DEFAULT_WORKERS)
