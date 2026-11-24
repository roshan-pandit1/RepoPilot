"""TEST ONLY: prepare and run the staged parser regression on a disposable database.

The default ``check`` action is read-only. ``run`` creates a private source copy,
installs only verified local wheels into a fresh environment, and may create a
single isolated Docker container. It never uses the application's database.
"""

from __future__ import annotations

import argparse
import ast
import errno
import hashlib
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
EXPECTED_UV = "0.13.6"
PROJECT_SHA256 = "e0fe0e272583fefecbc09d4c9e0631c41771f370b267a4dd4569fa349ee4e240"
LOCK_SHA256 = "40139126d31b521cc5377f1333b22d7c18de733840d1c63d848309ba7ad9c09a"
UV_WHEEL = "uv-0.13.6-py3-none-macosx_11_0_arm64.whl"
UV_WHEEL_SHA256 = "51361029b7cf91185d0092c4b356d110b4ad629e9cb11593f1e006ac72a72ca9"
IMAGE = "sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f"
MARKER = "repopilot-synthetic-capture-v1"
ROLE = "capture_fixture"
PURPOSE = "tree-sitter-0252-disposable-test"
SANDBOX = Path("/usr/bin/sandbox-exec")
PARSER_VERSIONS = {
    "tree-sitter": "0.25.2", "tree-sitter-c": "0.24.2", "tree-sitter-c-sharp": "0.23.5",
    "tree-sitter-cpp": "0.23.4", "tree-sitter-go": "0.25.0", "tree-sitter-java": "0.23.5",
    "tree-sitter-javascript": "0.25.0", "tree-sitter-rust": "0.24.2", "tree-sitter-typescript": "0.23.2",
}
RELEASE_TESTS = (
    "test_language_analysis.py", "test_code_primitives.py", "test_code_snapshot.py",
    "test_code_collect.py", "test_code_persistence.py", "test_multilingual_indexing.py",
    "test_code_workflow.py", "test_historical_readability.py", "test_investigation_evidence.py",
    "test_benchmark_provenance.py", "test_issue_retrieval_replay.py",
    "test_publication_identity_contract.py", "test_tree_sitter_go_regression.py",
    "test_investigation_migration.py", "test_retrieval_evaluation.py", "test_retrieval_heldout.py",
    "test_supervised_parser_integration.py", "test_auth_enrollment.py",
    "test_patch_proposals.py", "test_patch_provider_contract.py", "test_patch_validation.py",
    "test_patch_synthetic_execution.py",
)
HELPER_TESTS = ("conftest.py", "test_investigation_reports.py", "test_issue_context.py",
                "test_synthetic_capture.py", "test_supervised_parser_postgres_native.py",
                "test_supervised_parser_postgres_drift.py")
SYNTHETIC_CAPTURE_CASES = (
    "test_fixture_preserves_complete_context_and_orders_comments",
    "test_fixture_inventory_is_multilingual_and_labels_are_explicit",
    "test_malformed_context_and_incomplete_labels_are_rejected",
    "test_inventory_and_identity_reject_malformed_data",
    "test_registered_fixture_and_development_heldout_separation",
    "test_registered_fixture_hash_rejects_tampering",
    "test_database_guard_rejects_application_or_ambiguous_targets",
    "test_environment_guard_runs_before_database_access",
    "test_database_marker_is_required_before_schema_changes",
)
FIXTURES = (
    "evaluation/fixtures/synthetic-capture-v1.json", "evaluation/investigation-evidence-v1.json",
    "evaluation/repopilot-6349190.json", "evaluation/repopilot-v2-956a4f9.json",
    "evaluation/fixtures/tree_sitter_0252_matrix_fixtures.py",
    "evaluation/supervised_parser.py", "evaluation/supervised_parser_child.py",
    "evaluation/supervised_parser_simulator.py", "evaluation/supervised_parser_test_broker.py",
    "evaluation/test_supervised_parser.py", "evaluation/test_supervised_parser_native_smoke.py",
    "evaluation/test_supervised_parser_native_matrix.py",
)
HARNESS_FILES = ("evaluation/tree_sitter_pg_harness.py", "evaluation/test_tree_sitter_pg_harness.py")
DESELECT = "tests/test_retrieval_heldout.py::test_validation_reads_pinned_local_git_objects_without_modifying_repository"
P4_DESELECT = (
    "tests/test_patch_synthetic_execution.py::test_actual_isolated_synthetic_fixture",
    "tests/test_patch_synthetic_execution.py::test_actual_sandbox_preflight_without_fixture_execution",
)
REQUIRED_CASES = frozenset({
    "test_postgres_multilingual_search_and_citations",
    "test_postgres_concurrent_requests_share_one_active_job",
    "test_postgres_search_returns_commit_citation",
    "test_postgres_keyword_search_handles_natural_language_and_identifiers",
    "test_postgres_keyword_camelcase_and_bounded_results",
    "test_postgres_concurrent_delivery_commits_one_manifest",
    "test_postgres_v2_retrieval_deduplicates_and_fences_source",
    "test_postgres_legacy_job_survives_migration",
    "test_successful_supervised_synthetic_publication_preserves_identity",
    "test_failed_supervised_job_keeps_previous_publication",
    "test_queued_supervised_job_fails_closed_if_flag_is_disabled",
    "test_supervised_republication_has_distinct_uuid_and_fingerprints",
    "test_synthetic_proposal_lifecycle_and_unavailable_sandbox",
    "test_expired_worker_lease_is_reclaimed_without_partial_result",
    "test_authorization_and_csrf_are_enforced",
    "test_postgres_concurrent_patch_requests_are_idempotent",
    "test_cancel_during_generation_fences_late_provider_output",
    "test_mocked_synthetic_worker_persists_verified_result_and_duplicate_delivery",
    "test_worker_blocks_non_fixture_before_accessing_docker",
    "test_mocked_validation_cancellation_fences_late_result",
    "test_mocked_validation_does_not_publish_stale_source",
    "test_postgres_guard_serializes_revocation",
    "test_login_session_encrypted_state_replay_and_logout",
    "test_verified_enrollment_selection_and_current_access",
    "test_no_provider_is_reported_unavailable",
    "test_synthetic_provider_gets_bound_request_with_separate_fixed_instructions",
    "test_input_output_and_patch_limits_fail_closed",
    "test_credentials_never_enter_request_and_are_rejected_in_input_or_output",
    "test_invalid_model_output_fails_without_persisting_partial_diff",
    "test_provider_timeout_and_unsafe_patch_do_not_publish_partial_data",
    "test_provider_exception_is_sanitized_and_never_publishes_partial_output",
    "test_source_change_during_generation_never_publishes_diff",
    "test_unverified_test_results_cannot_be_presented_as_passing",
    "test_mocked_worker_persists_preflight_failure_without_a_success_result",
})
P6_REQUIRED_PARAMETERS = frozenset({
    "test_worker_rejects_incomplete_provider_configuration[configuration0-invalid_provider_configuration]",
    "test_worker_rejects_incomplete_provider_configuration[configuration1-provider_credentials_missing]",
    "test_worker_rejects_wrong_request_identity_before_provider_call[repository_id-903]",
    "test_worker_rejects_wrong_request_identity_before_provider_call[tenant_id-999]",
    "test_worker_rejects_wrong_request_identity_before_provider_call[repository_full_name-other/repository]",
    "test_unverified_input_is_rejected_before_provider_call[wrong_source_hash]",
    "test_unverified_input_is_rejected_before_provider_call[wrong_repository]",
})
NATIVE_PG_CASES = frozenset({"test_postgres_supervised_real_children_publish_and_cite",
                             "test_postgres_supervised_real_child_syntax_fallback_is_labeled",
                             "test_supervised_integration_postgres_upgrade_and_schema_drift"})


