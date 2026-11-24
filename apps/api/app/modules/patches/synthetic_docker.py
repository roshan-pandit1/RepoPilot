"""Test-only Docker boundary for the immutable P4 synthetic fixtures.

Not a sandbox for external source. Docker is never called with a shell, pulled
images, credentials, a host network, or a Docker socket mount.
"""
from dataclasses import dataclass
import json
from hashlib import sha256
import os
from pathlib import Path
import platform
import re
import secrets
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from app.modules.patches.synthetic_specs import IMAGE, SPECS, TEST_SHA256, FixtureSpec

ADAPTER = "p4-trusted-docker-v1"
POLICY = "p4-synthetic-policy-v1"
PURPOSE = "repopilot-p4-trusted-synthetic"
_ENV_KEYS = {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256",
             "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED", "UV_PROJECT_ENVIRONMENT"}
_PROBE = r'''import json,os,socket
status={}
for line in open("/proc/self/status"):
    if ":" in line:
        k,v=line.split(":",1);status[k]=v.strip()
def read(path):
    with open(path) as f:return f.read().strip()
def ro(path):return bool(os.statvfs(path).f_flag & os.ST_RDONLY)
tmp="/tmp/p4-preflight"
with open(tmp,"x") as f:f.write("x")
os.unlink(tmp)
entries=sorted(os.listdir("/sys/class/net"))
sysfs_interfaces=sorted(name for name in entries if os.path.islink("/sys/class/net/"+name)
                        and os.path.isdir("/sys/class/net/"+name))
routes4=read("/proc/self/net/route").splitlines()
if not routes4 or routes4[0].split()[:4]!=["Iface","Destination","Gateway","Flags"]:
    raise ValueError("invalid IPv4 route table")
mounts=[]
for line in read("/proc/self/mountinfo").splitlines():
    left,right=line.split(" - ",1)
    fields=left.split();details=right.split()
    if len(fields)<6 or not details:raise ValueError("invalid mount table")
    mounts.append([fields[4],details[0],fields[5]])
out={"uid":os.geteuid(),"gid":os.getegid(),"seccomp":status.get("Seccomp"),
     "no_new_privs":status.get("NoNewPrivs"),"cap_eff":status.get("CapEff"),
     "root_ro":ro("/"),"fixture_ro":ro("/fixture"),"tmp_writable":True,
     "sysfs_entries":entries,"sysfs_interfaces":sysfs_interfaces,
     "proc_interfaces":sorted(line.split(":",1)[0].strip() for line in read("/proc/net/dev").splitlines()[2:]),
     "socket_interfaces":sorted(name for _,name in socket.if_nameindex()),
     "route_count":len(routes4[1:]),"memory":read("/sys/fs/cgroup/memory.max"),
     "ipv6_addresses":[line.split() for line in read("/proc/self/net/if_inet6").splitlines()],
     "ipv6_routes":[line.split() for line in read("/proc/self/net/ipv6_route").splitlines()],
     "runtime_mounts":mounts,
     "pids":read("/sys/fs/cgroup/pids.max"),"cpu":read("/sys/fs/cgroup/cpu.max"),
     "socket_absent":not os.path.exists("/var/run/docker.sock"),
     "app_masked":not os.path.exists("/app/pyproject.toml"),
     "environment":sorted(os.environ),"cwd":os.getcwd()}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
'''


