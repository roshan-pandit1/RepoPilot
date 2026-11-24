"""P4 fixture and sandbox tests. Actual execution is explicit and opt-in."""
import json
import os
import signal
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.patches.execution import Outcome
from app.modules.patches.generation import ProviderConfiguration
from app.modules.patches.synthetic_docker import CommandResult, DockerDriver, SandboxFailure, verify_probe, verify_workspace
from app.modules.patches.synthetic_specs import (BAD_SOURCE, COMMIT, FIX_BAD, IMAGE, REPOSITORY,
    SNAPSHOT, SOURCE_PATH, SPECS, TEST_SHA256, select_spec)
from app.modules.patches.trusted_execution import run_synthetic, validate_completed_report
from app.modules.patches.validation import PatchError, SourceFile
from app.modules.patches.workspace import workspace_pair
from test_auth_enrollment import github_auth as github_auth


def fixture_context(spec):
    file = SourceFile(SOURCE_PATH, spec.source, spec.source_sha256, "synthetic-file", ("synthetic-evidence",))
    return SimpleNamespace(snapshot_id=SNAPSHOT, commit_sha=COMMIT, files=(file,))


def config(enabled=True):
    return SimpleNamespace(app_env="test", patch_synthetic_execution_enabled=enabled)


def probe_result(spec):
    zero = "0" * 32
    loopback = "0" * 31 + "1"
    data = {"uid": 65534, "gid": 65534, "seccomp": "2", "no_new_privs": "1", "cap_eff": "00000000",
            "root_ro": True, "fixture_ro": True, "tmp_writable": True,
            "sysfs_entries": ["lo"], "sysfs_interfaces": ["lo"],
            "proc_interfaces": ["lo"], "socket_interfaces": ["lo"], "route_count": 0,
            "ipv6_addresses": [[loopback, "01", "80", "10", "80", "lo"]],
            "ipv6_routes": [[zero, "00", zero, "00", zero, "ffffffff", "00000001", "00000000", "00200200", "lo"],
                            [loopback, "80", zero, "00", zero, "00000000", "00000001", "00000000", "80200001", "lo"]],
            "runtime_mounts": [["/", "overlay", "ro"], ["/proc", "proc", "rw,nosuid,nodev,noexec"],
                               ["/sys", "sysfs", "ro,nosuid,nodev,noexec"], ["/dev", "tmpfs", "rw,nosuid"],
                               ["/fixture", "virtiofs", "ro,nosuid,nodev"],
                               ["/tmp", "tmpfs", "rw,nosuid,nodev,noexec"],
                               *[[path, "tmpfs", "ro,nosuid,nodev,noexec"]
                                 for path in ("/app", "/home", "/opt", "/root", "/run/secrets")]],
            "memory": str(spec.memory_bytes), "pids": str(spec.pids), "cpu": "100000 100000",
            "socket_absent": True, "app_masked": True, "environment": ["HOME", "LANG", "PATH"], "cwd": "/fixture"}
    return CommandResult(0, json.dumps(data).encode(), b"")


class FakeDriver:
    """Simulates Docker outcomes. It does not start containers or run the fixture."""
    def __init__(self, results=None, failure=None):
        self.results = list(results or [(1, b"FAIL\n"), (0, b"PASS\n")])
        self.failure = failure
        self.events = []
        self.probe = False

    def inspect_image(self):
        self.events.append("image")
        if self.failure == "image_unavailable":
            raise SandboxFailure(self.failure)

    def create(self, spec, workspace, nonce, probe):
        self.events.append("create_probe" if probe else "create_test")
        self.probe = probe
        return nonce * 2, "repopilot-p4-" + nonce

    def verify(self, container, name, nonce, workspace, spec, probe):
        self.events.append("verify")
        if self.failure == "container_policy":
            raise SandboxFailure(self.failure)

    def start(self, container, timeout, limit, cancelled=None):
        self.events.append("probe" if self.probe else "test")
        if self.failure in {"timeout", "resource_limit", "output_limit", "cancelled"}:
            raise SandboxFailure(self.failure)
        if self.probe:
            return probe_result(SPECS[0]), 1
        code, out = self.results.pop(0)
        return CommandResult(code, out, b""), 2

    def cleanup(self, name, nonce):
        self.events.append("cleanup")
        if self.failure == "cleanup_failed":
            raise SandboxFailure(self.failure)

    def close(self):
        self.events.append("close")


