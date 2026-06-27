# STPA Worked Examples

This reference provides concrete examples of STPA analysis across different domains.

## Example 1: Adaptive Cruise Control (ACC)

### Step 1: Define Purpose

**Losses:**
- L-1: Loss of life or serious injury to people
- L-2: Damage to the vehicle or objects outside the vehicle

**System-Level Hazards:**
- H-1: Vehicle does not maintain safe distance from obstacles [L-1, L-2]
- H-2: Vehicle speed inappropriate for conditions [L-1, L-2]
- H-3: Vehicle unexpectedly accelerates or decelerates [L-1, L-2]

**System Boundary:** Vehicle with ACC system, including driver, ACC controller, braking system, propulsion system.

### Step 2: Control Structure

```
┌─────────────────────────────────────────────────────────┐
│                        Driver                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Brake, Accelerate, Steer, Shift                 │    │
│  │ On/Off/Cancel, Inc/Dec speed, Inc/Dec distance  │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│                     ▼                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Adaptive Cruise Control (ACC)           │    │
│  │                                                  │    │
│  │  Feedback: ACC Mode, Target speed/distance      │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                    │
│                     │ Accelerate, Brake                  │
│                     ▼                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │    Braking System    │    Propulsion System     │    │
│  │                                                  │    │
│  │  Feedback: Vehicle speed, Distance, Override    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Control Actions:**
- Driver → ACC: On, Off, Cancel, Increase speed, Decrease speed, Increase distance, Decrease distance
- Driver → Vehicle: Brake, Accelerate, Steer, Shift
- ACC → Braking System: Brake command
- ACC → Propulsion System: Accelerate command

**Feedback:**
- ACC → Driver: ACC Mode (On/Off/Standby), Target speed, Target distance (visual display)
- Vehicle → ACC: Vehicle speed, Distance to obstacle, Override detected

### Step 3: Unsafe Control Actions

**Control Action: ACC provides Brake command**

| Not Provided | Providing Causes Hazard | Too Early/Late | Stopped Too Soon/Applied Too Long |
|--------------|------------------------|----------------|-----------------------------------|
| UCA-1: ACC does not provide brake when obstacle is detected and closing distance is below threshold [H-1] | UCA-2: ACC provides brake when no obstacle ahead and road is clear [H-3] | UCA-3: ACC provides brake too late when obstacle is detected, insufficient time to stop [H-1] | UCA-4: ACC stops braking too soon, before safe distance achieved [H-1] |
| | UCA-5: ACC provides brake when driver is accelerating to pass [H-3] | | UCA-5: ACC applies brake too long, causing rear-end collision from following vehicle [H-2] |

**Control Action: ACC provides Accelerate command**

| Not Provided | Providing Causes Hazard | Too Early/Late | Stopped Too Soon/Applied Too Long |
|--------------|------------------------|----------------|-----------------------------------|
| UCA-6: ACC does not accelerate when gap to vehicle ahead has increased beyond target [H-2] | UCA-7: ACC provides accelerate when obstacle is ahead and distance is below safe threshold [H-1] | UCA-8: ACC provides accelerate too early after obstacle clears, before safe [H-1] | UCA-9: ACC applies acceleration too long, exceeding speed limit or safe speed [H-2] |

### Step 4: Loss Scenarios (for UCA-1)

**UCA-1: ACC does not provide brake when obstacle is detected and closing distance is below threshold**

**Scenario 1 - Sensor failure:**
The distance sensor fails or provides incorrect readings, causing ACC's process model to show no obstacle when one exists. ACC does not command braking because it believes the path is clear.

**Scenario 2 - Sensor limitation:**
The obstacle is not detectable by the sensor (e.g., pedestrian in low-light, motorcycle at edge of sensor cone, stationary object not recognized). ACC's process model is never updated with obstacle presence.

**Scenario 3 - Processing delay:**
Obstacle is detected but processing delays cause brake command to be issued after safe braking distance has passed. The control action is effectively "not provided" in time.

**Scenario 4 - Algorithm flaw:**
The ACC algorithm has a flaw in threshold calculation—it computes a required braking distance that is shorter than physical reality, so it doesn't command braking soon enough.

**Safety Requirements derived:**
- SR-1: ACC shall detect obstacles within X meters with Y% reliability
- SR-2: ACC shall fail-safe to driver control if sensor data is unavailable or inconsistent
- SR-3: ACC processing latency shall not exceed Z milliseconds
- SR-4: Braking distance calculations shall include safety margin of W%

---

## Example 2: Patient-Controlled Analgesia (PCA) Pump

### Step 1: Define Purpose

**Losses:**
- L-1: Loss of life or serious injury to patient
- L-2: Patient's pain is not relieved
- L-3: Loss of protected patient or proprietary hospital information
- L-4: Financial loss or loss of hospital reputation

**System-Level Hazards:**
- H-1: Patient has opioid overdose [L-1, L-4]
- H-2: Patient has opioid underdose [L-2]
- H-3: Patient information disclosed to unauthorized parties [L-3, L-4]

**System Boundary:** PCA pump system including pump hardware/software, clinician, patient, hospital network.

### Step 2: Control Structure (Simplified)

```
┌──────────────────────────────────────────────────────────┐
│                      Clinician                           │
│                                                          │
│  Control: Dose limits, drug selection, lockout interval  │
│  Feedback: Pump status, dosing history, patient state    │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    PCA Pump Controller                   │
│                                                          │
│  Contains: Dose calculation algorithm, safety limits,    │
│            patient/drug database                         │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ Deliver dose
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    Infusion Mechanism                    │
│                                                          │
│  Feedback: Flow rate, volume delivered, occlusion        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│                       Patient                            │
│                                                          │
│  Control: Bolus request button                           │
│  Feedback: Pain level, respiratory rate, consciousness   │
└──────────────────────────────────────────────────────────┘
```

### Step 3: Unsafe Control Actions

**Control Action: PCA Pump delivers dose**

| Not Provided | Providing Causes Hazard | Too Early/Late | Wrong Duration |
|--------------|------------------------|----------------|----------------|
| UCA-P1: Pump does not deliver dose when patient requests and is within safe parameters [H-2] | UCA-P2: Pump delivers dose when patient has already received maximum allowed in lockout period [H-1] | UCA-P3: Pump delivers dose too early, before lockout period expires [H-1] | UCA-P4: Pump delivers dose for too long, exceeding prescribed amount [H-1] |
| | UCA-P5: Pump delivers dose when drug concentration is incorrect (wrong drug loaded) [H-1] | | |
| | UCA-P6: Pump delivers dose when patient shows signs of respiratory depression [H-1] | | |

### Step 4: Loss Scenarios (for UCA-P2)

**UCA-P2: Pump delivers dose when patient has already received maximum allowed in lockout period**

**Scenario 1 - Clock/timer failure:**
The pump's internal clock fails or drifts, causing incorrect calculation of when the lockout period expires. The pump's process model shows lockout has passed when it hasn't.

**Scenario 2 - Manual override without safeguard:**
Clinician uses override to deliver additional dose but system doesn't properly track this in the cumulative dose calculation. Next patient request is approved despite exceeding limits.

**Scenario 3 - Database error:**
Patient's dosing history is corrupted or lost (power failure, software bug), causing pump to reset cumulative dose to zero. Subsequent requests are approved as if no prior doses given.

**Scenario 4 - Wrong patient parameters:**
Pump is programmed with wrong patient weight or wrong drug concentration. Calculated "safe" dose is actually an overdose for this specific patient.

**Safety Requirements derived:**
- SR-P1: Pump shall maintain dosing history in non-volatile memory
- SR-P2: Pump shall require positive confirmation before override
- SR-P3: Pump shall verify patient identity before delivering dose
- SR-P4: Pump shall require independent verification of drug concentration

---

## Example 3: Autonomous Vehicle Test Program

### Step 1: Define Purpose

**Losses:**
- L-1: Loss of life or serious injury (test driver, public, pedestrians)
- L-2: Damage to vehicle or property
- L-3: Loss of public trust in autonomous vehicle technology
- L-4: Regulatory or legal consequences

**System-Level Hazards:**
- H-1: Vehicle collides with obstacle, person, or other vehicle [L-1, L-2, L-3, L-4]
- H-2: Vehicle operates outside approved test conditions [L-1, L-3, L-4]
- H-3: Safety driver unable to take control when needed [L-1, L-2]

### Step 2: Control Structure (Organizational)

This example shows organizational control structure, not just technical:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Program Management                            │
│                                                                  │
│  Control: Go/No-Go decisions, resource allocation, test scope   │
│  Feedback: Test results, incident reports, safety metrics       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
┌───────────────────┐  ┌───────────────┐  ┌──────────────────┐
│  Engineering Team │  │     Legal     │  │    Trainers      │
│                   │  │               │  │                  │
│ - System Integr.  │  │ Go/No-Go on   │  │ Driver training  │
│ - Test Route Plan │  │ regulatory    │  │ and certification│
│ - Safety Engineers│  │ compliance    │  │                  │
│ - Post-drive Rev. │  │               │  │                  │
└─────────┬─────────┘  └───────────────┘  └────────┬─────────┘
          │                                         │
          │                                         │
          └──────────────────┬────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Safety Driver(s)                            │
│                                                                  │
│  Control: Override (brake, steer), engagement/disengagement     │
│  Feedback: Vehicle behavior, environment, system status         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Autonomous Vehicle                            │
│                                                                  │
│  Feedback: Sensor data, planned actions, confidence levels      │
└─────────────────────────────────────────────────────────────────┘
```

