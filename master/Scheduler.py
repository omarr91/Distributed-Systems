import copy
import logging
import os
import threading
from typing import Any


logger = logging.getLogger("master.scheduler")

ROUND_ROBIN  = "round_robin"
LEAST_LOADED = "least_loaded"
LOAD_AWARE   = "load_aware"
SUPPORTED_STRATEGIES = {ROUND_ROBIN, LEAST_LOADED, LOAD_AWARE}

MAX_LOAD_PER_WORKER = int(os.getenv("MAX_LOAD_PER_WORKER", "10"))

DEFAULT_WORKERS: dict[str, dict[str, Any]] = {
    "worker1": {"url": "http://localhost:8001", "active_requests": 0, "worker_active_requests": 0, "completed_requests": 0, "healthy": True, "consecutive_failures": 0},
    "worker2": {"url": "http://localhost:8002", "active_requests": 0, "worker_active_requests": 0, "completed_requests": 0, "healthy": True, "consecutive_failures": 0},
    "worker3": {"url": "http://localhost:8003", "active_requests": 0, "worker_active_requests": 0, "completed_requests": 0, "healthy": True, "consecutive_failures": 0},
    "worker4": {"url": "http://localhost:8004", "active_requests": 0, "worker_active_requests": 0, "completed_requests": 0, "healthy": True, "consecutive_failures": 0},
    "worker5": {"url": "http://localhost:8005", "active_requests": 0, "worker_active_requests": 0, "completed_requests": 0, "healthy": True, "consecutive_failures": 0},
}

WORKERS_URL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "workers_urls.txt"
)


def load_workers_from_file_or_env() -> dict[str, dict[str, Any]]:
    content = ""

    if os.path.exists(WORKERS_URL_FILE):
        with open(WORKERS_URL_FILE, "r") as f:
            content = f.read().strip()
        if content:
            logger.info("Loading workers from file: %s", WORKERS_URL_FILE)

    if not content and os.getenv("WORKER_URLS"):
        content = os.getenv("WORKER_URLS").strip()
        logger.info("Loading workers from WORKER_URLS env var: %s", content)

    if not content:
        logger.warning("No worker URLs found, using defaults")
        return DEFAULT_WORKERS

    workers: dict[str, dict[str, Any]] = {}
    for i, url in enumerate(content.split(","), start=1):
        url = url.strip()
        if not url:
            continue
        workers[f"worker{i}"] = {
            "url": url,
            "active_requests": 0,
            "worker_active_requests": 0,
            "completed_requests": 0,
            "healthy": True,
            "consecutive_failures": 0,
        }

    return workers if workers else DEFAULT_WORKERS


