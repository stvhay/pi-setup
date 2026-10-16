---
name: stamp-stpa-sec
description: Use for control-structure threat modeling (STPA-Sec), attack surfaces or safety/security risks.
---

# STPA-Sec: Security Analysis Extension

STPA-Sec extends STPA to address cybersecurity through a systems-theoretic lens. Security threats become causal scenarios for unsafe control actions—the adversary must solve their own control problem to succeed.

## When to Use

Use for adversarial control/feedback analysis linked to mission or safety losses, or an explicit STPA-Sec request. Ordinary threat modeling may suffice without that control-system objective. Honor STRIDE-only requests without silently replacing them with STPA-Sec; offer integration only as an option.

Establish the requested output before asking prospective-versus-incident questions. Software bugs use `~/.pi/agent/skills/systematic-debugging/SKILL.md`; proposal critique uses `~/.pi/agent/skills/redteam/SKILL.md`. Read the selected skill with scope, evidence and constraints rather than launching formal analysis by keyword. Stabilize active incidents before retrospective analysis.

Direct STPA-Sec entry needs no whole-base preload. When shared theory is needed, read `~/.pi/agent/skills/stamp-base/references/stamp-foundations.md`.

## Agentic Behavior

### Checkpoints

Pause and ask when:

| Situation | Ask |
|-----------|-----|
| Threat actor unclear | "What adversary are we defending against—insider, external attacker, nation-state?" |
| Trust boundaries unclear | "Where are the trust boundaries? What's inside vs outside the security perimeter?" |
| Safety-security intersection | "Should I analyze safety implications of security failures, or focus on security alone?" |
| Scope of attack scenarios | "Should I cover all STRIDE categories, or focus on specific threats?" |
| API without system context | "What does this API control? Is it part of a larger system, or is the API itself what we're protecting?" |

**Don't** checkpoint after every step. Pause on uncertainty, not ritual.

### Framing Conflicts

When users bring traditional security framing, surface integration opportunities:

| User Says | Response Pattern |
|-----------|------------------|
| "Just do a STRIDE analysis" | "STRIDE maps well to control structures. Want me to integrate it with control path analysis for deeper scenarios?" |
| "We need penetration testing" | "Pen testing finds vulnerabilities; STPA-Sec finds why they matter. Want me to map attack paths to mission impact?" |
| "Add more firewalls/encryption" | "Barriers without understanding control structure may leave gaps. Want to map what controls those barriers protect first?" |
| "Calculate attack probability" | "Attacker behavior isn't random. Want to map attack scenarios to control structure vulnerabilities instead?" |
| "Keep it simple/quick" | "I can do a quick STRIDE pass. But 10 more minutes mapping what your system controls often reveals 2-3 critical scenarios traditional STRIDE misses. Your call—quick or thorough?" |

**Acknowledge** their approach works. **Offer** STPA-Sec as enhancement, not replacement. **Let them choose**.

### Time Pressure

When users have hard deadlines:

| Time Available | Minimum Viable STPA-Sec |
|----------------|-------------------------|
| 30 minutes | Control structure sketch + trust boundaries + top 3 attack scenarios |
| 2 hours | Full control structure + STRIDE mapping + key security requirements |
| Half day | Complete STPA-Sec with all attack classes and mitigations |

> "With [X time], I can give you [minimum viable output]. Want that, or should we focus on your highest-value assets only?"

### Compliance Integration

STPA-Sec generates compliance artifacts as outputs, not separate activities:

| Compliance Need | STPA-Sec Output |
|-----------------|-----------------|
| STRIDE checklist | Security scenarios table, organized by STRIDE category |
| Attack probability matrix | Attack scenarios with required capabilities (qualitative, not probabilistic) |
| Threat model document | Control structure + trust boundaries + security scenarios |
| Penetration test scope | Attack surfaces and vulnerable control/feedback paths |

| User Says | Response Pattern |
|-----------|------------------|
| "Auditor requires [specific format]" | "I can generate that format from control structure analysis. Want it filled with actual causal scenarios, or just checkboxes?" |
| "This is just for compliance" | "Compliance artifacts are outputs of security analysis. Want me to do the analysis that fills your template meaningfully?" |

### Skill Handoffs

