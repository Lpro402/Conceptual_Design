# MPRO digital twins — architecture

## What makes these twins rather than simulations

A simulation answers "what would happen?". A digital twin is additionally
connected to its asset: it ingests the asset's telemetry, compares it with its
own model, quantifies how far it can be trusted, and feeds decisions back.
The MPRO twins are built around that loop, at the level the concept stage
allows — the "asset" is the software twin's simulated plant today, and the
same interfaces accept bench or field logs later.

## The twins and how they connect

| Twin | Code | Web | Role |
|---|---|---|---|
| General / system twin | `src/mpro/baseline.json`, `src/mpro/baseline.py` | `docs/hub.html`, 3D system view in the chemical twin | One design baseline shared by every twin |
| HMI screen twin | `src/mpro/software_twin/hmi.py` | `docs/?view=lcd` | Physical suitcase display; operator messages of the Configuration 2 HMI table |
| Chemical twin | `src/mpro/chemical_twin/` | `docs/chemical-twin/` | Cartridge plant: electrochemistry, thermal, H₂, mass balance |
| Software twin | `src/mpro/software_twin/` | `docs/` (HMI) | Configuration 2 mission logic + independent safety supervisor |
| Control twin | `src/mpro/control_twin/` | `docs/control-twin/` | Power/current, LIC DC-link and thermal loops |
| Integration twin | — | `docs/integration-twin/` | Integration levels L0–L3, threads T1–T7, gates |
| Twin services | `src/mpro/twin_services/` | layers panel in the chemical twin | Monitoring, diagnostics, prognostics, prescriptive, UQ |

```text
baseline.json ─┬─► chemical_twin ◄── step(power, airflow) ── software_twin ──► HMI / scenarios
               │        │ telemetry                              ▲
               ├─► control_twin (loops set airflow, power, V_DC) ┘
               └─► twin_services (assess telemetry → findings, prognosis, prescriptions; UQ emulator)
```

## Four capability layers (`twin_services/layers.py`)

1. **Monitoring** — every channel against its envelope (80–110 V, Boost
   current, 52 / 55 / 65 °C thresholds).
2. **Diagnostics** — residuals between measured and model-predicted stack
   voltage, and time-domain features (slope, RMS, kurtosis) of temperature and
   H₂, classify deviations: high resistance / air starvation, degraded cooling
   (blower 370 / tunnel 390), corrosion drift.
3. **Prognostics** — energy still to deliver, minutes to 3 kWh, minutes to the
   derating threshold, remaining aluminium margin.
4. **Prescriptive** — Boost permission, hold 10 kW, cold-start warm-up, clear
   cargo from the vents, early ramp-down, or hand over to the safety supervisor.

## Trust: validation and uncertainty (`twin_services/uq.py`)

Validation of a twin is treated as a statistical process: trust in the data,
in the model and in the update step. The chemical twin therefore ships with:

- **Validation metric** — mean squared error between measured and simulated
  series (`validation_mse`), ready for the first bench logs.
- **Space-filling design** — Latin hypercube over seven uncertain factors
  (coulombic and conversion efficiency, usable aluminium, heat fraction,
  cooling capability, ambient temperature, water volume).
- **Gaussian-process emulator** — Kriging fit of each response, checked by
  leave-one-out error, then Monte Carlo propagation to the probability of
  meeting the 3 kWh event, the thermal limit and the duration target.
- **Next-experiment choice** — expected improvement proposes the most
  informative next setting (a Bayesian-optimisation step), so tests are spent
  where the model is least certain.

`python apps/chemical_twin_study.py` runs the full study and writes figures
and a JSON summary to `exports/chemical_twin/`.

## Findings the twins surface today

- **Cold start** — at −25 °C the low stack voltage demands more current per
  kWh and the usable aluminium runs out near 2.5 kWh unless the cartridge
  warms up first; the thermal loop throttles airflow for self-heating.
- **Hot ambient** — at +50 °C Boost is disabled and the event derates, taking
  about 30 minutes for 3 kWh.
- **Heat balance (open item)** — the calibrated plant reproduces the documented
  35–50 °C envelope, while the first-principles check
  (`chemistry.energy_balance_check`, thermoneutral ≈ 2.93 V per cell) reports
  reaction heat of the same order as the electrical output. The detailed
  electrochemical-thermal model should close this gap.
- **DC link** — without the LIC the 10 → 12 kW step dips the bus about 1.3 V;
  the LIC cuts the dip by ~40 % and returns to a small average current.

## Reference

The layer structure, the validation-as-statistics view and the emulator
workflow follow the digital-twin lecture of the data-science course
(R. S. Kenett). No course material is reproduced in this repository.