class GuardError(RuntimeError):
    """A prerequisite or isolation check failed; do not continue to pytest."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError(message)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def load_contract(api: Path) -> dict:
    require(regular(api / "pyproject.toml") and digest(api / "pyproject.toml") == PROJECT_SHA256,
            "project declaration differs from the staged, reviewed state")
    require(regular(api / "uv.lock") and digest(api / "uv.lock") == LOCK_SHA256,
            "lockfile differs from the staged, reviewed state")
    project = tomllib.loads((api / "pyproject.toml").read_text())
    lock = tomllib.loads((api / "uv.lock").read_text())
    require(project.get("tool", {}).get("uv", {}).get("required-version") == f"=={EXPECTED_UV}",
            "project no longer requires the reviewed uv version")
    for name, version in PARSER_VERSIONS.items():
        require(f"{name}=={version}" in project["project"]["dependencies"], f"unexpected pin: {name}")
    packages = lock.get("package", [])
    by_name = {p["name"]: p for p in packages}
    require(len(by_name) == len(packages), "ambiguous duplicate lock entries")
    for name, version in PARSER_VERSIONS.items():
        require(by_name.get(name, {}).get("version") == version, f"lock mismatch: {name}")
    return by_name


def marker_matches(marker: str | None) -> bool:
    """Evaluate the small PEP 508 marker subset in this lock; unknown syntax fails closed."""
    if not marker:
        return True
    names = {"implementation_name": "cpython", "platform_python_implementation": "CPython",
             "platform_machine": "arm64", "sys_platform": "darwin", "os_name": "posix",
             "python_version": "3.14", "python_full_version": "3.14.10"}

    def evaluate(node: ast.AST):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Name):
            require(node.id in names, "unsupported dependency marker variable")
            return names[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [evaluate(value) for value in node.values]
            require(all(isinstance(value, bool) for value in values), "invalid dependency marker")
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left, right = evaluate(node.left), evaluate(node.comparators[0])
            op = node.ops[0]
            if isinstance(node.left, ast.Name) and node.left.id in {"python_version", "python_full_version"}:
                require(re.fullmatch(r"\d+(?:\.\d+)*", right) is not None, "unsupported version marker")
                left, right = tuple(map(int, left.split("."))), tuple(map(int, right.split(".")))
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
        raise GuardError("unsupported dependency marker syntax")

    try:
        result = evaluate(ast.parse(marker, mode="eval"))
    except (SyntaxError, TypeError, ValueError) as exc:
        raise GuardError("invalid dependency marker") from exc
    require(isinstance(result, bool), "invalid dependency marker result")
    return result


def required_packages(packages: dict) -> dict:
    root = packages.get("repopilot-api", {})
    pending = list(root.get("dependencies", [])) + list(root.get("dev-dependencies", {}).get("dev", []))
    seen = set()
    selected = {}
    while pending:
        dependency = pending.pop()
        if not marker_matches(dependency.get("marker")):
            continue
        name = dependency["name"]
        extras = tuple(sorted(dependency.get("extra", [])))
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        package = packages.get(name)
        require(package is not None and package.get("source") == {"registry": "https://pypi.org/simple"},
                f"unsupported or missing locked package: {name}")
        selected[name] = package
        pending.extend(package.get("dependencies", []))
        options = package.get("optional-dependencies", {})
        for extra in extras:
            require(extra in options, f"missing locked extra: {name}[{extra}]")
            pending.extend(options[extra])
    require(set(PARSER_VERSIONS) <= selected.keys(), "parser packages absent from resolved lock graph")
    return selected


def compatible_wheel(filename: str, mac_version: tuple[int, int]) -> bool:
    parts = filename.removesuffix(".whl").split("-")
    if not filename.endswith(".whl") or len(parts) < 5:
        return False
    py_tags, abi_tags, platforms = (part.split(".") for part in parts[-3:])
    valid_python = False
    for py in py_tags:
        if py in {"py3", "py314"} and "none" in abi_tags:
            valid_python = True
        match = re.fullmatch(r"cp3(\d+)", py)
        if match:
            minor = int(match.group(1))
            valid_python |= (minor == 14 and "cp314" in abi_tags) or (minor <= 14 and "abi3" in abi_tags)
    if not valid_python:
        return False
    for item in platforms:
        if item == "any":
            return True
        match = re.fullmatch(r"macosx_(\d+)_(\d+)_(arm64|universal2)", item)
        if match and (int(match.group(1)), int(match.group(2))) <= mac_version:
            return True
    return False


def audit_wheelhouse(packages: dict, wheelhouse: Path, mac_version: tuple[int, int]) -> tuple[dict, dict]:
    require(wheelhouse.is_dir() and not wheelhouse.is_symlink(), "offline wheelhouse is missing or unsafe")
    available, missing = {}, {}
    for name, package in sorted(packages.items()):
        candidates = []
        for wheel in package.get("wheels", []):
            filename = PurePosixPath(urllib.parse.unquote(urllib.parse.urlsplit(wheel["url"]).path)).name
            if compatible_wheel(filename, mac_version):
                candidates.append((filename, wheel["hash"].removeprefix("sha256:")))
        require(candidates, f"no compatible binary wheel in lock for {name}")
        found = None
        for filename, sha in sorted(candidates):
            candidate = wheelhouse / filename
            if candidate.exists() or candidate.is_symlink():
                require(regular(candidate), f"unsafe wheel path: {filename}")
                require(digest(candidate) == sha, f"wheel hash mismatch: {filename}")
                found = (candidate, sha)
                break
        if found:
            available[name] = found
        else:
            missing[name] = [filename for filename, _ in candidates]
    return available, missing


def clean_env(home: Path) -> dict[str, str]:
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(home), "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_ALLOW_PROTOCOL": ""}


def network_sandbox(args: list[str], port: int | None = None) -> list[str]:
    """Deny all network, except the single verified local PostgreSQL port when needed."""
    profile = "(version 1)(allow default)(deny network*)"
    if port is not None:
        require(type(port) is int and 0 < port < 65536, "invalid sandbox loopback port")
        profile += f'(allow network-outbound (remote ip "localhost:{port}"))'
    return [str(SANDBOX), "-p", profile, *args]


def command(args: list[str], *, env: dict, cwd: Path | None = None, timeout: int = 30,
            check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, env=env, cwd=cwd, timeout=timeout, check=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GuardError(f"command unavailable or timed out: {Path(args[0]).name}") from exc
    if check and result.returncode != 0:
        # Never print stderr: a subprocess may include secrets or database URLs.
        raise GuardError(f"command failed: {Path(args[0]).name} (exit {result.returncode})")
    return result


def verify_network_sandbox(python: Path, execute=command) -> None:
    """Probe only self-owned loopback listeners; never contact an external host."""
    require(SANDBOX.is_file() and os.access(SANDBOX, os.X_OK), "macOS sandbox-exec is unavailable")
    listeners = []
    try:
        for _ in range(2):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listeners.append(listener)
            listener.bind(("127.0.0.1", 0))
            listener.listen(8)
        ports = [listener.getsockname()[1] for listener in listeners]
        probe = ("import json,socket,sys; codes=[]\n"
                 "for raw in sys.argv[1:]:\n"
                 " s=socket.socket(); s.settimeout(2); codes.append(s.connect_ex(('127.0.0.1',int(raw)))); s.close()\n"
                 "a,b=socket.socketpair(); a.sendall(b'x'); ipc=(b.recv(1)==b'x'); a.close(); b.close()\n"
                 "print(json.dumps({'codes':codes,'ipc':ipc}))\n")
        arguments = [str(python), "-I", "-B", "-c", probe, *(str(port) for port in ports)]

        def measure(args):
            result = execute(args, env=clean_env(Path("/nonexistent")), timeout=8)
            try:
                return json.loads(result.stdout)
            except (ValueError, AttributeError) as exc:
                raise GuardError("invalid network sandbox probe") from exc

        baseline = measure(arguments)
        denied = measure(network_sandbox(arguments))
        selective = measure(network_sandbox(arguments, ports[0]))
        blocked = {errno.EPERM, errno.EACCES}
        require(baseline == {"codes": [0, 0], "ipc": True}, "local sandbox baseline failed")
        require(denied.get("ipc") is True and len(denied.get("codes", [])) == 2
                and all(code in blocked for code in denied["codes"]), "no-network sandbox was not enforced")
        require(selective.get("ipc") is True and len(selective.get("codes", [])) == 2
                and selective["codes"][0] == 0 and selective["codes"][1] in blocked,
                "single-port network sandbox was not enforced")
        print("Network sandbox verified with self-owned loopback probes; local IPC remains available")
    except OSError as exc:
        raise GuardError("cannot establish the required network sandbox") from exc
    finally:
        for listener in listeners:
            listener.close()


def check_interpreter(python: Path, execute=command) -> None:
    require(python.is_file() and os.access(python, os.X_OK), "CPython 3.14.10 interpreter is missing")
    probe = ("import json,platform,sys; print(json.dumps({'impl':platform.python_implementation(),"
             "'version':platform.python_version(),'machine':platform.machine(),'platform':sys.platform,"
             "'gil':sys._is_gil_enabled(),'base':sys.prefix==sys.base_prefix}))")
    result = execute([str(python), "-I", "-B", "-c", probe], env=clean_env(Path("/nonexistent")))
    try:
        actual = json.loads(result.stdout)
    except (ValueError, AttributeError) as exc:
        raise GuardError("could not verify Python interpreter") from exc
    require(actual == {"impl": "CPython", "version": "3.14.10", "machine": "arm64",
                       "platform": "darwin", "gil": True, "base": True},
            "need base, GIL-enabled CPython 3.14.10 on macOS ARM64")


def check_uv(binary: Path, wheel: Path, execute=command) -> None:
    require(regular(binary) and os.access(binary, os.X_OK), "verified uv 0.13.6 executable is missing")
    require(regular(wheel) and wheel.name == UV_WHEEL and digest(wheel) == UV_WHEEL_SHA256,
            "official uv 0.13.6 wheel is missing or has the wrong SHA-256")
    try:
        with zipfile.ZipFile(wheel) as archive:
            matches = [name for name in archive.namelist()
                       if not name.endswith("/") and PurePosixPath(name).name == "uv"]
            require(len(matches) == 1, "cannot identify uv executable in verified wheel")
            expected = hashlib.sha256(archive.read(matches[0])).hexdigest()
    except (OSError, zipfile.BadZipFile) as exc:
        raise GuardError("cannot read verified uv wheel") from exc
    require(digest(binary) == expected, "uv executable does not match verified wheel")
    version = execute(network_sandbox([str(binary), "--version"]), env=clean_env(Path("/nonexistent"))).stdout.strip()
    require(re.fullmatch(r"uv 0\.13\.6(?:\s+\([^\n]*\))?", version) is not None,
            "uv executable is not version 0.13.6")


def source_inventory(api: Path) -> dict[str, dict]:
    paths = [Path("pyproject.toml"), Path("uv.lock"), Path("alembic.ini")]
    paths += [Path("tests") / name for name in RELEASE_TESTS + HELPER_TESTS]
    paths += [Path(name) for name in FIXTURES]
    paths += [Path(name) for name in HARNESS_FILES]
    for name in ("app", "alembic"):
        root = api / name
        require(root.is_dir() and not root.is_symlink(), f"missing source directory: {name}")
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(item for item in dirs if item != "__pycache__")
            for item in dirs:
                require(not (Path(directory) / item).is_symlink(), "symlink in selected source tree")
            for item in sorted(files):
                if item.endswith(".py"):
                    paths.append((Path(directory) / item).relative_to(api))
    require(len(paths) == len(set(paths)), "duplicate staged source path")
    inventory = {}
    total = 0
    for relative in sorted(paths):
        require(not any(part.lower() in {".git", ".venv", "secrets", "credentials", ".aws"}
                        for part in relative.parts), f"excluded source path: {relative}")
        require(relative.name.lower() not in {"credentials.py", "secrets.py", "secret.py"},
                f"credential-named file requires separate review: {relative}")
        path = api / relative
        require(regular(path), f"required source or fixture missing: {relative}")
        require(all(not (api / parent).is_symlink() for parent in relative.parents if str(parent) != "."),
                f"unsafe source parent: {relative}")
        size = path.stat().st_size
        require(size <= 2 * 1024 * 1024, f"source exceeds staging bound: {relative}")
        total += size
        inventory[str(relative)] = {"sha256": digest(path), "bytes": size}
    require(total <= 64 * 1024 * 1024, "source inventory exceeds staging bound")
    # Missing or renamed release-gate tests must be noticed before pytest.
    all_tests = "\n".join((api / "tests" / name).read_text() for name in RELEASE_TESTS)
    found = {node.name for node in ast.walk(ast.parse(all_tests)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    required_functions = REQUIRED_CASES | {name.split("[", 1)[0] for name in P6_REQUIRED_PARAMETERS}
    require(required_functions <= found, "a required PostgreSQL test is missing")
    if SYNTHETIC_CAPTURE_CASES:
        capture = ast.parse((api / "tests/test_synthetic_capture.py").read_text())
        functions = {node.name: node for node in capture.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in SYNTHETIC_CAPTURE_CASES:
            require(name in functions, "a selected synthetic capture case is missing")
            require("synthetic_pg" not in {arg.arg for arg in functions[name].args.args},
                    "a synthetic capture case now needs a different disposable database")
    return inventory


def stage_sources(api: Path, destination: Path, inventory: dict) -> None:
    require(not destination.exists(), "source destination already exists")
    destination.mkdir(parents=True, mode=0o700)
    for relative, expected in inventory.items():
        source, target = api / relative, destination / relative
        require(regular(source) and digest(source) == expected["sha256"], "source changed while staging")
        data = source.read_bytes()
        require(len(data) == expected["bytes"] and hashlib.sha256(data).hexdigest() == expected["sha256"],
                "source changed while reading")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
    verify_inventory(destination, inventory, exact=True)


def verify_inventory(root: Path, inventory: dict, *, exact: bool = False) -> None:
    for relative, expected in inventory.items():
        path = root / relative
        require(regular(path) and path.stat().st_size == expected["bytes"]
                and digest(path) == expected["sha256"], f"staged source changed: {relative}")
    if exact:
        found = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            require(not any((Path(directory) / name).is_symlink() for name in dirs),
                    "symlink in staged source directory")
            for name in files:
                path = Path(directory) / name
                require(not path.is_symlink(), "symlink in staged source copy")
                found.add(str(path.relative_to(root)))
        require(found == set(inventory), "staged source contains missing or unexpected files")


def prepare_environment(uv: Path, python: Path, stage: Path, work: Path, wheels: dict, execute=command) -> Path:
    expected = required_packages(load_contract(stage))
    require(set(wheels) == set(expected), "wheelhouse does not match the locked test dependency closure")
    wheel_dir = work / "wheels"
    wheel_dir.mkdir(mode=0o700)
    for source, sha in wheels.values():
        target = wheel_dir / source.name
        require(regular(source) and digest(source) == sha, "verified wheel changed before copying")
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
        require(digest(target) == sha, "verified wheel changed during copying")
    env_dir = work / "venv"
    env = {**clean_env(work), "UV_PROJECT_ENVIRONMENT": str(env_dir), "UV_CACHE_DIR": str(work / "uv-cache"),
           "UV_PYTHON_DOWNLOADS": "never", "UV_LINK_MODE": "copy"}
    requirements = work / "requirements-verified.txt"
    fd = os.open(requirements, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        for name, package in sorted(expected.items()):
            version = package["version"]
            sha = wheels[name][1]
            require(re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name) is not None
                    and re.fullmatch(r"[A-Za-z0-9.+!-]+", version) is not None
                    and re.fullmatch(r"[0-9a-f]{64}", sha) is not None,
                    "unsafe locked package identity")
            stream.write(f"{name}=={version} --hash=sha256:{sha}\n")
    execute(network_sandbox([str(python), "-I", "-B", "-m", "venv", "--without-pip", str(env_dir)]),
            env=env, cwd=work, timeout=120)
    executable = env_dir / "bin" / "python"
    require(executable.is_file() and os.access(executable, os.X_OK), "fresh disposable Python environment is missing")
    execute(network_sandbox([str(uv), "pip", "sync", "--python", str(executable), "--require-hashes", "--offline",
                             "--no-index", "--no-build", "--no-python-downloads", "--no-config", "--find-links",
                             str(wheel_dir), str(requirements)]), env=env, cwd=work, timeout=300)
    probe = ("import importlib.metadata as m,json,sys; "
             "print(json.dumps({'prefix':sys.prefix,'packages':{x.metadata['Name'].lower().replace('_','-'):"
             "x.version for x in m.distributions()}}))")
    result = execute(network_sandbox([str(executable), "-I", "-B", "-c", probe]), env=clean_env(work))
    try:
        installed = json.loads(result.stdout)
    except (ValueError, AttributeError) as exc:
        raise GuardError("could not verify disposable Python environment") from exc
    require(Path(installed["prefix"]).resolve() == env_dir.resolve(), "unexpected disposable Python prefix")
    require(all(installed["packages"].get(name) == item["version"] for name, item in expected.items()),
            "disposable environment does not match locked packages")
    require(set(installed["packages"]) == set(expected), "unexpected package in disposable environment")
    execute(network_sandbox([str(uv), "lock", "--project", str(stage), "--check", "--offline", "--no-config",
                             "--no-python-downloads", "--python", str(python)]), env=env, cwd=work, timeout=120)
    print("uv 0.13.6 offline lock consistency check passed")
    return executable


def run_safety_tests(python: Path, stage: Path, work: Path, execute=command) -> None:
    """Run the staged, synthetic-only guard suite before creating a database."""
    test_file = stage / "evaluation/test_tree_sitter_pg_harness.py"
    require(regular(test_file), "staged harness safety tests are missing")
    result = execute(network_sandbox([str(python), "-I", "-B", str(test_file)]),
                     env={**clean_env(work), "TMPDIR": str(work)}, cwd=work, timeout=60)
    match = re.search(r"Ran (\d+) tests? in", result.stderr)
    require(match is not None and int(match.group(1)) >= 41 and re.search(r"(?m)^OK\s*$", result.stderr),
            "staged harness safety suite did not complete successfully")
    print(f"Staged harness safety tests: {match.group(1)} passed")


def run_native_tests(python: Path, stage: Path, work: Path) -> None:
    """Run synthetic parser children before Docker creation, with no credentials.

    The trusted pytest coordinator cannot itself be sandboxed on macOS because
    the actual production child must apply the reviewed, nested sandbox. Every
    parser child applies that no-network profile; the matrix additionally
    rejects IP sockets in the Python test coordinator.
    """
    report, log = work / "native-pytest.xml", work / "native-pytest.log"
    env = {**clean_env(work), "TMPDIR": str(work), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    args = [str(python), "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
            "--junitxml", str(report), "evaluation/test_supervised_parser.py",
            "evaluation/test_supervised_parser_native_smoke.py",
            "evaluation/test_supervised_parser_native_matrix.py"]
    print("Exact synthetic native test command:", shlex.join(args), flush=True)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            result = subprocess.run(args, env=env, cwd=stage, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GuardError("native parser tests failed to start or timed out; inspect private log") from exc
    require(result.returncode == 0, "native parser tests failed; inspect private log")
    try:
        cases = list(ET.parse(report).getroot().iter("testcase"))
    except (OSError, ET.ParseError) as exc:
        raise GuardError("missing or invalid native parser JUnit report") from exc
    require(bool(cases) and not any(any(case.find(kind) is not None for kind in ("skipped", "failure", "error"))
                                    for case in cases), "native parser tests skipped or failed")
    names = {case.get("name") for case in cases}
    extensions = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rs", ".c",
                  ".h", ".cpp", ".cc", ".hpp", ".cs"}
    require(all(f"test_actual_supervisor_and_collection_for_every_extension[{suffix}]" in names
                for suffix in extensions), "native supervised extension coverage is incomplete")
    require("test_actual_go_run_gate_reports_locked_parser_and_grammar" in names,
            "native Go run() gate did not execute")
    print(f"Synthetic native parser tests: {len(cases)} passed; 0 failed; 0 skipped")


def validate_target(url: str, database: str, port: int) -> None:
    require(re.fullmatch(r"repopilot_5b1_checks_[0-9a-f]{16}", database) is not None,
            "unsafe database identity")
    try:
        value = urllib.parse.urlsplit(url)
        valid = (value.scheme == "postgresql+psycopg" and value.username == ROLE and value.password is None
                 and value.hostname == "127.0.0.1" and value.port == port and 0 < port < 65536
                 and value.path == "/" + database and not value.query and not value.fragment
                 and value.netloc == f"{ROLE}@127.0.0.1:{port}")
    except ValueError as exc:
        raise GuardError("unsafe database URL") from exc
    require(valid, "unsafe database URL")


def make_target(database: str, port: int) -> str:
    return f"postgresql+psycopg://{ROLE}@127.0.0.1:{port}/{database}"


def verify_container(info: dict, cid: str, name: str, nonce: str, *, started: bool) -> int | None:
    require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None and info.get("id") == cid,
            "unexpected container identity")
    labels = info.get("labels")
    require(isinstance(labels, dict), "container ownership labels are missing")
    require(info.get("name") == "/" + name and info.get("image") == IMAGE
            and labels.get("repopilot.test-run") == nonce and labels.get("repopilot.test-purpose") == PURPOSE,
            "unexpected container ownership")
    require(info.get("privileged") is False and info.get("network") == "bridge", "unsafe container privileges or network")
    require(info.get("mounts") == [], "unexpected container mounts")
    require(info.get("tmpfs") == {"/var/lib/postgresql/data": "rw"}, "database storage is not the expected tmpfs")
    bindings = info.get("bindings")
    require(isinstance(bindings, dict) and set(bindings) == {"5432/tcp"}
            and isinstance(bindings["5432/tcp"], list) and len(bindings["5432/tcp"]) == 1,
            "unexpected port bindings")
    configured = bindings["5432/tcp"][0]
    require(isinstance(configured, dict) and configured.get("HostIp") == "127.0.0.1"
            and configured.get("HostPort") in ("", "0"),
            "database is not configured for a unique loopback port")
    if not started:
        return None
    ports = info.get("ports")
    require(isinstance(ports, dict) and set(ports) == {"5432/tcp"}
            and isinstance(ports["5432/tcp"], list) and len(ports["5432/tcp"]) == 1,
            "unexpected published ports")
    published = ports["5432/tcp"][0]
    require(isinstance(published, dict), "invalid published port details")
    raw_port = published.get("HostPort", "")
    require(published.get("HostIp") == "127.0.0.1" and isinstance(raw_port, str)
            and re.fullmatch(r"[0-9]{1,5}", raw_port) is not None, "database is not bound to loopback")
    port = int(raw_port)
    require(0 < port < 65536, "invalid published port")
    return port


class DockerDriver:
    """Docker CLI adapter; no shell, inherited credentials, global context or image pulls."""

    def __init__(self, docker: Path, socket: Path, work: Path, python: Path, stage: Path):
        require(docker.is_file() and os.access(docker, os.X_OK), "Docker CLI is unavailable")
        require(socket.is_absolute() and not socket.is_symlink() and socket.exists()
                and stat.S_ISSOCK(socket.stat().st_mode), "explicit local Docker Unix socket is unavailable")
        self.docker, self.socket, self.work, self.python, self.stage = docker, socket, work, python, stage
        config = work / "docker-config"
        config.mkdir(mode=0o700)
        self.env = {**clean_env(work), "DOCKER_CONFIG": str(config)}

    def docker_command(self, args: list[str], *, extra: dict | None = None, check: bool = True):
        return command([str(self.docker), "--host", f"unix://{self.socket}", *args],
                       env={**self.env, **(extra or {})}, cwd=self.work, check=check)

    def ping(self) -> None:
        self.docker_command(["info"])

    def image_ready(self) -> None:
        image = self.docker_command(["image", "inspect", "--format", "{{.Id}}", IMAGE]).stdout.strip()
        require(image == IMAGE, "reviewed local pgvector image is unavailable; no pull is permitted")

    def names(self) -> set[str]:
        result = self.docker_command(["ps", "-a", "--format", "{{.Names}}"])
        return {name for line in result.stdout.splitlines() for name in line.split(",") if name}

    def ids(self) -> set[str]:
        result = self.docker_command(["ps", "-a", "--no-trunc", "--format", "{{.ID}}"])
        return set(result.stdout.splitlines())

    def create(self, name: str, nonce: str, database: str, password: str) -> str:
        # No --rm: Docker would also remove associated anonymous volumes.
        args = ["create", "--pull=never", "--name", name, "--network", "bridge",
                "--label", f"repopilot.test-run={nonce}", "--label", f"repopilot.test-purpose={PURPOSE}",
                "--tmpfs", "/var/lib/postgresql/data:rw", "-p", "127.0.0.1::5432",
                "-e", f"POSTGRES_USER={ROLE}", "-e", f"POSTGRES_DB={database}",
                "-e", "POSTGRES_PASSWORD", "-e", "PGPASSWORD",
                "-e", "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256",
                "-e", "POSTGRES_HOST_AUTH_METHOD=scram-sha-256", IMAGE]
        return self.docker_command(args, extra={"POSTGRES_PASSWORD": password, "PGPASSWORD": password}).stdout.strip()

    def inspect(self, cid: str) -> dict:
        fields = {"id": ".Id", "name": ".Name", "image": ".Image", "labels": ".Config.Labels",
                  "privileged": ".HostConfig.Privileged", "network": ".HostConfig.NetworkMode",
                  "mounts": ".Mounts", "tmpfs": ".HostConfig.Tmpfs", "bindings": ".HostConfig.PortBindings",
                  "ports": ".NetworkSettings.Ports"}
        result = {}
        for key, field in fields.items():
            output = self.docker_command(["inspect", "--format", "{{json " + field + "}}", cid]).stdout
            try:
                result[key] = json.loads(output)
            except ValueError as exc:
                raise GuardError("invalid Docker inspection response") from exc
        return result

    def start(self, cid: str) -> None:
        self.docker_command(["start", cid])

    def wait(self, cid: str, database: str) -> None:
        for _ in range(30):
            result = self.docker_command(["exec", cid, "pg_isready", "-q", "-U", ROLE, "-d", database], check=False)
            if result.returncode == 0:
                return
            time.sleep(1)
        raise GuardError("disposable PostgreSQL did not become ready")

    def sql(self, cid: str, database: str, query: str) -> str:
        return self.docker_command(["exec", cid, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-Atq",
                                    "-U", ROLE, "-d", database, "-c", query]).stdout.strip()

    def auth_rule(self, cid: str, database: str) -> str:
        return self.sql(cid, database, "SELECT CASE WHEN "
            "count(*) FILTER (WHERE type LIKE 'host%' AND auth_method='scram-sha-256') > 0 "
            "AND count(*) FILTER (WHERE (type LIKE 'host%' OR type='local') AND "
            "(auth_method IS DISTINCT FROM 'scram-sha-256' OR error IS NOT NULL)) = 0 "
            "AND count(*) FILTER (WHERE error IS NOT NULL) = 0 "
            "THEN 'scram-sha-256' ELSE 'unsafe' END FROM pg_hba_file_rules")

    def initial_state(self, cid: str, database: str) -> str:
        return self.sql(cid, database, "SELECT current_database() || '|' || current_user || '|' || "
            "(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f'))")

    def set_marker(self, cid: str, database: str) -> None:
        require(re.fullmatch(r"repopilot_5b1_checks_[0-9a-f]{16}", database) is not None, "unsafe marker target")
        self.sql(cid, database, f"COMMENT ON DATABASE {database} IS '{MARKER}'")

    def marker_state(self, cid: str, database: str) -> str:
        return self.sql(cid, database, "SELECT current_database() || '|' || current_user || '|' || "
            "coalesce(shobj_description(oid, 'pg_database'),'') FROM pg_database WHERE datname=current_database()")

    def passwordless_rejected(self, port: int, database: str) -> bool:
        code = ("import psycopg,sys\ntry:\n"
                " psycopg.connect(host='127.0.0.1',port=int(sys.argv[1]),dbname=sys.argv[2],"
                "user='capture_fixture',password='',connect_timeout=3)\n"
                "except psycopg.OperationalError as e:\n"
                " s=str(e).lower(); sys.exit(0 if 'no password supplied' in s or 'password authentication failed' in s else 2)\n"
                "sys.exit(3)\n")
        result = command(network_sandbox([str(self.python), "-I", "-B", "-c", code, str(port), database], port),
                         env=clean_env(self.work), cwd=self.work, check=False)
        return result.returncode == 0

    def host_state(self, port: int, database: str, password: str) -> dict:
        code = ("import json,psycopg,sys\n"
                "with psycopg.connect(host='127.0.0.1',port=int(sys.argv[1]),dbname=sys.argv[2],"
                "user='capture_fixture',connect_timeout=3) as c:\n"
                " with c.cursor() as q:\n"
                "  q.execute(\"SELECT current_database(),current_user,shobj_description(oid,'pg_database') "
                "FROM pg_database WHERE datname=current_database()\"); row=q.fetchone()\n"
                "  q.execute(\"SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')\"); count=q.fetchone()[0]\n"
                "  print(json.dumps({'database':row[0],'role':row[1],'marker':row[2],'objects':count}))\n")
        result = command(network_sandbox([str(self.python), "-I", "-B", "-c", code, str(port), database], port),
                         env={**clean_env(self.work), "PGPASSWORD": password}, cwd=self.work)
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise GuardError("invalid authenticated database inspection") from exc

    def pytest(self, url: str, password: str) -> None:
        env = {**clean_env(self.work), "PGPASSWORD": password, "TEST_DATABASE_URL": url,
               "TMPDIR": str(self.work), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "APP_ENV": "test",
               "GITHUB_OAUTH_ENABLED": "false", "EMBEDDING_PROVIDER": "disabled", "EMBEDDING_ALLOW_PAID": "false",
               "INVESTIGATION_PROVIDER": "mock", "INVESTIGATION_REAL_ENABLED": "false",
               "INVESTIGATION_PAID_BACKGROUND_ENABLED": "false", "INVESTIGATION_COUNT_EXTERNAL_ENABLED": "false"}
        report = self.work / "pytest.xml"
        log = self.work / "pytest.log"
        args = [str(self.python), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "--junitxml", str(report), "--deselect", DESELECT]
        for case in P4_DESELECT:
            args += ["--deselect", case]
        args += ["tests/" + name for name in RELEASE_TESTS]
        args += ["tests/test_synthetic_capture.py::" + name for name in SYNTHETIC_CAPTURE_CASES]
        port = urllib.parse.urlsplit(url).port
        require(port is not None, "missing verified PostgreSQL port")
        args = network_sandbox(args, port)
        print("Exact test command:", shlex.join(args), flush=True)
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                result = subprocess.run(args, env=env, cwd=self.stage, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=900, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GuardError("pytest failed to start or timed out; inspect private log") from exc
        require(result.returncode == 0, "pytest failed; inspect private log")
        validate_junit(report)

    def pytest_native_postgres(self, url: str, password: str) -> None:
        """Run actual sandboxed parser children through a test-only local IPC broker."""
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        require(port is not None, "missing verified PostgreSQL port")
        validate_target(url, parsed.path.removeprefix("/"), port)
        broker_script = self.stage / "evaluation/supervised_parser_test_broker.py"
        require(regular(broker_script), "staged parser test broker is missing")
        pytest_socket, broker_socket = socket.socketpair()
        require(pytest_socket.family == socket.AF_UNIX and broker_socket.family == socket.AF_UNIX,
                "parser broker requires local IPC")
        broker = None
        result = None
        try:
            broker_env = {**clean_env(self.work), "TMPDIR": str(self.work)}
            broker = subprocess.Popen([str(self.python), "-I", "-B", str(broker_script), str(broker_socket.fileno())],
                                      env=broker_env, cwd=self.stage, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      pass_fds=(broker_socket.fileno(),), close_fds=True)
            broker_socket.close()
            env = {**clean_env(self.work), "PGPASSWORD": password, "TEST_DATABASE_URL": url,
                   "REPOPILOT_PARSER_BROKER_FD": str(pytest_socket.fileno()), "TMPDIR": str(self.work),
                   "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "APP_ENV": "test", "GITHUB_OAUTH_ENABLED": "false",
                   "EMBEDDING_PROVIDER": "disabled", "EMBEDDING_ALLOW_PAID": "false",
                   "INVESTIGATION_PROVIDER": "mock", "INVESTIGATION_REAL_ENABLED": "false",
                   "INVESTIGATION_PAID_BACKGROUND_ENABLED": "false", "INVESTIGATION_COUNT_EXTERNAL_ENABLED": "false"}
            report, log = self.work / "native-postgres.xml", self.work / "native-postgres.log"
            args = [str(self.python), "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                    "--junitxml", str(report), "tests/test_supervised_parser_postgres_native.py",
                    "tests/test_supervised_parser_postgres_drift.py"]
            args = network_sandbox(args, port)
            print("Exact native PostgreSQL test command:", shlex.join(args), flush=True)
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                result = subprocess.run(args, env=env, cwd=self.stage, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=300, check=False, pass_fds=(pytest_socket.fileno(),))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GuardError("native PostgreSQL tests failed to start or timed out; inspect private log") from exc
        finally:
            pytest_socket.close()
            broker_socket.close()
            if broker is not None:
                try:
                    broker.wait(timeout=15)
                except subprocess.TimeoutExpired as exc:
                    broker.kill()
                    broker.wait(timeout=5)
                    raise GuardError("parser broker cleanup timed out; child cleanup requires review") from exc
                require(broker.returncode == 0, "parser broker failed; inspect private test log")
        require(result is not None and result.returncode == 0, "native PostgreSQL tests failed; inspect private log")
        validate_named_junit(report, NATIVE_PG_CASES, "Native PostgreSQL tests")

    def remove(self, cid: str) -> None:
        # Ownership is verified immediately before this call; never remove volumes.
        self.docker_command(["rm", "-f", cid])


def validate_named_junit(report: Path, required_cases: frozenset[str], label: str) -> None:
    try:
        cases = list(ET.parse(report).getroot().iter("testcase"))
    except (OSError, ET.ParseError) as exc:
        raise GuardError("missing or invalid pytest JUnit report") from exc
    require(bool(cases), "no tests were collected")
    require(not any(any(case.find(kind) is not None for kind in ("skipped", "failure", "error")) for case in cases),
            "selected suite contains skipped, failed or errored tests")
    for name in required_cases:
        require(sum(case.get("name") == name for case in cases) == 1, f"required test did not execute: {name}")
    print(f"{label}: {len(cases)} passed; 0 failed; 0 skipped; "
          f"all {len(required_cases)} required cases executed")


def validate_junit(report: Path) -> None:
    validate_named_junit(report, REQUIRED_CASES | P6_REQUIRED_PARAMETERS, "PostgreSQL regression tests")


def cleanup_owned(driver, cid: str, name: str, nonce: str) -> None:
    """Remove only the exact container created by this run, never its volumes."""
    require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None, "cannot safely identify container for cleanup")
    driver.ping()
    if cid not in driver.ids():
        return
    info = driver.inspect(cid)
    labels = info.get("labels")
    require(isinstance(labels, dict), "container ownership could not be verified; cleanup refused")
    require(info.get("id") == cid and info.get("name") == "/" + name and info.get("image") == IMAGE
            and labels.get("repopilot.test-run") == nonce and labels.get("repopilot.test-purpose") == PURPOSE,
            "container ownership could not be verified; cleanup refused")
    driver.remove(cid)
    require(cid not in driver.ids(), "disposable container cleanup could not be confirmed")


def run_database_gate(driver, nonce: str, password: str, verify_inputs) -> None:
    """All checks here are required before the injected driver's pytest call."""
    require(re.fullmatch(r"[0-9a-f]{16}", nonce) is not None, "invalid run identity")
    require(re.fullmatch(r"[0-9a-f]{64}", password) is not None, "invalid test-only password")
    name = f"repopilot-ts0252-pg-{nonce}"
    database = f"repopilot_5b1_checks_{nonce}"
    driver.ping()
    driver.image_ready()
    require(name not in driver.names(), "unexpected existing container identity")
    cid = None
    try:
        cid = driver.create(name, nonce, database, password)
        require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None,
                f"Docker returned an invalid identity; inspect {name} manually")
        print(f"Created disposable container={cid} name={name} database={database}")
        verify_container(driver.inspect(cid), cid, name, nonce, started=False)
        driver.start(cid)
        driver.wait(cid, database)
        port = verify_container(driver.inspect(cid), cid, name, nonce, started=True)
        require(driver.auth_rule(cid, database) == "scram-sha-256", "SCRAM-only authentication guard failed")
        require(driver.initial_state(cid, database) == f"{database}|{ROLE}|0", "unexpected or nonempty database")
        driver.set_marker(cid, database)
        require(driver.marker_state(cid, database) == f"{database}|{ROLE}|{MARKER}", "database marker mismatch")
        require(driver.passwordless_rejected(port, database), "passwordless TCP access was not rejected")
        require(driver.host_state(port, database, password) == {
            "database": database, "role": ROLE, "marker": MARKER, "objects": 0,
        }, "authenticated loopback database verification failed")
        url = make_target(database, port)
        validate_target(url, database, port)
        require(verify_container(driver.inspect(cid), cid, name, nonce, started=True) == port,
                "published port changed before pytest")
        require(driver.marker_state(cid, database) == f"{database}|{ROLE}|{MARKER}",
                "database marker changed before pytest")
        verify_inputs()
        print(f"Verified disposable container={cid} database={database} host=127.0.0.1 port={port}")
        driver.pytest(url, password)
        verify_inputs()
        driver.pytest_native_postgres(url, password)
        verify_inputs()
    finally:
        if cid and re.fullmatch(r"[0-9a-f]{64}", cid):
            try:
                cleanup_owned(driver, cid, name, nonce)
            except GuardError:
                print(f"Cleanup not confirmed; inspect only container={cid} name={name}", file=sys.stderr)
                raise