def verify_workspace(workspace: Path, spec: FixtureSpec):
    if spec not in SPECS or workspace.name not in {"baseline", "patched"}:
        raise SandboxFailure("fixture_policy")
    parent = workspace.parent
    if (not parent.name.startswith("repopilot-patch-") or parent.parent.resolve() != Path(tempfile.gettempdir()).resolve()
            or parent.is_symlink() or workspace.is_symlink()
            or not parent.is_dir() or not workspace.is_dir() or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise SandboxFailure("workspace_policy")
    expected = {"src/calc.py": spec.source_sha256 if workspace.name == "baseline" else spec.patched_sha256,
                "test_add.py": TEST_SHA256}
    seen = set()
    for root, dirs, files in os.walk(workspace, followlinks=False):
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink() or path.relative_to(workspace).as_posix() != "src":
                raise SandboxFailure("workspace_policy")
        for name in files:
            path = Path(root) / name
            rel = path.relative_to(workspace).as_posix()
            if path.is_symlink() or not path.is_file() or rel not in expected or path.stat().st_size > 4096:
                raise SandboxFailure("workspace_policy")
            if sha256(path.read_bytes()).hexdigest() != expected[rel]:
                raise SandboxFailure("workspace_policy")
            seen.add(rel)
    if seen != set(expected):
        raise SandboxFailure("workspace_policy")


class SandboxFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: bytes
    stderr: bytes


class DockerDriver:
    """Mac ARM64 test runner using one explicitly local Unix socket."""

    def __init__(self):
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise SandboxFailure("unsupported_host")
        self.binary = Path("/Users/roshan/.docker/bin/docker")
        self.socket = Path("/Users/roshan/.docker/run/docker.sock")
        if (not self.binary.is_file() or not os.access(self.binary, os.X_OK)
                or self.socket.is_symlink() or not self.socket.exists()
                or not stat.S_ISSOCK(self.socket.stat().st_mode)):
            raise SandboxFailure("docker_unavailable")
        self._scratch = tempfile.TemporaryDirectory(prefix="repopilot-p4-docker-")
        self.home = Path(self._scratch.name)
        os.chmod(self.home, 0o700)
        self.config = self.home / "config"
        self.config.mkdir(mode=0o700)

    def close(self):
        self._scratch.cleanup()

    def command(self, args, *, timeout=15, limit=65536, cancelled=None):
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home), "DOCKER_CONFIG": str(self.config)}
        argv = [str(self.binary), "--host", f"unix://{self.socket}", *args]
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=env, cwd=self.home, start_new_session=True)
        except OSError:
            raise SandboxFailure("docker_unavailable") from None
        output = {proc.stdout: bytearray(), proc.stderr: bytearray()}
        selector = None
        deadline = time.monotonic() + timeout
        try:
            selector = selectors.DefaultSelector()
            for pipe in output:
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ)
            while selector.get_map():
                if cancelled and cancelled():
                    raise SandboxFailure("cancelled")
                if time.monotonic() >= deadline:
                    raise SandboxFailure("timeout")
                for key, _ in selector.select(timeout=0.05):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.fileobj].extend(chunk)
                    if sum(map(len, output.values())) > limit:
                        raise SandboxFailure("output_limit")
            code = proc.wait(timeout=max(0.1, deadline - time.monotonic()))
            return CommandResult(code, bytes(output[proc.stdout]), bytes(output[proc.stderr]))
        except BaseException as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=3)
            if isinstance(exc, subprocess.TimeoutExpired):
                raise SandboxFailure("timeout") from None
            raise
        finally:
            if selector is not None:
                selector.close()
            for pipe in output:
                pipe.close()

    def inspect_image(self):
        result = self.command(["image", "inspect", IMAGE])
        if result.code:
            raise SandboxFailure("image_unavailable")
        try:
            image, = json.loads(result.stdout)
            config = image["Config"]
            names = {entry.split("=", 1)[0] for entry in config.get("Env", [])}
            if (image["Id"] != IMAGE or image.get("Os") != "linux" or image.get("Architecture") != "arm64"
                    or config.get("Volumes") or not names <= _ENV_KEYS):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise SandboxFailure("image_policy") from None

    def inspect(self, identity):
        result = self.command(["inspect", identity])
        if result.code:
            raise SandboxFailure("inspection_failed")
        try:
            item, = json.loads(result.stdout)
            if not isinstance(item, dict):
                raise ValueError()
            return item
        except (ValueError, TypeError):
            raise SandboxFailure("inspection_failed") from None

    def create(self, spec: FixtureSpec, workspace: Path, nonce: str, probe: bool):
        if spec not in SPECS or type(probe) is not bool or not re.fullmatch(r"[0-9a-f]{32}", nonce):
            raise SandboxFailure("fixture_policy")
        verify_workspace(workspace, spec)
        name = "repopilot-p4-" + nonce
        command = ["-I", "-B", "-c", _PROBE] if probe else list(spec.arguments)
        args = ["create", "--pull=never", "--name", name, "--network", "none", "--user", "65534:65534",
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit", str(spec.pids),
                "--memory", str(spec.memory_bytes), "--memory-swap", str(spec.memory_bytes), "--cpus", "1",
                "--ulimit", "core=0:0", "--ulimit", "nofile=32:32", "--workdir", "/fixture",
                "--label", f"repopilot.p4.nonce={nonce}", "--label", f"repopilot.p4.purpose={PURPOSE}",
                "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=8m", "--tmpfs", "/app:ro,noexec,nosuid,nodev,size=1m",
                "--tmpfs", "/home:ro,noexec,nosuid,nodev,size=1m", "--tmpfs", "/root:ro,noexec,nosuid,nodev,size=1m",
                "--tmpfs", "/opt:ro,noexec,nosuid,nodev,size=1m", "--tmpfs", "/run/secrets:ro,noexec,nosuid,nodev,size=1m",
                "--mount", f"type=bind,src={workspace},dst=/fixture,readonly",
                "--entrypoint", "/usr/bin/env", IMAGE, "-i", *spec.environment, spec.executable, *command]
        result = self.command(args)
        if result.code:
            raise SandboxFailure("container_create_failed")
        container = result.stdout.decode("ascii", errors="ignore").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", container):
            raise SandboxFailure("container_identity")
        return container, name

    def verify(self, container, name, nonce, workspace, spec, probe):
        item = self.inspect(container)
        if not isinstance(item, dict):
            raise SandboxFailure("inspection_failed")
        cfg, host = item.get("Config", {}), item.get("HostConfig", {})
        network = item.get("NetworkSettings")
        if not isinstance(cfg, dict) or not isinstance(host, dict) or not isinstance(network, dict):
            raise SandboxFailure("inspection_failed")
        required_host = {"Privileged", "NetworkMode", "ReadonlyRootfs", "CapDrop", "CapAdd", "Binds",
                         "PidMode", "UTSMode", "SecurityOpt", "Memory", "MemorySwap", "PidsLimit",
                         "NanoCpus", "Tmpfs"}
        if not required_host <= host.keys():
            raise SandboxFailure("inspection_failed")
        labels = cfg.get("Labels") or {}
        networks = network.get("Networks")
        address_keys = {"IPAddress", "GlobalIPv6Address", "Gateway", "IPv6Gateway"}
        if (not isinstance(labels, dict) or not isinstance(networks, dict) or set(networks) != {"none"}
                or not isinstance(networks["none"], dict)
                or not address_keys <= networks["none"].keys()
                or any(networks["none"][key] not in (None, "") for key in address_keys)):
            raise SandboxFailure("container_security_policy")
        expected_args = ["-i", *spec.environment, spec.executable,
                         *(["-I", "-B", "-c", _PROBE] if probe else spec.arguments)]
        mounts = item.get("Mounts") or []
        actual_tmpfs = host.get("Tmpfs") or {}
        if (not isinstance(mounts, list) or any(not isinstance(mount, dict) for mount in mounts)
                or not isinstance(actual_tmpfs, dict)
                or any(not isinstance(options, str) for options in actual_tmpfs.values())):
            raise SandboxFailure("inspection_failed")
        if (item.get("Id") != container or item.get("Name") != "/" + name or item.get("Image") != IMAGE
                or labels.get("repopilot.p4.nonce") != nonce or labels.get("repopilot.p4.purpose") != PURPOSE):
            raise SandboxFailure("container_identity_policy")
        if (cfg.get("User") != "65534:65534" or cfg.get("WorkingDir") != "/fixture"
                or item.get("Path") != "/usr/bin/env" or item.get("Args") != expected_args):
            raise SandboxFailure("container_command_policy")
        if (host.get("Privileged") is not False or host.get("NetworkMode") != "none"
                or host.get("ReadonlyRootfs") is not True or host.get("CapDrop") != ["ALL"]
                or host.get("CapAdd") not in (None, []) or host.get("Binds") not in (None, [])
                or host.get("PidMode") != "" or host.get("UTSMode") != ""
                or host.get("SecurityOpt") != ["no-new-privileges"]):
            raise SandboxFailure("container_security_policy")
        if (host.get("Memory") != spec.memory_bytes or host.get("MemorySwap") != spec.memory_bytes
                or host.get("PidsLimit") != spec.pids or host.get("NanoCpus") != spec.cpu_nanos):
            raise SandboxFailure("container_resource_policy")
        if (len(mounts) != 1 or mounts[0].get("Type") != "bind" or mounts[0].get("RW") is not False
                or mounts[0].get("Source") != str(workspace) or mounts[0].get("Destination") != "/fixture"
                or set(actual_tmpfs) != {"/tmp", "/app", "/home", "/root", "/opt", "/run/secrets"}):
            raise SandboxFailure("container_mount_policy")
        for path, options in actual_tmpfs.items():
            entries = set(options.split(","))
            if not {"noexec", "nosuid", "nodev"} <= entries or ("rw" if path == "/tmp" else "ro") not in entries:
                raise SandboxFailure("container_mount_options")

    def start(self, container, timeout, limit, cancelled=None):
        started = time.monotonic()
        result = self.command(["start", "-a", container], timeout=timeout, limit=limit, cancelled=cancelled)
        elapsed = max(0, round((time.monotonic() - started) * 1000))
        state = self.inspect(container).get("State") or {}
        if state.get("Running") is not False or state.get("ExitCode") != result.code:
            raise SandboxFailure("container_state")
        if state.get("OOMKilled"):
            raise SandboxFailure("resource_limit")
        return result, elapsed

    def cleanup(self, name, nonce):
        def absent():
            result = self.command(["ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"])
            if result.code:
                raise SandboxFailure("cleanup_unverified")
            return name not in result.stdout.decode("utf-8", errors="replace").splitlines()
        try:
            item = self.inspect(name)
        except SandboxFailure:
            if absent():
                return
            raise SandboxFailure("cleanup_unverified") from None
        cfg, identity = item.get("Config", {}), item.get("Id", "")
        labels = cfg.get("Labels") or {}
        if (not re.fullmatch(r"[0-9a-f]{64}", identity) or item.get("Name") != "/" + name
                or item.get("Image") != IMAGE or labels.get("repopilot.p4.nonce") != nonce
                or labels.get("repopilot.p4.purpose") != PURPOSE):
            raise SandboxFailure("cleanup_ownership")
        result = self.command(["rm", "-f", identity])
        if result.code or not absent():
            raise SandboxFailure("cleanup_failed")


