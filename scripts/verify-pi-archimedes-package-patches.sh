#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FORK="$ROOT/forks/pi-archimedes"
VITEST="$FORK/node_modules/.bin/vitest"
TSC="$FORK/node_modules/.bin/tsc"
BASE_HEAD="a44f94267239db0ef5d36d18d93391bf9d51c182"
FORK_HEAD="59c57a18976f0d470bae8ae6d5704c6715f06ee6"
FORK_BRANCH="vendor/pi-setup-2111"
FORK_URL="https://github.com/stvhay/pi-archimedes.git"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

LOCAL_CANDIDATE=0
if [ "${1:-}" = --local-candidate ] && [ "$#" -eq 1 ]; then
  LOCAL_CANDIDATE=1
elif [ "$#" -ne 0 ]; then
  fail "usage: $0 [--local-candidate]"
fi
# Local proof never establishes publication. Default mode and check-vendor-pins.sh
# retain the remote gate; root gitlinks must not be committed while unpublished.

[ -x "$VITEST" ] || fail "missing fork test runtime; run corepack pnpm install --frozen-lockfile in forks/pi-archimedes"
[ -x "$TSC" ] || fail "missing fork TypeScript runtime; run corepack pnpm install --frozen-lockfile in forks/pi-archimedes"

read -r mode gitlink stage _ < <(git -C "$ROOT" ls-files --stage -- forks/pi-archimedes)
[ "$mode" = "160000" ] && [ "$stage" = "0" ] && [ "$gitlink" = "$FORK_HEAD" ] \
  || fail "forks/pi-archimedes gitlink does not match $FORK_HEAD"
[ "$(git -C "$FORK" rev-parse HEAD)" = "$FORK_HEAD" ] \
  || fail "forks/pi-archimedes checkout does not match $FORK_HEAD"
[ "$(git -C "$FORK" rev-parse 'v2.11.1^{}')" = "$BASE_HEAD" ] \
  || fail "v2.11.1 does not match npm base $BASE_HEAD"
[ "$(git config --file "$ROOT/.gitmodules" --get submodule.forks/pi-archimedes.url)" = "$FORK_URL" ] \
  || fail "unexpected pi-archimedes submodule URL"
[ "$(git config --file "$ROOT/.gitmodules" --get submodule.forks/pi-archimedes.branch)" = "$FORK_BRANCH" ] \
  || fail "unexpected pi-archimedes submodule branch"

verify_parent() {
  local head=$1 parent=$2
  [ "$(git -C "$FORK" show -s --format=%P "$head")" = "$parent" ] \
    || fail "$head is not exactly one commit on $parent"
}
verify_parent "$FORK_HEAD" "$BASE_HEAD"
git -C "$FORK" diff --quiet HEAD -- meta packages || fail "fork production/tests are dirty"
[ -z "$(git -C "$FORK" ls-files --others --exclude-standard -- meta packages)" ] || fail "fork has untracked production/tests"
if [ "$LOCAL_CANDIDATE" -eq 0 ]; then
  remote_head=$(git ls-remote --heads "$FORK_URL" "refs/heads/$FORK_BRANCH" | awk 'NR == 1 {print $1}')
  [ "$remote_head" = "$FORK_HEAD" ] \
    || fail "$FORK_BRANCH resolves to ${remote_head:-<missing>}, expected $FORK_HEAD"
else
  echo "LOCAL CANDIDATE ONLY: publication remains unverified; root vendor-pin gate still required."
fi

python3 - "$ROOT/patches/pi-packages" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
expected = {'pi-archimedes-meta-2.11.1.patch': '44c46ab575f598effc2ca6f00d1b56e60106ab1b387e2c6ba9648c9f2ff9280c', 'pi-archimedes-ask-2.11.1.patch': '1e7ab9454a3fabf403654e4c377ec0f0579d14802c155a1da93c49a2b1fe9eb3', 'pi-archimedes-core-2.11.1.patch': 'cf5e116a07abbe388ceb783dcaa5269d19334c828486120b02118b83612357e6', 'pi-archimedes-footer-2.11.1.patch': '4508468a3eb7823c51e849002a4a637e92ef5575b748e0171482c8daccab42eb', 'pi-archimedes-subagent-2.11.1.patch': '9447255b8af98424151fbe1e6e4a3d7684ff9d0e7642bc25e313734b144278c2'}
for name, digest in expected.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"patch integrity mismatch for {name}: expected {digest}, found {actual}")
PY

