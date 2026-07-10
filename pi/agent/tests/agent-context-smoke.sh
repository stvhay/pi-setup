#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

python3 -m py_compile bin/agent-instructions bin/agnt

bin/agnt -h >/tmp/agnt-help.txt
rg -n "Usage: agnt|tasks|invoke|soul" /tmp/agnt-help.txt >/dev/null

bin/agnt tasks >/tmp/agnt-tasks.txt
rg -n "orchestration|review|research" /tmp/agnt-tasks.txt >/dev/null

bin/agnt tasks --models >/tmp/agnt-task-models.txt
rg -n "openai-codex/gpt-5\.6-sol|openrouter-localish/google/gemma-4-31b-it|olla-cloud/gemini-flash" /tmp/agnt-task-models.txt >/dev/null

bin/agnt invoke -h >/tmp/agnt-invoke-help.txt
rg -n -- "--fanout|--list|--task|--no-metrics|--metrics-dir" /tmp/agnt-invoke-help.txt >/dev/null
bin/agnt metrics -h >/tmp/agnt-metrics-help.txt
rg -n "status|consolidate|reset|prune|import-session" /tmp/agnt-metrics-help.txt >/dev/null
bin/agnt metrics import-session -h >/tmp/agnt-import-session-help.txt
rg -n -- "--latest|--session-file|--kind" /tmp/agnt-import-session-help.txt >/dev/null
bin/agnt benchmark -h >/tmp/agnt-benchmark-help.txt
rg -n "pong" /tmp/agnt-benchmark-help.txt >/dev/null

FAKE_PI_DIR=$(mktemp -d)
METRICS_TMP=$(mktemp -d)
CONSUMED_TMP=$(mktemp -d)
AGG_TMP=$(mktemp -d)/agent-invocations.jsonl
cat > "$FAKE_PI_DIR/pi" <<'SH'
#!/usr/bin/env bash
if [[ "$*" == *"--mode json"* ]]; then
  printf '%s\n' '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"fake response"}],"usage":{"input":10,"output":5,"cacheRead":1,"cacheWrite":2,"totalTokens":18,"cost":{"input":0.01,"output":0.02,"cacheRead":0,"cacheWrite":0,"total":0.03}}}}'
else
  printf 'fake response'
