#!/usr/bin/env bash
set -euo pipefail

# Temporary bootstrap/repair launcher.
#
# This intentionally loads the normal Pi extension set, including
# orchestrator-service, but tells orchestrator-service not to remove write tools.
# That lets us test the real runner lifecycle (doctor, daemon, lease, status,
# drain) while preserving bash/edit/write during harness stabilization.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PI_ORCHESTRATOR_REPAIR_TOOLS=1

exec pi \
  --approve \
  --tools read,bash,edit,write,grep,find,ls,ticket_gateway,ticket_question,ticket_approval,ticket_decision_resolve \
  --name "orchestrator repair-tools mode" \
  "$@"
