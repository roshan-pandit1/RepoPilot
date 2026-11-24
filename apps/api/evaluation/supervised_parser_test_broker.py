"""TEST ONLY: relay synthetic requests over an inherited local socket pair.

The PostgreSQL pytest process has a one-port network sandbox. macOS cannot
nest the parser's sandbox there, so this clean-environment helper invokes the
unmodified production run() in a separate process; its native child still gets
the production no-network sandbox. No database URL or credentials are passed.
"""

import base64
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.ingestion import supervised_parser as supervisor  # noqa: E402

MAX_REQUEST = 150_000
MAX_REPLY = supervisor.MAX_RESPONSE + 4096


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdecimal():
        return 2
    channel = socket.socket(fileno=int(sys.argv[1]))
    channel.settimeout(30)
    original_socket = socket.socket

    def local_only(family=socket.AF_INET, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise PermissionError("test broker IP networking is disabled")
        return original_socket(family, *args, **kwargs)

    socket.socket = local_only
    with channel, channel.makefile("rb") as stream:
        while True:
            line = stream.readline(MAX_REQUEST + 1)
            if not line:
                return 0
            if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
                return 3
            message = json.loads(line, object_pairs_hook=supervisor._no_duplicates)
            if message == {"action": "stop"}:
                return 0
            if not isinstance(message, dict) or set(message) != {"action", "request"} or message["action"] != "parse":
                return 4
            request = message["request"]
            if not isinstance(request, dict) or set(request) != {
                "version", "request_id", "language", "path", "source_b64", "source_sha256", "max_lines"
            }:
                return 5
            raw = base64.b64decode(request["source_b64"], validate=True)
            if supervisor._request(raw, request["path"], request["language"], request["request_id"],
                                   request["max_lines"], request["source_sha256"]) != request:
                return 6
            result = supervisor.run(raw, path=request["path"], language=request["language"],
                                    request_id=request["request_id"], expected_sha256=request["source_sha256"],
                                    max_lines=request["max_lines"])
            reply = {"status": result.status.value, "response": result.response,
                     "exit_code": result.exit_code, "peak_rss_kib": result.peak_rss_kib}
            output = (json.dumps(reply, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
            if len(output) > MAX_REPLY:
                return 7
            channel.sendall(output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError):
        # Never print source or request contents from the socket.
        sys.exit(8)
