---
name: research
description: Use when doing multi-source research or investigating a topic; not for due diligence or background checks.
---

# Research Skill

Comprehensive research system using parallel Pi peer models across multiple sources.

**Pi note:** Use the generic local helper `~/.pi/agent/bin/agnt` for shell-based research. `agnt web-search` uses the SearXNG instance configured by `SEARXNG_URL`; it uses the backend's default category unless `--category` is explicit. Skills should call the generic helper names, not SearXNG directly.

## MANDATORY: URL Verification

**Every URL must be verified before delivery.** Research peers/models can hallucinate URLs. A single broken link is a catastrophic failure.

See `references/UrlVerificationProtocol.md` for details.

## Workflow Routing

Route to the appropriate workflow based on the request.

**CRITICAL:** For due diligence, company/person background checks, or vetting -> **USE OSINT SKILL INSTEAD**

### Research Modes (Primary Workflows)
- Quick/minor research (1 agent, 1 query) -> `workflows/QuickResearch.md`
- Standard research - DEFAULT (2 peers/search angles in parallel) -> `workflows/StandardResearch.md`
- Extensive research (9 peers/search angles in parallel) -> `workflows/ExtensiveResearch.md`

## Quick Reference

| Trigger | Mode | Speed |
|---------|------|-------|
| "quick research" | 1 peer/search angle | ~10-30s |
| "do research" | 2 peers/search angles (default) | ~30-60s |
| "extensive research" | 9 peers/search angles | ~1-5 min |

See `references/QuickReference.md` for detailed comparison.

## Integration

### Feeds Into
- Council debates (research context first)
- RedTeam analysis (gather precedents)
- Writing and content creation

### Uses
- Search and retrieval via `~/.pi/agent/bin/agnt web-search` and `~/.pi/agent/bin/agnt web-fetch`
- Model selection via `~/.pi/agent/bin/agnt route --task research`
- Live single/parallel execution via unnamed `subagent` calls

## File Organization

**Scratch (temporary work artifacts):** `.pi/research/scratch/`

**History (permanent):** `.pi/research/YYYY-MM-DD-[topic]/`
