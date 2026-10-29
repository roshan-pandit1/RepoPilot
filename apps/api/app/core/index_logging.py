"""Small JSON lifecycle events with no source content, credentials or exception details."""
import json
import logging

logger = logging.getLogger("repopilot.index_events")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def index_event(event: str, *, job_id: str, repository_id: int | None = None,
                task_id: str | None = None, snapshot_id: str | None = None,
                level: int | None = None) -> None:
    if level is None:
        level = logging.WARNING if event in {"index_job_failed", "index_job_retry",
                                             "index_authorization_revoked"} else logging.INFO
    data = {"event": event, "job_id": job_id, "repository_id": repository_id,
            "task_id": task_id, "snapshot_id": snapshot_id, "level": logging.getLevelName(level)}
    logger.log(level, json.dumps({key: value for key, value in data.items() if value is not None}))