def test_spec_is_pinned_and_refuses_altered_source_or_patch():
    spec = SPECS[0]
    context = fixture_context(spec)
    selected, files, changed = select_spec(REPOSITORY, context, FIX_BAD)
    assert selected.id == "synthetic-add-reproducer-v1" and len(files) == 2
    assert changed[0].after_sha256 == SPECS[1].source_sha256 and files[1].sha256 == TEST_SHA256
    for repo, ctx, diff in [("external/repository", context, FIX_BAD),
                            (REPOSITORY, SimpleNamespace(snapshot_id="wrong", commit_sha=COMMIT, files=context.files), FIX_BAD),
                            (REPOSITORY, context, FIX_BAD.replace("a + b", "a * b")),
                            (REPOSITORY, SimpleNamespace(snapshot_id=SNAPSHOT, commit_sha=COMMIT,
                             files=(SourceFile(SOURCE_PATH, BAD_SOURCE, "0" * 64, "1", ("e",)),)), FIX_BAD)]:
        with pytest.raises(PatchError):
            select_spec(repo, ctx, diff)


def test_synthetic_flag_fails_closed_outside_test(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "x" * 40)
    with pytest.raises(ValueError):
        Settings(app_env="production", patch_synthetic_execution_enabled=True)
    assert not Settings(app_env="test").patch_synthetic_execution_enabled
    result = run_synthetic(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD, config(False))
    assert result["status"] == "VALIDATION_UNAVAILABLE" and result["sandbox_used"] is False
    blocked = SimpleNamespace(app_env="production", patch_synthetic_execution_enabled=True)
    assert run_synthetic(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD, blocked)["status"] == "VALIDATION_UNAVAILABLE"


@pytest.mark.parametrize(("spec", "results", "expected"), [
    (SPECS[0], [(1, b"FAIL\n"), (0, b"PASS\n")], Outcome.BASELINE_FAILED_PATCH_PASSED),
    (SPECS[1], [(0, b"PASS\n"), (0, b"PASS\n")], Outcome.BOTH_PASSED),
])
def test_mocked_adapter_reports_comparison_without_real_execution(spec, results, expected):
    driver = FakeDriver(results)
    context = fixture_context(spec)
    report = run_synthetic(REPOSITORY, context, spec.patch, config(), driver_factory=lambda: driver)
    assert report["status"] == "COMPLETED" and report["outcome"] == expected
    assert driver.events.count("probe") == 1 and driver.events.count("test") == 2
    assert driver.events.count("cleanup") == 3 and driver.events[-1] == "close"
    validate_completed_report(report, REPOSITORY, context, spec.patch)


def test_saved_completed_report_rejects_forged_identity_and_claims():
    spec = SPECS[0]
    context = fixture_context(spec)
    report = run_synthetic(REPOSITORY, context, spec.patch, config(), driver_factory=FakeDriver)
    for changed in ({**report, "patch_sha256": "0" * 64},
                    {**report, "sandbox_used": False},
                    {**report, "test_executed": False},
                    {**report, "outcome": "BOTH_PASSED"},
                    {**report, "unexpected_output": "private"},
                    {**report, "sandbox": {**report["sandbox"], "patched_container_id": report["sandbox"]["baseline_container_id"]}}):
        with pytest.raises(PatchError, match="invalid_test_result"):
            validate_completed_report(changed, REPOSITORY, context, spec.patch)


@pytest.mark.parametrize(("failure", "expected"), [
    ("image_unavailable", "VALIDATION_UNAVAILABLE"), ("container_policy", "EXECUTION_BLOCKED"),
    ("timeout", "TIMEOUT"), ("resource_limit", "RESOURCE_LIMIT"),
    ("output_limit", "INFRASTRUCTURE_FAILURE"), ("cancelled", "CANCELLED"),
    ("cleanup_failed", "CLEANUP_FAILURE"),
])
def test_mocked_failures_never_report_completed(failure, expected):
    driver = FakeDriver(failure=failure)
    report = run_synthetic(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD, config(), driver_factory=lambda: driver)
    assert report["status"] == expected and report["status"] != "COMPLETED"
    assert driver.events[-1] == "close"


