"""Control twin: reduced-order models of the three MPRO control loops (design 4.3).

Hierarchy (fast → slow): current loop > LIC / DC-link loop > power loop >> thermal loop.

1. Cascaded EV power / current control — an outer PI power loop with a
   feed-forward current reference drives a fast inner current loop; the power
   reference is ramp-limited and the PI has anti-windup.
2. Low-side DC-link stabilisation by the LIC — the LIC rejects *short* load
   disturbances around a slowly tracking reference; it does not cover a
   sustained energy deficit, so its average contribution stays small.
3. Thermal / fluid regulation — feed-forward from the power command plus PI on
   core temperature (run on the chemical twin plant).

Plant parameters are labelled placeholders for tuning studies, not validated
values. The time-domain responses illustrate the architecture, as the design
chapter itself does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from mpro import baseline
from mpro.chemical_twin import CartridgePlant, PlantParameters

EFFICIENCY = baseline.value("operating_point", "conversion_efficiency")
V_DC_NOMINAL = float(baseline.value("operating_point", "stack_voltage_nominal_v"))
P_NOMINAL_W = baseline.value("operating_point", "net_power_nominal_kw") * 1000.0
P_BOOST_W = baseline.value("operating_point", "net_power_boost_kw") * 1000.0

# SIMULATED PLACEHOLDERS
V_EV = 400.0                 # vehicle-side DC voltage [V]
TAU_CURRENT_S = 0.005        # closed inner current loop
RAMP_W_PER_S = 20_000.0      # dP/dt limit protecting the cartridge
C_DC_F = 0.05                # low-side DC-link capacitance
TAU_STACK_S = 1.5            # slow polarisation (mass transport) time constant
STACK_OCV_V = 104.0          # series stack open-circuit voltage (chemical twin calibration)
STACK_R_OHMIC = 0.050        # immediate ohmic part of the 0.0711 Ω stack resistance
STACK_R_SLOW_OHM = 0.0211    # slow polarisation part (chemical twin calibration)
LIC_CURRENT_LIMIT_A = 150.0
TAU_VREF_S = 1.0             # LIC reference follows the slow operating point


@dataclass
class PI:
    kp: float
    ki: float
    out_min: float = -np.inf
    out_max: float = np.inf
    anti_windup: bool = True
    leak_per_s: float = 0.0
    integral: float = 0.0

    def step(self, error: float, dt: float) -> float:
        candidate = self.integral + self.ki * error * dt - self.leak_per_s * self.integral * dt
        unclamped = self.kp * error + candidate
        out = min(self.out_max, max(self.out_min, unclamped))
        # Conditional integration: freeze the integrator while saturated in the same direction.
        if not self.anti_windup or out == unclamped or (unclamped > out) != (error > 0):
            self.integral = candidate
        return out


def ramp_limit(target: float, previous: float, rate: float, dt: float) -> float:
    step = rate * dt
    return previous + max(-step, min(step, target - previous))


@dataclass
class Response:
    t: np.ndarray
    signals: dict[str, np.ndarray] = field(default_factory=dict)

    def __getitem__(self, key: str) -> np.ndarray:
        return self.signals[key]


# ------------------------------------------------------------ 1. power / current
def simulate_power_tracking(profile: list[tuple[float, float]] | None = None, t_end: float = 6.0,
                            dt: float = 1e-3, ramp_w_per_s: float = RAMP_W_PER_S,
                            kp: float = 2e-4, ki: float = 4e-3, anti_windup: bool = True,
                            current_limit_a: float = 40.0) -> Response:
    """Step to 10 kW, then Boost to 12 kW (default profile)."""
    profile = profile or [(0.0, P_NOMINAL_W), (3.0, P_BOOST_W)]
    power_pi = PI(kp, ki, -current_limit_a, current_limit_a, anti_windup)
    n = int(t_end / dt)
    t = np.arange(n) * dt
    p_cmd = p_ref = i_out = 0.0
    out = {k: np.zeros(n) for k in ("p_request", "p_reference", "p_out", "i_ref", "i_out")}
    for k in range(n):
        p_cmd = next(p for start, p in reversed(profile) if t[k] >= start)
        p_ref = ramp_limit(p_cmd, p_ref, ramp_w_per_s, dt)
        p_meas = V_EV * i_out
        i_ref = min(current_limit_a, max(-current_limit_a, p_ref / V_EV + power_pi.step(p_ref - p_meas, dt)))
        i_out += (i_ref - i_out) * dt / TAU_CURRENT_S
        for key, val in (("p_request", p_cmd), ("p_reference", p_ref), ("p_out", V_EV * i_out),
                         ("i_ref", i_ref), ("i_out", i_out)):
            out[key][k] = val
    return Response(t, out)


def step_metrics(resp: Response, t0: float, t1: float, target: float, band: float = 0.02) -> dict:
    mask = (resp.t >= t0) & (resp.t < t1)
    y, t = resp["p_out"][mask], resp.t[mask]
    outside = np.nonzero(np.abs(y - target) > band * target)[0]
    settle = t[outside[-1]] - t0 if outside.size else 0.0
    return {"overshoot_pct": max(0.0, (y.max() - target) / target * 100.0), "settling_s": float(settle),
            "max_dpdt_w_per_s": float(np.max(np.abs(np.diff(y))) / (t[1] - t[0]))}


# --------------------------------------------------------------- 2. DC link + LIC
def simulate_dc_link(with_lic: bool = True, t_end: float = 12.0, dt: float = 2e-4,
                     base_w: float = P_NOMINAL_W, step_w: float = P_BOOST_W, step_at: float = 2.0,
                     kp: float = 10.0, ki: float = 60.0) -> Response:
    """Converter load steps from 10 to 12 kW.

    The stack responds with an immediate ohmic drop plus a slow polarisation
    overpotential (first order, TAU_STACK_S). The LIC loop holds V_DC near a
    slowly moving reference, carrying the fast part of the step and handing the
    load back to the stack as the reference settles.
    """
    lic_pi = PI(kp, ki, -LIC_CURRENT_LIMIT_A, LIC_CURRENT_LIMIT_A, leak_per_s=1.0)
    n = int(t_end / dt)
    t = np.arange(n) * dt
    i0 = base_w / EFFICIENCY / V_DC_NOMINAL
    v_slow = STACK_R_SLOW_OHM * i0
    v = STACK_OCV_V - v_slow - STACK_R_OHMIC * i0
    v_ref = v
    out = {k: np.zeros(n) for k in ("v_dc", "i_stack", "i_lic", "i_load")}
    for k in range(n):
        p = step_w if t[k] >= step_at else base_w
        i_load = p / EFFICIENCY / max(v, 1.0)
        i_stack = max(0.0, (STACK_OCV_V - v_slow - v) / STACK_R_OHMIC)
        v_slow += (STACK_R_SLOW_OHM * i_stack - v_slow) * dt / TAU_STACK_S
        v_ref += (v - v_ref) * dt / TAU_VREF_S
        i_lic = lic_pi.step(v_ref - v, dt) if with_lic else 0.0
        v += (i_stack + i_lic - i_load) / C_DC_F * dt
        for key, val in (("v_dc", v), ("i_stack", i_stack), ("i_lic", i_lic), ("i_load", i_load)):
            out[key][k] = val
    return Response(t, out)


def dc_link_metrics(resp: Response, step_at: float = 2.0) -> dict:
    dt = resp.t[1] - resp.t[0]
    v = resp["v_dc"]
    before = v[resp.t < step_at][-1]
    fast = v[(resp.t >= step_at) & (resp.t < step_at + 0.2)]
    return {
        "fast_dip_v": float(before - fast.min()),
        "max_dvdt_v_per_s": float(np.max(np.abs(np.diff(v[resp.t >= step_at]))) / dt),
        "final_v": float(v[-1]),
        "lic_peak_a": float(np.max(np.abs(resp["i_lic"]))),
        "lic_mean_a_last_2s": float(np.mean(resp["i_lic"][resp.t > resp.t[-1] - 2.0])),
    }


# -------------------------------------------------------------------- 3. thermal
def simulate_thermal_boost(feed_forward: bool = True, boost_at_s: float = 300.0, t_end: float = 900.0,
                           dt: float = 5.0, params: PlantParameters | None = None,
                           setpoint_c: float = 45.0) -> Response:
    """10 kW then a Boost request; compares feed-forward + PI with PI alone."""
    plant = CartridgePlant(params or PlantParameters())
    plant.state.temperature_c = setpoint_c        # start at the regulated operating point
    pi = PI(0.08, 0.0008, -0.9, 0.6)
    n = int(t_end / dt)
    t = np.arange(n) * dt
    out = {k: np.zeros(n) for k in ("power_kw", "temperature_c", "cooling")}
    for k in range(n):
        p = baseline.value("operating_point", "net_power_boost_kw") if t[k] >= boost_at_s else baseline.value("operating_point", "net_power_nominal_kw")
        ff = 0.9 * p / (P_NOMINAL_W / 1000.0) if feed_forward else 0.9
        cooling = min(1.5, max(0.05, ff + pi.step(plant.state.temperature_c - setpoint_c, dt)))
        plant.step(dt, p, cooling)
        out["power_kw"][k], out["temperature_c"][k], out["cooling"][k] = p, plant.state.temperature_c, cooling
    return Response(t, out)


# ------------------------------------------------------- supervisory mode table
LOOP_MODES = {
    "DRY_READY / SELECTED": ("OFF", "Standby", "Standby"),
    "PRIME / FLOW CHECK": ("OFF", "Support auxiliaries", "Activation / flow control"),
    "ACTIVE_POWER": ("10 kW tracking", "V_DC regulation", "Closed-loop cooling"),
    "BOOST": ("≤ 12 kW", "Transient support", "High-flow + feed-forward"),
    "DERATED": ("Reduced P*", "V_DC regulation", "Maximum allowed cooling"),
    "RAMP_DOWN": ("Controlled reduction", "Transient support", "Continue cooling"),
    "PURGE / COOLDOWN": ("OFF", "Aux support", "Purge / cooldown"),
    "FAULT": ("Hard disable", "Isolate as required", "Safe shutdown path"),
}
