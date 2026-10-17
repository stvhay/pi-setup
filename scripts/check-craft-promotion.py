#!/usr/bin/env python3
"""Verify the four promoted Craft files against their recorded source manifest."""
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

FILES = {
    "scripts/start-craft-mcp.sh": ("agent/bin/start-craft-mcp.sh", "0755"),
    "integration/crafting-apps/SKILL.md": ("agent/skills/crafting-apps/SKILL.md", "0644"),
    "integration/crafting-apps/vectorcraft.md": ("agent/skills/crafting-apps/vectorcraft.md", "0644"),
    "integration/craft-mcp.json": ("agent/craft/mcp.json", "0644"),
}


def checked(root, relative):
    path = root
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink():
            raise ValueError("symlink in promoted Craft path")
    if not path.is_file():
        raise ValueError("promoted Craft file missing")
    return path


def verify(root):
    manifest = json.loads(checked(root, "agent/craft/source.json").read_bytes())
    if (manifest.get("repository") != "artcraft-setup"
            or not isinstance(manifest.get("commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", manifest["commit"])
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != set(FILES)):
        raise ValueError("invalid Craft provenance")
    for source, (target, mode) in FILES.items():
        record = manifest["files"][source]
        if record.get("target") != target or record.get("mode") != mode:
            raise ValueError("Craft promotion mapping changed")
        path = checked(root, target)
        if (hashlib.sha256(path.read_bytes()).hexdigest() != record.get("sha256")
                or stat.S_IMODE(path.stat().st_mode) != int(mode, 8)):
            raise ValueError("Craft promotion bytes/mode drift")
    print("PASS: Craft promotion hashes and modes match " + manifest["commit"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check-craft-promotion.py PI_CONFIG_ROOT")
    try:
        verify(Path(sys.argv[1]))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise SystemExit("FAIL: Craft promotion invalid or changed") from error
