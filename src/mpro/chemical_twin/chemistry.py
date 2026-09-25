"""Stoichiometry, mass balance and energy balance of the alkaline Al-air cartridge.

Reaction set (design 4.2):

* anode        Al + 4OH⁻ → Al(OH)₄⁻ + 3e⁻
* cathode      O₂ + 2H₂O + 4e⁻ → 4OH⁻
* overall      4Al + 3O₂ + 6H₂O → 4Al(OH)₃
* side         2Al + 6H₂O + 2OH⁻ → 2Al(OH)₄⁻ + 3H₂↑
* precipitate  Al(OH)₄⁻ → Al(OH)₃↓ + OH⁻

Constants are textbook values. Anything that is a modelling assumption rather
than a design-document value is named ``ASSUMED_*`` and must be treated as a
calibration parameter of the twin, not as a validated property.
"""

from __future__ import annotations

from dataclasses import dataclass

from mpro import baseline

FARADAY = 96_485.0          # C/mol
M_AL = 26.98e-3             # kg/mol
M_KOH = 56.11e-3            # kg/mol
M_H2O = 18.015e-3           # kg/mol
M_O2 = 32.00e-3             # kg/mol
M_ALOH3 = 78.00e-3          # kg/mol
MOLAR_VOLUME_STP = 22.414   # L/mol
ELECTRONS_PER_AL = 3

# Enthalpy of Al + 3/4 O2 + 3/2 H2O(l) -> Al(OH)3, from standard enthalpies of formation.
DELTA_H_PER_AL = -1276.0e3 + 1.5 * 285.8e3            # J/mol ≈ -847 kJ/mol
THERMONEUTRAL_CELL_V = -DELTA_H_PER_AL / (ELECTRONS_PER_AL * FARADAY)  # ≈ 2.93 V

# Series count is TBD in the design; the twin assumes ~1.2 V per cell at the
# nominal point, i.e. 80 cells for the 96 V stack. Illustrative only.
ASSUMED_CELL_VOLTAGE_V = 1.2
ASSUMED_SERIES_CELLS = round(baseline.value("operating_point", "stack_voltage_nominal_v") / ASSUMED_CELL_VOLTAGE_V)


def electrolyte_molarity(water_l: float) -> float:
    """KOH molarity after the dry charge dissolves in the measured water."""
    koh_mol = baseline.value("chemistry", "koh_charge_g") / 1000.0 / M_KOH
    return koh_mol / water_l


def relative_conductivity(molarity: float) -> float:
    """Normalised KOH conductivity (1.0 at the 4 M design point).

    Aqueous KOH conductivity rises with concentration, peaks near 6-7 M and
    falls beyond; a smooth ``M·exp(-M/6.5)`` shape reproduces that trend.
    """
    import math

    shape = lambda m: m * math.exp(-m / 6.5)  # noqa: E731
    target = baseline.value("chemistry", "electrolyte_molarity_after_activation")
    return shape(max(molarity, 0.05)) / shape(target)


def aluminum_rate_kg_s(stack_current_a: float, series_cells: int = ASSUMED_SERIES_CELLS) -> float:
    """Faradaic aluminium consumption for the whole series stack."""
    return stack_current_a * series_cells / (ELECTRONS_PER_AL * FARADAY) * M_AL


def hydrogen_rate_l_min(parasitic_al_kg_s: float) -> float:
    """H₂ at STP from the corrosion side reaction (1.5 mol H₂ per mol Al)."""
    return parasitic_al_kg_s / M_AL * 1.5 * MOLAR_VOLUME_STP * 60.0


@dataclass(frozen=True)
class MassBalance:
    aluminum_consumed_kg: float
    water_consumed_kg: float
    oxygen_consumed_kg: float
    al_oh3_equivalent_kg: float
    hydrogen_l_stp: float


def mass_balance(faradaic_al_kg: float, parasitic_al_kg: float) -> MassBalance:
    """Mass balance for a given split of electrochemical and corrosion Al consumption."""
    n_far = faradaic_al_kg / M_AL
    n_par = parasitic_al_kg / M_AL
    return MassBalance(
        aluminum_consumed_kg=faradaic_al_kg + parasitic_al_kg,
        water_consumed_kg=(1.5 * n_far + 3.0 * n_par) * M_H2O,
        oxygen_consumed_kg=0.75 * n_far * M_O2,
        al_oh3_equivalent_kg=(n_far + n_par) * M_ALOH3,
        hydrogen_l_stp=1.5 * n_par * MOLAR_VOLUME_STP,
    )


@dataclass(frozen=True)
class EnergyBalanceCheck:
    """First-principles heat estimate, kept separate from the calibrated plant."""

    gross_energy_kwh: float
    irreversible_heat_kwh: float
    heat_to_electric_ratio: float
    water_heat_capacity_kj_per_k: float


def energy_balance_check(gross_energy_kwh: float, cell_voltage_v: float = ASSUMED_CELL_VOLTAGE_V) -> EnergyBalanceCheck:
    """Heat released by the reaction for a given electrical output.

    Heat = I·(E_tn − V) per cell, so heat/electric = (E_tn − V)/V. This is an
    open design item for the thermal chapter: the calibrated plant reproduces the
    documented thermal envelope, while this check reports the raw chemistry.
    """
    ratio = (THERMONEUTRAL_CELL_V - cell_voltage_v) / cell_voltage_v
    water_kg = baseline.value("water", "target_l")
    return EnergyBalanceCheck(
        gross_energy_kwh=gross_energy_kwh,
        irreversible_heat_kwh=gross_energy_kwh * ratio,
        heat_to_electric_ratio=ratio,
        water_heat_capacity_kj_per_k=water_kg * 4.18,
    )
