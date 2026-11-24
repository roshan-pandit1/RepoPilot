"""Supervise the previously crash-prone synthetic Go parser workload."""

import os
from pathlib import Path
import subprocess
import sys


def test_large_synthetic_go_parses_in_a_supervised_process(tmp_path):
    program = r'''
import hashlib
import resource
from app.modules.ingestion.code_chunking import chunk_multilingual
from app.modules.ingestion.language_analysis import analyze_source

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
source = "package p\n" + "".join("func f" + str(i) + "() {}\n" for i in range(700))
assert hashlib.sha256(source.encode()).hexdigest() == "e2837fa61e44807608bb5ccdffa3d587208e69b5d6bcbd63793472132d7089db"
print("analysis_started", flush=True)
analysis = analyze_source("synthetic.go", source, timeout_seconds=1)
assert analysis.language == "go" and analysis.fallback_reason is None
assert len(analysis.symbols) == 700
chunks = chunk_multilingual(source, analysis)
assert len(chunks) == 701 and "".join(chunk.text for chunk in chunks) == source
assert chunks[1].symbol == "f0" and chunks[-1].symbol == "f699"
print("analysis_completed", flush=True)
'''
    api_dir = Path(__file__).resolve().parents[1]
    env = {"PATH": os.defpath, "PYTHONPATH": str(api_dir), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-u", "-c", program], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, (
        f"synthetic parser process exited {result.returncode}; "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert result.stdout.splitlines() == ["analysis_started", "analysis_completed"]