def test_nonzero_without_expected_failure_marker_is_infrastructure_failure():
    driver = FakeDriver([(2, b"unexpected\n")])
    report = run_synthetic(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD, config(), driver_factory=lambda: driver)
    assert report["status"] == "INFRASTRUCTURE_FAILURE" and report["test_executed"] is False


def test_probe_rejects_missing_controls():
    result = probe_result(SPECS[0])
    verify_probe(result, SPECS[0])
    value = json.loads(result.stdout)
    for key, unsafe in (("root_ro", False), ("seccomp", "0"), ("cap_eff", "1"),
                        ("sysfs_entries", ["lo", "bonding_masters"]),
                        ("sysfs_interfaces", ["lo", "eth0"]), ("proc_interfaces", ["lo", "eth0"]),
                        ("socket_interfaces", ["lo", "eth0"]), ("route_count", 1),
                        ("pids", "max"), ("socket_absent", False)):
        modified = {**value, key: unsafe}
        with pytest.raises(SandboxFailure):
            verify_probe(CommandResult(0, json.dumps(modified).encode(), b""), SPECS[0])


@pytest.mark.parametrize("mutation", [
    "nonloopback_address", "unexpected_ipv6_route", "forwarding_default", "invalid_route_record",
    "missing_address_records", "invalid_address_record", "non_integer_ipv4_route_count", "conflicting_interfaces",
    "unapproved_runtime_mount", "unapproved_mount_filesystem", "missing_runtime_mount", "duplicate_runtime_mount",
])
def test_probe_rejects_unsafe_or_incomplete_network_evidence(mutation):
    value = json.loads(probe_result(SPECS[0]).stdout)
    if mutation == "nonloopback_address":
        value["ipv6_addresses"][0][0] = "20010db8000000000000000000000001"
    elif mutation == "unexpected_ipv6_route":
        value["ipv6_routes"][1][0] = "20010db8000000000000000000000001"
    elif mutation == "forwarding_default":
        value["ipv6_routes"][0][8] = "00000001"
    elif mutation == "invalid_route_record":
        value["ipv6_routes"][0] = ["malformed"]
    elif mutation == "missing_address_records":
        del value["ipv6_addresses"]
    elif mutation == "invalid_address_record":
        value["ipv6_addresses"][0][1] = "invalid"
    elif mutation == "non_integer_ipv4_route_count":
        value["route_count"] = False
    elif mutation == "unapproved_runtime_mount":
        value["runtime_mounts"].append(["/etc/resolv.conf", "ext4", "ro"])
    elif mutation == "unapproved_mount_filesystem":
        value["runtime_mounts"][0][1] = "ext4"
    elif mutation == "missing_runtime_mount":
        value["runtime_mounts"].pop()
    elif mutation == "duplicate_runtime_mount":
        value["runtime_mounts"].append(value["runtime_mounts"][0])
    else:
        value["proc_interfaces"] = ["lo", "unexpected0"]
    with pytest.raises(SandboxFailure, match="preflight_"):
        verify_probe(CommandResult(0, json.dumps(value).encode(), b""), SPECS[0])


def test_interface_enumeration_failure_and_unsupported_runtime_fail_closed(monkeypatch):
    with pytest.raises(SandboxFailure, match="preflight_process_permissionerror"):
        verify_probe(CommandResult(1, b"", b"PermissionError"), SPECS[0])
    monkeypatch.setattr("app.modules.patches.synthetic_docker.platform.system", lambda: "Linux")
    with pytest.raises(SandboxFailure, match="unsupported_host"):
        DockerDriver()


def test_mocked_network_preflight_failure_stops_before_any_fixture_test():
    class NetworkFailure(FakeDriver):
        def start(self, container, timeout, limit, cancelled=None):
            result, elapsed = super().start(container, timeout, limit, cancelled)
            if self.probe:
                value = json.loads(result.stdout)
                value["socket_interfaces"] = ["lo", "unexpected0"]
                return CommandResult(0, json.dumps(value).encode(), b""), elapsed
            return result, elapsed
    driver = NetworkFailure()
    report = run_synthetic(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD, config(), driver_factory=lambda: driver)
    assert report["status"] == "EXECUTION_BLOCKED" and report["sandbox_used"] is False
    assert report["test_executed"] is False and report["tests_run"] == []
    assert "test" not in driver.events and driver.events.count("cleanup") == 1