### Step 3: Unsafe Control Actions (Organizational Level)

**Control Action: Program Management provides Go decision**

| Not Provided | Providing Causes Hazard | Too Early/Late | Wrong Duration |
|--------------|------------------------|----------------|----------------|
| UCA-M1: Management does not provide Go when system is ready and conditions are safe [L-4] | UCA-M2: Management provides Go when known safety defects exist [H-1, H-2] | UCA-M3: Management provides Go before safety review complete [H-1] | N/A |
| | UCA-M4: Management provides Go when drivers not adequately trained [H-3] | | |
| | UCA-M5: Management provides Go when test conditions exceed validated envelope [H-2] | | |

**Control Action: Safety Driver provides override**

| Not Provided | Providing Causes Hazard | Too Early/Late | Wrong Duration |
|--------------|------------------------|----------------|----------------|
| UCA-D1: Driver does not override when vehicle approaching hazard [H-1] | UCA-D2: Driver overrides when system correctly handling situation, causing loss of control [H-1] | UCA-D3: Driver overrides too late to prevent collision [H-1] | UCA-D4: Driver releases override too soon, before situation resolved [H-1] |
| UCA-D5: Driver does not override when system behaves unexpectedly [H-1] | | | |

### Step 4: Loss Scenarios (for UCA-D1)