class WorkerRegistry:
    def __init__(self, workers: dict[str, dict[str, Any]], strategy: str) -> None:
        if strategy not in SUPPORTED_STRATEGIES:
            raise ValueError(
                f"Unsupported scheduler strategy '{strategy}'. "
                f"Use one of: {', '.join(sorted(SUPPORTED_STRATEGIES))}"
            )
        self._workers            = copy.deepcopy(workers)
        self._lock               = threading.RLock()
        self._strategy           = strategy
        self._round_robin_index  = 0

    def select_worker(self, exclude: set[str] | None = None) -> str | None:
        exclude = exclude or set()
        with self._lock:
            healthy_workers = [
                name for name, w in self._workers.items()
                if w["healthy"] and name not in exclude
            ]

            if not healthy_workers:
                # fall back to all workers to avoid total blackout
                all_workers = [n for n in self._workers if n not in exclude]
                if not all_workers:
                    return None
                logger.warning("No healthy workers, falling back to all: %s", all_workers)
                healthy_workers = all_workers

            # skip overloaded workers if less-loaded ones exist
            not_overloaded = [
                n for n in healthy_workers
                if self._effective_load(n) < MAX_LOAD_PER_WORKER
            ]
            candidates = not_overloaded if not_overloaded else healthy_workers

            selected = self._select_worker(candidates)
            logger.debug("Selected %s via %s from %s", selected, self._strategy, candidates)
            return selected

    def _select_worker(self, candidates: list[str]) -> str:
        if self._strategy == ROUND_ROBIN:
            return self._select_round_robin(candidates)
        if self._strategy == LEAST_LOADED:
            return min(candidates, key=lambda n: self._workers[n]["active_requests"])
        # LOAD_AWARE
        return min(candidates, key=lambda n: self._effective_load(n))

    def _select_round_robin(self, candidates: list[str]) -> str:
        worker_names = list(self._workers.keys())
        for offset in range(len(worker_names)):
            index       = (self._round_robin_index + offset) % len(worker_names)
            worker_name = worker_names[index]
            if worker_name in candidates:
                self._round_robin_index = (index + 1) % len(worker_names)
                return worker_name
        return candidates[0]

    def get_worker_url(self, worker_name: str) -> str:
        with self._lock:
            return self._workers[worker_name]["url"]

    def increment_load(self, worker_name: str) -> None:
        with self._lock:
            self._workers[worker_name]["active_requests"] += 1

    def decrement_load(self, worker_name: str) -> None:
        with self._lock:
            self._workers[worker_name]["active_requests"] = max(
                0, self._workers[worker_name]["active_requests"] - 1
            )

    def record_success(self, worker_name: str) -> None:
        with self._lock:
            self._workers[worker_name]["consecutive_failures"] = 0
            self._workers[worker_name]["completed_requests"]  += 1
            self._workers[worker_name]["healthy"]              = True

    def record_failure(self, worker_name: str, threshold: int = 5) -> None:
        with self._lock:
            self._workers[worker_name]["consecutive_failures"] += 1
            failures = self._workers[worker_name]["consecutive_failures"]
            if failures >= threshold:
                logger.warning(
                    "Worker %s failed %d times consecutively, marking unhealthy",
                    worker_name, failures
                )
                self._workers[worker_name]["healthy"] = False

    def mark_healthy(self, worker_name: str) -> None:
        self._set_health(worker_name, True)

    def mark_unhealthy(self, worker_name: str) -> None:
        self._set_health(worker_name, False)

    def update_worker_status(self, worker_name: str, status: dict[str, Any]) -> None:
        with self._lock:
            self._workers[worker_name]["healthy"] = status.get("status") == "healthy"
            self._workers[worker_name]["worker_active_requests"] = int(status.get("active_requests", 0))
            self._workers[worker_name]["completed_requests"]     = int(status.get("completed_requests", 0))

    def _set_health(self, worker_name: str, healthy: bool) -> None:
        with self._lock:
            if self._workers[worker_name]["healthy"] != healthy:
                state = "healthy" if healthy else "unhealthy"
                logger.warning("Marking worker %s as %s", worker_name, state)
            self._workers[worker_name]["healthy"] = healthy

    def _effective_load(self, worker_name: str) -> int:
        w = self._workers[worker_name]
        return max(w["active_requests"], w["worker_active_requests"])

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            snapshot = copy.deepcopy(self._workers)
            for name in snapshot:
                snapshot[name]["effective_load"] = self._effective_load(name)
            return snapshot

    def scheduler_info(self) -> dict[str, Any]:
        with self._lock:
            return {
                "strategy":             self._strategy,
                "supported_strategies": sorted(SUPPORTED_STRATEGIES),
                "worker_count":         len(self._workers),
                "healthy_count":        sum(1 for w in self._workers.values() if w["healthy"]),
            }

    def select_least_loaded(self, exclude: set[str] | None = None) -> str | None:
        return self.select_worker(exclude=exclude)


def create_default_registry() -> WorkerRegistry:
    strategy = os.getenv("SCHEDULER_STRATEGY", LOAD_AWARE)
    return WorkerRegistry(load_workers_from_file_or_env(), strategy=strategy)