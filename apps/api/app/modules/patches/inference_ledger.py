"""Single-host, owner-controlled durable ledger for explicit pilot inference approval.

This authority is not wired to an HTTP route or a production worker. A local owner
must protect the directory and explicitly approve the complete identity. A committed
claim is never recycled, even when a process dies before transmission. SQLite and a
remote HTTP server cannot provide exactly-once execution.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import UUID, uuid4

from app.modules.patches.validation import safe_path

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_MODEL = re.compile(r"[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*\Z")
_TERMINAL = {"SUCCEEDED", "ABSTAINED", "FAILED", "OUTCOME_UNKNOWN"}
_KEYS = {"version", "tenant_id", "target_repository_id", "target_repository_name", "origin_repository_id",
         "origin_repository_name", "issue_id", "issue_number", "issue_body_sha256", "commit_sha", "investigation_id",
         "snapshot_id", "manifest_sha256", "evidence", "sources", "model", "model_sha256", "endpoint",
         "timeout_seconds", "input_bytes", "output_bytes", "request_sha256", "request_bytes", "transport"}


class LedgerError(ValueError):
    """A sanitized failure; never include private request data."""


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _id(value):
    return type(value) is int and 0 < value < 2**63


def _hex(value):
    return isinstance(value, str) and bool(_HEX.fullmatch(value))


def canonical_identity(identity: dict) -> bytes:
    """Validate and canonically serialize the complete approval identity, without source text."""
    if not isinstance(identity, dict) or set(identity) != _KEYS:
        raise LedgerError("identity_invalid")
    if (identity["version"] != "pilot-inference-identity-v1"
            or not all(_id(identity[k]) for k in ("tenant_id", "target_repository_id", "origin_repository_id", "issue_id", "issue_number"))
            or not all(isinstance(identity[k], str) and _NAME.fullmatch(identity[k]) for k in ("target_repository_name", "origin_repository_name"))
            or not all(_hex(identity[k]) for k in ("issue_body_sha256", "manifest_sha256", "model_sha256", "request_sha256"))
            or not isinstance(identity["commit_sha"], str) or not _SHA1.fullmatch(identity["commit_sha"])
            or not _uuid(identity["investigation_id"]) or not _uuid(identity["snapshot_id"])
            or not isinstance(identity["model"], str) or not _MODEL.fullmatch(identity["model"])
            or "cloud" in identity["model"].lower() or identity["endpoint"] != "http://127.0.0.1:11434"
            or type(identity["timeout_seconds"]) is not int or not 1 <= identity["timeout_seconds"] <= 30
            or type(identity["input_bytes"]) is not int or not 1 <= identity["input_bytes"] <= 524288
            or type(identity["output_bytes"]) is not int or not 1 <= identity["output_bytes"] <= 307200
            or type(identity["request_bytes"]) is not int or not 1 <= identity["request_bytes"] <= identity["input_bytes"]
            or not isinstance(identity["transport"], dict)
            or set(identity["transport"]) != {"cloud_disabled", "deny_nonloopback", "follow_redirects", "trust_env"}
            or identity["transport"]["cloud_disabled"] is not True
            or identity["transport"]["deny_nonloopback"] is not True
            or identity["transport"]["follow_redirects"] is not False
            or identity["transport"]["trust_env"] is not False):
        raise LedgerError("identity_invalid")
    sources, evidence = identity["sources"], identity["evidence"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 5 or not isinstance(evidence, list) or not 1 <= len(evidence) <= 30:
        raise LedgerError("identity_invalid")
    paths = set()
    for item in sources:
        if (not isinstance(item, dict) or set(item) != {"path", "byte_length", "sha256"}
                or not isinstance(item["path"], str) or not safe_path(item["path"]) or item["path"] in paths
                or type(item["byte_length"]) is not int or not 0 < item["byte_length"] <= 131072
                or not _hex(item["sha256"])):
            raise LedgerError("identity_invalid")
        paths.add(item["path"])
    ids = set()
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"id", "path", "start_line", "end_line", "fingerprint"}
                or not _uuid(item["id"]) or item["id"] in ids or item["path"] not in paths
                or type(item["start_line"]) is not int or type(item["end_line"]) is not int
                or not 1 <= item["start_line"] <= item["end_line"] or not _hex(item["fingerprint"])):
            raise LedgerError("identity_invalid")
        ids.add(item["id"])
    try:
        return json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise LedgerError("identity_invalid") from None


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class PilotLedger:
    """SQLite ledger, authoritative for cooperating processes on a single trusted host."""

    def __init__(self, directory: Path):
        """Open an existing authority; a missing file must never reset spent claims."""
        self.directory = Path(directory)
        if not self.directory.is_absolute():
            raise LedgerError("ledger_directory_invalid")
        try:
            directory_stat = self.directory.lstat()
            if (not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_uid != os.getuid()
                    or stat.S_IMODE(directory_stat.st_mode) != 0o700):
                raise LedgerError("ledger_directory_invalid")
            self.path = self.directory / "pilot-approval.sqlite3"
            self._verify_file()
            with closing(self._connect()) as db:
                if db.execute("PRAGMA user_version").fetchone()[0] != 1 or db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise LedgerError("ledger_corrupt")
                db.execute("SELECT identity_hash, request_sha256, request_bytes, identity, state, claim_token FROM approvals LIMIT 0")
                db.execute("SELECT identity_hash, event, timestamp FROM audit LIMIT 0")
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError):
            raise LedgerError("ledger_unavailable") from None

    @classmethod
    def create(cls, directory: Path):
        """Explicitly initialize a new authority in a newly created private directory.

        Callers must pin the authority externally; creating another authority is not
        equivalent to reopening a lost one and must never recycle previous approval.
        """
        directory = Path(directory)
        if not directory.is_absolute():
            raise LedgerError("ledger_directory_invalid")
        try:
            os.mkdir(directory, 0o700)
            obj = object.__new__(cls)
            obj.directory = directory
            obj.path = directory / "pilot-approval.sqlite3"
            fd = os.open(obj.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
            obj._verify_file()
            obj._initialize()
            return cls(directory)
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError):
            raise LedgerError("ledger_unavailable") from None

    def _verify_file(self):
        data = self.path.lstat()
        if (not stat.S_ISREG(data.st_mode) or data.st_uid != os.getuid() or data.st_nlink != 1
                or stat.S_IMODE(data.st_mode) != 0o600):
            raise LedgerError("ledger_file_invalid")

    def _connect(self):
        self._verify_file()
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", isolation_level=None, timeout=10, uri=True)
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA synchronous = FULL")
        # On macOS this requests F_FULLFSYNC for stronger synchronization. It does
        # not prove power-loss durability or protect against rollback by this user.
        db.execute("PRAGMA fullfsync = ON")
        if db.execute("PRAGMA fullfsync").fetchone()[0] != 1:
            db.close()
            raise LedgerError("ledger_durability_unavailable")
        db.execute("PRAGMA trusted_schema = OFF")
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
            db.close()
            raise LedgerError("ledger_journal_invalid")
        return db

    def _initialize(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE approvals (identity_hash TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL UNIQUE, "
                       "request_bytes INTEGER NOT NULL, identity BLOB NOT NULL, state TEXT NOT NULL, claim_token TEXT, "
                       "CHECK(state IN ('AWAITING_EXPLICIT_APPROVAL','APPROVED','ATTEMPT_CLAIMED','SUCCEEDED', "
                       "'ABSTAINED','FAILED','OUTCOME_UNKNOWN','INVALIDATED')), "
                       "CHECK((state IN ('AWAITING_EXPLICIT_APPROVAL','APPROVED','INVALIDATED') AND claim_token IS NULL) OR "
                       "(state IN ('ATTEMPT_CLAIMED','SUCCEEDED','ABSTAINED','FAILED','OUTCOME_UNKNOWN') AND claim_token IS NOT NULL)))")
            db.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, identity_hash TEXT NOT NULL REFERENCES approvals(identity_hash), "
                       "event TEXT NOT NULL, timestamp TEXT NOT NULL)")
            db.execute("PRAGMA user_version = 1")
            db.execute("COMMIT")

    def _transaction(self, operation):
        try:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                result = operation(db)
                db.execute("COMMIT")  # FULL synchronization before returning a claim.
                return result
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                db.close()
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError):
            raise LedgerError("ledger_unavailable") from None

    @staticmethod
    def _event(db, identity_hash, event):
        db.execute("INSERT INTO audit(identity_hash,event,timestamp) VALUES(?,?,?)", (identity_hash, event, _stamp()))

    def prepare(self, identity: dict) -> str:
        raw = canonical_identity(identity)
        key = sha256(raw).hexdigest()
        def operation(db):
            existing = db.execute("SELECT identity, state FROM approvals WHERE identity_hash=?", (key,)).fetchone()
            if existing:
                if existing[0] != raw:
                    raise LedgerError("identity_mismatch")
                return key
            db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,NULL)",
                       (key, identity["request_sha256"], identity["request_bytes"], raw, "AWAITING_EXPLICIT_APPROVAL"))
            self._event(db, key, "PREPARED")
            self._event(db, key, "AWAITING_EXPLICIT_APPROVAL")
            return key
        return self._transaction(operation)

    def approve(self, identity_hash: str, *, request_sha256: str, request_bytes: int, confirmation: str) -> None:
        """Explicit local action only; callers must establish human authorization externally.

        This method is intentionally not exposed through application routes or workers.
        The string is a guard against accidental use, not proof of human identity.
        """
        if (not _hex(identity_hash) or not _hex(request_sha256) or type(request_bytes) is not int
                or confirmation != f"APPROVE {identity_hash} {request_sha256}"):
            raise LedgerError("approval_invalid")
        def operation(db):
            row = db.execute("SELECT request_sha256,request_bytes,state FROM approvals WHERE identity_hash=?", (identity_hash,)).fetchone()
            if row != (request_sha256, request_bytes, "AWAITING_EXPLICIT_APPROVAL"):
                raise LedgerError("approval_invalid")
            db.execute("UPDATE approvals SET state='APPROVED' WHERE identity_hash=?", (identity_hash,))
            self._event(db, identity_hash, "APPROVED")
        self._transaction(operation)

    def claim(self, identity: dict, *, request_sha256: str, request_bytes: int) -> str:
        raw = canonical_identity(identity)
        key = sha256(raw).hexdigest()
        if (request_sha256 != identity["request_sha256"] or type(request_bytes) is not int
                or request_bytes != identity["request_bytes"]):
            raise LedgerError("approval_invalid")
        def operation(db):
            row = db.execute("SELECT identity,request_sha256,request_bytes,state FROM approvals WHERE identity_hash=?", (key,)).fetchone()
            if row != (raw, request_sha256, request_bytes, "APPROVED"):
                raise LedgerError("claim_unavailable")
            token = str(uuid4())
            result = db.execute("UPDATE approvals SET state='ATTEMPT_CLAIMED',claim_token=? WHERE identity_hash=? AND state='APPROVED'", (token, key))
            if result.rowcount != 1:
                raise LedgerError("claim_unavailable")
            self._event(db, key, "ATTEMPT_CLAIMED")
            return token
        return self._transaction(operation)

    def finish(self, identity_hash: str, claim_token: str, outcome: str) -> None:
        if not _hex(identity_hash) or not _uuid(claim_token) or outcome not in _TERMINAL:
            raise LedgerError("outcome_invalid")
        def operation(db):
            result = db.execute("UPDATE approvals SET state=? WHERE identity_hash=? AND state='ATTEMPT_CLAIMED' AND claim_token=?", (outcome, identity_hash, claim_token))
            if result.rowcount != 1:
                raise LedgerError("outcome_invalid")
            self._event(db, identity_hash, outcome)
        self._transaction(operation)

    def mark_outcome_unknown(self, identity_hash: str) -> None:
        """An explicit recovery decision; never return the entitlement to APPROVED."""
        if not _hex(identity_hash):
            raise LedgerError("identity_invalid")
        def operation(db):
            result = db.execute("UPDATE approvals SET state='OUTCOME_UNKNOWN' WHERE identity_hash=? AND state='ATTEMPT_CLAIMED'", (identity_hash,))
            if result.rowcount != 1:
                raise LedgerError("outcome_invalid")
            self._event(db, identity_hash, "OUTCOME_UNKNOWN")
        self._transaction(operation)

    def invalidate(self, identity_hash: str) -> None:
        """Invalidate only an unclaimed package; a consumed claim stays consumed."""
        if not _hex(identity_hash):
            raise LedgerError("identity_invalid")
        def operation(db):
            result = db.execute("UPDATE approvals SET state='INVALIDATED' WHERE identity_hash=? AND state IN ('AWAITING_EXPLICIT_APPROVAL','APPROVED')", (identity_hash,))
            if result.rowcount != 1:
                raise LedgerError("invalidation_invalid")
            self._event(db, identity_hash, "INVALIDATED")
        self._transaction(operation)

    def status(self, identity_hash: str) -> str:
        if not _hex(identity_hash):
            raise LedgerError("identity_invalid")
        def operation(db):
            row = db.execute("SELECT state FROM approvals WHERE identity_hash=?", (identity_hash,)).fetchone()
            if not row:
                raise LedgerError("identity_unknown")
            return row[0]
        return self._transaction(operation)