_MASK_FLAGS = frozenset({"ro", "nosuid", "nodev", "noexec"})
_PROC_FLAGS = frozenset({"ro", "nosuid", "nodev", "noexec"})
_RUNTIME_MOUNT_POLICY = {
    "/": ("overlay", frozenset({"ro"})),
    "/proc": ("proc", frozenset({"rw", "nosuid", "nodev", "noexec"})),
    "/sys": ("sysfs", _MASK_FLAGS),
    "/sys/fs/cgroup": ("cgroup2", _MASK_FLAGS),
    "/dev": ("tmpfs", frozenset({"rw", "nosuid"})),
    "/dev/pts": ("devpts", frozenset({"rw", "nosuid", "noexec"})),
    "/dev/mqueue": ("mqueue", frozenset({"rw", "nosuid", "nodev", "noexec"})),
    "/dev/shm": ("tmpfs", frozenset({"rw", "nosuid", "nodev", "noexec"})),
    "/fixture": ("virtiofs", frozenset({"ro", "nosuid", "nodev"})),
    "/tmp": ("tmpfs", frozenset({"rw", "nosuid", "nodev", "noexec"})),
    **{path: ("tmpfs", _MASK_FLAGS) for path in ("/app", "/home", "/opt", "/root", "/run/secrets")},
    **{path: ("proc", _PROC_FLAGS) for path in
       ("/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger")},
    **{path: ("tmpfs", frozenset({"rw", "nosuid"})) for path in
       ("/proc/interrupts", "/proc/kcore", "/proc/keys", "/proc/timer_list")},
    **{path: ("tmpfs", frozenset({"ro"})) for path in ("/proc/scsi", "/sys/firmware")},
}
_REQUIRED_RUNTIME_MOUNTS = frozenset({"/", "/proc", "/sys", "/dev", "/fixture", "/tmp", "/app", "/home",
                                      "/opt", "/root", "/run/secrets"})


