"""TypeScript review tests use original examples and never execute reviewed source."""
import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.pr_review import typescript_review as ts

NODE = "/Users/roshan/Library/Application Support/RepoPilot/toolchains/p6/node-v24.18.0-darwin-arm64/bin/node"
COMPILER = "/Volumes/;;;;;;;;;;;;;/Project/RepoPilot/apps/web/node_modules/typescript/lib/typescript.js"
NODE_HASH = "ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a"
COMPILER_HASH = "3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675"


@pytest.fixture
def settings():
    return SimpleNamespace(pr_typescript_review_enabled=True, app_env="test",
        pr_typescript_node_path=NODE, pr_typescript_node_sha256=NODE_HASH,
        pr_typescript_compiler_path=COMPILER, pr_typescript_compiler_sha256=COMPILER_HASH)


@pytest.fixture
def sandbox():
    if os.environ.get("RP_TEST_TYPESCRIPT_SANDBOX") != "1":
        pytest.skip("real macOS sandbox test requires explicit isolated opt-in")
    if sys.platform != "darwin" or not all(Path(p).is_file() for p in (NODE, COMPILER, "/usr/bin/sandbox-exec")):
        pytest.fail("opted-in TypeScript sandbox prerequisites are unavailable")


@pytest.mark.parametrize("path,source,line", [
    ("src/demo.ts", "function run(x: string) {\n return eval(x);\n}\n", 2),
    ("src/demo.tsx", "const View = ({x}: {x: string}) => <p>{eval(x)}</p>;\n", 1),
    ("src/unicode.ts", "const π = 'λ';\nfunction f(x: string) { return eval(x); }\n", 2),
])
def test_actual_parser_finds_direct_dynamic_eval(sandbox, settings, path, source, line):
    result = ts.scan_typescript(path, source, {line}, settings)
    assert len(result) == 1 and result[0]["rule_id"] == "TS-EVAL-001"
    assert result[0]["start_line"] == line and result[0]["path"] == path


@pytest.mark.parametrize("source", [
    "", "eval('constant');\n", "function f(eval: (x: string) => void, x: string) { eval(x); }\n",
    "const f = () => { throw new Error('source must never run'); };\n", "const s = '" + "x" * 20000 + "';\n",
])
def test_actual_parser_negative_cases(sandbox, settings, source):
    assert ts.scan_typescript("src/a.ts", source, {1}, settings) == []


def test_parser_syntax_failure_is_not_clean(sandbox, settings):
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts.scan_typescript("src/a.ts", "function {", {1}, settings)


def test_input_and_runtime_mismatch_fail_closed(settings):
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts.scan_typescript("../outside.ts", "x", {1}, settings)
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts.scan_typescript("src/a.ts", "x" * 100001, {1}, settings)
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts.scan_typescript("src/a.ts", "\ud800", {1}, settings)
    settings.app_env = "production"
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts.scan_typescript("src/a.ts", "x", {1}, settings)


def test_deep_input_fails_without_crashing_parent(sandbox, settings):
    source = "const x = " + "(" * 10000 + "1" + ")" * 10000 + ";"
    try:
        result = ts.scan_typescript("src/a.ts", source, {1}, settings)
        assert result == []
    except ts.TypeScriptAnalysisUnavailable:
        pass


@pytest.mark.parametrize("change", [
    {"path": "other.ts"}, {"source_sha256": "0" * 64}, {"pid": 2},
    {"findings": [{"rule": "TS-EVAL-001", "line": 999}]},
    {"findings": [{"rule": "UNKNOWN", "line": 1}]},
])
def test_forged_parser_output_is_rejected(change):
    source = "eval(x);\n"
    data = {"version": 1, "path": "a.ts", "source_sha256": sha256(source.encode()).hexdigest(),
            "pid": 1, "findings": [{"rule": "TS-EVAL-001", "line": 1}]}
    data.update(change)
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts._validate_output(json.dumps(data).encode(), "a.ts", sha256(source.encode()).hexdigest(), source, 1)
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts._validate_output(b"{", "a.ts", sha256(source.encode()).hexdigest(), source, 1)


