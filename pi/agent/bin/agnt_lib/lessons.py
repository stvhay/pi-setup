from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .core import capture

DEFAULT_LESSONS_URL = "https://pi-lessons.st5ve.com"

SECRET_PATTERNS = [
    (re.compile(r"([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*=)([^\s]+)", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(Authorization:\s*Bearer\s+)([^\s]+)", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "<redacted-token>"),
    (re.compile(r"\bghp_[A-Za-z0-9_]{8,}\b"), "<redacted-token>"),
    (re.compile(r"\bxox[A-Za-z0-9_-]{8,}\b"), "<redacted-token>"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_inbox() -> Path:
    return Path(os.environ.get("AGNT_LESSONS_INBOX") or (Path.home() / ".pi" / "lessons" / "inbox.jsonl")).expanduser()


def default_archive_dir() -> Path:
    return Path(os.environ.get("AGNT_LESSONS_ARCHIVE_DIR") or (Path.home() / ".pi" / "lessons" / "pushed")).expanduser()


def lessons_url(url: str | None = None) -> str:
    return (url or os.environ.get("AGNT_LESSONS_URL") or DEFAULT_LESSONS_URL).rstrip("/")


def redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def project_context() -> tuple[str, str]:
    try:
        root = capture(["git", "rev-parse", "--show-toplevel"]).strip()
        if root:
            path = Path(root)
            return path.name, str(path)
    except Exception:
        pass
    cwd = Path.cwd()
    return cwd.name, str(cwd)


def parse_payload(raw: str | None) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"agnt lessons: invalid --payload-json: {exc}")
    if not isinstance(parsed, dict):
        raise SystemExit("agnt lessons: --payload-json must be a JSON object")
    return parsed


def lesson_record(
    *,
    summary: str,
    kind: str = "other",
    area: str = "unknown",
    evidence: str | None = None,
    tags: List[str] | None = None,
    payload: Dict[str, Any] | None = None,
    project: str | None = None,
    project_dir: str | None = None,
    hostname: str | None = None,
    status: str = "new",
) -> Dict[str, Any]:
    if project is None or project_dir is None:
        detected_project, detected_dir = project_context()
        project = project or detected_project
        project_dir = project_dir or detected_dir
    return {
        "uuid": str(uuid_lib.uuid4()),
        "date": utc_now(),
        "hostname": hostname or socket.gethostname(),
        "project": project,
        "project_dir": project_dir,
        "kind": kind,
        "area": area,
        "summary": redact_text(summary) or "",
        "evidence": redact_text(evidence),
        "status": status,
        "tags": tags or [],
        "payload": payload or {},
    }


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], *, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def rows_to_jsonl(rows: Iterable[Dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def archive_rows(rows: List[Dict[str, Any]], archive_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = archive_dir / f"{stamp}.jsonl"
    write_jsonl(path, rows)
    return path


def post_lessons(url: str, rows: List[Dict[str, Any]], timeout: float = 10.0) -> Dict[str, Any]:
    data = rows_to_jsonl(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{lessons_url(url)}/lesson",
        data=data,
        headers={"Content-Type": "application/x-ndjson"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body or "{}")


def pull_lessons(url: str, params: Dict[str, str | None], timeout: float = 10.0) -> str:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value})
    full = f"{lessons_url(url)}/lessons" + (f"?{query}" if query else "")
    req = urllib.request.Request(full, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def limit_jsonl(text: str, limit: int | None) -> str:
    if not limit:
        return text
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:limit]) + ("\n" if lines[:limit] else "")


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def bead_draft(row: Dict[str, Any]) -> str:
    title = f"Lesson: {row.get('summary', 'Untitled lesson')}"
    body = "\n".join(
        [
            "### Context",
            f"Lesson `{row.get('uuid')}` captured from `{row.get('hostname')}` in project `{row.get('project')}` (`{row.get('project_dir')}`).",
            "",
            "### Problem",
            str(row.get("summary") or ""),
            "",
            "### Suggested Improvement",
            f"Review the `{row.get('area') or 'unknown'}` area and decide whether this lesson should become a Pi config/tooling change.",
            "",
            "### Evidence",
            str(row.get("evidence") or "No additional evidence provided."),
        ]
    )
    return f"# {title}\n\n{body}\n\nbd create --title={shell_quote(title)} --type=task --priority=2 --description={shell_quote(body)}\n"


def cmd_lessons(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt lessons", description="Capture, sync, and triage lessons learned as JSONL.")
    sub = parser.add_subparsers(dest="command")

    capture_cmd = sub.add_parser("capture", help="append one lesson to the local inbox")
    capture_cmd.add_argument("--summary", required=True)
    capture_cmd.add_argument("--kind", default="other")
    capture_cmd.add_argument("--area", default="unknown")
    capture_cmd.add_argument("--evidence")
    capture_cmd.add_argument("--tag", action="append", default=[])
    capture_cmd.add_argument("--payload-json")
    capture_cmd.add_argument("--out", "--file", dest="out")

    inbox_cmd = sub.add_parser("inbox", help="print local inbox JSONL")
    inbox_cmd.add_argument("--file")
    inbox_cmd.add_argument("--json", action="store_true")

    push_cmd = sub.add_parser("push", help="post local inbox JSONL to the lesson server")
    push_cmd.add_argument("--url")
    push_cmd.add_argument("--file")
    push_cmd.add_argument("--archive-dir")
    push_cmd.add_argument("--dry-run", action="store_true")

    pull_cmd = sub.add_parser("pull", help="fetch remote lessons as JSONL")
    pull_cmd.add_argument("--url")
    pull_cmd.add_argument("--status")
    pull_cmd.add_argument("--since")
    pull_cmd.add_argument("--project")
    pull_cmd.add_argument("--hostname")
    pull_cmd.add_argument("--limit", type=int)
    pull_cmd.add_argument("-o", "--output")

    triage_cmd = sub.add_parser("triage", help="draft or create Beads follow-ups from lessons")
    triage_cmd.add_argument("--file")
    triage_cmd.add_argument("--status", default="new")
    triage_cmd.add_argument("--draft-beads", action="store_true")
    triage_cmd.add_argument("--create-beads", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "capture":
        row = lesson_record(
            summary=args.summary,
            kind=args.kind,
            area=args.area,
            evidence=args.evidence,
            tags=args.tag,
            payload=parse_payload(args.payload_json),
        )
        out = Path(args.out).expanduser() if args.out else default_inbox()
        write_jsonl(out, [row], append=True)
        print(str(out))
        return 0

    if args.command == "inbox":
        path = Path(args.file).expanduser() if args.file else default_inbox()
        rows = read_jsonl(path)
        if args.json:
            print(json.dumps({"schemaVersion": 1, "path": str(path), "count": len(rows), "lessons": rows}, indent=2, sort_keys=True))
        else:
            print(rows_to_jsonl(rows), end="")
        return 0

    if args.command == "push":
        path = Path(args.file).expanduser() if args.file else default_inbox()
        rows = read_jsonl(path)
        if not rows:
            print(f"No lessons to push in {path}")
            return 0
        if args.dry_run:
            print(rows_to_jsonl(rows), end="")
            return 0
        try:
            result = post_lessons(args.url, rows)
        except Exception as exc:
            print(f"agnt lessons push failed; preserved inbox {path}: {exc}", file=sys.stderr)
            return 1
        archive = archive_rows(rows, Path(args.archive_dir).expanduser() if args.archive_dir else default_archive_dir())
        path.write_text("", encoding="utf-8")
        print(json.dumps({"pushed": len(rows), "archive": str(archive), "server": result}, indent=2, sort_keys=True))
        return 0

    if args.command == "pull":
        try:
            text = pull_lessons(args.url, {"status": args.status, "since": args.since, "project": args.project, "hostname": args.hostname})
        except Exception as exc:
            print(f"agnt lessons pull failed: {exc}", file=sys.stderr)
            return 1
        text = limit_jsonl(text, args.limit)
        if args.output:
            path = Path(args.output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    if args.command == "triage":
        path = Path(args.file).expanduser() if args.file else default_inbox()
        rows = [row for row in read_jsonl(path) if not args.status or row.get("status") == args.status]
        if args.draft_beads or not args.create_beads:
            for row in rows:
                print(bead_draft(row))
            return 0
        if args.create_beads:
            status = 0
            for row in rows:
                title = f"Lesson: {row.get('summary', 'Untitled lesson')}"
                body = bead_draft(row).split("\nbd create", 1)[0].strip()
                proc = subprocess.run(["bd", "create", "--title", title, "--type", "task", "--priority", "2", "--description", body], text=True)
                if proc.returncode != 0:
                    status = proc.returncode
            return status

    parser.print_help(sys.stderr)
    return 2
