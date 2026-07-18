# ADR-001: Limit the implementation to a software concept demonstrator

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

The project needs a tangible illustration of Software Tier 0 before product
tree, formal interfaces, ICD, N-squared, Tier 1, COTS, and detailed design.
Implementing real firmware or vehicle communication would imply unsupported
requirements and safety claims.

## Decision

Build a local Python/Streamlit demonstrator with deterministic state machines,
simulated hardware, manual fault injection, and automated behavioral tests.
Maintain an independent conceptual safety supervisor. Mark every threshold and
measurement as a simulated placeholder.

## Consequences

- The model can support presentations, architecture discussion, and test-case
  development.
- It cannot validate hardware, electrochemistry, thermal behavior, CCS2, or
  functional safety.
- The code structure is temporary repository organization, not a product tree.
- Production firmware, RTOS, embedded drivers, and real protocols remain out
  of scope.

