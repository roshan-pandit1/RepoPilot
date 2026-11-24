from types import SimpleNamespace

import pytest

from app.core import worker_readiness as module


class FakeControl:
    def __init__(self, queues, registered):
        self.queues = queues
        self.tasks = registered

    def inspect(self, *, timeout):
        assert timeout == 1.0
        return self

    def active_queues(self):
        return self.queues

    def registered(self):
        return self.tasks


@pytest.mark.parametrize(("queues", "registered", "expected"), [
    ({"worker-a": [{"name": "p15"}]}, {"worker-a": list(module._REQUIRED_TASKS)}, True),
    ({"worker-a": [{"name": "other"}]}, {"worker-a": list(module._REQUIRED_TASKS)}, False),
    ({"worker-a": [{"name": "p15"}]}, {"worker-b": list(module._REQUIRED_TASKS)}, False),
    ({"worker-a": [{"name": "p15"}]}, {"worker-a": ["ingest_issue"]}, False),
    (None, None, False),
])
def test_probe_requires_same_worker_queue_and_core_tasks(monkeypatch, queues, registered, expected):
    control = FakeControl(queues, registered)
    client = SimpleNamespace(conf=SimpleNamespace(update=lambda **kwargs: None), control=control, close=lambda: None)
    monkeypatch.setattr(module, "Celery", lambda *args, **kwargs: client)
    assert module._observe_worker("redis://broker", "p15") is expected



def test_transport_timeout_exceeds_reply_window(monkeypatch):
    options = {}
    control = FakeControl({"worker-a": [{"name": "p15"}]},
                          {"worker-a": list(module._REQUIRED_TASKS)})
    client = SimpleNamespace(conf=SimpleNamespace(update=lambda **kwargs: options.update(kwargs)),
                             control=control, close=lambda: None)
    monkeypatch.setattr(module, "Celery", lambda *args, **kwargs: client)
    assert module._observe_worker("redis://broker", "p15")
    assert options["broker_transport_options"]["socket_timeout"] > 1.0
    assert options["broker_transport_options"]["retry_policy"]["max_retries"] == 0



def test_patch_capability_only_required_when_enabled(monkeypatch):
    tasks = list(module._REQUIRED_TASKS)
    control = FakeControl({"worker-a": [{"name": "p15"}]}, {"worker-a": tasks})
    client = SimpleNamespace(conf=SimpleNamespace(update=lambda **kwargs: None),
                             control=control, close=lambda: None)
    monkeypatch.setattr(module, "Celery", lambda *args, **kwargs: client)
    assert module._observe_worker("redis://broker", "p15", require_patch=False)
    assert not module._observe_worker("redis://broker", "p15", require_patch=True)
    tasks.append("process_patch_proposal")
    assert module._observe_worker("redis://broker", "p15", require_patch=True)


def test_cache_distinguishes_patch_capability(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "_observe_worker",
                        lambda url, queue, require_patch: calls.append(require_patch) or not require_patch)
    probe = module.WorkerReadiness(ttl=3)
    assert probe.check("redis://broker", "p15", False)
    assert not probe.check("redis://broker", "p15", True)
    assert calls == [False, True]


def test_probe_fails_closed_and_closes_client(monkeypatch):
    closed = []
    class Broken:
        def inspect(self, **kwargs):
            raise OSError("private broker detail")
    client = SimpleNamespace(conf=SimpleNamespace(update=lambda **kwargs: None), control=Broken(),
                             close=lambda: closed.append(True))
    monkeypatch.setattr(module, "Celery", lambda *args, **kwargs: client)
    assert module._observe_worker("redis://broker", "p15") is False
    assert closed == [True]


def test_cache_limits_repeated_probes_and_expires(monkeypatch):
    now = [10.0]
    calls = []
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module, "_observe_worker", lambda url, queue, require_patch: calls.append((url, queue, require_patch)) or len(calls) == 1)
    probe = module.WorkerReadiness(ttl=3)
    assert probe.check("redis://broker", "p15")
    assert probe.check("redis://broker", "p15")
    assert len(calls) == 1
    now[0] += 3.1
    assert not probe.check("redis://broker", "p15")
    assert len(calls) == 2


def test_readiness_reports_worker_down(monkeypatch):
    from app import main
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, statement): pass
    class Redis:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ping(self): return True
    monkeypatch.setattr(main, "get_engine", lambda: SimpleNamespace(connect=lambda: Conn()))
    monkeypatch.setattr(main.Redis, "from_url", lambda *args, **kwargs: Redis())
    monkeypatch.setattr(main.worker_readiness, "check", lambda *args: False)
    response = main.ready()
    assert response.status_code == 503
    monkeypatch.setattr(main.worker_readiness, "check", lambda *args: True)
    assert main.ready() == {"status": "ready", "dispatcher": "not_checked"}


@pytest.mark.parametrize(("failed", "expected"), [
    ("database", "database"),
    ("configuration", "configuration"),
    ("broker", "broker"),
    ("broker_false", "broker"),
    ("worker", "worker"),
    ("worker_false", "worker"),
])
def test_readiness_classifies_unavailable_without_leaking_errors(monkeypatch, failed, expected):
    import json
    from app import main

    private_detail = "private synthetic failure detail"

    def error():
        raise RuntimeError(private_detail)

    class Conn:
        def __enter__(self):
            if failed == "database":
                error()
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            pass

    class Broker:
        def __enter__(self):
            if failed == "broker":
                error()
            return self

        def __exit__(self, *args):
            pass

        def ping(self):
            return failed != "broker_false"

    settings = SimpleNamespace(redis_url="redis://synthetic", worker_readiness_queue="celery",
                               patch_proposals_enabled=False)
    monkeypatch.setattr(main, "get_engine", lambda: SimpleNamespace(connect=lambda: Conn()))
    monkeypatch.setattr(main, "get_settings", lambda: error() if failed == "configuration" else settings)
    monkeypatch.setattr(main.Redis, "from_url", lambda *args, **kwargs: Broker())
    monkeypatch.setattr(main.worker_readiness, "check", lambda *args: error() if failed == "worker" else
                        failed != "worker_false")
    response = main.ready()
    assert response.status_code == 503
    assert json.loads(response.body) == {"status": "unavailable", "dependency": expected,
                                         "dispatcher": "not_checked"}
    assert private_detail.encode() not in response.body
