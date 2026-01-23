# DBR Simulator & Flow-based Scheduler Technical Specification

## 1. Overview
This system is a time-stepped manufacturing simulator based on the **DBR (Drum-Buffer-Rope)** methodology. It is designed to optimize production flow, minimize changeovers, and maximize equipment utilization by making intelligent, flow-aware scheduling decisions.

## 2. System Architecture
The system is decoupled into two main components:
- **`DBRSimulator`**: Manages the time-stepped environment, equipment states, WIP tracking, and I/O.
- **`DBRScheduler`**: An interchangeable logic module that decides which equipment should perform which task at any given idle moment.

---

## 3. Core Logic: Flow-based DBR Scheduling
The scheduler utilizes a **Flow-based scoring algorithm** with **Future WIP Awareness**.

### A. Drum-Buffer-Rope (DBR) Mechanics
- **Drum (Bottleneck)**: Identifies the process with the highest load (`Target * Standard Time`) as the Drum. All other processes synchronize with the Drum's pace.
- **Final Target Orientation**: Upstream processes are driven by the **final process's plan**. A process only works if the final target is not yet satisfied by (Finished Goods + Units currently downstream). This creates a natural "Pull" system.
- **Rope**: Controls the release of materials to ensure the Drum and final processes are never starved, essentially managing the total system inventory level.

### B. Scoring Algorithm (The "Flow" Engine)
For each idle equipment, the scheduler calculates a `Score` for all capable tasks:
`Score = FlowValue + ResidentBonus - MovePenalty - BalancePenalty + PriorityBonus`

1.  **Flow Value (Potential)**:
    - **Immediate WIP**: High weight for work currently available.
    - **Future WIP**: WIP in upstream material buffers.
    - **In-process WIP**: WIP currently being processed by machines in upstream stages.
    - *Logic: If `Immediate + Future > 0`, the station is considered active.*
2.  **Resident Bonus**:
    - A significant bonus (+200) given if the equipment is already at the station. This encourages "staying and waiting" for flow rather than jumping to other stations.
3.  **Move Penalty**:
    - Deducted based on `Changeover Time * 15`. Prevents jumping for small, transient WIP gains.
4.  **Balance Penalty**:
    - A heavy penalty (-500) per already assigned machine to ensure units are spread across the line (Parallelism) rather than dogpiling on a single station.

---

## 4. Simulation Engine Details
### State Machine (Equipment)
- **IDLE**: Waiting for assignment.
- **CHANGEOVER**: Moving/Setting up for a new task.
- **WORKING**: Actively processing units.

### Time Step (1 minute)
1.  **Step Equipment**: Decrement `remaining_time`. If finished, increment `achieved` and transfer WIP to the next step's buffer.
2.  **Collect Idle Units**: Gather all units in `IDLE` state.
3.  **Dynamic Scheduling**: Call `scheduler.select_tasks()` with the current global context (WIP, Achieving, Assignments).
4.  **Execute Assignments**: Trigger work or changeover for assigned units.
5.  **Logging**: Print status only when major state changes occur (Activity tracking).

### Early Exit Condition
The simulator monitors the global state and terminates before the `total_minutes` limit if:
- `All WIP == 0`
- `All Equipment statuses == IDLE`
- `All Production Targets reached`

---

## 5. Performance Metrics
- **Achievement Rate**: (Achieved / Plan) * 100 per process.
- **Equipment Utilization**: (Total Working Time / (Num Equipments * Total Elapsed Time)) * 100.
- **Changeover Count**: Total number of setup operations performed.
- **CAPA (Capacity)**: `(Allocated Machines * 10) / Standard Time` (10-minute projection).

## 6. Development Roadmap
- [ ] Support for multiple model types per process with setup matrix.
- [ ] Non-linear process routing (Branching/Merging).
- [ ] Machine breakdown (MTBF/MTTR) modeling.
- [ ] Integration with Reinforcement Learning (RL) for dynamic policy optimization.