def _runtime_mounts_safe(records):
    """Reject unknown runtime mounts, even when Docker omits them from Mounts."""
    if not isinstance(records, list) or len(records) > 128:
        return False
    seen = set()
    for record in records:
        if not isinstance(record, list) or len(record) != 3 or not all(isinstance(item, str) for item in record):
            return False
        path, fs, options = record
        if path in seen or path not in _RUNTIME_MOUNT_POLICY:
            return False
        expected_fs, required_options = _RUNTIME_MOUNT_POLICY[path]
        actual_options = set(options.split(","))
        if fs != expected_fs or not required_options <= actual_options or {"ro", "rw"} <= actual_options:
            return False
        seen.add(path)
    return _REQUIRED_RUNTIME_MOUNTS <= seen


def _ipv6_loopback_only(addresses, routes):
    """Accept only a loopback address and known local or rejected default routes.

    Unknown records or kernel route flags fail closed; these are not evidence
    that the container is a sandbox for untrusted code.
    """
    if not isinstance(addresses, list) or not isinstance(routes, list) or len(addresses) > 1 or len(routes) > 128:
        return False

    def number(value, digits):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{" + str(digits) + "}", value):
            raise ValueError()
        return int(value, 16)

    try:
        for record in addresses:
            if not isinstance(record, list) or len(record) != 6:
                return False
            address, index, prefix, scope, flags, name = record
            if (number(address, 32) != 1 or number(index, 2) == 0 or number(prefix, 2) != 128
                    or number(scope, 2) != 16 or name != "lo"):
                return False
            number(flags, 2)
        for record in routes:
            if not isinstance(record, list) or len(record) != 10:
                return False
            dest, dest_prefix, source, source_prefix, gateway, metric, ref, use, flags, name = record
            dest, dest_prefix = number(dest, 32), number(dest_prefix, 2)
            source, source_prefix, gateway = number(source, 32), number(source_prefix, 2), number(gateway, 32)
            metric, flags = number(metric, 8), number(flags, 8)
            number(ref, 8)
            number(use, 8)
            if name != "lo" or source != 0 or source_prefix != 0 or gateway != 0:
                return False
            rejected_default = (dest == 0 and dest_prefix == 0 and metric == 0xFFFFFFFF and flags == 0x00200200)
            local_loopback = (dest == 1 and dest_prefix == 128 and metric == 0 and flags == 0x80200001
                              and len(addresses) == 1)
            if not (rejected_default or local_loopback):
                return False
    except (TypeError, ValueError):
        return False
    return True


