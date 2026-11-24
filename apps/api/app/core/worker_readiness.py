"""Bounded, cached Celery control-plane observation for the required task queue.

A reply establishes that one broker-connected worker reports the configured queue
and core tasks, plus the patch task when proposals are enabled. It is not proof of
dispatcher health or task completion. A busy solo worker may be unable to reply within
the timeout and is considered unavailable.
"""
import threading
import time

from celery import Celery

_REQUIRED_TASKS = frozenset({"ingest_issue", "sync_repository", "index_repository", "investigate_issue"})


def _observe_worker(redis_url: str, queue: str, require_patch: bool = False) -> bool:
    client = Celery("repopilot-readiness", broker=redis_url)
    client.conf.update(
        broker_connection_timeout=0.5,
        broker_connection_retry=False,
        broker_transport_options={"socket_connect_timeout": 0.5, "socket_timeout": 2.5,
                                  "retry_policy": {"max_retries": 0}},
    )
    try:
        inspector = client.control.inspect(timeout=1.0)
        queues = inspector.active_queues() or {}
        eligible = {name for name, entries in queues.items() if isinstance(entries, list)
                    and any(isinstance(item, dict) and item.get("name") == queue for item in entries)}
        if not eligible:
            return False
        tasks = inspector.registered() or {}
        required = _REQUIRED_TASKS | ({"process_patch_proposal"} if require_patch else set())
        return any(required.issubset(set(tasks.get(name) or [])) for name in eligible)
    except Exception:
        return False
    finally:
        client.close()


class WorkerReadiness:
    def __init__(self, ttl: float = 3.0):
        self._ttl = ttl
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str, bool], tuple[float, bool]] = {}

    def check(self, redis_url: str, queue: str, require_patch: bool = False) -> bool:
        key = (redis_url, queue, require_patch)
        with self._lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and now - cached[0] < self._ttl:
                return cached[1]
            result = _observe_worker(redis_url, queue, require_patch)
            self._cache = {key: (time.monotonic(), result)}
            return result


worker_readiness = WorkerReadiness()