TMP=$(mktemp -d "${TMPDIR:-/tmp}/pi-archimedes-package-proof.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
BASE="$TMP/base/node_modules"
PROJECTED="$TMP/projected/node_modules"
mkdir -p "$TMP/packs" "$BASE/@pi-archimedes" "$PROJECTED/@pi-archimedes"

pack_exact() {
  local spec=$1 expected_name=$2 expected_version=$3 expected_integrity=$4 metadata
  metadata="$TMP/$(printf '%s' "$expected_name" | tr '/@' '__').json"
  npm pack "$spec" --ignore-scripts --json --pack-destination "$TMP/packs" > "$metadata"
  python3 - "$metadata" "$TMP/packs" "$expected_name" "$expected_version" "$expected_integrity" <<'PY'
import base64
import hashlib
import json
import pathlib
import sys

metadata, packs, expected_name, expected_version, expected_integrity = sys.argv[1:]
entry = json.loads(pathlib.Path(metadata).read_text(encoding="utf-8"))[0]
if (entry.get("name"), entry.get("version"), entry.get("integrity")) != (
    expected_name,
    expected_version,
    expected_integrity,
):
    raise SystemExit(f"unexpected npm metadata: {entry}")
tarball = pathlib.Path(packs, entry["filename"])
actual = "sha512-" + base64.b64encode(hashlib.sha512(tarball.read_bytes()).digest()).decode()
if actual != expected_integrity:
    raise SystemExit(f"integrity mismatch for {tarball}: {actual}")
print(tarball)
PY
}

extract() {
  local tarball=$1 destination=$2
  mkdir -p "$destination"
  tar -xzf "$tarball" -C "$destination" --strip-components=1
}

while IFS='|' read -r package name integrity; do
  tarball=$(pack_exact "$name@2.11.1" "$name" "2.11.1" "$integrity")
  for root in "$BASE" "$PROJECTED"; do
    extract "$tarball" "$root/$name"
  done
done <<'PACKAGES'
meta|pi-archimedes|sha512-mtG8nkfEPDusDJgHuf72bT1CePc4TzPQchT9DCEIpbIiYQRqLE5lYMQPwYn3jq5L7OZUPQS4UzRmeYJoxYl+NQ==
core|@pi-archimedes/core|sha512-zeiBPDLj6cb9VaFye+1YNGVf/GYH61uTp+tHD2Pwl1+IUz7TXlC7EDGpzNT+GqlkPnDr7gQOmS40HyoYzw3T0A==
ui|@pi-archimedes/ui|sha512-0t6lit7JuWYeoT4h/ESGpwxzAIecF+/4pi46Ijvxak536mKRW8HMEq6TEUtZZMUO2qHDIrrI5aMUlnMJRXH+iQ==
sudo|@pi-archimedes/sudo|sha512-XxuABsisHUmZDIQbT/Rvk9R1iyFTHjvRhyAhHXDEzOCOvmKkv9Rgn0lzKyiZbOsx0RekhbDJVf8N/YmYEYYPDQ==
ask|@pi-archimedes/ask|sha512-Su2ck665KjXP0BxI3FmCDFHqF8quj70veXPq4XWOLm4R4YItWpUkhaa72Ff2ZzMpzbiu9X4pyKurf6BFpoGtvQ==
todo|@pi-archimedes/todo|sha512-Tz4ujTgAr5oNnAo0oCFUqdg6/4PeBPBRZDCyHKiq69SDZgS2VKWL0wsAhECZB2Mb9n7uRsWyI/AQIHM06Chs5w==
notify|@pi-archimedes/notify|sha512-zPVrdEiTV7nfij2ZQwzMmNwBVDIAsKqLWuv5xOAlrm2htjqI14E//BWhjvZAm8HD52vQLJq9eib3lt6JHVfBqA==
session-name|@pi-archimedes/session-name|sha512-sn6flx/RF05C1RnQGLY2wr1/9DHy2vAVtGk2azRNMkKywvTT3AOs8IngXMKc9Z5Y5xgMPpRDPqH0uTUzVBYQ9g==
footer|@pi-archimedes/footer|sha512-K1Ic+qs7G6HmBkY4vOy4Fg9nHifboFGRKAQUXDxrJvt/NuxsXjGivRaiN0iS9aZgSzgutkoU3IpH1tzgnhrQJQ==
diff|@pi-archimedes/diff|sha512-0En3NT0OgjDUXy9+KIUiAYCZyIhiXUMaR8Ftw786Mta7PrhLKUJcSsyUySmqMLPsn0M/6PykNDDKrZiTDAfRdg==
image-paste|@pi-archimedes/image-paste|sha512-Gq9zPi+ye57ObiYJ2ImcxAaDgf5pboSjBfhrtJ/x41OQKfX7NCIzjUW8Cu4tWhNx4FxUwKaNw1uC5ob59DHWRg==
subagent|@pi-archimedes/subagent|sha512-5GK78g89o2FCuelZjgRulww+5M0uq0F7RkD9/iGCyvhaTT2zTwmqthVdk8ya9Wc4fA6Jpl8k3ibqr+YbMlZdcg==
web|@pi-archimedes/web|sha512-i6018XhNMsq7WBhNFjjxOJsUfM9XOTbRZwzoXDP6C9veHY+X4vHLwprtK41Rl3Dbry/yjdg+Tn7UndYtv08hsg==
PACKAGES
LANGFUSE_TGZ=$(pack_exact \
  "pi-langfuse@1.7.0" "pi-langfuse" "1.7.0" \
  "sha512-dXMv4NLySMzOfIBmaSNUsu83HQNh3N4qxjgD9l5hvmWARSJ75W2YnD1dfIoRi9QUb2LnJsmSVHqJV9ENDL5K8w==")
extract "$LANGFUSE_TGZ" "$PROJECTED/pi-langfuse"

compare_manifest() {
  python3 - "$1" "$2" <<'PY'
import json
import pathlib
import sys

published_path, source_path = map(pathlib.Path, sys.argv[1:])
published = json.loads(published_path.read_text(encoding="utf-8"))
source = json.loads(source_path.read_text(encoding="utf-8"))
for section in ("dependencies", "devDependencies", "peerDependencies"):
    for name, value in source.get(section, {}).items():
        if isinstance(value, str) and value.startswith("workspace:"):
            actual = published.get(section, {}).get(name)
            if actual != "2.11.1":
                raise SystemExit(f"unexpected published dependency {name}: {actual}")
            source[section][name] = actual
if published != source:
    raise SystemExit(f"published manifest differs from source: {published_path}")
PY
}

verify_base_source() {
  local package=$1 base_dir source_root path source_path source_file
  case "$package" in
    meta) base_dir="$BASE/pi-archimedes"; source_root=meta ;;
    *) base_dir="$BASE/@pi-archimedes/$package"; source_root="packages/$package" ;;
  esac
  while IFS= read -r path; do
    path=${path#"$base_dir/"}
    source_path="$source_root/$path"
    [ "$path" = LICENSE ] && source_path=LICENSE
    source_file="$TMP/source-$package-${path//\//_}"
    git -C "$FORK" show "$BASE_HEAD:$source_path" > "$source_file" \
      || fail "$package npm base file has no v2.11.1 source: $path"
    if [ "$path" = package.json ]; then
      compare_manifest "$base_dir/$path" "$source_file"
    else
      cmp "$base_dir/$path" "$source_file" \
        || fail "$package npm base differs from v2.11.1 source at $path"
    fi
  done < <(find "$base_dir" -type f | sort)
}

