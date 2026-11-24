"""Prepare the reviewed P6 toolchain outside the repository; never build packages.

``check`` is offline and read-only. ``fetch`` verifies official metadata, applies
the explicit size caps, and stores only exact binary artifacts and toolchains.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

spec = importlib.util.spec_from_file_location("p6_disposable_gate", Path(__file__).with_name("tree_sitter_pg_harness.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

INVENTORY = Path(__file__).with_name("p6-toolchain-artifacts.json")
ROOT = Path.home() / "Library/Application Support/RepoPilot/toolchains/p6"
NODE_VERSION = "24.18.0"
NODE_FILE = f"node-v{NODE_VERSION}-darwin-arm64.tar.gz"
NODE_SHA = "e1a97e14c99c803e96c7339403282ea05a499c32f8d83defe9ef5ec66f979ed1"
NODE_SIZE = 52087559
NODE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/{NODE_FILE}"
NODE_SUMS = f"https://nodejs.org/dist/v{NODE_VERSION}/SHASUMS256.txt"
NODE_CAP = 100 * 1024 * 1024
WHEEL_CAP = 200 * 1024 * 1024
HOSTS = {"nodejs.org", "pypi.org", "files.pythonhosted.org"}


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    gate.require(parsed.scheme == "https" and parsed.hostname in HOSTS and not parsed.username
                 and not parsed.password and parsed.port in (None, 443) and not parsed.fragment,
                 "unexpected artifact URL")


def check_budget(node_bytes, wheel_bytes):
    gate.require(type(node_bytes) is int and 0 <= node_bytes <= NODE_CAP
                 and type(wheel_bytes) is int and 0 <= wheel_bytes <= WHEEL_CAP, "approved download cap exceeded")


def fetch(url, limit):
    check_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "RepoPilot-P6/1"})
    with opener.open(request, timeout=30) as response:
        check_url(response.geturl())
        gate.require(response.status == 200, "artifact metadata request failed")
        value = response.read(limit + 1)
    gate.require(len(value) <= limit, "artifact metadata exceeds bound")
    return value


def load_inventory():
    gate.require(gate.regular(INVENTORY), "toolchain artifact inventory is missing")
    inventory = json.loads(INVENTORY.read_text())
    gate.require(inventory.get("version") == "repopilot-p6-toolchain-artifacts-v1"
                 and inventory.get("python_lock_sha256") == gate.LOCK_SHA256, "unexpected artifact inventory")
    node = inventory.get("node")
    gate.require(node == {"version": NODE_VERSION, "filename": NODE_FILE, "size": NODE_SIZE, "sha256": NODE_SHA,
                          "url": NODE_URL, "checksum_url": NODE_SUMS}, "unexpected Node artifact")
    packages = gate.required_packages(gate.load_contract(gate.API_ROOT))
    records = inventory.get("wheels")
    gate.require(isinstance(records, list) and len(records) == len(packages) + 1, "unexpected wheel inventory")
    by_name = {}
    mac_version = tuple(map(int, platform.mac_ver()[0].split(".")[:2]))
    gate.require(platform.system() == "Darwin" and platform.machine() == "arm64" and len(mac_version) == 2,
                 "toolchain requires macOS ARM64")
    for record in records:
        gate.require(isinstance(record, dict) and set(record) == {
            "name", "version", "filename", "size", "sha256", "url", "metadata_url"}, "invalid wheel record")
        name, version, filename, size, digest = (record[key] for key in ("name", "version", "filename", "size", "sha256"))
        gate.require(isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name)
                     and isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9.+!-]+", version)
                     and name not in by_name and isinstance(filename, str) and PurePosixPath(filename).name == filename
                     and type(size) is int and 0 < size <= WHEEL_CAP and isinstance(digest, str)
                     and re.fullmatch(r"[0-9a-f]{64}", digest) and gate.compatible_wheel(filename, mac_version),
                     "unsafe wheel identity")
        gate.require(record["metadata_url"] == f"https://pypi.org/pypi/{name}/{version}/json",
                     "unexpected wheel metadata URL")
        check_url(record["url"])
        parsed = urllib.parse.urlsplit(record["url"])
        gate.require(parsed.hostname == "files.pythonhosted.org" and parsed.path.startswith("/packages/")
                     and PurePosixPath(parsed.path).name == filename and not parsed.query,
                     "unexpected wheel URL")
        if name == "uv":
            gate.require(version == gate.EXPECTED_UV and filename == gate.UV_WHEEL and digest == gate.UV_WHEEL_SHA256,
                         "unexpected uv wheel")
        else:
            package = packages.get(name, {})
            gate.require(package.get("version") == version and any(
                wheel.get("url") == record["url"] and wheel.get("size") == size
                and wheel.get("hash") == "sha256:" + digest for wheel in package.get("wheels", [])),
                "wheel is not the exact locked artifact")
        by_name[name] = record
    gate.require(set(by_name) == set(packages) | {"uv"}, "wheel dependency closure is incomplete")
    return inventory, by_name


def private_root(create):
    base = ROOT.parents[1]  # .../RepoPilot
    gate.require(base.is_dir() and not base.is_symlink() and base.stat().st_uid == os.getuid()
                 and stat.S_IMODE(base.stat().st_mode) == 0o700, "RepoPilot private directory is unsafe")
    for path in (ROOT.parent, ROOT, ROOT / "wheels", ROOT / "artifacts"):
        if create and not path.exists() and not path.is_symlink():
            path.mkdir(mode=0o700)
        gate.require(path.is_dir() and not path.is_symlink() and path.stat().st_uid == os.getuid()
                     and stat.S_IMODE(path.stat().st_mode) == 0o700, "private toolchain directory is unsafe")


def artifact_valid(path, record):
    if not path.exists() and not path.is_symlink():
        return False
    gate.require(gate.regular(path) and path.stat().st_uid == os.getuid()
                 and stat.S_IMODE(path.stat().st_mode) == 0o600 and path.stat().st_size == record["size"]
                 and gate.digest(path) == record["sha256"], "existing artifact is unsafe or has wrong hash")
    return True


def verify_published(record):
    metadata = json.loads(fetch(record["metadata_url"], 4 * 1024 * 1024))
    gate.require(metadata.get("info", {}).get("version") == record["version"], "PyPI version mismatch")
    matches = [item for item in metadata.get("urls", []) if item.get("filename") == record["filename"]]
    gate.require(len(matches) == 1, "PyPI wheel identity missing or ambiguous")
    item = matches[0]
    gate.require(item.get("packagetype") == "bdist_wheel" and item.get("url") == record["url"]
                 and item.get("size") == record["size"] and item.get("digests", {}).get("sha256") == record["sha256"],
                 "PyPI wheel metadata disagrees with the locked artifact")


def download(record, directory):
    target = directory / record["filename"]
    if artifact_valid(target, record):
        return 0
    check_url(record["url"])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
    request = urllib.request.Request(record["url"], headers={"Accept-Encoding": "identity", "User-Agent": "RepoPilot-P6/1"})
    fd, temporary = tempfile.mkstemp(prefix=".p6-download-", dir=directory)
    written, digest = 0, hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as output, opener.open(request, timeout=60) as response:
            check_url(response.geturl())
            gate.require(response.status == 200 and response.headers.get("Content-Length") == str(record["size"]),
                         "artifact response length mismatch")
            while chunk := response.read(1024 * 1024):
                written += len(chunk)
                gate.require(written <= record["size"], "artifact exceeds approved size")
                digest.update(chunk)
                output.write(chunk)
        gate.require(written == record["size"] and digest.hexdigest() == record["sha256"], "artifact hash mismatch")
        gate.require(not target.exists() and not target.is_symlink(), "artifact target appeared during download")
        os.replace(temporary, target)
        return written
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def extract_uv(wheel, *, create):
    target = ROOT / "uv"
    with zipfile.ZipFile(wheel) as archive:
        matches = [item for item in archive.infolist() if PurePosixPath(item.filename).name == "uv" and not item.is_dir()]
        gate.require(len(matches) == 1 and matches[0].file_size <= 128 * 1024 * 1024, "invalid uv executable")
        expected = hashlib.sha256(archive.read(matches[0])).hexdigest()
        if target.exists() or target.is_symlink():
            gate.require(gate.regular(target) and target.stat().st_uid == os.getuid()
                         and stat.S_IMODE(target.stat().st_mode) == 0o700 and gate.digest(target) == expected,
                         "existing uv executable does not match wheel")
        else:
            gate.require(create, "verified uv executable is missing")
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
            with os.fdopen(fd, "wb") as stream, archive.open(matches[0]) as source:
                shutil.copyfileobj(source, stream)
            gate.require(gate.digest(target) == expected, "extracted uv executable hash mismatch")
    gate.check_uv(target, wheel)
    return expected


def node_member_hash(archive_path):
    with tarfile.open(archive_path, "r:gz") as archive:
        prefix = f"node-v{NODE_VERSION}-darwin-arm64"
        members = archive.getmembers()
        gate.require(bool(members) and len(members) < 50000
                     and sum(item.size for item in members if item.isfile()) <= 600 * 1024 * 1024,
                     "unexpected Node archive inventory")
        for item in members:
            path = PurePosixPath(item.name)
            gate.require(not path.is_absolute() and path.parts and path.parts[0] == prefix
                         and ".." not in path.parts and not item.isdev() and not item.isfifo(), "unsafe Node archive")
            if item.issym() or item.islnk():
                base = posixpath.dirname(item.name) if item.issym() else ""
                resolved = posixpath.normpath(posixpath.join(base, item.linkname))
                gate.require(not item.linkname.startswith("/") and resolved.startswith(prefix + "/"),
                             "unsafe Node archive link")
        matches = [item for item in members if item.name == prefix + "/bin/node" and item.isfile()]
        gate.require(len(matches) == 1, "Node executable missing from archive")
        stream = archive.extractfile(matches[0])
        gate.require(stream is not None, "cannot read Node executable")
        digest = hashlib.sha256()
        while data := stream.read(1024 * 1024):
            digest.update(data)
        return digest.hexdigest()


def verify_node_tree(archive_path, target):
    """Recheck every installed file and link against the verified archive."""
    prefix = f"node-v{NODE_VERSION}-darwin-arm64"
    expected = set()
    with tarfile.open(archive_path, "r:gz") as archive:
        for item in archive.getmembers():
            parts = PurePosixPath(item.name).parts
            gate.require(parts and parts[0] == prefix and ".." not in parts, "unsafe Node archive path")
            if len(parts) == 1:
                gate.require(item.isdir(), "unsafe Node archive root")
                continue
            relative = str(PurePosixPath(*parts[1:]))
            gate.require(relative not in expected, "duplicate Node archive path")
            expected.add(relative)
            path = target / relative
            if item.isdir():
                gate.require(path.is_dir() and not path.is_symlink(), "Node directory mismatch")
            elif item.isfile():
                gate.require(gate.regular(path) and path.stat().st_size == item.size, "Node file mismatch")
                source = archive.extractfile(item)
                gate.require(source is not None, "Node archive file unreadable")
                digest = hashlib.sha256()
                while data := source.read(1024 * 1024):
                    digest.update(data)
                gate.require(gate.digest(path) == digest.hexdigest(), "Node file hash mismatch")
            elif item.issym():
                gate.require(path.is_symlink() and os.readlink(path) == item.linkname, "Node symlink mismatch")
            else:
                raise gate.GuardError("unsupported Node archive entry")
    found = set()
    for directory, dirs, files in os.walk(target, followlinks=False):
        for name in dirs + files:
            found.add(str((Path(directory) / name).relative_to(target)))
    gate.require(found == expected, "Node installation has missing or unexpected files")


def install_node(archive_path, *, create):
    expected = node_member_hash(archive_path)
    name = f"node-v{NODE_VERSION}-darwin-arm64"
    target = ROOT / name
    if not target.exists() and not target.is_symlink():
        gate.require(create, "verified Node installation is missing")
        staging = Path(tempfile.mkdtemp(prefix=".node-install-", dir=ROOT))
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(staging, filter="data")
            source = staging / name
            gate.require(source.is_dir() and not source.is_symlink() and gate.digest(source / "bin/node") == expected,
                         "extracted Node executable hash mismatch")
            gate.require(not target.exists() and not target.is_symlink(), "Node target appeared during extraction")
            os.replace(source, target)
        finally:
            shutil.rmtree(staging)
    binary = target / "bin/node"
    gate.require(target.is_dir() and not target.is_symlink() and gate.regular(binary)
                 and gate.digest(binary) == expected and os.access(binary, os.X_OK), "Node installation is unsafe")
    verify_node_tree(archive_path, target)
    env = {**gate.clean_env(Path("/nonexistent")), "PATH": str(target / "bin") + ":/usr/bin:/bin"}
    result = gate.command(gate.network_sandbox([str(binary), "-p", "JSON.stringify({version:process.version,arch:process.arch,platform:process.platform})"]), env=env)
    gate.require(json.loads(result.stdout) == {"version": "v" + NODE_VERSION, "arch": "arm64", "platform": "darwin"},
                 "unexpected Node runtime")
    npm = gate.command(gate.network_sandbox([str(target / "bin/npm"), "--version"]), env=env).stdout.strip()
    gate.require(re.fullmatch(r"\d+\.\d+\.\d+", npm) is not None, "unexpected npm version")
    return expected, npm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "fetch"))
    args = parser.parse_args()
    os.umask(0o077)
    inventory, records = load_inventory()
    private_root(args.action == "fetch")
    node_path = ROOT / "artifacts" / NODE_FILE
    wheel_dir = ROOT / "wheels"
    missing_node = not artifact_valid(node_path, inventory["node"])
    missing = [item for item in records.values() if not artifact_valid(wheel_dir / item["filename"], item)]
    node_bytes = NODE_SIZE if missing_node else 0
    wheel_bytes = sum(item["size"] for item in missing)
    print(f"Planned new downloads: Node {node_bytes} bytes; wheels {wheel_bytes} bytes ({len(missing)} files)", flush=True)
    check_budget(node_bytes, wheel_bytes)
    if args.action == "fetch":
        sums = fetch(NODE_SUMS, 128 * 1024).decode("ascii")
        lines = [line.split() for line in sums.splitlines() if line.split() and line.split()[-1] == NODE_FILE]
        gate.require(len(lines) == 1 and lines[0] == [NODE_SHA, NODE_FILE], "official Node checksum mismatch")
        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(verify_published, records.values()))
        print("Official Node checksum and all PyPI wheel identities verified", flush=True)
        node_downloaded = download(inventory["node"], ROOT / "artifacts")
        with ThreadPoolExecutor(max_workers=6) as executor:
            wheel_downloaded = sum(executor.map(lambda item: download(item, wheel_dir), records.values()))
        gate.require(node_downloaded == node_bytes and wheel_downloaded == wheel_bytes, "download accounting mismatch")
        print(f"Downloaded Node {node_downloaded} bytes; wheels {wheel_downloaded} bytes", flush=True)
    else:
        gate.require(not missing_node and not missing, "verified local artifacts are incomplete")
    uv_sha = extract_uv(wheel_dir / gate.UV_WHEEL, create=args.action == "fetch")
    node_sha, npm = install_node(node_path, create=args.action == "fetch")
    packages = gate.required_packages(gate.load_contract(gate.API_ROOT))
    available, absent = gate.audit_wheelhouse(packages, wheel_dir, tuple(map(int, platform.mac_ver()[0].split(".")[:2])))
    gate.require(not absent and len(available) == len(packages), "offline wheelhouse verification failed")
    record = {"version": "repopilot-p6-toolchain-verification-v1", "node": NODE_VERSION,
              "node_artifact_sha256": NODE_SHA, "node_binary_sha256": node_sha, "npm": npm,
              "uv": gate.EXPECTED_UV, "uv_binary_sha256": uv_sha, "uv_wheel_sha256": gate.UV_WHEEL_SHA256,
              "python_lock_sha256": gate.LOCK_SHA256,
              "wheels": [{key: item[key] for key in ("name", "version", "filename", "size", "sha256")}
                         for item in sorted(records.values(), key=lambda value: value["name"])],
              "checksum_manifest_signature_verified": False,
              "signature_note": "GnuPG and a trusted Node release-key ring were unavailable."}
    if args.action == "fetch":
        target = ROOT / "verification.json"
        gate.require(not target.is_symlink(), "unsafe verification manifest")
        fd, temp = tempfile.mkstemp(prefix=".manifest-", dir=ROOT)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream, indent=2, sort_keys=True)
                stream.write("\n")
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print(f"Verified Node {NODE_VERSION}, npm {npm}, uv {gate.EXPECTED_UV} and {len(available)} locked wheels")
    print(f"Private toolchain: {ROOT}")


if __name__ == "__main__":
    try:
        main()
    except (gate.GuardError, OSError, ValueError, KeyError, TypeError, tarfile.TarError,
            zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"BLOCKED: {exc}")
        raise SystemExit(1) from None
