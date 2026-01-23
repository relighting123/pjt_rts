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
2.  **Changeover Management**: Applies setup times defined in `changeover_rules.json` when switching between product/process combinations.
3.  **Filtered Logging**: Displays machine allocation counts at T=0, changeover start points, and T=1440 as requested.
4.  **Summary Metrics**: Reports Planning Achievement Rate, Equipment Utilization, and Total Changeover count.

## Execution Results

The simulator was run using the provided data in the `data/` directory.

### Console Output Snippet

```text
==================== DBR Simulation Started ====================
time   | product    | process    | model      | active   | target   | prod(after)  | wip    | capa  
----------------------------------------------------------------------------------------------------
0      | Fast_A     | Step_10    | Basic      | 0        | 0        | 0            | 36     | 0.0   
0      | Fast_A     | Step_20    | Basic      | 0        | 0        | 0            | 36     | 0.0   
0      | Fast_A     | Step_30    | Basic      | 0        | 2        | 0            | 34     | 0.0   
----------------------------------------------------------------------------------------------------
...
----------------------------------------------------------------------------------------------------
215    | Fast_A     | Step_10    | Basic      | 0        | 0        | 0            | 36     | 0.0   
215    | Fast_A     | Step_20    | Basic      | 0        | 0        | 0            | 36     | 0.0   
215    | Fast_A     | Step_30    | Basic      | 2        | 0        | 36           | 0      | 2.0   
----------------------------------------------------------------------------------------------------

[Terminated] All final production targets met at 215 minutes.

=== Final Summary (Target Achievement per Product) ===
  Product Fast_A: 36/36 (100.0%)
  Product Heavy_B: 0/0 (100.0%)
------------------------------
Overall Product Achievement: 100.00%
Equipment Utilization:       83.72%
Total Changeover Count:      2
==============================
```

## Files Created/Modified
- [scheduler.py](file:///C:/Users/jaehw/Desktop/프로젝트/rl-rts/scheduler.py): Contains the DBR scheduling logic and the abstract interface.
- [simulator.py](file:///C:/Users/jaehw/Desktop/프로젝트/rl-rts/simulator.py): The main simulation engine, refactored for modularity.
