# DBR Simulator Walkthrough

I have implemented a manufacturing scheduling simulator based on DBR (Drum-Buffer-Rope) theory.

## Key Features

1.  **Modular Architecture**:
    - **`scheduler.py`**: Separates the DBR logic from the simulation environment. Defines a `BaseScheduler` interface, making it easy to swap with other algorithms (e.g., RL, Heuristics).
    - **`simulator.py`**: A generic time-stepped execution engine that handles equipment states, WIP, and reporting.
2.  **DBR Logic**:
    - **Drum**: Automatically identifies the bottleneck process based on load (Plan × ST).
    - **Buffer**: Maintains a WIP buffer before the Drum to ensure it never starves.
    - **Rope**: Controls material release at the first step (`Step_10`) based on the Drum's processing pace and buffer status.
3.  **JIT Backward Scheduling**:
    - Logic calculates the latest possible start window to meet the 22-hour deadline.
    - Prevents premature upstream production and keeps WIP as low as possible.
4.  **Final Target Orientation**:
    - Upstream processes only work if the total system potential (Finished + Downstream WIP) is less than the final goal.
5.  **Summary Metrics**: Reports Planning Achievement Rate, Equipment Utilization, and Total Changeover count.

### Verification Results

The simulation now terminates once the final process targets are met. With JIT Backward Scheduling, production is delayed until the latest possible window (around T=1080 for Step_30), preventing unnecessary WIP accumulation.

#### Simulation Log (Excerpt)
```text
...
1075   | Fast_A     | Step_30    | Basic      | 0        | 0        | 0            | 36     | 0.0
...
1080   | Fast_A     | Step_30    | Basic      | 0        | 2        | 0            | 36     | 0.0
...
1090   | Fast_A     | Step_30    | Basic      | 2        | 0        | 0            | 36     | 2.0
...
1295   | Fast_A     | Step_30    | Basic      | 2        | 0        | 36           | 0      | 2.0

[Terminated] All final production targets met at 1295 minutes.
```

#### Final Summary
- **Target Achievement**: 100.0% (36/36)
- **Utilization**: 13.90% (JIT efficiency)
- **Changeover Count**: 2

> [!NOTE]
> The utilization is lower by design. In a JIT system, we only work when necessary to meet the deadline, minimizing waste and WIP.

### Console Output Snippet

```text
==================== DBR Simulation Started ====================
time   | product    | process    | model      | active   | target   | prod(after)  | wip    | capa  
----------------------------------------------------------------------------------------------------
...
1075   | Fast_A     | Step_10    | Basic      | 0        | 0        | 0            | 36     | 0.0
1075   | Fast_A     | Step_20    | Basic      | 0        | 0        | 0            | 36     | 0.0
1075   | Fast_A     | Step_30    | Basic      | 0        | 0        | 0            | 36     | 0.0
----------------------------------------------------------------------------------------------------
1080   | Fast_A     | Step_10    | Basic      | 0        | 0        | 0            | 36     | 0.0
1080   | Fast_A     | Step_20    | Basic      | 0        | 0        | 0            | 36     | 0.0
1080   | Fast_A     | Step_30    | Basic      | 0        | 2        | 0            | 36     | 0.0
----------------------------------------------------------------------------------------------------
...
1295   | Fast_A     | Step_30    | Basic      | 2        | 0        | 36           | 0      | 2.0
----------------------------------------------------------------------------------------------------

[Terminated] All final production targets met at 1295 minutes.

=== Final Summary (Target Achievement per Product) ===
  Product Fast_A: 36/36 (100.0%)
  Product Heavy_B: 0/0 (100.0%)
------------------------------
Overall Product Achievement: 100.00%
Equipment Utilization:       13.90%
Total Changeover Count:      2
==============================
```

## Files Created/Modified
- [scheduler.py](file:///C:/Users/jaehw/Desktop/프로젝트/rl-rts/scheduler.py): Contains the DBR scheduling logic and JIT gate.
- [simulator.py](file:///C:/Users/jaehw/Desktop/프로젝트/rl-rts/simulator.py): The main simulation engine.