fi
SH
chmod +x "$FAKE_PI_DIR/pi"
PATH="$FAKE_PI_DIR:$PATH" bin/agnt invoke --metrics-dir "$METRICS_TMP" fake-provider/fake-model 'hello' >/tmp/agnt-metrics-stdout.txt
rg -n 'fake response' /tmp/agnt-metrics-stdout.txt >/dev/null
PATH="$FAKE_PI_DIR:$PATH" bin/agnt invoke --no-metrics --metrics-dir "$METRICS_TMP" fake-provider/fake-model 'hello' >/tmp/agnt-no-metrics-stdout.txt
rg -n 'fake response' /tmp/agnt-no-metrics-stdout.txt >/dev/null
python3 - <<PY
import json, pathlib
files = list(pathlib.Path('$METRICS_TMP').glob('*.metrics.json'))
assert len(files) == 1, files
data = json.loads(files[0].read_text())
assert data['provider'] == 'fake-provider'
assert data['model'] == 'fake-model'
assert data['usageSource'] == 'message_end'
assert data['usage']['totalTokens'] == 18
assert data['usage']['cost']['total'] == 0.03
PY
ASSUMED_COST_TMP=$(mktemp -d)
cat > "$FAKE_PI_DIR/pi" <<'SH'
#!/usr/bin/env bash
printf '%s\n' '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"fake response"}],"usage":{"input":10,"output":5,"cacheRead":100,"cacheWrite":0,"totalTokens":115,"cost":{"input":0,"output":0,"cacheRead":0,"cacheWrite":0,"total":0}}}}'
SH
chmod +x "$FAKE_PI_DIR/pi"
PATH="$FAKE_PI_DIR:$PATH" bin/agnt invoke --metrics-dir "$ASSUMED_COST_TMP" olla-cloud/gpt-4.1-mini 'hello' >/tmp/agnt-assumed-cost-stdout.txt
python3 - <<PY
import json, pathlib
files = list(pathlib.Path('$ASSUMED_COST_TMP').glob('*.metrics.json'))
assert len(files) == 1, files
data = json.loads(files[0].read_text())
assert data['usage']['costSource'] == 'openrouter-assumed'
assert data['usage']['costEstimated'] is True
assert abs(data['usage']['cost']['total'] - 0.000012) < 0.0000001, data['usage']['cost']
PY
rm -rf "$ASSUMED_COST_TMP"
LOCAL_COST_TMP=$(mktemp -d)
PATH="$FAKE_PI_DIR:$PATH" AGNT_LOCAL_GPU_WATTS=285 AGNT_ELECTRICITY_USD_PER_KWH=0.1304 bin/agnt invoke --metrics-dir "$LOCAL_COST_TMP" ollama/gemma4:31b 'hello' >/tmp/agnt-local-cost-stdout.txt
python3 - <<PY
import json, pathlib
files = list(pathlib.Path('$LOCAL_COST_TMP').glob('*.metrics.json'))
assert len(files) == 1, files
data = json.loads(files[0].read_text())
usage = data['usage']
assert usage['costSource'] == 'local-free'
assert usage['cost']['total'] == 0
assert usage['opportunityCost']['source'] == 'openrouter-proxy'
assert usage['localCompute']['electricityUsdPerKwh'] == 0.1304
assert usage['localCompute']['gpuWatts'] == 285
assert usage['localCompute']['gpuWattsSource'] == 'env:AGNT_LOCAL_GPU_WATTS'
assert usage['localCompute']['estimatedEnergyCostUsd'] >= 0
PY
rm -rf "$LOCAL_COST_TMP"
bin/agnt metrics status --metrics-dir "$METRICS_TMP" >/tmp/agnt-metrics-status.txt
rg -n '"pendingFiles": 1|"totalTokens": 18' /tmp/agnt-metrics-status.txt >/dev/null
bin/agnt metrics consolidate --metrics-dir "$METRICS_TMP" --consumed-dir "$CONSUMED_TMP" --output "$AGG_TMP" >/tmp/agnt-metrics-consolidate.txt
test -s "$AGG_TMP"
test "$(find "$METRICS_TMP" -name '*.metrics.json' | wc -l | tr -d ' ')" = 0
python3 - <<PY
import json, pathlib
line = pathlib.Path('$AGG_TMP').read_text().splitlines()[0]
data = json.loads(line)
assert data['summary']['invocations'] == 1
assert data['summary']['usage']['totalTokens'] == 18
assert data['records'][0]['target'] == 'fake-provider/fake-model'
PY
rm -rf "$FAKE_PI_DIR" "$METRICS_TMP" "$CONSUMED_TMP" "$(dirname "$AGG_TMP")"

bin/agnt instructions AGENTS.md --check >/tmp/agnt-instructions-check.txt
rg -n "PASS" /tmp/agnt-instructions-check.txt >/dev/null

bin/agnt soul --check >/tmp/agnt-soul-check.txt
rg -n "PASS" /tmp/agnt-soul-check.txt >/dev/null

bin/agnt soul >/tmp/agnt-soul.txt
rg -n "collaborative partner|Safety boundary" /tmp/agnt-soul.txt >/dev/null

SOUL_TMP=$(mktemp -d)
mkdir -p "$SOUL_TMP/SOUL.d"
printf '# Soul root\n\nSafety boundary. Be a collaborative partner.\n' > "$SOUL_TMP/SOUL.md"
printf '# Soul supplement\n' > "$SOUL_TMP/SOUL.d/local.md"
bin/agnt soul "$SOUL_TMP/SOUL.md" | rg -n "Soul root|Soul supplement" >/dev/null

TMP=$(mktemp -d)
trap 'rm -rf "$TMP" "$SOUL_TMP"' EXIT
mkdir -p "$TMP/AGENTS.d/models/openrouter-localish/google"
printf '# Root\n' > "$TMP/AGENTS.md"
printf '# Provider context\n' > "$TMP/AGENTS.d/models/openrouter-localish.md"
printf '# Nested model context\n' > "$TMP/AGENTS.d/models/openrouter-localish/google/gemma-4-31b-it.md"
bin/agent-instructions "$TMP/AGENTS.md" --context openrouter-localish/google/gemma-4-31b-it > /tmp/agnt-nested-context.txt
rg -n "Provider context|Nested model context" /tmp/agnt-nested-context.txt >/dev/null
