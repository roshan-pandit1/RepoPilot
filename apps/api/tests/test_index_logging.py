import json
import logging

from app.core.index_logging import index_event, logger


def test_index_events_are_json_with_safe_fields_and_warning_severity(monkeypatch):
    events = []
    monkeypatch.setattr(logger, "log", lambda level, message: events.append((level, json.loads(message))))
    index_event("index_job_retry", job_id="job-1", repository_id=42, task_id="task-1")
    index_event("index_snapshot_published", job_id="job-1", repository_id=42, snapshot_id="snapshot-1")
    assert events[0][0] == logging.WARNING
    assert events[0][1] == {"event": "index_job_retry", "job_id": "job-1", "repository_id": 42,
                            "task_id": "task-1", "level": "WARNING"}
    assert events[1][0] == logging.INFO
    assert events[1][1]["snapshot_id"] == "snapshot-1"


def test_worker_preserves_structured_event_severity():
    from app.workers.tasks import celery

    assert celery.conf.worker_redirect_stdouts is False
