"""Original synthetic fixtures for narrow, non-executing PR rule."""
import pytest

from app.modules.pr_review.scanner import scan_changed_file


@pytest.mark.parametrize('source', [
    'import subprocess\ndef run(name):\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess as sp\nasync def run(value):\n    sp.check_output(f"tool {value}", shell=True)\n',
    'from subprocess import run as launch\ndef task(arg):\n    launch(f"tool {arg}", shell=True)\n',
])
def test_flags_direct_function_parameter_interpolated_into_shell(source):
    out = scan_changed_file('src/worker.py', source, {3})
    assert len(out) == 1 and out[0]['rule_id'] == 'PY-SHELL-001'
    assert out[0]['start_line'] == out[0]['end_line'] == 3
    assert out[0]['severity'] == 'MEDIUM' and out[0]['confidence'] == 'MEDIUM'


@pytest.mark.parametrize('source', [
    'import subprocess\ndef run(name):\n    subprocess.run(["echo", name], shell=False)\n',
    'import subprocess\ndef run(name):\n    subprocess.run("echo fixed", shell=True)\n',
    'import subprocess\ndef run(name):\n    subprocess.run(f"echo {name}", shell=False)\n',
    'import subprocess\nsubprocess = other\ndef run(name):\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess\nimport other as subprocess\ndef run(name):\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess\ndef run(name):\n    subprocess.run(f"echo {name}")\n',
    'def run(subprocess, name):\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess\ndef run(subprocess, name):\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess\ndef run(name):\n    name = "fixed"\n    subprocess.run(f"echo {name}", shell=True)\n',
    'import subprocess\ndef run(name):\n    subprocess.run(f"echo {name.value}", shell=True)\n',
    'import subprocess\ndef run():\n    subprocess.run(f"echo {global_value}", shell=True)\n',
    'from subprocess import run\ndef task(run, arg):\n    run(f"tool {arg}", shell=True)\n',
])
def test_non_matching_or_ambiguous_cases_are_not_reported(source):
    assert scan_changed_file('src/worker.py', source, set(range(1, 10))) == []


def test_only_added_lines_and_safe_supported_paths_are_reported():
    source = 'import subprocess\ndef run(name):\n    subprocess.run(f"echo {name}", shell=True)\n'
    assert not scan_changed_file('src/worker.py', source, {2})
    assert not scan_changed_file('../worker.py', source, {3})
    assert not scan_changed_file('src/worker.ts', source, {3})
    assert not scan_changed_file('src/worker.py', 'not valid python (', {1})
    assert not scan_changed_file('src/worker.py', source, {True})
