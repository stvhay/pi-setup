# STPA-Sec: Security Extension

STPA-Sec extends STPA to address cybersecurity through a systems-theoretic lens. Rather than treating security as separate from safety, it recognizes that security threats are mechanisms that can cause the same unsafe control actions STPA identifies.

## Core Insight

**Security threats are causal scenarios for unsafe control actions.**

When STPA asks "why might this unsafe control action occur?", traditional answers focus on accidents: sensor failure, software bugs, human error. STPA-Sec adds: "because an adversary intentionally caused it."

The adversary must solve their own control problem to succeed:

```
<Exploit> <Provides> <Malicious Action> when <Context>
```

This has the same structure as an Unsafe Control Action:
- **Controller**: The exploit/attack mechanism
- **Type**: Provides (injects), blocks (denies), modifies (tampers)
- **Control Action**: The malicious command or data
- **Context**: System state that makes attack successful

## Mapping Security Threats to STPA Causal Factors

Security threats map directly to STPA's causal scenario categories:

### Feedback Path Attacks

| STPA Causal Factor | Security Attack Class |
|-------------------|----------------------|
| Feedback not provided | **Denial of Service** - block sensor data |
| Incorrect feedback | **Spoofing** - inject false sensor readings |
| Feedback delayed | **Denial of Service** - slow network, queue flooding |

### Control Path Attacks

| STPA Causal Factor | Security Attack Class |
|-------------------|----------------------|
| Control action not executed | **Denial of Service** - block commands |
| Wrong control action executed | **Tampering** - modify commands in transit |
| Unauthorized control action | **Spoofing** - inject malicious commands |

### Controller Attacks

| STPA Causal Factor | Security Attack Class |
|-------------------|----------------------|
| Flawed control algorithm | **Tampering** - modify software/firmware |
| Incorrect process model | **Spoofing** - corrupt state information |
| Wrong goals | **Tampering** - modify configuration/policy |

## STRIDE Integration

Microsoft's STRIDE threat taxonomy maps to control structure elements:

| STRIDE Threat | Control Structure Target | Effect |
|--------------|-------------------------|--------|
| **S**poofing | Controller identity, feedback source | False commands accepted, wrong process model |
| **T**ampering | Control actions, feedback, algorithm | Modified behavior, corrupted state |
| **R**epudiation | Audit/logging feedback | Loss of accountability, hidden attacks |
| **I**nformation Disclosure | Process model, control actions | Adversary learns system state |
| **D**enial of Service | Any control/feedback path | Missing control actions, stale process model |
| **E**levation of Privilege | Controller authority | Unauthorized control actions |

## Mission-Focused Analysis

Traditional security focuses on protecting system components (the "safe" in Schneier's attack tree example). STPA-Sec focuses on **mission impact**.

**Key reframing:**
- Don't ask: "How can the attacker compromise this component?"
- Ask: "What mission losses result if this control action is unsafe?"

This shifts security from a tactical (protect everything) to strategic (protect what matters) discussion.

### Defining Security Losses

Security losses should be defined in mission terms:

| Traditional Security | STPA-Sec Mission Loss |
|---------------------|----------------------|
| Data breach | L-1: Sensitive information disclosed to unauthorized parties |
| System compromise | L-2: System performs unauthorized actions |
| Ransomware | L-3: Mission capability unavailable when needed |
| Integrity violation | L-4: Decisions made on corrupted information |

## STPA-Sec Process

STPA-Sec follows the same four steps as STPA, with security-specific additions:

### Step 1: Define Purpose (Security Addition)

In addition to safety losses, identify:
- **Security-specific losses**: Data confidentiality, system integrity, availability
- **Adversary-relevant hazards**: System states an adversary would want to cause
- **Trust boundaries**: Where control/feedback crosses security domains

### Step 2: Model Control Structure (Security Addition)

Annotate the control structure with:
- **Trust boundaries**: Mark where controllers/paths cross security domains
- **Attack surfaces**: External interfaces, network connections, physical access points
- **Authentication points**: Where identity is verified (or assumed)

### Step 3: Identify Unsafe Control Actions (No Change)

UCAs remain the same—STPA-Sec doesn't change what's unsafe, only adds reasons why it might occur.

### Step 4: Identify Loss Scenarios (Security Addition)

For each UCA, add security-specific scenarios:

**Template:**
```
UCA: [Controller] [does/does not] [action] when [context]

Security Scenarios:
- Spoofing: Adversary impersonates [X] to cause [UCA]
- Tampering: Adversary modifies [Y] to cause [UCA]
- DoS: Adversary blocks [Z] to cause [UCA]
```

For each scenario, identify:
1. **Attack vector**: How adversary gains access
2. **Required capabilities**: What adversary needs (access, knowledge, resources)
3. **Indicators**: How attack might be detected
4. **Mitigations**: Controls that prevent or limit attack

## Wargaming with STPA-Sec

STPA-Sec enables structured security wargaming (used in DoD Cyber Table Top exercises):

### Process

1. **OPFOR describes attack class and goals**
   - Select element to attack (from control structure)
   - Select effect to achieve (from UCA analysis)
   - Select attack class (from STRIDE)

2. **Both teams describe possible outcomes**
   - What system effects result from successful attack?
   - What mission impacts follow?

3. **Operational team describes workarounds**
   - How would operators detect the attack?
   - What manual procedures could mitigate?

4. **Iterate with next attack class**
   - Systematically cover attack classes for each critical element

### Example

```
Element: Boom Contact Sensor
Effect: Delayed Pulse Feedback
Attack Classes: Denial of Service, Tampering

Scenario 1 (DoS): Adversary floods sensor network, delaying feedback
- System effect: Controller doesn't know boom has contacted
- Mission effect: Refueling operation continues past safe point

Scenario 2 (Tampering): Adversary modifies sensor to delay pulse
- System effect: Same as above
- Mission effect: Same as above
- Detection: Sensor self-test might detect modification
```

## Security Requirements from STPA-Sec

Transform security scenarios into requirements:

| Scenario | Security Requirement |
|----------|---------------------|
| Spoofed commands accepted | SR-1: Controller shall authenticate command source |
| Tampered feedback undetected | SR-2: Feedback shall include integrity verification |
| DoS blocks critical control | SR-3: Critical paths shall have redundant channels |
| Stale process model from delayed feedback | SR-4: Controller shall detect and flag stale data |

## When to Apply STPA-Sec

Use STPA-Sec when:
- System has network connections or external interfaces
- Adversarial threats are credible (not just accidents)
- Safety and security are coupled (security failure → safety failure)
- Mission assurance requires understanding cyber risk

STPA-Sec is particularly valuable for:
- Cyber-physical systems (vehicles, industrial control, medical devices)
- Critical infrastructure (power grid, water systems)
- Military and defense systems
- Systems with wireless or remote access

## Relationship to STPA

STPA-Sec is an extension, not a replacement:
- **STPA alone**: Sufficient when adversarial threats are not credible
- **STPA-Sec**: Adds security scenarios to standard STPA analysis
- **Combined output**: Safety requirements + security requirements, both traceable to hazards

The control structure model is shared—security analysis builds on safety analysis rather than duplicating it.
