"""Validate human-supplied chi #1188 review files without producing labels."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.evaluation.human_relevance import review_digest, validate_adjudication, validate_review  # noqa: E402
from evaluation.prepare_chi_1188_review import ROOT, _dir, load_chi  # noqa: E402


def read_private_json(path: Path, root: Path = ROOT) -> dict:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("invalid_private_submission")
    resolved_root, resolved = root.resolve(strict=True), path.resolve(strict=True)
    if path != resolved or not resolved.is_relative_to(resolved_root) or resolved == resolved_root:
        raise ValueError("submission_outside_private_root")
    _dir(resolved_root)
    for parent in reversed(resolved.relative_to(resolved_root).parents):
        directory = resolved_root / parent
        _dir(directory)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600
                or st.st_uid != os.getuid() or st.st_size > 256_000):
            raise ValueError("invalid_private_submission")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(256_001)
        if len(raw) != st.st_size:
            raise ValueError("invalid_private_submission")
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate_json_key")
                result[key] = value
            return result

        data = json.loads(raw, object_pairs_hook=unique_pairs)
        if not isinstance(data, dict):
            raise ValueError("invalid_private_submission")
        return data
    finally:
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--adjudication", type=Path)
    args = parser.parse_args()
    try:
        issue, inventory, sources = load_chi()
        reviews = [validate_review(read_private_json(path), inventory, sources, issue) for path in args.review]
        if args.adjudication:
            result = validate_adjudication(read_private_json(args.adjudication), reviews, inventory, sources, issue)
            print(f"adjudication_status={result.status}")
        print(f"validated_partial_reviews={len(reviews)}")
        for review in reviews:
            print(f"review_record_sha256={review_digest(review)}")
        print("Human identity and independent review are self-attested, not authenticated.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Do not print source text, review rationales, paths or arbitrary exception contents.
        raise SystemExit(f"Review validation failed: {type(exc).__name__}") from None


if __name__ == "__main__":
    main()
