"""The four capability layers of the MPRO digital twin.

A digital twin is more than a simulation: it is fed by the asset's telemetry,
compares it with the model, and returns decisions. The course framework names
four increasing capabilities, implemented here for the active cartridge:

1. Monitoring   — is every measured value inside its envelope right now?
2. Diagnostics  — why does the asset deviate from the model (residual analysis)?
3. Prognostics  — what will happen next (energy, time-to-threshold)?
4. Prescriptive — what should the controller or operator do about it?

Inputs are plain telemetry dictionaries, so the layers serve the software twin,
the chemical twin and recorded logs alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from mpro import baseline
from mpro.chemical_twin import CartridgePlant, PlantParameters
from mpro.chemical_twin.plant import THERMAL_SETPOINT_C

Telemetry = dict[str, float]


@dataclass(frozen=True)
class Finding:
    layer: str
    code: str
    severity: str  # INFO | WARNING | CRITICAL
    message: str


# ----------------------------------------------------------------- 1. monitoring
def monitor(sample: Telemetry) -> list[Finding]:
    op, th = baseline.load()["operating_point"], baseline.load()["thermal"]
    findings = []
    v = sample.get("voltage_v", 0.0)
    if sample.get("current_a", 0.0) > 1.0 and not op["stack_voltage_envelope_v"][0] <= v <= op["stack_voltage_envelope_v"][1]:
        findings.append(Finding("monitoring", "V_ENVELOPE", "WARNING", f"Stack voltage {v:.1f} V is outside 80–110 V"))
    if sample.get("current_a", 0.0) > op["stack_current_boost_a"][1]:
        findings.append(Finding("monitoring", "I_LIMIT", "WARNING", f"Stack current {sample['current_a']:.0f} A exceeds the Boost envelope"))
    t = sample.get("temperature_c", 25.0)
    if t >= th["shutdown_c"]:
        findings.append(Finding("monitoring", "T_SHUTDOWN", "CRITICAL", f"Core {t:.1f} °C ≥ shutdown threshold"))
    elif t >= th["derate_c"]:
        findings.append(Finding("monitoring", "T_DERATE", "WARNING", f"Core {t:.1f} °C ≥ derating threshold"))
    elif t >= th["boost_disable_c"]:
        findings.append(Finding("monitoring", "T_BOOST_OFF", "INFO", f"Core {t:.1f} °C: Boost disabled"))
    return findings


# ---------------------------------------------------------------- 2. diagnostics
def features(series: np.ndarray) -> dict[str, float]:
    """Time-domain condition features, as used for fault classification."""
    centred = series - series.mean()
    rms = float(np.sqrt(np.mean(centred ** 2)))
    return {
        "mean": float(series.mean()),
        "rms": rms,
        "peak_to_peak": float(np.ptp(series)),
        "slope_per_min": float(np.polyfit(np.arange(len(series)), series, 1)[0] * 60.0) if len(series) > 1 else 0.0,
        "kurtosis": float(np.mean(centred ** 4) / rms ** 4) if rms > 0 else 0.0,
    }


def voltage_residual(sample: Telemetry, params: PlantParameters | None = None) -> float:
    """Measured minus model-predicted stack voltage at the measured power and temperature."""
    plant = CartridgePlant(params or PlantParameters())
    plant.state.temperature_c = sample.get("temperature_c", 45.0)
    start = baseline.value("chemistry", "aluminum_mass_kg")
    plant.state.aluminum_kg = sample.get("al_kg", start)
    predicted, _ = plant.operating_point(sample.get("power_kw", 0.0))
    return sample.get("voltage_v", predicted) - predicted


def diagnose(history: list[Telemetry], params: PlantParameters | None = None) -> list[Finding]:
    if len(history) < 3:
        return []
    findings = []
    residuals = np.array([voltage_residual(s, params) for s in history[-6:] if s.get("power_kw", 0) > 0.5])
    if residuals.size and residuals.mean() < -4.0:
        findings.append(Finding("diagnostics", "HIGH_RESISTANCE", "WARNING",
                                f"Voltage {abs(residuals.mean()):.1f} V below model: electrolyte flow, "
                                "conductivity or cathode air starvation suspected"))
    temps = np.array([s.get("temperature_c", 25.0) for s in history[-12:]])
    power = np.array([s.get("power_kw", 0.0) for s in history[-12:]])
    tf = features(temps)
    # Warm-up towards the setpoint is normal; above it the thermal loop must hold temperature.
    if temps[-1] > THERMAL_SETPOINT_C + 4.0 and tf["slope_per_min"] > 0.6 and np.ptp(power) < 0.5:
        findings.append(Finding("diagnostics", "COOLING_DEGRADED", "WARNING",
                                f"Temperature rising {tf['slope_per_min']:.1f} °C/min at constant power: "
                                "blower 370 / tunnel 390 path suspected"))
    h2 = np.array([s.get("h2_l_min", 0.0) for s in history[-12:]])
    if h2.size > 2 and features(h2)["slope_per_min"] > 0.3 and tf["slope_per_min"] < 0.5:
        findings.append(Finding("diagnostics", "CORROSION_RISE", "WARNING",
                                "H₂ rising without a matching temperature rise: inhibitor or anode passivation drift"))
    return findings


# ----------------------------------------------------------------- 3. prognostics
@dataclass(frozen=True)
class Prognosis:
    remaining_energy_kwh: float
    minutes_to_event_complete: float | None
    minutes_to_derate: float | None
    aluminum_margin_kg: float


def prognose(history: list[Telemetry], params: PlantParameters | None = None) -> Prognosis:
    target = baseline.value("operating_point", "usable_energy_per_event_kwh")
    derate = baseline.value("thermal", "derate_c")
    last = history[-1]
    remaining = max(0.0, target - last.get("energy_kwh", 0.0))
    power = last.get("power_kw", 0.0)
    to_complete = remaining / power * 60.0 if power > 0.1 else None
    to_derate = None
    if len(history) >= 3:
        temps = np.array([s["temperature_c"] for s in history[-6:]])
        times = np.array([s["t_s"] for s in history[-6:]])
        slope = np.polyfit(times, temps, 1)[0]
        if slope > 1e-4 and temps[-1] < derate:
            to_derate = (derate - temps[-1]) / slope / 60.0
    usable = (params or PlantParameters()).usable_al_fraction
    start = baseline.value("chemistry", "aluminum_mass_kg")
    margin = last.get("al_kg", start) - start * (1.0 - usable)
    return Prognosis(remaining, to_complete, to_derate, margin)


# ---------------------------------------------------------------- 4. prescriptive
def prescribe(sample: Telemetry, prognosis: Prognosis, findings: list[Finding]) -> list[str]:
    th = baseline.load()["thermal"]
    t = sample.get("temperature_c", 25.0)
    actions = []
    if any(f.severity == "CRITICAL" for f in findings):
        actions.append("Hand authority to the independent safety supervisor: isolate power, purge, lock.")
        return actions
    if t < 20.0 and sample.get("power_kw", 0.0) > 0:
        actions.append("Cold cartridge: throttle airflow for self-warm-up before requesting Boost.")
    if t < th["boost_disable_c"] and (prognosis.minutes_to_derate is None or prognosis.minutes_to_derate > 10):
        actions.append("Thermal margin available: 12 kW Boost may be permitted.")
    else:
        actions.append("Hold 10 kW nominal: thermal margin is insufficient for Boost.")
    if any(f.code == "COOLING_DEGRADED" for f in findings):
        actions.append("Check blower 370 and tunnel 390; ask the driver to clear cargo from the vents.")
    if any(f.code == "HIGH_RESISTANCE" for f in findings):
        actions.append("Reduce the power reference and verify electrolyte flow and air supply.")
    if prognosis.aluminum_margin_kg < 0.02 and prognosis.remaining_energy_kwh > 0.05:
        actions.append("Aluminium reserve nearly used: start controlled ramp-down.")
    return actions


@dataclass
class TwinAssessment:
    monitoring: list[Finding] = field(default_factory=list)
    diagnostics: list[Finding] = field(default_factory=list)
    prognosis: Prognosis | None = None
    prescriptions: list[str] = field(default_factory=list)


def assess(history: list[Telemetry], params: PlantParameters | None = None) -> TwinAssessment:
    """Run all four layers on a telemetry history (oldest first)."""
    mon = monitor(history[-1])
    dia = diagnose(history, params)
    prog = prognose(history, params)
    return TwinAssessment(mon, dia, prog, prescribe(history[-1], prog, mon + dia))


def validation_mse(measured: list[float], simulated: list[float]) -> float:
    """Mean squared error between asset measurements and twin output."""
    m, s = np.asarray(measured, float), np.asarray(simulated, float)
    return float(np.mean((m - s) ** 2))
