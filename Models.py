from dataclasses import dataclass

@dataclass
class Request:
    id: int
    query: str

@dataclass
class Response:
    id: int
    worker_id: int
    result: str
    latency: float