"""The local parallel gate must retain full pytest discovery and failure evidence."""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-python-tests.py"


def test_parallel_gate_balances_durations_instead_of_file_count():
    namespace = runpy.run_path(str(SCRIPT))
    assert "partition_files" in namespace
    files = list("abcdefgh")
    durations = dict(zip(files, range(9, 1, -1)))
    groups = namespace["partition_files"](files, durations)
    assert groups == [["a", "h"], ["b", "g"], ["c", "f"], ["d", "e"]]
    assert [sum(durations[path] for path in group) for group in groups] == [11] * 4


@pytest.mark.parametrize("files, expected", [
    ([], []),
    (["nested/new_test.py", "test_new.py"], [["nested/new_test.py"], ["test_new.py"]]),
    (list("abcde"), [["a", "e"], ["b"], ["c"], ["d"]]),
])
def test_parallel_gate_includes_unknown_files_once_with_stable_ties(files, expected):
    namespace = runpy.run_path(str(SCRIPT))
    assert "partition_files" in namespace
    groups = namespace["partition_files"](list(reversed(files)), {"deleted_test.py": 999})
    assert groups == expected
    assert sorted(path for group in groups for path in group) == sorted(files)


@pytest.mark.parametrize("failure", [False, True])
def test_parallel_gate_discovers_nested_tests_and_propagates_failures(tmp_path, failure):
    suite = tmp_path / "tests"
    (suite / "nested").mkdir(parents=True)
    (suite / "test_first.py").write_text("def test_first(): assert True\n")
    (suite / "nested/second_test.py").write_text(
        f"def test_second(): assert {not failure}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c",
         f"import runpy; from pathlib import Path; "
         f"raise SystemExit(runpy.run_path({str(SCRIPT)!r})['main'](Path({str(suite)!r})))"],
        capture_output=True, text=True,
    )
    assert result.returncode == int(failure), result.stdout + result.stderr
    assert "Collected 2 tests in 2 files" in result.stdout
    assert "Executed 2 tests" in result.stdout
    logs = Path(result.stdout.split("Logs: ", 1)[1].splitlines()[0])
    assert (logs / "collection.log").is_file()
    output = "\n".join(p.read_text() for p in logs.glob("shard-*.log"))
    assert ("FAILED" in output) == failure
    assert len(list(logs.glob("shard-*.xml"))) == 2


def test_parallel_gate_rejects_missing_execution_reports(tmp_path):
    suite = tmp_path / "tests"
    suite.mkdir()
    (suite / "test_one.py").write_text("def test_one(): pass\n")
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy, subprocess; from pathlib import Path; from types import SimpleNamespace; "
         "subprocess.run = lambda *args, **kwargs: SimpleNamespace(returncode=0); "
         f"raise SystemExit(runpy.run_path({str(SCRIPT)!r})['main'](Path({str(suite)!r})))"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Executed 0 tests; expected 1" in result.stdout


def test_parallel_gate_stops_on_collection_error(tmp_path):
    suite = tmp_path / "tests"
    suite.mkdir()
    (suite / "test_broken.py").write_text("invalid python syntax!\n")
    result = subprocess.run(
        [sys.executable, "-c",
         f"import runpy; from pathlib import Path; "
         f"raise SystemExit(runpy.run_path({str(SCRIPT)!r})['main'](Path({str(suite)!r})))"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "SyntaxError" in result.stdout
    logs = Path(result.stdout.split("Logs: ", 1)[1].splitlines()[0])
    assert not list(logs.glob("shard-*"))
