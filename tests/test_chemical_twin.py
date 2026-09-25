import pytest

from mpro import baseline
from mpro.chemical_twin import CartridgePlant, PlantParameters, run_event
from mpro.chemical_twin import chemistry


def test_dry_koh_charge_gives_4_molar_at_design_water() -> None:
    assert chemistry.electrolyte_molarity(1.8) == pytest.approx(4.0, abs=0.02)
    assert chemistry.electrolyte_molarity(2.2) < chemistry.electrolyte_molarity(1.8)


def test_full_conversion_mass_balance_matches_chemical_design() -> None:
    al = baseline.value("chemistry", "aluminum_mass_kg")
    balance = chemistry.mass_balance(al, 0.0)
    assert balance.al_oh3_equivalent_kg == pytest.approx(baseline.value("chemistry", "al_oh3_equivalent_kg"), rel=0.01)
    assert balance.oxygen_consumed_kg == pytest.approx(baseline.value("chemistry", "oxygen_consumed_kg"), rel=0.01)


def test_side_reaction_produces_hydrogen() -> None:
    assert chemistry.mass_balance(0.0, 0.027).hydrogen_l_stp == pytest.approx(33.6, rel=0.01)


def test_operating_point_reproduces_the_electrochemical_design_envelope() -> None:
    plant = CartridgePlant()
    plant.state.temperature_c = 45.0
    v_nom, i_nom = plant.operating_point(10.0)
    v_boost, i_boost = plant.operating_point(12.0)
    assert 80 <= v_boost < v_nom <= 110
    assert 105 <= i_nom <= 120
    assert 128 <= i_boost <= 145


@pytest.mark.parametrize(("kw", "minutes"), [(10.0, 18.0), (12.0, 15.0)])
def test_event_delivers_3_kwh_in_design_time(kw: float, minutes: float) -> None:
    result, _ = run_event(requested_kw=kw)
    assert result.delivered_energy_kwh == pytest.approx(3.0, abs=0.05)
    assert result.duration_min == pytest.approx(minutes, abs=0.5)
    assert 35.0 <= result.peak_temperature_c <= 52.0
    assert not result.shutdown
    assert result.aluminum_utilization <= PlantParameters().usable_al_fraction + 0.01


def test_hot_ambient_disables_boost_and_derates() -> None:
    result, _ = run_event(PlantParameters(ambient_c=50.0), requested_kw=12.0)
    assert result.boost_seconds < 120
    assert result.derated_seconds > 0
    assert result.peak_temperature_c < baseline.value("thermal", "shutdown_c")


def test_loss_of_cooling_reaches_protection_thresholds() -> None:
    result, _ = run_event(PlantParameters(ua_w_k=12.0), requested_kw=10.0)
    assert result.peak_temperature_c >= baseline.value("thermal", "derate_c")


def test_first_principles_heat_is_reported_as_open_item() -> None:
    check = chemistry.energy_balance_check(3.26)
    assert chemistry.THERMONEUTRAL_CELL_V == pytest.approx(2.93, abs=0.01)
    assert check.heat_to_electric_ratio > 1.0
