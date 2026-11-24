"""Offline synthetic guard tests for P6 artifact preparation."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_p6_toolchain as tool  # noqa: E402


class ToolchainGuardTests(unittest.TestCase):
    def test_download_caps_fail_closed(self):
        tool.check_budget(tool.NODE_CAP, tool.WHEEL_CAP)
        for node, wheels in ((tool.NODE_CAP + 1, 0), (0, tool.WHEEL_CAP + 1), (-1, 0), (0, True)):
            with self.assertRaises(tool.gate.GuardError):
                tool.check_budget(node, wheels)

    def test_only_official_https_hosts_are_accepted(self):
        for url in ("http://nodejs.org/test", "https://nodejs.org.evil.invalid/test",
                    "https://user@pypi.org/test", "https://pypi.org:444/test"):
            with self.assertRaises(tool.gate.GuardError):
                tool.check_url(url)
        tool.check_url("https://pypi.org/pypi/uv/0.13.6/json")

    def test_wrong_published_wheel_hash_is_rejected(self):
        record = {"name": "example", "version": "1.0", "filename": "example-1.0-py3-none-any.whl",
                  "size": 4, "sha256": "a" * 64, "url": "https://files.pythonhosted.org/packages/example.whl",
                  "metadata_url": "https://pypi.org/pypi/example/1.0/json"}
        response = {"info": {"version": "1.0"}, "urls": [{"filename": record["filename"],
                    "packagetype": "bdist_wheel", "url": record["url"], "size": 4,
                    "digests": {"sha256": "b" * 64}}]}
        with mock.patch.object(tool, "fetch", return_value=json.dumps(response).encode()):
            with self.assertRaises(tool.gate.GuardError):
                tool.verify_published(record)

    def test_existing_artifact_must_be_regular_private_and_hash_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "test.whl"
            target.write_bytes(b"safe")
            target.chmod(0o600)
            record = {"size": 4, "sha256": hashlib.sha256(b"safe").hexdigest()}
            self.assertTrue(tool.artifact_valid(target, record))
            target.write_bytes(b"evil")
            with self.assertRaises(tool.gate.GuardError):
                tool.artifact_valid(target, record)
            target.unlink()
            target.symlink_to(root / "missing")
            with self.assertRaises(tool.gate.GuardError):
                tool.artifact_valid(target, record)

    def test_node_archive_rejects_path_traversal_and_escaping_symlink(self):
        prefix = f"node-v{tool.NODE_VERSION}-darwin-arm64"
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "node.tar.gz"
            for unsafe in ("../escape", f"{prefix}/../../escape"):
                with tarfile.open(archive_path, "w:gz") as archive:
                    item = tarfile.TarInfo(unsafe)
                    item.size = 1
                    archive.addfile(item, io.BytesIO(b"x"))
                with self.assertRaises(tool.gate.GuardError):
                    tool.node_member_hash(archive_path)
            with tarfile.open(archive_path, "w:gz") as archive:
                item = tarfile.TarInfo(f"{prefix}/bin/link")
                item.type = tarfile.SYMTYPE
                item.linkname = "../../../escape"
                archive.addfile(item)
            with self.assertRaises(tool.gate.GuardError):
                tool.node_member_hash(archive_path)

    def test_node_archive_requires_exact_executable(self):
        prefix = f"node-v{tool.NODE_VERSION}-darwin-arm64"
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "node.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                item = tarfile.TarInfo(f"{prefix}/bin/node")
                item.size = 4
                archive.addfile(item, io.BytesIO(b"node"))
            self.assertEqual(tool.node_member_hash(archive_path), hashlib.sha256(b"node").hexdigest())

    def test_installed_node_tree_rejects_tampered_or_extra_files(self):
        prefix = f"node-v{tool.NODE_VERSION}-darwin-arm64"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "node.tar.gz"
            target = root / "installed"
            (target / "bin").mkdir(parents=True)
            (target / "bin/node").write_bytes(b"node")
            with tarfile.open(archive_path, "w:gz") as archive:
                for path in (prefix, f"{prefix}/bin"):
                    item = tarfile.TarInfo(path)
                    item.type = tarfile.DIRTYPE
                    archive.addfile(item)
                item = tarfile.TarInfo(f"{prefix}/bin/node")
                item.size = 4
                archive.addfile(item, io.BytesIO(b"node"))
            tool.verify_node_tree(archive_path, target)
            (target / "bin/node").write_bytes(b"evil")
            with self.assertRaises(tool.gate.GuardError):
                tool.verify_node_tree(archive_path, target)
            (target / "bin/node").write_bytes(b"node")
            (target / "extra").write_text("extra")
            with self.assertRaises(tool.gate.GuardError):
                tool.verify_node_tree(archive_path, target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