for package in meta core ui sudo ask todo notify session-name footer diff image-paste subagent web; do
  verify_base_source "$package"
done

PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh"
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh" --check
PI_PACKAGE_ROOT="$PROJECTED" "$ROOT/scripts/apply-pi-package-patches.sh"

production_paths() {
  local package_dir=$1
  printf '%s\n' package.json
  (cd "$package_dir" && find src -type f -name '*.ts' ! -name '*.test.ts' -print)
}

compare_projection_path() {
  local package_dir=$1 fork_dir=$2 path=$3 label=$4
  [ -f "$package_dir/$path" ] && [ -f "$fork_dir/$path" ] \
    || fail "$label production file set differs from maintained fork at $path"
  if [ "$path" = package.json ]; then
    compare_manifest "$package_dir/$path" "$fork_dir/$path"
  else
    cmp "$package_dir/$path" "$fork_dir/$path" \
      || fail "$label projection differs from maintained fork at $path"
  fi
}

# Include the OS implementation even when Nix/Homebrew supplies PATH patch.
PATCH_ENGINES=("$(command -v patch)")
if [ -x /usr/bin/patch ] && ! [ /usr/bin/patch -ef "${PATCH_ENGINES[0]}" ]; then
  PATCH_ENGINES+=(/usr/bin/patch)
fi

