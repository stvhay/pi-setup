from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from .core import ROOT

PASS = "pass"
WARNING = "warning"
FAIL = "fail"
SKIP = "skip"

DEFAULT_CHECKS = [
    "command.pi",
    "command.bd",
    "python.version",
    "git.root",
    "node.version",
    "provider.env",
    "catalog.parse",
    "verification.commands",
]

PROVIDER_ENV_VARS = {
    "openrouter": ["OPENROUTER_API_KEY"],
    "openrouter-localish": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "olla-cloud": ["OLLA_HOST"],
}

DEFAULT_NODE_LTS_MAJORS = {20, 22, 24}


def check_result(
    check_id: str,
    status: str,
    message: str,
    *,
    severity: str = "low",
    evidence: Dict[str, Any] | None = None,
    suggested_actions: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
        "evidence": evidence or {},
        "suggestedActions": suggested_actions or [],
    }


def run_quiet(argv: List[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def check_command(name: str, *, required: bool = True) -> Dict[str, Any]:
    path = shutil.which(name)
    check_id = f"command.{name}"
    if not path:
        return check_result(
            check_id,
            FAIL if required else WARNING,
            f"{name} executable not found on PATH",
            severity="high" if required else "medium",
            suggested_actions=[f"Install {name} or update PATH before running dependent agent workflows."],
        )
    return check_result(check_id, PASS, f"{name} executable found", evidence={"path": path})


def check_beads() -> Dict[str, Any]:
    exe = shutil.which("bd") or shutil.which("beads")
    if not exe:
        return check_result(
            "command.bd",
            WARNING,
            "bd/beads executable not found on PATH",
            severity="medium",
            suggested_actions=["Install Beads or ensure bd/beads is on PATH before using Beads-backed workflows."],
        )
    evidence: Dict[str, Any] = {"path": exe}
    if Path.cwd().joinpath(".beads").exists():
        try:
            proc = run_quiet([exe, "doctor"], timeout=10)
            evidence.update({"doctorExit": proc.returncode})
            if proc.returncode != 0:
                return check_result(
                    "command.bd",
                    WARNING,
                    "bd doctor reported issues",
                    severity="medium",
                    evidence=evidence,
                    suggested_actions=["Run `bd doctor` and address the reported Beads workspace issues."],
                )
        except Exception as exc:  # pragma: no cover - defensive around external tool behavior
            evidence["doctorError"] = str(exc)
            return check_result("command.bd", WARNING, "bd doctor could not run", severity="medium", evidence=evidence)
    return check_result("command.bd", PASS, "bd/beads executable found", evidence=evidence)


def check_python_version() -> Dict[str, Any]:
    version = platform.python_version()
    ok = sys.version_info >= (3, 11)
    return check_result(
        "python.version",
        PASS if ok else FAIL,
        "Python version is supported" if ok else "Python version is too old",
        severity="high" if not ok else "low",
        evidence={"version": version, "executable": sys.executable},
        suggested_actions=[] if ok else ["Use Python 3.11 or newer for agnt tooling."],
    )


def check_git_root() -> Dict[str, Any]:
    try:
        proc = run_quiet(["git", "rev-parse", "--show-toplevel"])
    except FileNotFoundError:
        return check_result("git.root", FAIL, "git executable not found", severity="high")
    if proc.returncode != 0:
        return check_result(
            "git.root",
            FAIL,
            "Current directory is not inside a git repository",
            severity="high",
            evidence={"stderr": proc.stderr.strip()[-500:]},
        )
    return check_result("git.root", PASS, "Git root resolved", evidence={"root": proc.stdout.strip()})


def lts_majors() -> set[int]:
    raw = os.environ.get("AGNT_NODE_LTS_MAJORS")
    if not raw:
        return set(DEFAULT_NODE_LTS_MAJORS)
    majors: set[int] = set()
    for chunk in re.split(r"[,\s]+", raw):
        if chunk.strip().isdigit():
            majors.add(int(chunk))
    return majors or set(DEFAULT_NODE_LTS_MAJORS)


def parse_node_major(version: str) -> int | None:
    match = re.search(r"v?(\d+)", version)
    return int(match.group(1)) if match else None


def detect_home_manager(home: Path) -> tuple[str | None, List[str]]:
    actions: List[str] = []
    if os.environ.get("IN_NIX_SHELL") or os.environ.get("NIX_PROFILES"):
        actions.append("Prefer the project Nix/direnv environment for Node instead of mutating shell startup files.")
        return "nix", actions
    if (home / ".config" / "home-manager").exists() or (home / ".nix-profile").exists():
        actions.append("Home Manager/Nix markers detected; update the managed home configuration rather than appending to shell rc files.")
        return "home-manager", actions
    if (home / ".local" / "share" / "chezmoi").exists() or shutil.which("chezmoi"):
        actions.append("chezmoi detected; update the managed dotfile source instead of editing generated shell rc files directly.")
        return "chezmoi", actions
    if (home / ".yadm").exists() or shutil.which("yadm"):
        actions.append("yadm detected; update the managed dotfile source instead of editing generated shell rc files directly.")
        return "yadm", actions
    return None, actions


def detect_node_manager(home: Path) -> str | None:
    if os.environ.get("IN_NIX_SHELL") or os.environ.get("NIX_PROFILES"):
        return "nix"
    if (home / ".nvm").exists() or os.environ.get("NVM_DIR") or shutil.which("nvm"):
        return "nvm"
    if shutil.which("fnm"):
        return "fnm"
    if shutil.which("asdf") or (home / ".asdf").exists():
        return "asdf"
    node_path = shutil.which("node") or ""
    if "homebrew" in node_path or "opt/homebrew" in node_path:
        return "homebrew"
    return None


def node_suggestions(manager: str | None, home: Path) -> List[str]:
    actions: List[str] = []
    home_manager, home_actions = detect_home_manager(home)
    actions.extend(home_actions)
    if manager == "nvm":
        actions.extend(["nvm install --lts", "nvm alias default 'lts/*'"])
        profile_d = home / ".local" / "etc" / "profile.d"
        if profile_d.exists() and home_manager is None:
            actions.append(f"If shell init is needed, add a marked nvm loader snippet at {profile_d / 'pi-node-lts.sh'} rather than appending ad hoc rc-file lines.")
    elif manager == "fnm":
        actions.append("fnm install --lts && fnm default lts-latest")
    elif manager == "asdf":
        actions.append("asdf plugin add nodejs || true; asdf install nodejs lts; asdf global nodejs lts")
    elif manager == "nix":
        actions.append("Add an LTS nodejs package to the project Nix/direnv environment.")
    elif manager == "homebrew":
        actions.append("Install or link a Homebrew Node LTS version, or prefer nvm/fnm for per-user LTS selection.")
    else:
        actions.append("Install active Node LTS or use nvm/fnm/asdf to select an LTS version.")
    return actions


def check_node_version() -> Dict[str, Any]:
    path = shutil.which("node")
    home = Path(os.environ.get("HOME") or str(Path.home())).expanduser()
    manager = detect_node_manager(home)
    if not path:
        return check_result(
            "node.version",
            WARNING,
            "node executable not found on PATH",
            severity="medium",
            evidence={"manager": manager},
            suggested_actions=node_suggestions(manager, home),
        )
    try:
        proc = run_quiet(["node", "--version"])
    except Exception as exc:
        return check_result("node.version", WARNING, "node --version failed", severity="medium", evidence={"path": path, "error": str(exc), "manager": manager})
    version = proc.stdout.strip()
    major = parse_node_major(version)
    evidence = {"path": path, "version": version, "major": major, "manager": manager, "ltsMajors": sorted(lts_majors())}
    if proc.returncode != 0 or major is None:
        return check_result("node.version", WARNING, "Could not determine node version", severity="medium", evidence=evidence)
    if major not in lts_majors():
        return check_result(
            "node.version",
            WARNING,
            "Node is not an active LTS major according to agnt policy",
            severity="medium",
            evidence=evidence,
            suggested_actions=node_suggestions(manager, home),
        )
    return check_result("node.version", PASS, "Node major is accepted by agnt LTS policy", evidence=evidence)


def redact_env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return "present:redacted"
    return "missing"


def configured_providers() -> set[str]:
    providers: set[str] = set(PROVIDER_ENV_VARS)
    for path in [ROOT / "settings.json", ROOT / "models.json"]:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        text = json.dumps(data)
        for provider in PROVIDER_ENV_VARS:
            if provider in text:
                providers.add(provider)
    return providers


def check_provider_env() -> Dict[str, Any]:
    evidence: Dict[str, str] = {}
    missing: List[str] = []
    for provider in sorted(configured_providers()):
        for name in PROVIDER_ENV_VARS.get(provider, []):
            evidence[name] = redact_env_value(name)
    for name, state in evidence.items():
        if state == "missing":
            missing.append(name)
    if missing:
        return check_result(
            "provider.env",
            WARNING,
            "Some provider environment variables are not set",
            severity="medium",
            evidence=evidence,
            suggested_actions=[f"Set {name} in your shell or ignored local env before using dependent providers." for name in sorted(set(missing))],
        )
    return check_result("provider.env", PASS, "Known provider environment variables are present", evidence=evidence)


def check_catalog_parse() -> Dict[str, Any]:
    parsed: List[str] = []
    for path in [ROOT / "catalog.json", ROOT / "models.json", ROOT / "settings.json"]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parsed.append(str(path.relative_to(ROOT)))
        except Exception as exc:
            return check_result("catalog.parse", FAIL, f"Could not parse {path.name}", severity="high", evidence={"path": str(path), "error": str(exc)})
    return check_result("catalog.parse", PASS, "Core agnt JSON config parsed", evidence={"parsed": parsed})


def check_verification_commands() -> Dict[str, Any]:
    repo = ROOT.parent.parent
    evidence: Dict[str, Any] = {
        "bash": shutil.which("bash") or "missing",
        "python": sys.executable,
        "pytest": shutil.which("pytest") or shutil.which("py.test") or "missing",
        "checkPiConfig": str(repo / "scripts" / "check-pi-config.sh"),
    }
    missing: List[str] = []
    if evidence["bash"] == "missing":
        missing.append("bash")
    if evidence["pytest"] == "missing" and not (repo / ".venv" / "bin" / "python").exists():
        missing.append("pytest/.venv")
    if not (repo / "scripts" / "check-pi-config.sh").is_file():
        missing.append("scripts/check-pi-config.sh")
    if missing:
        return check_result(
            "verification.commands",
            WARNING,
            "Some documented verification command prerequisites are missing",
            severity="medium",
            evidence=evidence,
            suggested_actions=[f"Install or restore {item} before claiming repository verification is available." for item in missing],
        )
    return check_result("verification.commands", PASS, "Documented verification command prerequisites are present", evidence=evidence)


CHECKS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "command.pi": lambda: check_command("pi", required=True),
    "command.bd": check_beads,
    "python.version": check_python_version,
    "git.root": check_git_root,
    "node.version": check_node_version,
    "provider.env": check_provider_env,
    "catalog.parse": check_catalog_parse,
    "verification.commands": check_verification_commands,
}


def selected_checks(check_names: Iterable[str] | None = None, skip: Iterable[str] | None = None) -> List[str]:
    names = list(check_names or DEFAULT_CHECKS)
    skipped = set(skip or [])
    unknown = [name for name in names if name not in CHECKS]
    if unknown:
        names.extend([])  # keep function side-effect free for caller error handling
    return [name for name in names if name in CHECKS and name not in skipped]


def doctor_report(check_names: Iterable[str] | None = None, skip: Iterable[str] | None = None) -> Dict[str, Any]:
    checks = [CHECKS[name]() for name in selected_checks(check_names, skip)]
    failures = [check for check in checks if check["status"] == FAIL]
    warnings = [check for check in checks if check["status"] == WARNING]
    status = "failed" if failures else ("degraded" if warnings else "passed")
    suggested: List[str] = []
    for check in checks:
        suggested.extend(check.get("suggestedActions") or [])
    return {
        "schemaVersion": 1,
        "status": status,
        "passed": not failures,
        "summary": {"checkCount": len(checks), "failureCount": len(failures), "warningCount": len(warnings)},
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "suggestedActions": suggested,
    }


def cmd_doctor(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="agnt doctor", description="Check local Pi/agnt operational readiness.")
    parser.add_argument("topic", nargs="?", choices=["node"], help="run a focused doctor topic")
    parser.add_argument("--json", action="store_true", help="emit JSON (default for now)")
    parser.add_argument("--strict", action="store_true", help="exit nonzero when required checks fail")
    parser.add_argument("--check", action="append", default=[], help="run a specific check id; may be repeated")
    parser.add_argument("--skip", action="append", default=[], help="skip a check id; may be repeated")
    args = parser.parse_args(argv)
    checks = args.check or (["node.version"] if args.topic == "node" else None)
    unknown = [name for name in checks or [] if name not in CHECKS]
    if unknown:
        print(f"agnt doctor: unknown check(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    report = doctor_report(check_names=checks, skip=args.skip)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["failures"] else 0