**UCA-D1: Driver does not override when vehicle approaching hazard**

**Scenario 1 - Attention/alertness:**
Driver is fatigued, distracted, or complacent after many uneventful miles. Driver's process model doesn't update with hazard presence quickly enough to initiate override.

**Scenario 2 - Trust in automation:**
Driver has learned to trust the system through many successful interventions. Driver's process model assumes system will handle hazard, delaying recognition that override is needed.

**Scenario 3 - Mode confusion:**
Driver believes system is in manual mode when it's actually in autonomous mode (or vice versa). Driver doesn't intervene because they believe they're already in control.

**Scenario 4 - Inadequate training:**
Driver not trained on this specific failure mode or hazard type. Driver doesn't recognize the pre-indicators that system is failing to respond appropriately.

**Scenario 5 - Information overload:**
Multiple alerts and system status changes overwhelm driver. Critical hazard information is lost in noise, preventing timely override.

**Safety Requirements derived:**
- SR-D1: Driver attention monitoring shall alert if driver appears inattentive
- SR-D2: System shall clearly indicate current mode at all times
- SR-D3: Training shall include specific failure mode recognition
- SR-D4: Critical hazard alerts shall be distinct from routine notifications
- SR-D5: Maximum continuous operation time shall be limited to X hours

---

## Key Patterns Across Examples

### Hazard Specification

Good hazards are:
- **System-level** (not component-level): "Vehicle violates minimum separation" not "Sensor fails"
- **States** (not events): "Patient has overdose" not "Pump delivers overdose"
- **Controllable**: Something the system can prevent

### UCA Context

Context is critical—the same action can be safe or unsafe depending on conditions:
- "ACC brakes" is safe when obstacle ahead, unsafe when clear road
- "Pump delivers dose" is safe within limits, unsafe when exceeded

### Scenario Categories

Most scenarios fall into:
1. **Controller doesn't know** (feedback missing, sensor failure, information not provided)
2. **Controller knows but acts wrong** (algorithm flaw, conflicting goals)
3. **Controller acts but action fails** (actuator failure, communication loss)
4. **Process model incorrect** (stale data, wrong assumptions, mode confusion)
