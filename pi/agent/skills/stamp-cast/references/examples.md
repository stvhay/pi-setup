# CAST Worked Examples

This reference provides concrete examples of CAST accident analysis across different domains.

## Example 1: Cardiac Transplant Medication Error

### Background

A patient was admitted to a Chicago hospital for a cardiac transplant. Written orders called for administration of immunosuppression medication before surgery. The CCU nurse handed off the patient to the surgical team. Surgeons started surgery without the patient having received immunosuppression medication. Surgery was successful, but the patient's ventricular function worsened. The patient was placed on ECMO and treated for transplant rejection. The patient did not survive.

### Step 1: Basic Information

**Loss:** Death of patient (L-1)

**Hazard:** Patient undergoes transplant surgery without required immunosuppression (H-1)

**Safety Constraint:** Patient must receive immunosuppression medication before transplant surgery begins (SC-1)

**Events (neutral language):**
1. Patient admitted for cardiac transplant
2. Written orders included preoperative immunosuppression
3. CCU nurse handed off patient to surgical team
4. Surgery began
5. Immunosuppression medication was not administered before surgery
6. Patient experienced transplant rejection
7. Patient placed on ECMO
8. Patient did not survive

### Step 2: Control Structure

```
┌─────────────────────────────────────────────────────────────┐
│                   Hospital Administration                    │
│                                                              │
│  Responsibilities: Establish medication procedures,          │
│                    ensure staffing and training              │
└─────────────────────────────┬────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ CCU Administration│  │ OR Administration │  │Pharmacy Services │
│                  │  │                  │  │                  │
│ CCU procedures,  │  │ Surgical safety  │  │ Med dispensing,  │
│ staffing         │  │ protocols        │  │ verification     │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼                     ▼                     │
┌──────────────────┐  ┌──────────────────┐          │
│    CCU Nurse     │  │ Circulating RN   │          │
│                  │  │ (OR Nurse)       │          │
│ Patient prep,    │  │ Final check,     │◄─────────┘
│ medication admin │  │ surgery readiness│
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         │     Handoff         │
         └──────────┬──────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                        Surgeons                              │
│                                                              │
│  Responsibilities: Verify patient ready, perform surgery     │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Patient                               │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Component Analysis

#### CCU Nurse

**Safety Responsibilities:**
- Prepare patient for surgery per written orders
- Administer preoperative medications
- Complete handoff checklist

**Role in Adverse Event:**
- Did not administer immunosuppression medication before handoff

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed immunosuppression was to be given by OR team | Procedure was ambiguous about which unit administers preoperative immunosuppression |
| Believed medication would be verified at handoff | No explicit verification step in handoff protocol |

**Questions for further investigation:**
- What did the handoff checklist include?
- Was immunosuppression explicitly listed as CCU responsibility?
- How often had this nurse handled transplant patients?

---

#### Circulating RN (Operating Room Nurse)

**Safety Responsibilities:**
- Final check that patient is ready for surgery
- Verify all preoperative requirements complete

**Role in Adverse Event:**
- Did not stop surgery from proceeding despite patient not having received immunosuppression

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed patient had received immunosuppression | No mechanism to verify medication administration |
| Believed CCU had completed all preoperative tasks | Trust in handoff process |

**Questions for further investigation:**
- How was she supposed to know if medication was given?
- Was there a checklist item for immunosuppression?
- Could she have verified with pharmacy?

---

#### Surgeons

**Safety Responsibilities:**
- Verify patient ready for surgery
- Confirm critical preoperative requirements

**Role in Adverse Event:**
- Began surgery without verifying immunosuppression status

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Assumed preoperative medications complete if patient in OR | Standard workflow expectation |
| Believed OR nurse had verified readiness | Division of responsibilities |

**Questions for further investigation:**
- Was immunosuppression verification part of surgical timeout?
- Did surgeons have visibility into medication records?

---

#### CCU Administration

**Safety Responsibilities:**
- Ensure safe practices in CCU
- Maintain staffing levels and training
- Establish safe medication procedures

**Role in Adverse Event:**
- Did not establish safe, standardized medication procedure for preoperative immunosuppression

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed staff knew how to order and administer all medications | Transplants are rare; procedure not routinized |
| Believed existing handoff procedures were adequate | No feedback indicating gaps |

---

### Step 4: Systemic Factors

**Communication gaps:**
- No explicit communication of immunosuppression status at handoff
- No mechanism for OR to verify CCU medication administration

**Procedure deficiencies:**
- Ambiguity about which unit administers transplant-specific preoperative medications
- Handoff checklist did not include transplant-specific items

**Safety information system:**
- No forcing function requiring verification of immunosuppression before surgery
- Medication status not visible to OR team

### Step 5: Recommendations

| Recommendation | Addresses | Assigned To | Verification |
|----------------|-----------|-------------|--------------|
| Create transplant-specific preoperative checklist with explicit immunosuppression verification | Procedure ambiguity | CCU Admin + OR Admin | Checklist in use |
| Add immunosuppression to surgical timeout checklist | Missing verification | OR Admin | Audit of timeout compliance |
| Implement electronic verification that critical preoperative medications administered | Missing feedback to OR | Hospital IT + Pharmacy | System deployed and tested |
| Require pharmacy confirmation before patient transport to OR | Missing control | Pharmacy Services | Policy implemented |

---

## Example 2: Walkerton Water Contamination

### Background

In May 2000, the water supply of Walkerton, Ontario became contaminated with E. coli O157:H7 and Campylobacter. Seven people died and more than 2,300 became ill. The contamination originated from a farm near Well 5, which had a shallow location and inadequate protection from surface contamination. Heavy rains washed cattle manure into the well's water source.

### Step 1: Basic Information

**Loss:**
- L-1: Death of residents (7 fatalities)
- L-2: Serious illness (2,300+ affected)
- L-3: Loss of public trust in water system

**Hazard:** Public is exposed to E. coli or other health-related contaminants through drinking water (H-1)

**Safety Constraints:**
- SC-1: Water quality must not be compromised
- SC-2: Public health measures must reduce risk of exposure if water quality is compromised

### Step 2: Control Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Provincial Government                            │
│  (Budgets, laws, regulatory policy)                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ministry of   │    │   Ministry of   │    │ Ministry of Agr.│
│    Health       │    │  Environment    │    │ Food & Rural    │
│                 │    │                 │    │    Affairs      │
│ Health regs,    │    │ Water standards,│    │ Farm practices, │
│ advisories      │    │ inspections,    │    │ manure mgmt     │
│                 │    │ certification   │    │                 │
└────────┬────────┘    └────────┬────────┘    └─────────────────┘
         │                      │
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────────────────────────────────┐
│ BGOS Medical    │    │              Walkerton PUC                   │
│ Dept of Health  │    │         (Public Utilities Commission)        │
│                 │    │                                              │
│ Local health    │    │  Responsibilities: Water treatment,         │
│ monitoring,     │◄───│  chlorination, monitoring, reporting        │
│ outbreak resp.  │    │                                              │
└────────┬────────┘    └───────────────────┬─────────────────────────┘
         │                                 │
         │                                 │
         ▼                                 ▼
┌─────────────────┐    ┌─────────────────────────────────────────────┐
│   Public        │    │            Physical System                   │
│   Health        │◄───│                                              │
│                 │    │  Well 5: Shallow, near farm, porous bedrock │
│   Residents     │    │  Well 7: No chlorinator                      │
│                 │    │  Heavy rains + cattle manure                 │
└─────────────────┘    └─────────────────────────────────────────────┘
```