def test_changed_executable_is_rejected_before_docker_is_called():
    driver = DockerDriver.__new__(DockerDriver)
    driver.command = lambda *_args, **_kwargs: pytest.fail("Docker must not be called")
    with pytest.raises(SandboxFailure, match="fixture_policy"):
        driver.create(replace(SPECS[0], executable="/bin/sh"), Path("/tmp/unused"), "a" * 32, False)


def test_workspace_inventory_rejects_unexpected_files_and_symlinks():
    spec, files, changed = select_spec(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD)
    with workspace_pair(files, changed) as (baseline, _patched):
        verify_workspace(baseline, spec)
        (baseline / "extra.py").symlink_to(baseline / "test_add.py")
        with pytest.raises(SandboxFailure, match="workspace_policy"):
            verify_workspace(baseline, spec)


def test_inspection_rejects_unsafe_network_mounts_privileges_and_limits():
    driver = DockerDriver.__new__(DockerDriver)
    spec, nonce, identity = SPECS[0], "a" * 32, "b" * 64
    workspace = Path("/private/tmp/fixture")
    name = "repopilot-p4-" + nonce
    record = {"Id": identity, "Name": "/" + name, "Image": IMAGE, "Path": "/usr/bin/env",
        "Args": ["-i", *spec.environment, spec.executable, *spec.arguments],
        "Config": {"User": "65534:65534", "WorkingDir": "/fixture", "Labels":
            {"repopilot.p4.nonce": nonce, "repopilot.p4.purpose": "repopilot-p4-trusted-synthetic"}},
        "HostConfig": {"Privileged": False, "NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"],
            "CapAdd": None, "Binds": None, "PidMode": "", "UTSMode": "",
            "SecurityOpt": ["no-new-privileges"], "Memory": spec.memory_bytes,
            "MemorySwap": spec.memory_bytes, "PidsLimit": spec.pids, "NanoCpus": spec.cpu_nanos,
            "Tmpfs": {"/tmp": "rw,noexec,nosuid,nodev,size=8m", **{path: "ro,noexec,nosuid,nodev,size=1m"
                for path in ("/app", "/home", "/root", "/opt", "/run/secrets")}}},
        "Mounts": [{"Type": "bind", "Source": str(workspace), "Destination": "/fixture", "RW": False}],
        "NetworkSettings": {"Networks": {"none": {"IPAddress": "", "GlobalIPv6Address": "",
                                                   "Gateway": "", "IPv6Gateway": ""}}}}
    driver.inspect = lambda _identity: record
    driver.verify(identity, name, nonce, workspace, spec, False)
    for key, bad in (("NetworkMode", "host"), ("Privileged", True), ("ReadonlyRootfs", False),
                     ("CapDrop", []), ("Memory", 0), ("PidsLimit", 0), ("SecurityOpt", []),
                     ("SecurityOpt", "no-new-privileges"), ("PidMode", "host")):
        original = record["HostConfig"][key]
        record["HostConfig"][key] = bad
        with pytest.raises(SandboxFailure):
            driver.verify(identity, name, nonce, workspace, spec, False)
        record["HostConfig"][key] = original
    original_pid_mode = record["HostConfig"].pop("PidMode")
    with pytest.raises(SandboxFailure, match="inspection_failed"):
        driver.verify(identity, name, nonce, workspace, spec, False)
    record["HostConfig"]["PidMode"] = original_pid_mode
    networks = record["NetworkSettings"]["Networks"]
    for bad in ({}, {**networks, "bridge": {}}, {"none": {}},
                {"none": {**networks["none"], "IPAddress": "192.0.2.1"}}):
        record["NetworkSettings"]["Networks"] = bad
        with pytest.raises(SandboxFailure):
            driver.verify(identity, name, nonce, workspace, spec, False)
    record["NetworkSettings"]["Networks"] = networks
    record["Mounts"].append({"Type": "bind", "Source": "/var/run/docker.sock", "RW": False})
    with pytest.raises(SandboxFailure):
        driver.verify(identity, name, nonce, workspace, spec, False)


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"[null]", b'["invalid"]'])
def test_malformed_docker_inspection_fails_closed(body):
    driver = DockerDriver.__new__(DockerDriver)
    driver.command = lambda *_args, **_kwargs: CommandResult(0, body, b"")
    with pytest.raises(SandboxFailure, match="inspection_failed"):
        driver.inspect("synthetic")


