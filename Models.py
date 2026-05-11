from dataclasses import dataclass

@dataclass
class Request:
    id: int
    query: str

@dataclass
class Response:
    selected_worker: str
    worker_response: dict