verify_projection() {
  local package=$1 package_dir base_dir fork_dir patch_file reverse_output forward_output path patch_bin
  case "$package" in
    meta)
      package_dir="$PROJECTED/pi-archimedes"
      base_dir="$BASE/pi-archimedes"
      fork_dir="$FORK/meta"
      ;;
    *)
      package_dir="$PROJECTED/@pi-archimedes/$package"
      base_dir="$BASE/@pi-archimedes/$package"
      fork_dir="$FORK/packages/$package"
      ;;
  esac
  patch_file="$ROOT/patches/pi-packages/pi-archimedes-$package-2.11.1.patch"

  while IFS= read -r path; do
    compare_projection_path "$package_dir" "$fork_dir" "$path" "$package"
  done < <({ production_paths "$package_dir"; production_paths "$fork_dir"; } | sort -u)

  for patch_bin in "${PATCH_ENGINES[@]}"; do
    reverse_output=$(LC_ALL=C "$patch_bin" --verbose --force --fuzz=0 --reverse --dry-run -p1 -d "$package_dir" < "$patch_file" 2>&1)
    if grep -Eiq 'offset|fuzz' <<<"$reverse_output"; then
      fail "$package $patch_bin reverse dry-run used offset or fuzz"
    fi
    "$patch_bin" --batch --silent --fuzz=0 --reverse -p1 -d "$package_dir" < "$patch_file"
    diff -qr "$base_dir" "$package_dir" \
      || fail "$package $patch_bin reverse did not restore the exact npm base"

    forward_output=$(LC_ALL=C "$patch_bin" --verbose --force --fuzz=0 --forward -p1 -d "$package_dir" < "$patch_file" 2>&1)
    if grep -Eiq 'offset|fuzz' <<<"$forward_output"; then
      fail "$package $patch_bin reapply used offset or fuzz"
    fi
    while IFS= read -r path; do
      compare_projection_path "$package_dir" "$fork_dir" "$path" "$package reapplied"
    done < <({ production_paths "$package_dir"; production_paths "$fork_dir"; } | sort -u)
    echo "Verified exact $package round trip: $patch_bin"
  done
}

for package in meta ask core footer subagent; do
  verify_projection "$package"
done

if rg -n -i '\b(beads?|closeout|ticket_approval|quality[-_ ]policy|billing[-_ ]class|acceptance decision)\b' \
  "$PROJECTED/@pi-archimedes/subagent/src" "$PROJECTED/@pi-archimedes/core/src/events.ts"; then
  fail "Archimedes public ports contain pi-setup governance behavior"
fi

# Install test-only dependency links without substituting any Archimedes source.
python3 - "$FORK" "$PROJECTED" <<'PYLINK'
import json
import pathlib
import sys
fork, projected = map(pathlib.Path, sys.argv[1:])
for source in [fork / "meta", *sorted((fork / "packages").iterdir())]:
    if not (source / "package.json").is_file():
        continue
    manifest = json.loads((source / "package.json").read_text())
    destination = projected / manifest["name"]
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name in manifest.get(section, {}):
            if name.startswith("@pi-archimedes/"):
                continue
            dependency = source / "node_modules" / name
            link = destination / "node_modules" / name
            if dependency.exists() and not link.exists():
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(dependency.resolve())
PYLINK
for package in subagent footer ask; do
  cp "$FORK/packages/$package/src/"*.test.ts "$PROJECTED/@pi-archimedes/$package/src/"
done
for test in events events-host-bus; do
  cp "$FORK/packages/core/src/$test.test.ts" "$PROJECTED/@pi-archimedes/core/src/"
done
cp "$FORK/meta/src/settings.test.ts" "$FORK/meta/src/settings-manager.test.ts" "$PROJECTED/pi-archimedes/src/"

ln -s "$FORK/packages/subagent/node_modules/@earendil-works" "$PROJECTED/@earendil-works"
ln -s "$FORK/packages/subagent/node_modules/typebox" "$PROJECTED/typebox"
ln -s "$FORK/node_modules/vitest" "$PROJECTED/vitest"
ln -s "$FORK/node_modules/fast-check" "$PROJECTED/fast-check"
ln -s "$FORK/packages/subagent/node_modules/@types" "$PROJECTED/@types"

cat > "$TMP/projected/package.json" <<'JSON'
{"private":true,"type":"module"}
JSON
cat > "$TMP/projected/public-types.ts" <<'TS'
import { resolveAgentModel } from "@pi-archimedes/subagent/agents";
import {
  SUBAGENT_OUTPUT_CONTRACTS,
  type OutputLimitEvidence,
  type ResolvedChildExecution,
  type SubagentChildTraceRef,
  type SubagentDetails,
  type SubagentExecutionMode,
  type SubagentExecutionProfile,
  type SubagentLimits,
  type SubagentOutputContract,
  type SubagentProgressSummary,
  type SubagentResult,
  type SubagentTermination,
  type SubagentTerminationReason,
  type SubagentToolResult,
  type SubagentUsage,
  type SubagentUsageState,
} from "@pi-archimedes/subagent/types";
import {
  Events,
  emitOn,
  type AskRequestPayload,
  type AskResponsePayload,
  type CostUpdatePayload,
  type TodoClearPayload,
  type TodoUpdatePayload,
} from "@pi-archimedes/core/events";
import { createEventBus } from "@earendil-works/pi-coding-agent";