def test_cleanup_refuses_an_unowned_container():
    driver = DockerDriver.__new__(DockerDriver)
    nonce = "a" * 32
    name = "repopilot-p4-" + nonce
    driver.inspect = lambda _identity: {"Id": "b" * 64, "Name": "/" + name, "Image": IMAGE,
        "Config": {"Labels": {"repopilot.p4.nonce": "wrong", "repopilot.p4.purpose": "repopilot-p4-trusted-synthetic"}}}
    driver.command = lambda *_args, **_kwargs: pytest.fail("unowned container must not be removed")
    with pytest.raises(SandboxFailure, match="cleanup_ownership"):
        driver.cleanup(name, nonce)


def test_cleanup_failure_and_unverifiable_absence_fail_closed():
    driver = DockerDriver.__new__(DockerDriver)
    nonce = "a" * 32
    name = "repopilot-p4-" + nonce
    driver.inspect = lambda _identity: {"Id": "b" * 64, "Name": "/" + name, "Image": IMAGE,
        "Config": {"Labels": {"repopilot.p4.nonce": nonce, "repopilot.p4.purpose": "repopilot-p4-trusted-synthetic"}}}
    driver.command = lambda *_args, **_kwargs: CommandResult(1, b"", b"")
    with pytest.raises(SandboxFailure, match="cleanup_failed"):
        driver.cleanup(name, nonce)


