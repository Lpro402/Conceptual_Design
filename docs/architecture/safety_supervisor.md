# Independent safety supervisor

## Intent

This module demonstrates architectural separation between normal mission
control and a protective override path. It is not a functional-safety design
and makes no SIL, ASIL, diagnostic-coverage, timing, redundancy, or compliance
claim.

## Simulated faults

- E-Stop
- HVIL open
- isolation fault
- overtemperature
- hydrogen alarm
- leak
- abnormal pressure
- loss of electrolyte flow
- pump failure
- fan failure
- contactor feedback mismatch

## Protective response

A critical injected fault immediately:

1. disables simulated conversion;
2. opens simulated input and output contactors;
3. asserts simulated gate disable;
4. closes simulated water admission;
5. stops the simulated pump;
6. retains ventilation/purge when the simulated fan is available;
7. latches the fault;
8. writes a timestamped critical log entry.

The main controller cannot resume mission sequencing while a fault is latched.
Reset exists only to make repeated demonstrations convenient; a real system
would require an engineered fault-clear and service policy.

