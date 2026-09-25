"""Time-stepped plant model of one active MPRO cartridge (the chemical twin core).

The plant is deliberately low-order so it can run inside the software twin, in
the browser twin and inside uncertainty studies:

* electrochemistry — linear polarisation ``V = N·(E_oc − R·i)`` fitted to the
  design points (96 V at ~113 A nominal, ~138 A in 12 kW Boost), with
  electrolyte conductivity and end-of-discharge fade;
* Faradaic + corrosion aluminium consumption, H₂ from the side reaction,
  water consumption and retained products (mass balance of design 4.2);
* lumped thermal capacity ``C·dT/dt = Q − UA·(T − T_amb)`` calibrated so the
  nominal event settles inside the 35–50 °C window and Boost reaches the
  provisional 52/55 °C protection thresholds of design 4.4.

Numbers are conceptual design values or labelled calibration assumptions.
They are not test evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from mpro import baseline

from . import chemistry


@dataclass(frozen=True)
class PlantParameters:
    """Uncertain parameters of the chemical twin (the factors of UQ studies)."""

    cell_ocv_v: float = 104.0 / chemistry.ASSUMED_SERIES_CELLS   # calibrated: 96 V @ ~113 A
    cell_resistance_ohm: float = 0.0711 / chemistry.ASSUMED_SERIES_CELLS  # calibrated: ~138 A @ 13 kW
    coulombic_efficiency: float = 0.96        # ASSUMED share of Al that yields current
    conversion_efficiency: float = baseline.value("operating_point", "conversion_efficiency")
    usable_al_fraction: float = 0.85          # ASSUMED design reserve (no full consumption)
    heat_fraction: float = 0.127              # calibrated to the 4.4 thermal envelope
    thermal_capacity_j_k: float = 25_000.0    # ASSUMED cartridge + electrolyte + structure
    ua_w_k: float = 60.0                      # ASSUMED effective heat rejection at nominal airflow
    ambient_c: float = 25.0
    water_l: float = baseline.value("water", "target_l")

    def with_(self, **changes) -> "PlantParameters":
        return replace(self, **changes)


@dataclass
class PlantState:
    time_s: float = 0.0
    temperature_c: float = 25.0
    aluminum_kg: float = baseline.value("chemistry", "aluminum_mass_kg")
    faradaic_al_kg: float = 0.0
    parasitic_al_kg: float = 0.0
    net_energy_kwh: float = 0.0
    gross_energy_kwh: float = 0.0
    hydrogen_l: float = 0.0
    stack_voltage_v: float = 0.0
    stack_current_a: float = 0.0
    net_power_kw: float = 0.0
    hydrogen_rate_l_min: float = 0.0
    history: list[dict] = field(default_factory=list)


@dataclass
class CartridgePlant:
    params: PlantParameters = field(default_factory=PlantParameters)
    state: PlantState = field(init=False)

    def __post_init__(self) -> None:
        self.state = PlantState(temperature_c=self.params.ambient_c)

    # ------------------------------------------------------------------ physics
    @property
    def molarity(self) -> float:
        return chemistry.electrolyte_molarity(self.params.water_l)

    @property
    def utilization(self) -> float:
        start = baseline.value("chemistry", "aluminum_mass_kg")
        return 1.0 - self.state.aluminum_kg / start

    def _resistance(self) -> float:
        n = chemistry.ASSUMED_SERIES_CELLS
        temp_factor = math.exp(-0.012 * (self.state.temperature_c - 45.0))
        return n * self.params.cell_resistance_ohm * temp_factor / chemistry.relative_conductivity(self.molarity)

    def _ocv(self) -> float:
        n = chemistry.ASSUMED_SERIES_CELLS
        usable = self.params.usable_al_fraction
        depletion = min(self.utilization / usable, 1.0)
        fade = 1.0 - 0.06 * depletion ** 4          # end-of-discharge voltage fade
        cold = 1.0 - 0.004 * max(0.0, 20.0 - self.state.temperature_c)
        return n * self.params.cell_ocv_v * fade * cold

    def operating_point(self, net_power_kw: float) -> tuple[float, float]:
        """Stack voltage and current that deliver ``net_power_kw`` after conversion."""
        gross_w = max(net_power_kw, 0.0) * 1000.0 / self.params.conversion_efficiency
        e, r = self._ocv(), self._resistance()
        disc = e * e - 4.0 * r * gross_w
        if gross_w == 0.0:
            return e, 0.0
        if disc < 0.0:                              # beyond maximum power: saturate
            current = e / (2.0 * r)
        else:
            current = (e - math.sqrt(disc)) / (2.0 * r)
        return e - r * current, current

    def max_net_power_kw(self) -> float:
        e, r = self._ocv(), self._resistance()
        return e * e / (4.0 * r) * self.params.conversion_efficiency / 1000.0

    @property
    def depleted(self) -> bool:
        return self.utilization >= self.params.usable_al_fraction

    # ------------------------------------------------------------------ dynamics
    def step(self, dt_s: float, net_power_kw: float, cooling: float = 1.0) -> PlantState:
        """Advance the plant; ``cooling`` scales airflow (0 = blower lost, 1.5 = high flow)."""
        s, p = self.state, self.params
        if self.depleted:
            net_power_kw = 0.0
        voltage, current = self.operating_point(net_power_kw)
        gross_kw = voltage * current / 1000.0
        delivered_kw = gross_kw * p.conversion_efficiency

        far_rate = chemistry.aluminum_rate_kg_s(current)
        corrosion_scale = 2.0 ** ((s.temperature_c - 45.0) / 10.0)
        idle_corrosion = 2.0e-7 if s.temperature_c > 0 else 0.0   # wetted cartridge at rest
        par_rate = far_rate * (1.0 - p.coulombic_efficiency) / p.coulombic_efficiency * corrosion_scale + idle_corrosion
        al_used = (far_rate + par_rate) * dt_s
        s.aluminum_kg = max(0.0, s.aluminum_kg - al_used)
        s.faradaic_al_kg += far_rate * dt_s
        s.parasitic_al_kg += par_rate * dt_s

        heat_w = p.heat_fraction * gross_kw * 1000.0 + 0.25 * (1.0 - p.conversion_efficiency) * gross_kw * 1000.0
        ua = p.ua_w_k * max(cooling, 0.05)
        s.temperature_c += (heat_w - ua * (s.temperature_c - p.ambient_c)) / p.thermal_capacity_j_k * dt_s

        s.stack_voltage_v, s.stack_current_a = voltage, current
        s.net_power_kw = delivered_kw
        s.gross_energy_kwh += gross_kw * dt_s / 3600.0
        s.net_energy_kwh += delivered_kw * dt_s / 3600.0
        s.hydrogen_rate_l_min = chemistry.hydrogen_rate_l_min(par_rate)
        s.hydrogen_l += s.hydrogen_rate_l_min * dt_s / 60.0
        s.time_s += dt_s
        return s

    def record(self) -> None:
        s = self.state
        s.history.append({
            "t_s": s.time_s, "power_kw": s.net_power_kw, "voltage_v": s.stack_voltage_v,
            "current_a": s.stack_current_a, "temperature_c": s.temperature_c,
            "energy_kwh": s.net_energy_kwh, "h2_l_min": s.hydrogen_rate_l_min,
            "al_kg": s.aluminum_kg,
        })

    def mass_balance(self) -> chemistry.MassBalance:
        return chemistry.mass_balance(self.state.faradaic_al_kg, self.state.parasitic_al_kg)


@dataclass(frozen=True)
class EventResult:
    delivered_energy_kwh: float
    duration_min: float
    peak_temperature_c: float
    hydrogen_l: float
    aluminum_utilization: float
    water_consumed_kg: float
    boost_seconds: float
    derated_seconds: float
    shutdown: bool


THERMAL_SETPOINT_C = 45.0   # inside the 35-50 °C nominal electrolyte window


def thermal_loop_command(temperature_c: float, command_kw: float) -> float:
    """Thermal/fluid loop of design 4.3: power feed-forward plus proportional feedback.

    Returns the airflow scale for :meth:`CartridgePlant.step`. In the cold the
    loop throttles airflow so the cartridge self-heats; in Boost the
    feed-forward raises airflow before the temperature error appears.
    """
    nominal = baseline.value("operating_point", "net_power_nominal_kw")
    feed_forward = 0.9 * command_kw / nominal
    feedback = 0.08 * (temperature_c - THERMAL_SETPOINT_C)
    return min(1.5, max(0.05, feed_forward + feedback))


def run_event(params: PlantParameters | None = None, requested_kw: float | None = None,
              dt_s: float = 5.0, record: bool = False) -> tuple[EventResult, CartridgePlant]:
    """Simulate one rescue event under the supervisory thermal logic of design 4.3/4.4.

    The requested power is honoured while thermal margin exists: Boost is
    disabled above 52 °C, power derates above 55 °C and the event stops at 65 °C.
    The event ends when 3 kWh are delivered or the usable aluminium is exhausted.
    """
    plant = CartridgePlant(params or PlantParameters())
    t = baseline.load()["thermal"]
    nominal = baseline.value("operating_point", "net_power_nominal_kw")
    target = baseline.value("operating_point", "usable_energy_per_event_kwh")
    requested = nominal if requested_kw is None else requested_kw
    peak, boost_s, derated_s, shutdown = plant.state.temperature_c, 0.0, 0.0, False

    while plant.state.net_energy_kwh < target and plant.state.time_s < 3 * 3600:
        temp = plant.state.temperature_c
        if temp >= t["shutdown_c"]:
            shutdown = True
            break
        if plant.depleted:
            break
        command = requested
        if temp >= t["boost_disable_c"]:
            command = min(command, nominal)
        if temp >= t["derate_c"]:
            command = min(command, nominal * max(0.4, 1.0 - (temp - t["derate_c"]) / (t["shutdown_c"] - t["derate_c"])))
            derated_s += dt_s
        if command > nominal:
            boost_s += dt_s
        plant.step(dt_s, command, thermal_loop_command(temp, command))
        peak = max(peak, plant.state.temperature_c)
        if record:
            plant.record()

    balance = plant.mass_balance()
    return EventResult(
        delivered_energy_kwh=plant.state.net_energy_kwh,
        duration_min=plant.state.time_s / 60.0,
        peak_temperature_c=peak,
        hydrogen_l=plant.state.hydrogen_l,
        aluminum_utilization=plant.utilization,
        water_consumed_kg=balance.water_consumed_kg,
        boost_seconds=boost_s,
        derated_seconds=derated_s,
        shutdown=shutdown,
    ), plant
