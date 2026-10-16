# Browser Permissions Design and Implementation Plan

**Issue:** pi-m3fg — Project browser permissions and autonomous downloads
**Date:** 2026-10-16
**Branch:** main (current checkout; no branch/integration/deployment authorized)
**Design:** approved in conversation: browser-only .perms, global downloads allow, explicit ask/deny, aligned browser instructions. Shell/device enforcement excluded.

## Goal and boundary

Remove repeated download confirmations by default. Retain explicit ask/deny and optional project network allow/block lists. This is browser-request policy, not an OS sandbox, device grant, shell firewall, or protection against arbitrary code running as the same OS user.

Use public BetterWright `createPiExtension` and `NetworkPolicy` exports in a tracked composition adapter. Disable package-owned auto-registration, retaining rolling npm package. No installed-package edits or new dependencies. Query of existing graph identified approval/Beads components but no BetterWright wrapper; verified live package 2.8.9 source and public declarations.

## Policy contract

- Read only `.perms/{downloads,net-allowlist,net-blocklist}` at canonical Pi session cwd; no ancestor search or cross-project inheritance.
- Downloads: `BETTERWRIGHT_PI_DOWNLOAD_POLICY` explicit host override > project `downloads` > `allow`. Valid values allow/ask/deny; no model-controlled permission parameter.
- Network lines: blanks and # comments ignored; exact hostname/IP, explicit `*.domain` (subdomains only), optional port. No regex, arbitrary URLs, paths, CIDR, custom trie, or DNS lookups in parser. Normalize DNS case/trailing dot and IP forms; reject malformed/ambiguous syntax, bound file input.
- Missing allowlist means unrestricted except blocklist/upstream protections. Present empty allowlist means deny all network destinations. Block wins. Scheme/default port handling must be consistent for navigation and transport.
- Apply network rules to browser requests and DNS-resolved transport addresses, using trusted `resolvedFrom` only for transport-address attribution; check blocklist against both source name and actual IP. Preserve baseline denials and metadata floor. Non-network about/data/blob behavior remains upstream.
- No automatic prompt on denied network requests. Clear diagnostic identifies .perms policy.
- Private receipt per canonical project under `~/.pi/runtime/browser-permissions/`, private atomic writes, schema validation. No receipt needed for untouched default with no .perms files. Project policy requires explicit human slash-command approval; saved fingerprint must match current policy, including absence/empty distinctions. Deleted previously approved restrictions cannot silently return to defaults.
- `/browser-permissions` previews effective settings and approval status. `/browser-permissions approve` requires live UI, shows exact policy/root/scope/consequence/reversal, rechecks content/session after confirmation, persists one receipt then reloads. Rejection/no UI/drift does not grant authority.
- Freeze browser options to validated runtime policy; require reload after policy/root changes. Check tools and browser commands before execution, recheck after download confirmation, and reject changed/unapproved policy in network hook. In-flight responses/connections are not retroactively revoked; restart browser when immediate revocation is required.
- Align upstream injected download sentence and download-tool description with active policy. Refuse unsupported upstream prompt contract rather than silently preserve contradictory guidance.

## Files and tasks

1. Tests first: `tests/test_browser_permissions.py`; update package assertion in `tests/test_pi_packages.py`. Use real filesystem/parser/matcher and Pi extension loader; synthetic BetterWright public API fixture where browser/host side effects must be excluded.
2. Policy logic: `pi/agent/extensions/lib/browser-permissions.ts` — bounded parser, canonical snapshot/fingerprint, deterministic matching, private receipts, guidance text.
3. Adapter: `pi/agent/extensions/browser-permissions.ts` — load installed public exports, compose existing tools/commands/events, trusted approve command, dynamic prompt alignment and immutable runtime binding.
4. Config: `pi/agent/settings.json` — BetterWright object form with extensions disabled to avoid duplicate registration.
5. Docs: `pi/README.md`, `docs/extension-web-compatibility.md`, `docs/ARCHITECTURE.md` — format/precedence, migration, approval UX, rolling compatibility, runtime storage, browser-only/local-vs-remote limitations and reload behavior. Update `tests/test_agent_os_compat.py` to accept dated rolling observations rather than hard-code the old observation date.

## Verification

- Observe focused RED before production implementation, then GREEN.
- Cover defaults/ask/deny; exact/wildcard/ports/IPv4/IPv6; empty allowlist; deny precedence; malformed rules; source and resolved-IP checks; metadata never reopened; receipts/rejection/no UI/root isolation/deletion/drift; approval-wait race; tools and slash commands; prompt alignment and upstream mismatch; lifecycle close preservation.
- Run real installed BetterWright policy/registration smoke without launching browser or accessing network.
- Run focused and full deterministic suites; review boundary diff with routed independent reviewer before final commit.

```bash
.venv/bin/python -m pytest tests/test_browser_permissions.py tests/test_pi_packages.py tests/test_agent_os_compat.py -q
scripts/check-pi-config.sh
bash -n scripts/*.sh
.venv/bin/python -m ruff check pi/agent/bin/agnt_lib tests
.venv/bin/python -m pytest tests/ --durations=15
pi/agent/bin/agnt eval run routing-smoke
pi/agent/bin/agnt eval run role-context-smoke
```

## Evidence before final candidate

- Initial focused RED: seven missing-implementation assertions plus package configuration assertion failed as intended. Existing Ponytail discovery test separately failed because actual user `~/.agents` contributed an extra skill; source inspection confirmed extension count was unaffected. No unrelated test logic changed to hide this baseline failure.
- Focused GREEN: `HOME=<temporary empty directory> .venv/bin/python -m pytest tests/test_browser_permissions.py tests/test_pi_packages.py tests/test_agent_os_compat.py -q` — 34 passed. Use isolated temporary HOME for final pytest gate to avoid ambient user skill discovery.
- Installed BetterWright 2.8.9 non-network smoke passed: real public entrypoint registration, all five tools, policy-aligned prompt, network matching, resolved-IP attribution, metadata/IP-mapped metadata rejection, shutdown. No browser launched.
- Boundary discovery found check-before-upstream-queue race. Two regression tests failed with successful queued dispatch before fix; adapter now owns an outer serialization lane and revalidates inside it. Fresh verifier independently reproduced original placement and confirmed repaired real-upstream tool/command queues across drift/shutdown/reload/session transitions (24 queued rejections). No serious current-candidate findings. Validated private review records: `.pi/reviews/pi-m3fg/{discovery,verification}.json`; delegated refs `f7a0d2c6-0ef9-40c6-ac70-61b6743550eb` and `52873b6d-f86b-43f7-9884-adf6719e4e3e`.

## Acceptance and closeout

Default download path has no confirm call; ask retains upstream confirmation; deny rejects. Network filtering never broadens upstream protections. Project edits cannot silently replace approved policy. All existing browser tools remain available and retain upstream behavior except documented permission changes. Commit only task-owned files, direct-closeout pi-m3fg, then handoff. Preserve unrelated untracked plans. No deployment, push, or branch integration included.
