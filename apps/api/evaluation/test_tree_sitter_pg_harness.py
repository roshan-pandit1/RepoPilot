"""Synthetic safety tests; these never invoke Docker, PostgreSQL, pytest or a model."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tree_sitter_pg_harness as h  # noqa: E402


class FakeDocker:
    """Imitates only the runner's adapter and records every potentially mutating action."""

    def __init__(self):
        self.calls = []
        self.cid = "a" * 64
        self.nonce = "1234567890abcdef"
        self.name = f"repopilot-ts0252-pg-{self.nonce}"
        self.database = f"repopilot_5b1_checks_{self.nonce}"
        self.available = True
        self.image_available = True
        self.existing = set()
        self.present = False
        self.started = False
        self.inspections = 0
        self.wrong_owner = False
        self.mounts = []
        self.privileged = False
        self.network = "bridge"
        self.tmpfs = {"/var/lib/postgresql/data": "rw"}
        self.binding_host = "127.0.0.1"
        self.published_host = "127.0.0.1"
        self.final_port = "49111"
        self.scram = "scram-sha-256"
        self.marker = h.MARKER
        self.passwordless_denied = True
        self.authenticated = True
        self.authentication_error = False
        self.objects = 0

    def ping(self):
        self.calls.append("ping")
        if not self.available:
            raise h.GuardError("Docker daemon unavailable")

    def image_ready(self):
        self.calls.append("image")
        if not self.image_available:
            raise h.GuardError("image unavailable")

    def names(self):
        self.calls.append("names")
        return self.existing

    def ids(self):
        self.calls.append("ids")
        return {self.cid} if self.present else set()

    def create(self, name, nonce, database, password):
        self.calls.append("create")
        assert (name, nonce, database, password) == (self.name, self.nonce, self.database, "f" * 64)
        self.present = True
        return self.cid

    def inspect(self, cid):
        self.calls.append("inspect")
        self.inspections += 1
        assert cid == self.cid
        port = self.final_port if self.inspections >= 3 else "49111"
        return {"id": cid, "name": "/" + self.name, "image": h.IMAGE,
                "labels": {"repopilot.test-run": "wrong" if self.wrong_owner else self.nonce,
                           "repopilot.test-purpose": h.PURPOSE},
                "privileged": self.privileged, "network": self.network, "mounts": self.mounts,
                "tmpfs": self.tmpfs,
                "bindings": {"5432/tcp": [{"HostIp": self.binding_host, "HostPort": ""}]},
                "ports": {"5432/tcp": [{"HostIp": self.published_host, "HostPort": port}]} if self.started else {}}

    def start(self, cid):
        self.calls.append("start")
        self.started = True

    def wait(self, cid, database):
        self.calls.append("wait")

    def auth_rule(self, cid, database):
        self.calls.append("auth_rule")
        return self.scram

    def initial_state(self, cid, database):
        self.calls.append("initial_state")
        return f"{database}|{h.ROLE}|{self.objects}"

    def set_marker(self, cid, database):
        self.calls.append("set_marker")

    def marker_state(self, cid, database):
        self.calls.append("marker_state")
        return f"{database}|{h.ROLE}|{self.marker}"

    def passwordless_rejected(self, port, database):
        self.calls.append("passwordless")
        return self.passwordless_denied

    def host_state(self, port, database, password):
        self.calls.append("host_state")
        if self.authentication_error:
            raise h.GuardError("authentication failed")
        return {"database": database, "role": h.ROLE, "marker": h.MARKER,
                "objects": 0 if self.authenticated else 1}

    def pytest(self, url, password):
        self.calls.append("pytest")

    def pytest_native_postgres(self, url, password):
        self.calls.append("pytest_native_postgres")

    def remove(self, cid):
        self.calls.append("remove")
        self.present = False


class DatabaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.docker = FakeDocker()

    def gate(self, verify=lambda: None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            h.run_database_gate(self.docker, self.docker.nonce, "f" * 64, verify)

    def rejected_before_pytest(self):
        with self.assertRaises(h.GuardError):
            self.gate()
        self.assertNotIn("pytest", self.docker.calls)
        self.assertNotIn("pytest_native_postgres", self.docker.calls)

    def test_success_path_is_mock_only_and_cleans_its_own_container(self):
        self.gate()
        self.assertEqual(self.docker.calls.count("pytest"), 1)
        self.assertEqual(self.docker.calls.count("pytest_native_postgres"), 1)
        self.assertEqual(self.docker.calls.count("remove"), 1)
        self.assertFalse(self.docker.present)

    def test_missing_docker_daemon_stops_before_create(self):
        self.docker.available = False
        self.rejected_before_pytest()
        self.assertNotIn("create", self.docker.calls)

    def test_missing_local_image_stops_before_create(self):
        self.docker.image_available = False
        self.rejected_before_pytest()
        self.assertNotIn("create", self.docker.calls)

    def test_unexpected_existing_name_is_not_created_or_removed(self):
        self.docker.existing.add(self.docker.name)
        self.rejected_before_pytest()
        self.assertNotIn("create", self.docker.calls)
        self.assertNotIn("remove", self.docker.calls)

    def test_unexpected_container_identity_cannot_be_cleaned_up(self):
        self.docker.wrong_owner = True
        self.rejected_before_pytest()
        self.assertNotIn("remove", self.docker.calls)

    def test_unexpected_mounts_stop_before_start(self):
        self.docker.mounts = [{"Type": "volume", "Name": "application-data"}]
        self.rejected_before_pytest()
        self.assertNotIn("start", self.docker.calls)
        self.assertIn("remove", self.docker.calls)

    def test_missing_tmpfs_stops_before_start(self):
        self.docker.tmpfs = {}
        self.rejected_before_pytest()
        self.assertNotIn("start", self.docker.calls)

    def test_privileged_or_host_network_container_stops_before_start(self):
        for change in ("privileged", "network"):
            with self.subTest(change=change):
                self.docker = FakeDocker()
                setattr(self.docker, change, True if change == "privileged" else "host")
                self.rejected_before_pytest()
                self.assertNotIn("start", self.docker.calls)

    def test_non_loopback_configured_port_stops_before_start(self):
        self.docker.binding_host = "0.0.0.0"
        self.rejected_before_pytest()
        self.assertNotIn("start", self.docker.calls)

    def test_non_loopback_published_port_stops_before_sql(self):
        self.docker.published_host = "0.0.0.0"
        self.rejected_before_pytest()
        self.assertNotIn("auth_rule", self.docker.calls)

    def test_missing_scram_requirement_stops_before_marker(self):
        self.docker.scram = "unsafe"
        self.rejected_before_pytest()
        self.assertNotIn("set_marker", self.docker.calls)

    def test_nonempty_database_stops_before_marker(self):
        self.docker.objects = 1
        self.rejected_before_pytest()
        self.assertNotIn("set_marker", self.docker.calls)

    def test_wrong_database_marker(self):
        self.docker.marker = "wrong"
        self.rejected_before_pytest()
        self.assertNotIn("passwordless", self.docker.calls)

    def test_passwordless_access_must_be_rejected(self):
        self.docker.passwordless_denied = False
        self.rejected_before_pytest()
        self.assertNotIn("host_state", self.docker.calls)

    def test_failed_authenticated_guard(self):
        self.docker.authenticated = False
        self.rejected_before_pytest()

    def test_authenticated_connection_failure_stops_before_pytest(self):
        self.docker.authentication_error = True
        self.rejected_before_pytest()

    def test_unsafe_database_url_never_reaches_pytest(self):
        with mock.patch.object(h, "make_target", return_value="postgresql+psycopg://x@localhost/repopilot-local"):
            self.rejected_before_pytest()

    def test_port_change_before_pytest_is_rejected(self):
        self.docker.final_port = "49112"
        self.rejected_before_pytest()

    def test_source_change_before_pytest_is_rejected(self):
        def changed():
            raise h.GuardError("changed source")
        with self.assertRaises(h.GuardError):
            self.gate(changed)
        self.assertNotIn("pytest", self.docker.calls)

    def test_cleanup_rejects_wrong_ownership(self):
        self.docker.present = True
        self.docker.wrong_owner = True
        with self.assertRaisesRegex(h.GuardError, "ownership"):
            h.cleanup_owned(self.docker, self.docker.cid, self.docker.name, self.docker.nonce)
        self.assertNotIn("remove", self.docker.calls)

    def test_cleanup_does_not_remove_when_daemon_unavailable(self):
        self.docker.present = True
        self.docker.available = False
        with self.assertRaises(h.GuardError):
            h.cleanup_owned(self.docker, self.docker.cid, self.docker.name, self.docker.nonce)
        self.assertNotIn("remove", self.docker.calls)

    def test_unsafe_database_urls_are_rejected(self):
        database = self.docker.database
        good = h.make_target(database, 49111)
        h.validate_target(good, database, 49111)
        bad = [good.replace("127.0.0.1", "localhost"), good + "?host=/tmp",
               good.replace(h.ROLE + "@", h.ROLE + ":password@"),
               good.replace(database, "repopilot-local"), good.replace("49111", "5432"),
               good.replace("127.0.0.1", "127.0.0.2"), good + "#fragment"]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(h.GuardError):
                h.validate_target(url, database, 49111)


class PreparationGuardTests(unittest.TestCase):
    def test_staged_safety_suite_must_pass_before_database_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_file = root / "evaluation/test_tree_sitter_pg_harness.py"
            test_file.parent.mkdir()
            test_file.write_text("synthetic only")
            execute = mock.Mock(return_value=SimpleNamespace(stderr="Ran 41 tests in 0.01s\n\nOK\n"))
            with contextlib.redirect_stdout(io.StringIO()):
                h.run_safety_tests(Path("/synthetic/venv/python"), root, root, execute)
            self.assertIn("(deny network*)", execute.call_args.args[0][2])
            execute.return_value = SimpleNamespace(stderr="Ran 40 tests in 0.01s\n\nOK\n")
            with self.assertRaisesRegex(h.GuardError, "safety suite did not complete"):
                h.run_safety_tests(Path("/synthetic/venv/python"), root, root, execute)

    def test_network_sandbox_allows_only_the_requested_loopback_port(self):
        denied = h.network_sandbox(["uv", "sync"])
        allowed = h.network_sandbox(["pytest"], 49111)
        self.assertEqual(denied[:2], [str(h.SANDBOX), "-p"])
        self.assertIn("(deny network*)", denied[2])
        self.assertNotIn("network-outbound", denied[2])
        self.assertIn('(remote ip "localhost:49111")', allowed[2])
        for port in (0, 65536, -1, "49111", True):
            with self.subTest(port=port), self.assertRaises(h.GuardError):
                h.network_sandbox(["pytest"], port)

    def test_network_sandbox_probe_rejects_a_profile_that_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory) / "sandbox-exec"
            sandbox.write_text("synthetic")
            sandbox.chmod(0o700)
            listeners = [mock.MagicMock(), mock.MagicMock()]
            listeners[0].getsockname.return_value = ("127.0.0.1", 49111)
            listeners[1].getsockname.return_value = ("127.0.0.1", 49112)
            results = [SimpleNamespace(stdout=json.dumps(value)) for value in (
                {"codes": [0, 0], "ipc": True}, {"codes": [1, 1], "ipc": True},
                {"codes": [0, 0], "ipc": True},
            )]
            with mock.patch.object(h, "SANDBOX", sandbox), \
                 mock.patch.object(h.socket, "socket", side_effect=listeners), \
                 self.assertRaisesRegex(h.GuardError, "single-port network sandbox was not enforced"):
                h.verify_network_sandbox(Path("/synthetic/python"), mock.Mock(side_effect=results))
            self.assertTrue(all(listener.close.called for listener in listeners))

    def test_missing_python_interpreter_fails_before_external_commands(self):
        execute = mock.Mock()
        with self.assertRaisesRegex(h.GuardError, "interpreter is missing"):
            h.check_interpreter(Path("/nonexistent/python"), execute)
        execute.assert_not_called()

    def test_missing_disposable_environment_stops_after_mock_offline_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "fixture.whl"
            wheel.write_bytes(b"synthetic")
            wheels = {"pytest": (wheel, hashlib.sha256(wheel.read_bytes()).hexdigest())}
            execute = mock.Mock()
            with mock.patch.object(h, "load_contract", return_value={}), \
                 mock.patch.object(h, "required_packages", return_value={"pytest": {"version": "1"}}), \
                 self.assertRaisesRegex(h.GuardError, "environment is missing"):
                h.prepare_environment(root / "uv", root / "python", root / "stage", root, wheels, execute)
            execute.assert_called_once()
            args = execute.call_args.args[0]
            self.assertEqual(args[0], str(h.SANDBOX))
            self.assertIn("(deny network*)", args[2])
            self.assertNotIn("network-outbound", args[2])
            self.assertIn("venv", args)
            self.assertIn("--without-pip", args)

    def test_offline_lock_check_is_required_before_database_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "fixture.whl"
            wheel.write_bytes(b"synthetic")
            sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
            wheels = {"pytest": (wheel, sha)}
            calls = []
            def execute(args, **_kwargs):
                calls.append(args)
                if "-m" in args and "venv" in args:
                    executable = root / "venv/bin/python"
                    executable.parent.mkdir(parents=True)
                    executable.write_text("synthetic")
                    executable.chmod(0o700)
                    return SimpleNamespace(stdout="")
                if "-c" in args:
                    return SimpleNamespace(stdout=json.dumps({"prefix": str(root / "venv"),
                                                              "packages": {"pytest": "1"}}))
                return SimpleNamespace(stdout="")
            with mock.patch.object(h, "load_contract", return_value={}), \
                 mock.patch.object(h, "required_packages", return_value={"pytest": {"version": "1"}}), \
                 contextlib.redirect_stdout(io.StringIO()):
                h.prepare_environment(root / "uv", root / "python", root / "stage", root, wheels, execute)
            self.assertEqual(len(calls), 4)
            self.assertEqual((root / "requirements-verified.txt").read_text(), f"pytest==1 --hash=sha256:{sha}\n")
            self.assertIn("--require-hashes", calls[1])
            self.assertIn("--offline", calls[1])
            self.assertIn("--no-index", calls[1])
            self.assertIn("--no-build", calls[1])
            self.assertIn("lock", calls[-1])
            self.assertIn("--check", calls[-1])
            self.assertIn("--offline", calls[-1])
            self.assertIn("(deny network*)", calls[-1][2])

    def test_wrong_uv_version_fails_with_verified_synthetic_wheel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uv = root / "uv"
            uv.write_bytes(b"synthetic uv executable")
            uv.chmod(0o700)
            wheel = root / h.UV_WHEEL
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("uv/", "")
                archive.writestr("uv-0.13.6.data/scripts/uv", uv.read_bytes())
            expected = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with mock.patch.object(h, "UV_WHEEL_SHA256", expected):
                with self.assertRaisesRegex(h.GuardError, "not version 0.13.6"):
                    h.check_uv(uv, wheel, lambda *a, **k: SimpleNamespace(stdout="uv 0.9.5"))

    def test_missing_uv_wheel_fails_without_running_uv(self):
        execute = mock.Mock()
        with self.assertRaises(h.GuardError):
            h.check_uv(Path("/nonexistent/uv"), Path("/nonexistent/wheel"), execute)
        execute.assert_not_called()

    def test_missing_fixture_stops_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("app/__init__.py", "alembic/env.py", "tests/test_fixture.py", "tests/conftest.py",
                         "pyproject.toml", "uv.lock", "alembic.ini"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("def test_required(): pass\n" if path.endswith("test_fixture.py") else "fixture\n")
            with mock.patch.object(h, "RELEASE_TESTS", ("test_fixture.py",)), \
                 mock.patch.object(h, "HELPER_TESTS", ("conftest.py",)), \
                 mock.patch.object(h, "FIXTURES", ("evaluation/fixtures/needed.json",)), \
                 mock.patch.object(h, "HARNESS_FILES", ()), \
                 mock.patch.object(h, "SYNTHETIC_CAPTURE_CASES", ()), \
                 mock.patch.object(h, "P6_REQUIRED_PARAMETERS", frozenset()), \
                 mock.patch.object(h, "REQUIRED_CASES", frozenset({"test_required"})):
                with self.assertRaisesRegex(h.GuardError, "required source or fixture missing"):
                    h.source_inventory(root)
                fixture = root / "evaluation/fixtures/needed.json"
                fixture.parent.mkdir(parents=True)
                fixture.write_text("{}\n")
                (root / ".env").write_text("synthetic secret")
                (root / "database.sqlite").write_text("synthetic database")
                inventory = h.source_inventory(root)
                self.assertNotIn(".env", inventory)
                self.assertNotIn("database.sqlite", inventory)
                destination = root.parent / (root.name + "-copy")
                try:
                    h.stage_sources(root, destination, inventory)
                    h.verify_inventory(destination, inventory)
                    (destination / ".env").write_text("unexpected synthetic secret")
                    with self.assertRaisesRegex(h.GuardError, "unexpected files"):
                        h.verify_inventory(destination, inventory, exact=True)
                    (destination / ".env").unlink()
                    (destination / "tests/test_fixture.py").write_text("changed")
                    with self.assertRaisesRegex(h.GuardError, "staged source changed"):
                        h.verify_inventory(destination, inventory)
                finally:
                    import shutil
                    shutil.rmtree(destination)

    def test_symlinked_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("app", "alembic", "tests", "evaluation"):
                (root / name).mkdir()
            for name in ("pyproject.toml", "uv.lock", "alembic.ini"):
                (root / name).write_text("fixture")
            (root / "tests/conftest.py").write_text("")
            (root / "tests/test_fixture.py").write_text("def test_required(): pass\n")
            (root / "evaluation/bad.json").symlink_to(root / "uv.lock")
            with mock.patch.object(h, "RELEASE_TESTS", ("test_fixture.py",)), \
                 mock.patch.object(h, "HELPER_TESTS", ("conftest.py",)), \
                 mock.patch.object(h, "FIXTURES", ("evaluation/bad.json",)), \
                 mock.patch.object(h, "HARNESS_FILES", ()), \
                 mock.patch.object(h, "SYNTHETIC_CAPTURE_CASES", ()), \
                 mock.patch.object(h, "P6_REQUIRED_PARAMETERS", frozenset()), \
                 mock.patch.object(h, "REQUIRED_CASES", frozenset({"test_required"})):
                with self.assertRaises(h.GuardError):
                    h.source_inventory(root)

    def test_missing_and_tampered_wheels_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            filename = "synthetic-1-py3-none-any.whl"
            data = b"synthetic wheel bytes"
            package = {"synthetic": {"wheels": [{"url": "https://invalid/" + filename,
                                                  "hash": "sha256:" + hashlib.sha256(data).hexdigest()}]}}
            available, missing = h.audit_wheelhouse(package, root, (14, 0))
            self.assertFalse(available)
            self.assertIn("synthetic", missing)
            (root / filename).write_bytes(data)
            available, missing = h.audit_wheelhouse(package, root, (14, 0))
            self.assertIn("synthetic", available)
            self.assertFalse(missing)
            (root / filename).write_bytes(b"tampered")
            with self.assertRaisesRegex(h.GuardError, "wheel hash mismatch"):
                h.audit_wheelhouse(package, root, (14, 0))

    def test_wheel_abi_and_unknown_markers_fail_closed(self):
        self.assertTrue(h.compatible_wheel("x-1-cp312-abi3-macosx_11_0_arm64.whl", (14, 0)))
        self.assertFalse(h.compatible_wheel("x-1-cp314-cp314t-macosx_11_0_arm64.whl", (14, 0)))
        self.assertFalse(h.compatible_wheel("x-1-cp314-cp314-manylinux_2_17_aarch64.whl", (14, 0)))
        with self.assertRaises(h.GuardError):
            h.marker_matches("unknown_environment == 'x'")

    def test_dependency_graph_excludes_unrequested_model_extra(self):
        registry = {"registry": "https://pypi.org/simple"}
        packages = {
            "repopilot-api": {"dependencies": [{"name": "tree-sitter"}],
                              "optional-dependencies": {"local-embeddings": [{"name": "model"}]},
                              "dev-dependencies": {"dev": [{"name": "pytest"}]}},
            "tree-sitter": {"name": "tree-sitter", "version": "0.25.2", "source": registry},
            "pytest": {"name": "pytest", "version": "1", "source": registry},
            "model": {"name": "model", "version": "1", "source": registry},
        }
        with mock.patch.object(h, "PARSER_VERSIONS", {"tree-sitter": "0.25.2"}):
            self.assertEqual(set(h.required_packages(packages)), {"tree-sitter", "pytest"})

    def test_junit_requires_all_postgres_cases_and_no_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "junit.xml"
            cases = "".join(f'<testcase name="{name}" />'
                            for name in sorted(h.REQUIRED_CASES | h.P6_REQUIRED_PARAMETERS))
            report.write_text(f"<testsuite>{cases}</testsuite>")
            with contextlib.redirect_stdout(io.StringIO()):
                h.validate_junit(report)
            missing_parameter = next(iter(h.P6_REQUIRED_PARAMETERS))
            removed = f'<testcase name="{missing_parameter}" />'
            report.write_text(f"<testsuite>{cases.replace(removed, '')}</testsuite>")
            with self.assertRaisesRegex(h.GuardError, "required test did not execute"):
                h.validate_junit(report)
            report.write_text(f"<testsuite>{cases}<testcase name='extra'><skipped/></testcase></testsuite>")
            with self.assertRaises(h.GuardError):
                h.validate_junit(report)
            report.write_text("<testsuite><testcase name='only-one'/></testsuite>")
            with self.assertRaises(h.GuardError):
                h.validate_junit(report)

    def test_missing_prerequisites_stop_cli_before_docker(self):
        with mock.patch.object(h, "check_inputs", return_value=({}, {}, ["uv missing"])), \
             mock.patch.object(h, "DockerDriver") as docker, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(h.main(["run"]), 1)
        docker.assert_not_called()


class CommandConstructionTests(unittest.TestCase):
    def driver(self):
        driver = object.__new__(h.DockerDriver)
        driver.docker = Path("/synthetic/docker")
        driver.socket = Path("/synthetic/docker.sock")
        driver.work = Path("/synthetic/work")
        driver.env = {**h.clean_env(driver.work), "DOCKER_CONFIG": "/synthetic/work/docker-config"}
        return driver

    def test_docker_create_is_temporary_loopback_and_secret_free_in_argv(self):
        driver = self.driver()
        password = "f" * 64
        with mock.patch.object(h, "command", return_value=SimpleNamespace(stdout="a" * 64)) as execute:
            driver.create("repopilot-ts0252-pg-1234567890abcdef", "1234567890abcdef",
                          "repopilot_5b1_checks_1234567890abcdef", password)
        args = execute.call_args.args[0]
        env = execute.call_args.kwargs["env"]
        self.assertIn("--pull=never", args)
        self.assertNotIn("--rm", args)
        self.assertIn("/var/lib/postgresql/data:rw", args)
        self.assertIn("127.0.0.1::5432", args)
        self.assertIn("POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256", args)
        self.assertNotIn(password, " ".join(args))
        self.assertNotIn("--privileged", args)
        self.assertNotIn("--mount", args)
        self.assertNotIn("--volume", args)
        self.assertEqual(env["POSTGRES_PASSWORD"], password)
        self.assertNotIn("DOCKER_CONTEXT", env)
        self.assertNotIn("DOCKER_HOST", env)

    def test_auth_sql_checks_all_host_rule_types_and_parse_errors(self):
        driver = self.driver()
        with mock.patch.object(driver, "sql", return_value="scram-sha-256") as sql:
            self.assertEqual(driver.auth_rule("a" * 64, "fixture"), "scram-sha-256")
        query = sql.call_args.args[2]
        self.assertIn("type LIKE 'host%'", query)
        self.assertIn("type='local'", query)
        self.assertIn("error IS NOT NULL", query)
        self.assertIn("IS DISTINCT FROM 'scram-sha-256'", query)

    def test_docker_inspection_parses_only_selected_fields(self):
        driver = self.driver()
        fields = ["a" * 64, "/owned", h.IMAGE, {"repopilot.test-run": "fixture"}, False, "bridge", [],
                  {"/var/lib/postgresql/data": "rw"}, {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]},
                  {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49111"}]}]
        with mock.patch.object(driver, "docker_command", side_effect=[SimpleNamespace(stdout=json.dumps(v))
                                                                      for v in fields]) as docker:
            info = driver.inspect("a" * 64)
        self.assertEqual(info["id"], "a" * 64)
        self.assertEqual(info["mounts"], [])
        self.assertEqual(docker.call_count, len(fields))
        self.assertTrue(all(".Config.Env" not in " ".join(call.args[0]) for call in docker.call_args_list))

    def test_passwordless_probe_distinguishes_auth_rejection_from_connection_failure(self):
        driver = self.driver()
        driver.python = Path("/synthetic/venv/python")
        with mock.patch.object(h, "command", return_value=SimpleNamespace(returncode=0)) as execute:
            self.assertTrue(driver.passwordless_rejected(49111, "repopilot_5b1_checks_1234567890abcdef"))
        self.assertIn('(remote ip "localhost:49111")', execute.call_args.args[0][2])
        self.assertNotIn("PGPASSWORD", execute.call_args.kwargs["env"])
        self.assertNotIn("TEST_DATABASE_URL", execute.call_args.kwargs["env"])
        with mock.patch.object(h, "command", return_value=SimpleNamespace(returncode=2)):
            self.assertFalse(driver.passwordless_rejected(49111, "repopilot_5b1_checks_1234567890abcdef"))

    def test_container_removal_never_requests_volume_removal(self):
        driver = self.driver()
        with mock.patch.object(driver, "docker_command") as docker:
            driver.remove("a" * 64)
        self.assertEqual(docker.call_args.args[0], ["rm", "-f", "a" * 64])
        self.assertNotIn("-v", docker.call_args.args[0])

    def test_pytest_runs_with_only_the_disposable_database_port_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            driver = self.driver()
            driver.work = Path(directory)
            driver.stage = Path(directory)
            driver.python = Path("/synthetic/venv/python")
            url = "postgresql+psycopg://capture_fixture@127.0.0.1:49111/repopilot_5b1_checks_1234567890abcdef"
            with mock.patch.object(h.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as execute, \
                 mock.patch.object(h, "validate_junit"):
                driver.pytest(url, "f" * 64)
            args = execute.call_args.args[0]
            self.assertEqual(args[0], str(h.SANDBOX))
            self.assertIn("(deny network*)", args[2])
            self.assertIn('(remote ip "localhost:49111")', args[2])
            self.assertNotIn("f" * 64, " ".join(args))

    def test_native_pg_broker_has_no_database_credentials_and_pytest_keeps_port_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            driver = self.driver()
            driver.work = Path(directory)
            driver.stage = Path(directory)
            driver.python = Path("/synthetic/venv/python")
            broker_script = driver.stage / "evaluation/supervised_parser_test_broker.py"
            broker_script.parent.mkdir()
            broker_script.write_text("# synthetic\n")
            url = "postgresql+psycopg://capture_fixture@127.0.0.1:49111/repopilot_5b1_checks_1234567890abcdef"
            broker = mock.Mock(returncode=0)
            with mock.patch.object(h.subprocess, "Popen", return_value=broker) as launch, \
                 mock.patch.object(h.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as execute, \
                 mock.patch.object(h, "validate_named_junit"):
                driver.pytest_native_postgres(url, "f" * 64)
            broker_args = launch.call_args.args[0]
            broker_env = launch.call_args.kwargs["env"]
            self.assertNotIn("PGPASSWORD", broker_env)
            self.assertNotIn("TEST_DATABASE_URL", broker_env)
            self.assertNotIn("GITHUB_TOKEN", broker_env)
            self.assertNotIn("f" * 64, " ".join(broker_args))
            self.assertEqual(len(launch.call_args.kwargs["pass_fds"]), 1)
            pytest_args = execute.call_args.args[0]
            self.assertEqual(pytest_args[0], str(h.SANDBOX))
            self.assertIn("(deny network*)", pytest_args[2])
            self.assertIn('(remote ip "localhost:49111")', pytest_args[2])
            self.assertEqual(len(execute.call_args.kwargs["pass_fds"]), 1)
            self.assertNotIn("f" * 64, " ".join(pytest_args))


if __name__ == "__main__":
    unittest.main(verbosity=2)
