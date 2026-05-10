import copy
import logging
import os
import threading
from typing import Any


logger = logging.getLogger("master.scheduler")

ROUND_ROBIN = "round_robin"
LEAST_LOADED = "least_loaded"
LOAD_AWARE = "load_aware"
SUPPORTED_STRATEGIES = {ROUND_ROBIN, LEAST_LOADED, LOAD_AWARE}


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


def load_workers_from_file() -> dict[str, dict[str, Any]]:
    if not os.path.exists("workers_urls.txt"):
        return DEFAULT_WORKERS
    worker_urls = ""
    with open("workers_urls.txt",'r') as f:
        worker_urls = f.read()
        f.close()

    workers: dict[str, dict[str, Any]] = {}
    for i, url in enumerate(worker_urls.split(","), start=1):
        url = url.strip()
        if not url:
            continue
        name = f"worker{i}"
        workers[name] = {
            "url": url,
            "active_requests": 0,
            "worker_active_requests": 0,
            "completed_requests": 0,
            "healthy": True,
        }

    return workers


class WorkerRegistry:
    def __init__(self, workers: dict[str, dict[str, Any]], strategy: str = LOAD_AWARE) -> None:
        if strategy not in SUPPORTED_STRATEGIES:
            raise ValueError(
                f"Unsupported scheduler strategy '{strategy}'. "
                f"Use one of: {', '.join(sorted(SUPPORTED_STRATEGIES))}"
            )

        self._workers = copy.deepcopy(workers)
        self._lock = threading.RLock()
        self._strategy = strategy
        self._round_robin_index = 0

    def select_worker(self, exclude: set[str] | None = None) -> str | None:
        exclude = exclude or set()
        with self._lock:
            healthy_workers = [
                name
                for name, worker in self._workers.items()
                if worker["healthy"] and name not in exclude
            ]

            if not healthy_workers:
                return None

            selected = self._select_worker(healthy_workers)
            logger.debug(
                "Selected worker %s using %s from candidates %s",
                selected,
                self._strategy,
                healthy_workers,
            )
            return selected

    def select_least_loaded(self, exclude: set[str] | None = None) -> str | None:
        return self.select_worker(exclude=exclude)

    def _select_worker(self, healthy_workers: list[str]) -> str:
        if self._strategy == ROUND_ROBIN:
            return self._select_round_robin(healthy_workers)

        if self._strategy == LEAST_LOADED:
            return min(
                healthy_workers,
                key=lambda name: self._workers[name]["active_requests"],
            )

        return min(
            healthy_workers,
            key=lambda name: self._effective_load(name),
        )

    def _select_round_robin(self, healthy_workers: list[str]) -> str:
        worker_names = list(self._workers.keys())

        for offset in range(len(worker_names)):
            index = (self._round_robin_index + offset) % len(worker_names)
            worker_name = worker_names[index]
            if worker_name in healthy_workers:
                self._round_robin_index = (index + 1) % len(worker_names)
                return worker_name

        return healthy_workers[0]

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

    def scheduler_info(self) -> dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "supported_strategies": sorted(SUPPORTED_STRATEGIES),
            }


def create_default_registry() -> WorkerRegistry:
    strategy = os.getenv("SCHEDULER_STRATEGY", LOAD_AWARE)
    return WorkerRegistry(load_workers_from_file(), strategy=strategy)