const resolveModel: (name: string, cwd: string) => string | undefined = resolveAgentModel;
const mode: SubagentExecutionMode = "one-shot";
const outputContract: SubagentOutputContract = "artifact";
const reason: SubagentTerminationReason = "idle-limit";
const usageState: SubagentUsageState = "partial";
const limits: SubagentLimits = {
  maxProviderRequests: 1,
  maxToolCalls: 2,
  maxTotalTokens: 3,
  maxOutputTokens: 4,
  maxCostUsd: 0.5,
  maxDurationMs: 6,
  maxIdleMs: 7,
};
const profile: SubagentExecutionProfile = { mode, thinking: "high" };
const outputLimit: OutputLimitEvidence = {
  requested: 4,
  effective: 4,
  enforcement: "applied",
};
const execution: ResolvedChildExecution = { profile, limits, outputLimit };
const termination: SubagentTermination = { reason, limit: 4, observed: 4, usageState };
const usage: SubagentUsage = {
  input: 1,
  output: 2,
  cacheRead: 3,
  cacheWrite: 4,
  cost: 0.5,
  turns: 1,
};
const childTrace: SubagentChildTraceRef = { sessionId: "session", traceId: "trace" };
const progressSummary: SubagentProgressSummary = { toolCount: 1, tokens: 10, durationMs: 20 };
const result: SubagentResult = {
  agent: "reviewer",
  task: "Review",
  childSessionId: "session",
  childTrace,
  exitCode: 2,
  usage,
  provider: "provider",
  model: "model",
  execution,
  outputContract,
  finalOutput: "partial",
  error: "limited",
  termination,
  progress: undefined,
  progressSummary,
};
const details: SubagentDetails = { mode: "parallel", results: [result], progress: [] };
const toolResult: SubagentToolResult = {
  content: [{ type: "text", text: "partial" }],
  details,
  isError: true,
};
const cost: CostUpdatePayload = {
  source: "subagent:reviewer",
  inputTokens: 1,
  outputTokens: 2,
  cacheReadTokens: 3,
  cacheWriteTokens: 4,
  cost: 0.5,
};
const todos: TodoUpdatePayload = {
  source: "subagent:reviewer",
  todos: [{ content: "Review", description: "Review", status: "in_progress" }],
};
const todoClear: TodoClearPayload = { source: "subagent:reviewer" };
const ask: AskRequestPayload = {
  source: "subagent:reviewer",
  requestId: "request",
  questions: [{
    id: "question",
    question: "Continue?",
    description: "Choose",
    options: [{ label: "Yes" }],
    multi: false,
    recommended: 0,
  }],
};
const answer: AskResponsePayload = {
  requestId: "request",
  cancelled: false,
  results: [{ id: "question", selectedOptions: ["Yes"], customInput: "note" }],
};
const events = createEventBus();
emitOn(events, Events.COST_UPDATE, cost);
emitOn(events, Events.TODOS_UPDATE, todos);
emitOn(events, Events.TODOS_CLEAR, todoClear);
emitOn(events, Events.ASK_REQUEST, ask);
emitOn(events, Events.ASK_RESPONSE, answer);
const off = events.on(Events.ASK_RESPONSE, (_payload: unknown) => {});
void [resolveModel, SUBAGENT_OUTPUT_CONTRACTS, toolResult, off];
TS

(
  cd "$TMP/projected"
  "$TSC" --noEmit --strict --skipLibCheck --target ES2022 \
    --module NodeNext --moduleResolution NodeNext --types node public-types.ts
)
for package in subagent footer ask; do
  (cd "$PROJECTED/@pi-archimedes/$package" && env -u PI_SUBAGENT_SOCKET "$VITEST" run --silent=true)
done
(cd "$PROJECTED/@pi-archimedes/core" && "$VITEST" run --silent=true src/events.test.ts src/events-host-bus.test.ts)
(cd "$PROJECTED/pi-archimedes" && "$VITEST" run --silent=true src/settings.test.ts src/settings-manager.test.ts)
(
  cd "$ROOT"
  PI_ARCHIMEDES_TEST_SCHEMA="$PROJECTED/@pi-archimedes/subagent/src/tool-schema.ts" \
    "$ROOT/.venv/bin/python" -m pytest tests/test_subagent_reports.py -q
)

echo "PASS: Archimedes npm bases, fork projections, reversibility, public declarations, installed-package contracts and managed JSON/SDK composition verified"
