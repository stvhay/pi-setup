from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "pi" / "agent" / "extensions" / "langfuse-config-env.ts"
SETTINGS = ROOT / "pi" / "agent" / "settings.json"
SKILL_SOURCE = "git:github.com/langfuse/skills@13a79944c3c16cde049bb39576102cd768baa06b"


def test_langfuse_skill_is_pinned_and_reuses_extension_config(tmp_path):
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert SKILL_SOURCE in settings["packages"]

    config = tmp_path / ".pi" / "agent" / "pi-langfuse" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "publicKey": "pk-test",
                "secretKey": "sk-test",
                "host": "https://langfuse.example.com",
                "privacyPreset": "conversations",
            }
        ),
        encoding="utf-8",
    )

    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      delete process.env.LANGFUSE_PUBLIC_KEY;
      process.env.LANGFUSE_SECRET_KEY = "explicit-secret";
      delete process.env.LANGFUSE_BASE_URL;
      install();

      assert.equal(process.env.LANGFUSE_PUBLIC_KEY, "pk-test");
      assert.equal(process.env.LANGFUSE_SECRET_KEY, "explicit-secret");
      assert.equal(process.env.LANGFUSE_BASE_URL, "https://langfuse.example.com");
    """
    node = shutil.which("node")
    assert node
    subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )
