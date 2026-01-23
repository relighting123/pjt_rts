# DBR Manufacturing Scheduler Simulator

A Python-based manufacturing simulation engine based on **DBR (Drum-Buffer-Rope)** theory, designed to optimize production flow, manage bottlenecks, and maintain a steady production heartbeat (**Takt Time**).

## 🚀 Key Features

- **Modular Architecture**: Complete separation between the Simulation Engine (`simulator.py`) and the Scheduling Logic (`scheduler.py`).
- **DBR Implementation**:
  - **Drum**: Automated bottleneck identification based on resource load.
  - **Buffer**: WIP protection for the bottleneck to prevent starvation.
  - **Rope**: Material release control based on the bottleneck's pace.
- **Takt-based Pacing**: Smart gating mechanism to ensure steady production flow over a 22-hour horizon, preventing early "dogpiling" and excessive WIP.
- **Changeover Management**: Handles complex setup rules between different product/process combinations.
- **Detailed Reporting**: Real-time allocation logs, Capacity calculations, and final performance metrics (Achievement Rate, Utilization, Changeover Count).

## 📁 Project Structure

```text
├── data/
│   ├── equipment_inventory.json   # Machine counts per model
│   ├── equipment_capability.json  # Process feasibility and ST (Standard Time)
│   ├── plan_wip.json              # Production targets and initial WIP
│   └── changeover_rules.json      # Setup time rules
├── scheduler.py                   # DBR Scheduling logic
├── simulator.py                   # Time-stepped simulation engine
└── README.md                      # Project documentation
```

## 🛠️ How to Run

1. **Prerequisites**: Python 3.8+ (No external dependencies required for the base simulator).
2. **Execute Simulation**:
   ```bash
   python simulator.py
   ```

## 📊 Example Output

```text
==================== DBR Simulation Started ====================
time   | product    | process    | target(achieved) | wip    | capa
-------------------------------------------------------------------
0      | Fast_A     | Step_10    | 0                | 36     | 1.0
...
[Terminated] All final production targets met at 1390 minutes.

=== Final Summary ===
Overall Product Achievement: 100.00%
Equipment Utilization:       38.85%
Total Changeover Count:      54
```

## 🧠 Core Logic: Takt-based Balancing

The simulator uses a **Takt Gate** in the scheduler:
- It calculates the required heartbeat: `Deadline (1320 min) / Target Quantity`.
- It restricts production starts to match this pulse cumulative-wise.
- This results in a stable, low-WIP flow instead of a last-minute rush, which is ideal for JIT (Just-In-Time) manufacturing environments.