def test_command_reaps_cli_when_cancellation_monitor_raises(monkeypatch, tmp_path):
    """A broken monitor must not leave its owned Docker CLI process running."""
    calls = []

    class Pipe:
        def __init__(self, number):
            self.number = number
            self.closed = False

        def fileno(self):
            return self.number

        def close(self):
            self.closed = True

    class Process:
        pid = 4242
        stdout = Pipe(11)
        stderr = Pipe(12)

        def wait(self, timeout):
            calls.append(("wait", timeout))
            return 0

    class Selector:
        def register(self, pipe, events):
            pass

        def get_map(self):
            return {"synthetic": True}

        def close(self):
            calls.append(("selector_closed",))

    process = Process()
    monkeypatch.setattr("app.modules.patches.synthetic_docker.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr("app.modules.patches.synthetic_docker.os.set_blocking", lambda *args: None)
    monkeypatch.setattr("app.modules.patches.synthetic_docker.selectors.DefaultSelector", Selector)
    monkeypatch.setattr("app.modules.patches.synthetic_docker.os.killpg", lambda *args: calls.append(("killpg", *args)))
    driver = DockerDriver.__new__(DockerDriver)
    driver.binary, driver.socket, driver.home, driver.config = Path("/synthetic/docker"), Path("/synthetic/socket"), tmp_path, tmp_path

    def broken_monitor():
        raise RuntimeError("synthetic monitor failure")

    with pytest.raises(RuntimeError, match="synthetic monitor failure"):
        driver.command(["info"], cancelled=broken_monitor)
    assert ("killpg", process.pid, signal.SIGKILL) in calls
    assert ("wait", 3) in calls
    assert process.stdout.closed and process.stderr.closed
    assert ("selector_closed",) in calls


def synthetic_parent(client, factory, github, monkeypatch):
    from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, Repository
    from app.workers.tasks import process_investigation
    from test_investigation_evidence import stub_retrieval, submit
    from test_issue_context import setup_issue

    setup_issue(client, github)
    github.repositories = lambda token, installation: [{"id": 902, "full_name": REPOSITORY, "private": False}]
    original = github.issue
    github.issue = lambda *args: {**original(*args), "title": "process_sync fails", "body": "Synthetic fixture", "labels": []}
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        repo.full_name = REPOSITORY
        db.add(CodeSnapshot(id=SNAPSHOT, tenant_id=repo.tenant_id, repository_id=902,
                            commit_sha=COMMIT, published=True))
        db.flush()
        file = IndexedFile(id=str(uuid4()), snapshot_id=SNAPSHOT, tenant_id=repo.tenant_id,
                           repository_id=902, path=SOURCE_PATH, content_hash=SPECS[0].source_sha256)
        db.add(file)
        db.flush()
        chunk = CodeChunk(id=str(uuid4()), file_id=file.id, tenant_id=repo.tenant_id, repository_id=902,
                          symbol="add", start_line=1, end_line=2, source_text=BAD_SOURCE.decode())
        db.add(chunk)
        chunk_id = chunk.id
    stub_retrieval(monkeypatch, factory, chunk_id)
    parent = submit(client)
    process_investigation(parent, factory, github)
    return parent


def test_mocked_synthetic_worker_persists_verified_result_and_duplicate_delivery(client, factory, github_auth, monkeypatch):
    from app.core.config import get_settings
    from app.domain.models import PatchProposal
    from app.modules.patches.worker import process_patch
    from test_auth_enrollment import csrf
    from test_patch_proposals import create, enable, proposal_root

    parent = synthetic_parent(client, factory, github_auth, monkeypatch)
    class Provider:
        configuration = ProviderConfiguration("synthetic-test", "p4-fixture", requires_credentials=False)
        def generate(self, request, *, timeout_seconds):
            return json.dumps({"diff": FIX_BAD, "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "Synthetic fixture."})
    enable(monkeypatch, Provider())
    monkeypatch.setattr(get_settings(), "patch_synthetic_execution_enabled", True)
    driver = FakeDriver()
    monkeypatch.setattr("app.modules.patches.trusted_execution.DockerDriver", lambda: driver)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, Provider())
    url = proposal_root(parent) + "/" + proposal
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    process_patch(proposal, factory, github_auth)
    process_patch(proposal, factory, github_auth)
    result = client.get(url)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "tests_passed"
    assert result.json()["test_result"]["outcome"] == "BASELINE_FAILED_PATCH_PASSED"
    assert driver.events.count("test") == 2  # Simulated results only, no container ran.
    with factory() as db:
        assert db.get(PatchProposal, proposal).status == "tests_passed"


def test_worker_blocks_non_fixture_before_accessing_docker(client, factory, github_auth, monkeypatch):
    from app.core.config import get_settings
    from app.modules.patches.worker import process_patch
    from test_auth_enrollment import csrf
    from test_patch_proposals import SyntheticProvider, create, enable, parent_setup, proposal_root

    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "patch_synthetic_execution_enabled", True)
    monkeypatch.setattr("app.modules.patches.trusted_execution.DockerDriver", lambda: pytest.fail("Docker must not be called"))
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    url = proposal_root(parent) + "/" + proposal
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    process_patch(proposal, factory, github_auth)
    result = client.get(url).json()
    assert result["status"] == "static_validated" and result["test_result"]["status"] == "EXECUTION_BLOCKED"
    assert result["test_result"]["test_executed"] is False


def test_mocked_worker_persists_preflight_failure_without_a_success_result(client, factory, github_auth, monkeypatch):
    from app.core.config import get_settings
    from app.modules.patches.worker import process_patch
    from test_auth_enrollment import csrf
    from test_patch_proposals import create, enable, proposal_root

    parent = synthetic_parent(client, factory, github_auth, monkeypatch)
    class Provider:
        configuration = ProviderConfiguration("synthetic-test", "p4-fixture", requires_credentials=False)
        def generate(self, request, *, timeout_seconds):
            return json.dumps({"diff": FIX_BAD, "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "Synthetic fixture."})
    enable(monkeypatch, Provider())
    monkeypatch.setattr(get_settings(), "patch_synthetic_execution_enabled", True)
    monkeypatch.setattr("app.modules.patches.trusted_execution.DockerDriver", lambda: FakeDriver(failure="container_policy"))
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, Provider())
    url = proposal_root(parent) + "/" + proposal
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    process_patch(proposal, factory, github_auth)
    result = client.get(url)
    assert result.status_code == 200
    assert result.json()["status"] == "static_validated"
    assert result.json()["test_result"]["status"] == "EXECUTION_BLOCKED"
    assert result.json()["test_result"]["test_executed"] is False


def test_mocked_validation_cancellation_fences_late_result(client, factory, github_auth, monkeypatch):
    from app.core.config import get_settings
    from app.domain.models import PatchOutbox, PatchProposal
    from app.modules.patches.worker import process_patch
    from test_auth_enrollment import csrf
    from test_patch_proposals import create, enable, proposal_root

    parent = synthetic_parent(client, factory, github_auth, monkeypatch)
    class Provider:
        configuration = ProviderConfiguration("synthetic-test", "p4-fixture", requires_credentials=False)
        def generate(self, request, *, timeout_seconds):
            return json.dumps({"diff": FIX_BAD, "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "Synthetic fixture."})
    enable(monkeypatch, Provider())
    monkeypatch.setattr(get_settings(), "patch_synthetic_execution_enabled", True)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, Provider())
    url = proposal_root(parent) + "/" + proposal
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    class CancelDriver(FakeDriver):
        def start(self, container, timeout, limit, cancelled=None):
            if not self.probe:
                response = client.post(url + "/review", headers=csrf(client), json={"decision": "rejected"})
                assert response.status_code == 200 and cancelled()
                raise SandboxFailure("cancelled")
            return super().start(container, timeout, limit, cancelled)
    monkeypatch.setattr("app.modules.patches.trusted_execution.DockerDriver", CancelDriver)
    process_patch(proposal, factory, github_auth)
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "static_validated" and task.review_state == "rejected"
        assert task.test_result["status"] == "cancelled" and task.test_result["tests_run"] == []
        assert db.get(PatchOutbox, proposal).status == "processed"


def test_mocked_validation_does_not_publish_stale_source(client, factory, github_auth, monkeypatch):
    from app.core.config import get_settings
    from app.domain.models import CodeChunk, PatchProposal
    from app.modules.patches.worker import process_patch
    from test_auth_enrollment import csrf
    from test_patch_proposals import create, enable, proposal_root
    from sqlalchemy import select

    parent = synthetic_parent(client, factory, github_auth, monkeypatch)
    class Provider:
        configuration = ProviderConfiguration("synthetic-test", "p4-fixture", requires_credentials=False)
        def generate(self, request, *, timeout_seconds):
            return json.dumps({"diff": FIX_BAD, "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "Synthetic fixture."})
    enable(monkeypatch, Provider())
    monkeypatch.setattr(get_settings(), "patch_synthetic_execution_enabled", True)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, Provider())
    url = proposal_root(parent) + "/" + proposal
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    class StaleDriver(FakeDriver):
        def start(self, container, timeout, limit, cancelled=None):
            result = super().start(container, timeout, limit, cancelled)
            if not self.probe and self.events.count("test") == 2:
                with factory.begin() as db:
                    db.scalar(select(CodeChunk)).source_text = "def add(a, b):\n    return 10\n"
            return result
    monkeypatch.setattr("app.modules.patches.trusted_execution.DockerDriver", StaleDriver)
    process_patch(proposal, factory, github_auth)
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.test_result["status"] == "pending"


@pytest.mark.skipif(os.environ.get("REPOPILOT_P4_ACTUAL") != "1", reason="explicit isolated synthetic execution required")
@pytest.mark.parametrize(("spec", "expected"), [
    (SPECS[0], Outcome.BASELINE_FAILED_PATCH_PASSED), (SPECS[1], Outcome.BOTH_PASSED),
])
def test_actual_isolated_synthetic_fixture(spec, expected):
    report = run_synthetic(REPOSITORY, fixture_context(spec), spec.patch, config())
    assert report["status"] == "COMPLETED", (report["status"], report["reason"], report["sandbox_used"], report["test_executed"])
    assert report["outcome"] == expected and report["sandbox_used"] is True and report["test_executed"] is True
    validate_completed_report(report, REPOSITORY, fixture_context(spec), spec.patch)


@pytest.mark.skipif(os.environ.get("REPOPILOT_P4_ACTUAL") != "1", reason="explicit isolated synthetic execution required")
def test_actual_sandbox_preflight_without_fixture_execution():
    from app.modules.patches.synthetic_docker import DockerDriver, container_run
    from app.modules.patches.trusted_execution import _container_readable
    from app.modules.patches.workspace import workspace_pair

    spec, files, changed = select_spec(REPOSITORY, fixture_context(SPECS[0]), FIX_BAD)
    driver = DockerDriver()
    try:
        driver.inspect_image()
        with workspace_pair(files, changed) as (baseline, patched), _container_readable(baseline, patched):
            result, _, _ = container_run(driver, spec, baseline, probe=True)
            assert result.code == 0
    finally:
        driver.close()
