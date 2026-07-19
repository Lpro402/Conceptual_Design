# Software Tier-0 architecture

## Purpose

The software model demonstrates top-level responsibilities and deterministic
sequencing for an academic Metalyte PRO-MPRO concept. It deliberately avoids
RTOS, thread, embedded-driver, real-time, hardware, and CCS2 implementation
claims.

## Logical modules

| Module | Tier-0 responsibility |
|---|---|
| Main System Controller | Mission state, guarded transitions, coordination |
| Independent Safety Supervisor | Fault evaluation, latching, direct override |
| HMI Manager | State-specific user instruction |
| EV Communication Manager | Simulated connection and handshake boundary |
| Cassette & Reaction Manager | Three-cassette lifecycle and exclusivity |
| Power Control Manager | Simulated pre-charge, converter, contactors, shutdown |
| Thermal & Fluid Manager | Simulated water, flow, fan, vent, purge |
| Service & Logging Manager | Timestamped event history |
| Simulated HAL | Sensor snapshots and actuator-command representation |

## Authority split

The main controller owns mission progression but cannot clear a safety latch.
The safety supervisor holds a direct reference to the power and thermal/fluid
managers, allowing it to command safe simulated outputs without relying on the
mission controller to complete a normal transition.

## External engineering relationships

- Mechanical Tier 0 provides packaging, HMI location, cartridge access, and
  deployment context.
- Electronic Tier 0 provides conceptual power isolation, sensing, actuator,
  and communication responsibilities.
- Electrochemical Tier 0 provides cassette lifecycle and reaction constraints.
- Thermal Tier 0 provides future limits for flow, purge, cooling, and derating.

All present numeric values are simulated placeholders.

## Demonstration surfaces

Two user interfaces express this architecture without changing its scope:

- The static English HMI in `docs/` is the public, report-ready system view.
  It provides guided operation, live presentation values, fault injection,
  safety outputs, event history, and service-readiness visualization.
- The Streamlit application in `software_demo/` is the executable Python
  engineering reference used by the automated state-machine tests.

Neither interface controls real hardware, implements CCS2, or makes a
functional-safety claim.