Load only for a distinct requested/approved output (reuse already-loaded instructions):

- Safety requirements beyond security: `~/.pi/agent/skills/stamp-stpa/SKILL.md`.
- Systemic explanation of a specific past incident: `~/.pi/agent/skills/stamp-cast/SKILL.md`.
- Idea-level critique before formal modeling: `~/.pi/agent/skills/redteam/SKILL.md`.

From STPA, retain the existing control model and add adversarial scenarios only when requested. Across handoffs carry boundary, losses/hazards, controllers, actions/feedback, stable IDs, assumptions, evidence and constraints. The schemas are not interchangeable. Ask before expanding scope; do not discard earlier constraints or make these steps mandatory.

## Methodology Deep Dive

Read and follow [references/stpa-security.md](references/stpa-security.md) for the STPA-Sec process, mission-focused analysis, wargaming, and security-requirements derivation.

## Output Schema

When producing STPA-Sec analysis, structure output for machine parsing:

```yaml
stpa_sec_analysis:
  system:
    name: string
    boundary: string
    trust_boundaries:
      - id: TB-1
        description: string
        crosses: [control_action_ids | feedback_path_ids]
    losses:
      - id: L-1
        description: string
        type: confidentiality | integrity | availability | safety | mission
    hazards:
      - id: H-1
        description: string
        losses: [L-1]

  threat_model:
    adversaries:
      - id: string
        type: insider | external | nation_state | opportunistic
        capabilities: [string]
        goals: [loss_ids]

  control_structure:
    controllers:
      - id: string
        type: human | automated
        trust_level: trusted | untrusted | partially_trusted
    attack_surfaces:
      - element: controller_id | control_action_id | feedback_path_id
        exposure: network | physical | supply_chain
        trust_boundary: TB-1

  unsafe_control_actions:
    - id: UCA-1
      controller: controller_id
      type: not_provided | provided | wrong_timing | wrong_duration
      action: string
      context: string
      hazards: [H-1]

  security_scenarios:
    - uca: UCA-1
      attack_class: spoofing | tampering | repudiation | information_disclosure | dos | elevation
      scenario: string
      attack_vector: string
      required_capabilities: [string]
      indicators: [string]

  security_requirements:
    - id: SR-1
      requirement: string
      addresses: [UCA-1]
      mitigates: [security_scenario_ids]
      verification: string
```

Use this schema when:
- Handing off to another agent
- Integrating with traditional security tools
- Feeding back into STPA for safety analysis

## Related

**RELATED SKILLS:**
- stamp-base — Theoretical foundations and routing
- stamp-stpa — Safety-focused prospective analysis (without adversarial scenarios)
- stamp-cast — Retrospective analysis (including security incidents)

## Depict Syntax

When producing a diagram, read `~/.pi/agent/skills/stamp-base/references/depict.md` for generic grammar (reuse if loaded); no whole-base routing step is needed. Without a diagram request, skip that reference. Keep the method-specific examples and annotations below.

### Example: API Security Control Structure

```
admin [ auth_service config_mgmt ]
auth_service api_gateway: issue_token, revoke / auth_request
api_gateway backend: validated_request / response
external api_gateway: request @red / data
```

### Example: Microservices Attack Surface

```
external
load_balancer
svc_a svc_b svc_c -
database
external load_balancer: request @red
load_balancer svc_a: route; load_balancer svc_b: route; load_balancer svc_c: route
svc_a database: query; svc_b database: query @red; svc_c database: query
```

Shows horizontal microservices with one vulnerable database path.

### STPA-Sec Specific Usage

- Use `@red` to highlight attack surfaces (paths crossing trust boundaries)
- Nesting `[ ]` represents security domains (DMZ, internal, external)
- Use horizontal `-` for parallel services, redundant paths, or distributed components
- Label feedback paths that could be spoofed or tampered
- Use `(state)` or `<port>` in names to annotate security-relevant details

### Limitations

Depict handles **structure**, not **threat analysis**. Trust boundaries, STRIDE mappings, and attack scenarios require separate tables or prose—depict shows the control structure those analyses reference.

**Trust boundary workaround:** Use separate depict diagrams for each security domain, or use nesting `[ ]` to group elements within the same trust zone.
