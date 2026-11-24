"""Test-only child. Source is inert data; no repository code is imported or run."""

import base64
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import sysconfig

request_id = None


def main():
    global request_id
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_048_576, 1_048_576))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    sys.path.insert(0, sysconfig.get_path("purelib"))
    sys.path.insert(0, str(Path(__file__).parent))
    from app.modules.ingestion.code_chunking import chunk_multilingual, chunk_python
    from app.modules.ingestion.language_analysis import LANGUAGES, analyze_source

    request = json.loads(sys.stdin.buffer.read(150_001))
    if (not isinstance(request.get("request_id"), str) or len(request["request_id"]) != 32
            or any(c not in "0123456789abcdef" for c in request["request_id"])):
        raise ValueError("invalid_request_id")
    request_id = request["request_id"]
    raw = base64.b64decode(request["source_b64"], validate=True)
    if len(raw) > 100_000 or hashlib.sha256(raw).hexdigest() != request["source_sha256"]:
        raise ValueError("invalid_source")
    source = raw.decode("utf-8")
    path = request["path"]
    registered = LANGUAGES.get(Path(path).suffix.lower())
    if request["version"] != 1 or registered is None or registered.name != request["language"]:
        raise ValueError("invalid_contract")
    analysis = analyze_source(path, source, max_bytes=100_000, max_nodes=50_000,
                              timeout_seconds=1.0)
    chunks = (chunk_python(source, max_lines=request["max_lines"])
              if analysis.language == "python" else
              chunk_multilingual(source, analysis, max_lines=request["max_lines"]))
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    result = []
    for chunk in chunks:
        start, end = offsets[chunk.start_line - 1], offsets[chunk.end_line]
        result.append({"start_line": chunk.start_line, "end_line": chunk.end_line,
                       "start_byte": start, "end_byte": end,
                       "content_sha256": hashlib.sha256(raw[start:end]).hexdigest(),
                       "symbol": chunk.symbol, "symbol_kind": chunk.symbol_kind})
    response = {
        "version": 1, "request_id": request["request_id"], "worker_pid": os.getpid(),
        "language": analysis.language,
        "path": path, "source_sha256": hashlib.sha256(raw).hexdigest(),
        "grammar": registered.module, "grammar_entrypoint": registered.entrypoint,
        "parser_version": analysis.parser_version,
        "parser_status": "fallback" if analysis.fallback_reason else "parsed",
        "fallback_reason": analysis.fallback_reason,
        "chunk_strategy": "python-ast" if analysis.language == "python" else "multilingual",
        "symbols": [{"name": item.name, "kind": item.kind, "parent": item.parent,
                     "start_line": item.start_line, "end_line": item.end_line}
                    for item in analysis.symbols],
        "imports": [list(item) for item in analysis.import_lines], "chunks": result,
    }
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not print input, exceptions or tracebacks from untrusted source.
        if request_id is None:
            sys.exit(78)
        print(json.dumps({"version": 1, "request_id": request_id, "error": "parser_error"}),
              flush=True)
