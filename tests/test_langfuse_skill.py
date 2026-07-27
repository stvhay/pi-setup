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


def run_extension_script(script: str, *, home: Path | None = None):
    node = shutil.which("node")
    assert node
    subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **({"HOME": str(home)} if home else {})},
    )


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
    run_extension_script(script, home=tmp_path)


def test_subscription_models_are_aliased_with_zero_cost():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      let handler;
      install({{ on: (event, callback) => {{ if (event === "message_end") handler = callback; }} }});
      const message = {{
        role: "assistant",
        provider: "openai-codex",
        model: "gpt-5.6-sol",
        usage: {{
          input: 12,
          output: 3,
          cacheRead: 5,
          cost: {{ input: 1, output: 2, cacheRead: 3, cacheWrite: 4, total: 10 }},
        }},
      }};
      const result = await handler({{ message }});

      assert.equal(result.message.model, "gpt-5.6-sol-subscription");
      assert.deepEqual(result.message.usage.cost, {{
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        total: 0,
      }});
      assert.equal(result.message.usage.input, 12);
      assert.equal(result.message.usage.output, 3);
      assert.equal(result.message.usage.cacheRead, 5);
    """
    run_extension_script(script)


def test_metered_models_are_not_changed():
    script = f"""
      import assert from "node:assert/strict";
      import install from {EXTENSION.as_uri()!r};

      let handler;
      install({{ on: (event, callback) => {{ if (event === "message_end") handler = callback; }} }});
      const message = {{
        role: "assistant",
        provider: "openrouter-localish",
        model: "gpt-5.6-sol",
        usage: {{ cost: {{ total: 10 }} }},
      }};

      assert.equal(await handler({{ message }}), undefined);
      assert.equal(message.model, "gpt-5.6-sol");
      assert.equal(message.usage.cost.total, 10);
    """
    run_extension_script(script)
