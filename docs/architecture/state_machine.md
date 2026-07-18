# Deterministic state machine

## Nominal event

```text
STANDBY
  -> WAKE_UP_SELF_TEST
  -> VEHICLE_CONNECTION
  -> CASSETTE_SELECTION
  -> WATER_ACTIVATION
  -> PRIMING
  -> PRE_CHARGE
  -> POWER_TRANSFER [optional DERATING]
  -> RAMP_DOWN
  -> PURGE_COOLDOWN
  -> READY | SERVICE_REQUIRED
```

Every transition is exposed as a named controller method and checks its allowed
source state. `POWER_TRANSFER` also checks self-test, EV connection, HVIL,
isolation, cassette, water, priming, simulated thermal/fluid conditions, and
pre-charge.

## Fault route

```text
ANY OPERATING STATE
  -> EMERGENCY_SHUTDOWN
  -> FAULT_LOCKED
  -> demonstrator reset only
```

The dashboard user advances from `EMERGENCY_SHUTDOWN` to `FAULT_LOCKED` only
after the simulated outputs have already been forced safe. This separation
makes the protective action visible during demonstrations.

## Cassette lifecycle

```text
DRY_READY -> SELECTED -> ACTIVATING -> ACTIVE -> SPENT
                                         \-> FAULTED
```

Only one cassette may be selected or active. A completed event makes that
cassette `SPENT`; after the third completed event, purge ends in
`SERVICE_REQUIRED`.

