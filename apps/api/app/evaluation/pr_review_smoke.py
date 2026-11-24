"""Tiny original synthetic scanner smoke benchmark; not a general review benchmark."""
import json
import time

from app.modules.pr_review.scanner import RULE_VERSION, scan_changed_file

# The same author knew the implemented rule when writing the holdout; this is not
# an independent quality estimate and does not measure general defect recall.
CASES = (
    ('d-positive', 'development', 'import subprocess\ndef f(x):\n    subprocess.run(f"echo {x}", shell=True)\n', {3}, True, 3),
    ('d-argv', 'development', 'import subprocess\ndef f(x):\n    subprocess.run(["echo",x], shell=False)\n', {3}, False, None),
    ('d-fixed', 'development', 'import subprocess\ndef f(x):\n    subprocess.run("echo fixed", shell=True)\n', {3}, False, None),
    ('d-unchanged', 'development', 'import subprocess\ndef f(x):\n    subprocess.run(f"echo {x}", shell=True)\n', {2}, False, None),
    ('h-positive-async', 'holdout', 'import subprocess as sp\nasync def test(a):\n    sp.check_output(f"cmd {a}", shell=True)\n', {3}, True, 3),
    ('h-positive-alias', 'holdout', 'from subprocess import run as launch\ndef f(text):\n    launch(f"cmd {text}", shell=True)\n', {3}, True, 3),
    ('h-positive-mixed', 'holdout', 'import subprocess\ndef f(a,b):\n    subprocess.call(f"cmd {a} {b}", shell=True)\n', {3}, True, 3),
    ('h-positive-kw', 'holdout', 'import subprocess\ndef f(*, value):\n    subprocess.Popen(f"echo {value}", shell=True)\n', {3}, True, 3),
    ('h-safe-argv', 'holdout', 'import subprocess\ndef f(x):\n    subprocess.run(["tool",x])\n', {3}, False, None),
    ('h-safe-shell-false', 'holdout', 'import subprocess\ndef f(x):\n    subprocess.run(f"tool {x}", shell=False)\n', {3}, False, None),
    ('h-unknown-object', 'holdout', 'import subprocess\ndef f(obj):\n    subprocess.run(f"tool {obj.value}", shell=True)\n', {3}, False, None),
    ('h-shadow', 'holdout', 'import subprocess\ndef f(subprocess,x):\n    subprocess.run(f"tool {x}", shell=True)\n', {3}, False, None),
    ('h-local', 'holdout', 'import subprocess\ndef f():\n    subprocess.run(f"tool {external}", shell=True)\n', {3}, False, None),
    ('h-unchanged', 'holdout', 'import subprocess\ndef f(x):\n    subprocess.run(f"tool {x}", shell=True)\n', {1}, False, None),
)


def evaluate():
    output = {'version': 'synthetic-pr-rule-smoke-v1', 'analyzer': RULE_VERSION, 'splits': {}}
    for split in ('development', 'holdout'):
        rows = [row for row in CASES if row[1] == split]
        tp = fp = fn = tn = evidence_correct = duplicates = byte_count = 0
        start = time.perf_counter()
        for _name, _split, source, added, positive, location in rows:
            byte_count += len(source.encode())
            findings = scan_changed_file('src/example.py', source, added)
            positive_result = bool(findings)
            tp += int(positive and positive_result)
            fn += int(positive and not positive_result)
            fp += int(not positive and positive_result)
            tn += int(not positive and not positive_result)
            duplicates += max(0, len(findings) - 1)
            evidence_correct += sum(f['start_line'] == location and f['end_line'] == location for f in findings if positive)
        elapsed = (time.perf_counter() - start) * 1000
        output['splits'][split] = {'cases': len(rows), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall_for_rule_cases': tp / (tp + fn) if tp + fn else None,
            'false_positive_rate': fp / (fp + tn) if fp + tn else None,
            'evidence_location_accuracy': evidence_correct / tp if tp else None,
            'duplicate_findings': duplicates, 'source_bytes': byte_count,
            'local_elapsed_ms': round(elapsed, 3)}
    return output


if __name__ == '__main__':
    print(json.dumps(evaluate(), sort_keys=True))
