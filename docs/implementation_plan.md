# DBR Simulator Implementation Plan

Develop a manufacturing scheduling simulator based on DBR (Drum-Buffer-Rope) theory to optimize equipment allocation and achieve delivery plans.

## Proposed Changes

### Core Architecture: Modular Design
- [NEW] `scheduler.py`: Contains the `BaseScheduler` interface and the specific `DBRScheduler` implementation.
  - `BaseScheduler`: Abstract class defining how to select tasks for idle machines.
  - `DBRScheduler`: Implementation of Drum-Buffer-Rope logic.
- [MODIFY] `simulator.py`: Refactored to act as a pure emission/execution engine.
  - Accepts any object that implements `BaseScheduler`.
  - Manages time-steps, machine states, and inventory.
  - Responsible for reporting and logging based on simulation events.

### Algorithm: DBR (Drum-Buffer-Rope)
- **Drum**: Identify the bottleneck process (highest load).
- **Buffer**: Maintain a time-based buffer before the Drum and before Shipping.
- **Rope**: Control the release of raw materials (Step_10) and pacing of all stages.
  - **Takt-based Pacing (Steady Flow)**:
    - **Takt Time** = `22h (1320m) / Total Target`.
    - **Pacing Gate**: A station only starts a new unit if `(Achieved + Running) < (CurrentTime / TaktTime + 1)`.
    - Machines only begin work according to this steady "pulse", ensuring no dogpiling at any stage.
  - **Inflow Assumption**: Upstream WIP for Step_30 is assumed to arrive at the same Takt interval.
  - **Final Target Orientation**: Upstream processes produce based on the **final process's plan**, ensuring enough material for the ultimate goal.
  - **Move Penalty**: Changeovers are only allowed if another station is critical (Drum starving) and current station has 0 value.

### Output and Logging
- Implement a logging system that captures:
  - Initial state (T=0).
  - States at points of equipment changeover.
  - Final state (T=1440).
- Detailed Table Columns:
  - `time`, `product`, `process`, `model`, `active`, `target`, `prod(after)`, `wip`, `capa`.
  - `capa` = (Active Machines * 10) / Standard Time.
- Summary report including:
  - Planning Achievement Rate (%)
  - Equipment Utilization (%)
  - Total Changeover Count

## Verification Plan

### Automated Verification
- Run the simulator using the provided JSON data.
- Check if the console output matches the user's requirements (Start, Changeover, End logs).
- Verify that terminal outputs the final summary with Achievement Rate, Utilization, and Changeover count.

### Manual Verification
- Review the logs to ensure DBR logic is applied (e.g., release at Step_10 is throttled by the Drum).
- Validate that changeover times are correctly applied according to `changeover_rules.json`.