### Step 3: Component Analysis

#### Walkerton PUC Operators

**Safety Responsibilities:**
- Monitor water quality
- Maintain adequate chlorination
- Report adverse test results to authorities
- Issue boil-water advisories when needed

**Role in Adverse Event:**
- Did not maintain adequate chlorine residuals
- Did not report adverse water quality results to health authorities
- Made false entries in operating records
- Did not issue boil-water advisory when contamination suspected

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed chlorination levels were adequate | Inadequate training on chlorine requirements |
| Believed adverse results didn't require reporting | Misunderstanding of regulatory requirements |
| Did not understand severity of E. coli contamination | Lack of knowledge about health consequences |

**Contributing factors:**
- Operators had minimal training and no certification
- Previous operator (who had more knowledge) had retired
- Budget constraints limited training and equipment
- Culture of "we've always done it this way"

---

#### Ministry of Environment

**Safety Responsibilities:**
- Set water quality standards
- Inspect water systems
- Certify operators
- Enforce compliance

**Role in Adverse Event:**
- Did not conduct adequate inspections of Walkerton water system
- Did not ensure operators were properly trained and certified
- Did not follow up on previous inspection findings

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed local operators were adequately trained | No verification mechanism |
| Believed inspection findings were being addressed | No follow-up process |
| Believed privatization of testing labs would maintain reporting | Reporting chain was broken |

**Contributing factors:**
- Budget cuts reduced inspection staff by 30%
- Privatization of water testing labs eliminated direct reporting to MOE
- No mechanism to ensure labs reported adverse results to health authorities

---

#### Ministry of Health / Local Health Unit

**Safety Responsibilities:**
- Monitor for disease outbreaks
- Issue health advisories
- Respond to water contamination events

**Role in Adverse Event:**
- Did not receive adverse water quality results until outbreak was well underway
- Did not issue boil-water advisory until May 21 (contamination began May 12)

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed they would be notified of water quality problems | Reporting chain was broken |
| Initially believed illnesses were from other sources | E. coli symptoms similar to other GI illness |

