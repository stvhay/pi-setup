#!/usr/bin/env python3
"""Run the complete local pytest gate in four isolated processes; retain logs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import pytest


class Collection:
    def pytest_collection_finish(self, session):
        self.count = len(session.items)
        self.files = sorted({str(item.path) for item in session.items})


def partition_files(files, durations):
    groups = [[] for _ in range(min(4, len(files)))]
    totals = [0.0] * len(groups)
    for path in sorted(files, key=lambda path: (-durations.get(path, 1), path)):
        index = min(range(len(groups)), key=totals.__getitem__)
        groups[index].append(path)
        totals[index] += durations.get(path, 1)
    return groups


def main(test_root=Path(__file__).resolve().parents[1] / "tests"):
    logs = Path(tempfile.mkdtemp(prefix="pi-python-tests-"))
    print(f"Logs: {logs}", flush=True)
    collection = Collection()
    with (logs / "collection.log").open("w") as output, redirect_stdout(output), redirect_stderr(output):
        code = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", str(test_root)], plugins=[collection])
    if code:
        print((logs / "collection.log").read_text())
        return int(code)
    print(f"Collected {collection.count} tests in {len(collection.files)} files", flush=True)
    # shortcut: historical weights drift; refresh from JUnit when shard times diverge.
    durations = json.loads(Path(__file__).with_name("python-test-durations.json").read_text())
    weights = {str((test_root / path).resolve()): seconds for path, seconds in durations.items()}
    groups = partition_files(collection.files, weights)

    def run(index):
        with (logs / f"shard-{index}.log").open("w") as output:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 *groups[index], f"--junitxml={logs / f'shard-{index}.xml'}"],
                stdout=output, stderr=subprocess.STDOUT,
            )
        return result.returncode

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(run, range(len(groups))))
    executed = 0
    for index, code in enumerate(codes):
        report = logs / f"shard-{index}.xml"
        if report.exists():
            executed += len(list(ET.parse(report).getroot().iter("testcase")))
        print(f"Shard {index}: exit {code}; {logs / f'shard-{index}.log'}")
        print("\n".join((logs / f"shard-{index}.log").read_text().splitlines()[-8:]))
    print(f"Executed {executed} tests; expected {collection.count}")
    return int(any(codes) or executed != collection.count)


if __name__ == "__main__":
    raise SystemExit(main())