def verify_probe(result: CommandResult, spec: FixtureSpec):
    if result.code != 0:
        text = result.stderr.decode("utf-8", errors="replace")
        kind = next((name for name in ("PermissionError", "FileNotFoundError", "OSError", "ModuleNotFoundError")
                     if name in text), "unknown")
        raise SandboxFailure("preflight_process_" + kind.lower())
    try:
        value = json.loads(result.stdout)
        cpu = value["cpu"].split()
        checks = {"identity": value["uid"] == value["gid"] == 65534,
                  "seccomp": value["seccomp"] == "2", "no_new_privs": value["no_new_privs"] == "1",
                  "capabilities": int(value["cap_eff"], 16) == 0, "root_readonly": value["root_ro"] is True,
                  "fixture_readonly": value["fixture_ro"] is True, "scratch": value["tmp_writable"] is True,
                  "network": (value["sysfs_entries"] == ["lo"]
                              and value["sysfs_interfaces"] == value["proc_interfaces"] == value["socket_interfaces"] == ["lo"]
                              and type(value["route_count"]) is int and value["route_count"] == 0
                              and _ipv6_loopback_only(value["ipv6_addresses"], value["ipv6_routes"])),
                  "runtime_mounts": _runtime_mounts_safe(value["runtime_mounts"]),
                  "memory": int(value["memory"]) == spec.memory_bytes,
                  "pids": int(value["pids"]) == spec.pids,
                  "cpu": len(cpu) == 2 and cpu[0].isdigit() and cpu[1].isdigit() and int(cpu[0]) > 0 and cpu[0] == cpu[1],
                  "socket": value["socket_absent"] is True, "app": value["app_masked"] is True,
                  "environment": set(value["environment"]) <= {"PATH", "HOME", "LANG", "LC_CTYPE"},
                  "cwd": value["cwd"] == "/fixture"}
        failed = [name for name, valid in checks.items() if not valid]
        if failed:
            suffix = "_".join(failed[:3])
            if failed == ["network"] and isinstance(value["sysfs_entries"], list):
                names = value["sysfs_entries"]
                suffix += "_count" + str(len(names))
                proc = value.get("proc_interfaces", [])
                if isinstance(proc, list) and type(value.get("route_count")) is int:
                    suffix += "_proc_count" + str(len(proc)) + "_routes" + str(value["route_count"])
                sock = value.get("socket_interfaces", [])
                if isinstance(sock, list):
                    suffix += "_socket_count" + str(len(sock)) + ("_onlylo" if sock == ["lo"] else "")
                if isinstance(sock, list) and len(sock) <= 5 and all(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,16}", name) for name in sock):
                    suffix += "_socket_" + "_".join(sock)
                if isinstance(proc, list) and len(proc) <= 5 and all(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,16}", name) for name in proc):
                    suffix += "_proc_" + "_".join(proc) + "_routes" + str(value.get("route_count"))
                if len(names) <= 5 and all(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,16}", name) for name in names):
                    suffix += "_" + "_".join(names)
            raise SandboxFailure(("preflight_" + suffix)[:80])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise SandboxFailure("preflight_failed") from None


def container_run(driver, spec, workspace, *, probe, cancelled=None):
    nonce = secrets.token_hex(16)
    name = "repopilot-p4-" + nonce
    try:
        container, actual_name = driver.create(spec, workspace, nonce, probe)
        if actual_name != name:
            raise SandboxFailure("container_identity")
        driver.verify(container, name, nonce, workspace, spec, probe)
        result, elapsed = driver.start(container, spec.timeout_seconds,
                                       16384 if probe else spec.output_bytes, cancelled)
        if probe:
            verify_probe(result, spec)
        return result, elapsed, container
    finally:
        # If creation failed before returning an ID, inspect the unique name first.
        driver.cleanup(name, nonce)