def check_inputs(api: Path, python: Path, uv: Path, uv_wheel: Path, wheelhouse: Path,
                 *, execute=command) -> tuple[dict, dict, list[str]]:
    """Collect read-only prerequisite failures; never start Docker or install packages."""
    errors = []
    inventory, wheels, packages = {}, {}, {}
    try:
        check_interpreter(python, execute)
    except (GuardError, OSError) as exc:
        errors.append(str(exc))
    if not regular(uv) or not os.access(uv, os.X_OK):
        errors.append("verified uv 0.13.6 executable is missing")
    if not regular(uv_wheel):
        errors.append("official uv 0.13.6 wheel is missing")
    if regular(uv) and os.access(uv, os.X_OK) and regular(uv_wheel):
        try:
            check_uv(uv, uv_wheel, execute)
        except (GuardError, OSError) as exc:
            errors.append(str(exc))
    try:
        inventory = source_inventory(api)
        packages = required_packages(load_contract(api))
    except (GuardError, OSError, ValueError, KeyError, SyntaxError) as exc:
        errors.append(f"source or lock preflight: {exc}")
    if packages:
        if not wheelhouse.is_dir() or wheelhouse.is_symlink():
            missing = [f"{name}=={item['version']}" for name, item in sorted(packages.items())]
            errors.append("offline wheelhouse is missing; unverified packages: " + ", ".join(missing))
        else:
            try:
                version = platform.mac_ver()[0]
                pieces = tuple(map(int, version.split(".")[:2]))
                require(sys.platform == "darwin" and len(pieces) == 2, "macOS version is unavailable")
                wheels, missing = audit_wheelhouse(packages, wheelhouse, pieces)
                if missing:
                    descriptions = [f"{name}=={packages[name]['version']} ({' or '.join(candidates)})"
                                    for name, candidates in sorted(missing.items())]
                    errors.append("offline wheels missing: " + "; ".join(descriptions))
            except (GuardError, OSError, ValueError, KeyError) as exc:
                errors.append(str(exc))
    return inventory, wheels, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEST ONLY: staged Tree-sitter disposable PostgreSQL gate")
    parser.add_argument("action", choices=("check", "run"), help="check is read-only; run may create a test container")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="base CPython 3.14.10 ARM64")
    parser.add_argument("--uv", type=Path, default=Path("/nonexistent/uv"), help="verified uv 0.13.6 executable")
    parser.add_argument("--uv-wheel", type=Path, default=Path("/nonexistent/" + UV_WHEEL))
    parser.add_argument("--wheelhouse", type=Path, default=Path("/nonexistent/wheelhouse"))
    parser.add_argument("--docker", type=Path, default=Path(shutil.which("docker") or "/nonexistent/docker"))
    parser.add_argument("--socket", type=Path, default=Path.home() / ".docker/run/docker.sock")
    args = parser.parse_args(argv)
    inventory, wheels, errors = check_inputs(API_ROOT, args.python, args.uv, args.uv_wheel, args.wheelhouse)
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}", file=sys.stderr)
        print("Docker and PostgreSQL were not contacted; no dependencies were installed.", file=sys.stderr)
        return 1
    print(f"Preflight: {len(inventory)} source/fixture files and {len(wheels)} locked wheels verified")
    if args.action == "check":
        print("Read-only check only; Docker daemon and database guards were not exercised")
        return 0
    # Fresh private state; never copy source or install into the repository or its .venv.
    work = Path(tempfile.mkdtemp(prefix="repopilot-ts0252-pg-", dir="/private/tmp"))
    os.chmod(work, 0o700)
    require(not work.resolve().is_relative_to(REPO_ROOT), "temporary directory is inside the repository")
    print(f"Private run artifacts: {work}")
    stage = work / "source" / "apps" / "api"
    stage_sources(API_ROOT, stage, inventory)
    runner_sha = digest(Path(__file__))
    uv_sha = digest(args.uv)
    manifest = {"source_kind": "current-working-tree-snapshot", "git_commit": None, "runner_sha256": runner_sha,
                "files": inventory, "python": "CPython 3.14.10 GIL-enabled macOS ARM64",
                "uv_version": EXPECTED_UV, "uv_binary_sha256": uv_sha, "uv_wheel_sha256": UV_WHEEL_SHA256,
                "wheels": {name: {"filename": path.name, "sha256": sha} for name, (path, sha) in wheels.items()},
                "deselected_real_git_case": DESELECT}
    manifest_file = work / "source-manifest.json"
    fd = os.open(manifest_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
    driver = DockerDriver(args.docker, args.socket, work, work / "venv/bin/python", stage)
    driver.ping()  # Read-only check before creating the disposable environment.
    verify_network_sandbox(args.python)  # Local synthetic sockets only; before any package installation.
    uv_copy = work / "uv"
    shutil.copyfile(args.uv, uv_copy)
    os.chmod(uv_copy, 0o700)
    require(digest(uv_copy) == uv_sha, "uv executable changed during copying")
    check_uv(uv_copy, args.uv_wheel)
    python = prepare_environment(uv_copy, args.python, stage, work, wheels)
    driver.python = python

    def verify_inputs() -> None:
        require(digest(Path(__file__)) == runner_sha, "runner changed during verification")
        verify_inventory(API_ROOT, inventory)
        verify_inventory(stage, inventory, exact=True)

    verify_inputs()
    run_safety_tests(python, stage, work)
    verify_inputs()
    run_native_tests(python, stage, work)
    verify_inputs()
    run_database_gate(driver, secrets.token_hex(8), secrets.token_hex(32), verify_inputs)
    print(f"Disposable container cleaned; private source manifest and test results retained in {work}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GuardError, OSError, ValueError, KeyError, SyntaxError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
