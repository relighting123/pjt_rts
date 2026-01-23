# DBR Simulator Presentation Storyboard

## Slide 1: Title
**Title**: Intelligent Manufacturing Control through DBR Simulation
**Content**:
- Decoupled Simulator & Flow-based Scheduler
- Optimizing Throughput & Minimizing Changeovers
- Developed by Antigravity AI

## Slide 2: The Problem: "The Dogpiling Effect"
**Key Visual**: Illustration of all machines moving to a single bottleneck process.
**Description**:
- Machines follow immediate WIP blindly.
- Result: Excessive Changeovers and broken production flow.
- Achievement suffers when upstream WIP is ignored.

## Slide 3: The Solution: DBR Flow Logic
**Key Concepts**:
- **Drum**: Identify the heartbeat of the factory.
- **Rope**: Material release controlled by the heartbeat.
- **Flow Scoring**: Awareness of **Future WIP** and **In-process WIP**.
- Stay at station to maintain flow instead of jumping for short-term gains.

## Slide 4: Flow Scoring Algorithm
**Formula**: `Score = Potential - Penalty + Bonus`
**Breakdown**:
- **Potential**: Immediate WIP (Weight 10) + Future WIP (Weight 5).
- **Resident Bonus**: Strong incentive (+200) to keep stable positions.
- **Move Penalty**: Costly setups discourage jumping.
- **Balance Penalty**: Self-organizing distribution across the whole line.

## Slide 5: Efficiency Gains
**Comparison**:
| Metric | Bunching Scheduler | DBR Flow Scheduler |
| :--- | :--- | :--- |
| Achievement | 100% | 100% |
| Changeovers | 13+ | **3** |
| Stability | Low (Constant jumping) | **High (Steady flow)** |

## Slide 6: Continuous Monitoring (I/O)
**Features**:
- Real-time 10-column Status Table.
- **Allocated (Active)**: Shows total capacity committed to a process.
- **CAPA**: Accurate 10-min throughput projection.
- **Early Exit**: Simulation terminates automatically when work is done.

## Slide 7: Future Vision
**Content**:
- Digital Twin integration.
- Reinforcement Learning for dynamic policy generation.
- Scalability to complex, multi-product global supply chains.