**Contributing factors:**
- No direct communication channel from water testing labs
- Relied on PUC operators to report (they didn't)
- Weekend delayed response when outbreak pattern emerged

---

### Step 4: Systemic Factors

**Communication breakdown:**
- Privatization of testing labs broke the reporting chain
- Test results went to PUC only, not to health authorities
- No feedback loop from labs to Ministry of Environment

**Regulatory gaps:**
- No requirement for labs to report adverse results to health authorities
- Operator certification requirements not enforced
- Inspection frequency inadequate for system risk level

**Resource constraints:**
- Budget cuts reduced Ministry of Environment inspection capacity
- Small municipalities lacked resources for proper water system operation
- Training and certification seen as optional expenses

**Safety culture:**
- "We've always done it this way" mentality at PUC
- Production pressure (keeping water flowing) over safety
- No near-miss reporting or learning from incidents

**Changes over time:**
- Experienced operator retired, taking knowledge with him
- Privatization of testing created gaps not recognized
- Budget pressures accumulated over years

### Step 5: Recommendations

| Recommendation | Addresses | Assigned To |
|----------------|-----------|-------------|
| Require testing labs to report adverse results directly to health authorities | Communication gap | Provincial Government |
| Mandate operator certification with regular recertification | Training deficiency | Ministry of Environment |
| Establish minimum inspection frequency based on system risk | Inspection gaps | Ministry of Environment |
| Create automated notification system for adverse water quality | Feedback failure | Ministry of Health |
| Require source water protection plans for all drinking water systems | Physical vulnerability | Ministry of Environment |

---

## Example 3: Industrial Scaffolding Fall

### Background

Workers were assembling a large, complex product in a manufacturing facility. A part was not available when needed, so a decision was made to add it later. When the part arrived, workers had to disassemble a large piece of the product to insert the missing part. Scaffolding had been constructed during the previous shift. When workers went to remove the large piece, the scaffolding blocked removal. Workers removed floorboards from the scaffolding to create clearance. Four workers were holding the large piece while moving it to the end of the scaffolding to take it down to the shop floor. All four turned simultaneously and one fell through the hole in the scaffolding where the floorboards had been removed.

### Step 1: Basic Information

**Loss:** Serious injury to worker (fall from height)

**Hazard:** Worker exposed to fall hazard (unguarded opening in scaffolding)

**Safety Constraint:** Scaffolding must maintain fall protection at all times when workers are present

### Step 3: Component Analysis (Selected)

#### Workers Who Removed Floorboards

**Safety Responsibilities:**
- Follow safe work procedures
- Maintain fall protection
- Report unsafe conditions

**Role in Adverse Event:**
- Removed floorboards from scaffolding without installing alternative fall protection

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed hole would be visible and avoidable | All four were focused on carrying the heavy piece |
| Believed task would be quick and risk was low | Time pressure to complete rework |
| Did not recognize fall hazard severity | Hole was "temporary" in their mental model |

**Contributing factors:**
- Production pressure to complete the rework quickly
- No fall protection equipment readily available
- Previous shift had not anticipated this scenario
- No procedure for this specific situation

---

#### Production Planning

**Safety Responsibilities:**
- Ensure parts available when needed
- Plan work sequences to minimize hazards

**Role in Adverse Event:**
- Did not ensure part was available at correct time in assembly sequence

**Why?**

| Process Model Flaw | Context |
|-------------------|---------|
| Believed out-of-sequence installation was routine | Schedule pressures accepted as normal |
| Did not recognize safety implications of rework | Safety not considered in planning decisions |

---

### Step 4: Systemic Factors

**Production pressure:**
- Missing part created schedule pressure
- Workers improvised to "get the job done"
- Safety procedures seen as obstacles to productivity

**Management of change:**
- No formal assessment of hazards introduced by out-of-sequence work
- Scaffolding was built for original plan, not for rework scenario
- No communication between shifts about modified work

**Procedure gaps:**
- No procedure for modifying scaffolding during work
- No requirement for fall protection plan when scaffolding modified
- Stop-work authority unclear

### Key Lessons from This Case

1. **Production pressure drives improvisation**: When schedule pressure exists, workers will find ways to work around obstacles, often without full hazard recognition.

2. **Management of change applies to work sequences**: Changing the planned sequence of work changes the hazards. Scaffolding designed for Plan A may not protect workers executing Plan B.

3. **Hazard recognition degrades under task load**: Workers carrying a heavy object have reduced capacity to recognize fall hazards. Design should assume degraded awareness during demanding tasks.

4. **"Temporary" hazards are still hazards**: The mental model of "it's just for a minute" reduces perceived risk, but the physical hazard is unchanged.
