# Configuration 2 state machine

Implemented in `src/mpro/software_twin/controller.py`, mirrored by the web HMI
(`docs/assets/app.js`). The numbers in brackets refer to the Configuration 2
design changes.

## Nominal mission

```text
SYSTEM_STANDBY        [9.1] asleep; wakes only from USER_WAKE, DBIT_TIMER, SERVICE_PORT
  -> SELF_TEST        [9.1] temperature-compensated thresholds
  -> ENVIRONMENT_CHECK[4.1, 5.2] enclosed space blocks; wall needs the diffuser on the open side;
                       obstructed vents require clearing cargo and a re-check
  -> AWAIT_DEPLOY     [2.1] CABLE_DEPLOYED + VENT_DEPLOYED + explicit driver confirmation
  -> AWAIT_CONNECT    [8.1] HVIL continuity over a check window, CP level, IMD (warning / block)
  -> EV_HANDSHAKE     [8.1] ISO 15118; communication failure only -> DIN 70121
  -> FILL_SESSION     [1.1, 1.2] batch pouring into chamber 220, cartridge valve closed
  -> CONFIRM_ACTIVATION  irreversible confirmation
  -> WATER_ADMISSION  reaction clock starts at real admission
  -> PRIME_FLOW_CHECK KOH dissolution, flow, air, gas path, thermal readiness (≤ 60 s)
  -> PRECHARGE
  -> ACTIVE_POWER     10 kW; 12 kW Boost only with thermal margin  <-> DERATED
  -> RAMP_DOWN
  -> PURGE_COOLDOWN   cartridge SPENT, products retained
  -> SAFE_TO_DISCONNECT
  -> SYSTEM_STANDBY | SERVICE_REQUIRED (after the third event)
```

Correctable conditions (enclosed space, missing water, HVIL window failure, …)
keep the current state and publish a `blocker` message; they are not faults.

## Fill session rules

- Pouring may pause and resume without cancelling the session.
- Transition to `WATER_ADMISSION` requires 1.8–2.2 L measured, the activation
  confirmation and every safety permission. Above 2.2 L the fill is rejected
  until chamber 220 is drained.
- A controller restart invalidates the measurement: no automatic wetting,
  re-measure and re-confirm.
- `STOP` / cancel before wetting returns the cartridge to `DRY_READY` and the
  system to `SAFE_TO_DISCONNECT` — nothing was energised.

## Fault routes

```text
before wetting:  fault -> FAULT_LOCKED                      (cartridge stays DRY_READY)
after wetting:   fault -> POWER_ISOLATION -> PURGE_COOLDOWN -> FAULT_LOCKED
```

## Cartridge lifecycle

```text
DRY_READY -> SELECTED -> ACTIVATING -> ACTIVE -> SPENT
    ^           |                        \-> FAULTED
    +-----------+  cancel before wetting
```

Only one cartridge may be selected or active. A wetted cartridge never returns
to `DRY_READY`.
