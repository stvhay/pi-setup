#!/usr/bin/env python3
"""Private, scoped PhotoCraft config reconciliation; never starts a server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


TEMPLATE = {"mcpServers": {"photocraft-pilot": {
    "command": "agent/bin/start-craft-mcp.sh", "args": ["photocraft"],
    "enabled": False, "cwd": ".", "timeout": 30, "exposure": "codemode",
}}}


def checked(root, relative):
    path = root
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink():
            raise ValueError("Craft MCP refuses symlink components")
        if path.exists() and not (path.is_file() if path == root / relative else path.is_dir()):
            raise ValueError("Craft MCP requires regular files and real directories")
    return path


def unique_object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("Craft MCP refuses duplicate JSON keys")
        data[key] = value
    return data


def load(data):
    def invalid_constant(_):
        raise ValueError("Craft MCP requires finite JSON values")
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def snapshot(path):
    if not path.exists():
        return None, None
    info = path.stat()
    return path.read_bytes(), (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_mode)


def reconcile(source, destination, apply=False):
    template = checked(source, "agent/craft/mcp.json")
    if not template.exists():
        return
    template_bytes = template.read_bytes()
    if load(template_bytes) != TEMPLATE:
        raise ValueError("Craft MCP template differs from supported disabled PhotoCraft contract")
    launcher = checked(source, "agent/bin/start-craft-mcp.sh")
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError("Craft MCP source launcher missing or not executable")
    target = checked(destination, "agent/mcp.json")
    old, identity = snapshot(target)
    data = load(old) if old is not None else {}
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise ValueError("Craft MCP requires JSON objects for config and mcpServers")
    servers = data.setdefault("mcpServers", {})
    if "photocraft_pilot" in servers:
        raise ValueError("Craft MCP normalized server name collision")
    command = str(destination / "agent/bin/start-craft-mcp.sh")
    if "photocraft-pilot" in servers:
        entry = servers["photocraft-pilot"]
        previous = str(Path.home() / ".artcraft/start-craft-mcp.sh")
        if (not isinstance(entry, dict)
                or entry.get("command") not in (previous, command)
                or entry.get("args") != ["photocraft"]
                or "url" in entry or entry.get("type", "stdio") != "stdio"
                or ("enabled" in entry and not isinstance(entry["enabled"], bool))):
            raise ValueError("Craft MCP PhotoCraft entry is not a recognized launcher configuration")
        entry["command"] = command
    else:
        servers["photocraft-pilot"] = {**TEMPLATE["mcpServers"]["photocraft-pilot"], "command": command}
    if old is not None and data == load(old):
        print("Craft MCP already matches; no writes.")
        return
    new = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    mode = stat.S_IMODE(identity[3]) if identity else 0o600
    digest = lambda value: hashlib.sha256(value).hexdigest() if value is not None else None
    receipt = {"destination": str(target), "beforeSha256": digest(old), "afterSha256": digest(new),
               "beforeMode": f"{mode:04o}" if identity else None, "afterMode": f"{mode:04o}",
               "verified": False}
    print("Craft MCP: " + json.dumps(receipt))
    if not apply:
        print("Preview: PhotoCraft command/args only (or new disabled entry); unrelated MCP state preserved.")
        return
    # shortcut: static path checks, use OS isolation for concurrent hostile writers.
    checked(destination, "runtime/deployment-backups/placeholder")
    backup_root = destination / "runtime/deployment-backups"
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="craft-", dir=backup_root))
    if old is not None:
        with (backup / "before.json").open("xb") as output:
            os.chmod(output.name, 0o600)
            output.write(old)
            output.flush()
            os.fsync(output.fileno())
    receipt_path = backup / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Craft MCP recovery: {backup}", flush=True)
    temporary = None
    try:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".craft-mcp-", delete=False) as output:
            temporary = Path(output.name)
            output.write(new)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(mode)
        if (checked(source, "agent/craft/mcp.json").read_bytes() != template_bytes
                or snapshot(checked(destination, "agent/mcp.json")) != (old, identity)):
            raise ValueError("Craft MCP source or destination drift; stopped before replacement")
        os.replace(temporary, target)
        if snapshot(checked(destination, "agent/mcp.json"))[0] != new or stat.S_IMODE(target.stat().st_mode) != mode:
            raise ValueError("Craft MCP verification failed; recovery retained")
        receipt["verified"] = True
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        reconcile(args.source.resolve(), args.destination.resolve(), args.apply)
    except (OSError, ValueError) as error:
        # JSON errors can embed private keys/values; do not echo config or exception text.
        message = str(error) if type(error) is ValueError and str(error).startswith("Craft MCP") else "Craft MCP invalid JSON or filesystem failure"
        raise SystemExit(message) from None