def test_child_crash_timeout_and_output_limit_are_contained(monkeypatch):
    monkeypatch.setattr(ts, "_rss_kib", lambda pid: 1000)
    monkeypatch.setattr(ts, "TIMEOUT", .2)
    for code in ("import sys;sys.exit(5)", "import time;time.sleep(5)",
                 "import sys;sys.stdout.write('x'*50000);sys.stdout.flush()"):
        proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        with pytest.raises(ts.TypeScriptAnalysisUnavailable):
            ts._supervise(proc, b"{}")
        assert proc.poll() is not None


def test_runtime_hash_mismatch_is_rejected(sandbox, settings):
    settings.pr_typescript_compiler_sha256 = "0" * 64
    with pytest.raises(ts.TypeScriptAnalysisUnavailable, match="runtime_mismatch"):
        ts.scan_typescript("src/a.ts", "const x = 1;", {1}, settings)


def test_network_filesystem_and_process_canaries_are_denied(sandbox, settings, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-parent-only-canary")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="rp-ts-canary-", dir="/private/tmp") as temp:
        root = Path(temp)
        work = root / "work"
        work.mkdir(mode=0o700)
        (root / "outside.txt").write_text("synthetic canary")
        ts._copy_checked(NODE, work / "node", NODE_HASH, executable=True)
        script = work / "canary.cjs"
        script.write_text("""const fs=require('node:fs'), net=require('node:net'), cp=require('node:child_process');
const out={};out.secret=Boolean(process.env.GITHUB_TOKEN);try{fs.readFileSync(process.argv[2]);out.read=true}catch{out.read=false}
try{fs.writeFileSync(process.argv[3],'x');out.write=true}catch{out.write=false}
try{cp.execFileSync('/usr/bin/true');out.spawn=true}catch{out.spawn=false}
const s=net.createConnection({host:'127.0.0.1',port:9});
s.on('error',e=>{out.net=e.code;console.log(JSON.stringify(out))});
s.setTimeout(2000,()=>{out.net='timeout';s.destroy();console.log(JSON.stringify(out))});""")
        proc = subprocess.run(["/usr/bin/sandbox-exec", "-p", ts._profile(work), str(work / "node"),
            str(script), str(root / "outside.txt"), str(root / "unexpected.txt")], cwd=work,
            env={"PATH": "/usr/bin:/bin", "HOME": str(work)}, capture_output=True, timeout=10)
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result == {"secret": False, "read": False, "write": False, "spawn": False, "net": "EPERM"}
        assert not (root / "unexpected.txt").exists()


def test_production_configuration_cannot_enable_typescript():
    from pydantic import ValidationError
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", database_url="sqlite://",
                 github_webhook_secret="x" * 40, pr_typescript_review_enabled=True)


def test_output_line_must_contain_the_reviewed_construct():
    source = "const safe = 1;\neval(value);\n"
    digest = sha256(source.encode()).hexdigest()
    data = {"version": 1, "path": "src/a.ts", "source_sha256": digest, "pid": 1,
            "findings": [{"rule": "TS-EVAL-001", "line": 1}]}
    with pytest.raises(ts.TypeScriptAnalysisUnavailable):
        ts._validate_output(json.dumps(data).encode(), "src/a.ts", digest, source, 1)


def test_duplicate_calls_on_one_line_are_deduplicated(sandbox, settings):
    source = "function f(a: string, b: string) { eval(a); eval(b); }\n"
    result = ts.scan_typescript("src/a.ts", source, {1}, settings)
    assert len(result) == 1 and result[0]["start_line"] == 1


def test_sampled_rss_excess_terminates_child(monkeypatch):
    monkeypatch.setattr(ts, "_rss_kib", lambda pid: ts.MAX_RSS_KIB + 1)
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    with pytest.raises(ts.TypeScriptAnalysisUnavailable, match="resource_limit"):
        ts._supervise(proc, b"{}")
    assert proc.poll() is not None
