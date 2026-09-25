import numpy as np
import pytest

from mpro.chemical_twin import PlantParameters, run_event
from mpro.twin_services import assess, uq
from mpro.twin_services.layers import validation_mse


def test_latin_hypercube_has_one_point_per_stratum() -> None:
    design = uq.latin_hypercube(20, 3, np.random.default_rng(0))
    for column in design.T:
        assert sorted(np.floor(column * 20).astype(int)) == list(range(20))


def test_gaussian_process_interpolates_and_reports_uncertainty() -> None:
    x = np.linspace(0, 1, 12)[:, None]
    y = np.sin(6 * x[:, 0])
    gp = uq.GaussianProcess().fit(x, y)
    assert np.allclose(gp.predict(x), y, atol=1e-3)
    _, std_far = gp.predict(np.array([[3.0]]), return_std=True)
    _, std_near = gp.predict(x[:1], return_std=True)
    assert std_far[0] > std_near[0]


def test_emulator_of_the_chemical_twin_is_adequate() -> None:
    rng = np.random.default_rng(3)
    unit = uq.latin_hypercube(24, len(uq.FACTORS), rng)
    energy = uq.simulate(uq.scale(unit))[:, 0]
    assert uq.leave_one_out_rmse(unit, energy) < 0.15


def test_uq_factors_are_plant_parameters() -> None:
    assert uq.factor_names() == list(uq.FACTORS)


def test_nominal_event_raises_no_diagnostic_findings() -> None:
    _, plant = run_event(requested_kw=10.0, record=True)
    history = plant.state.history
    assert not any(assess(history[:k]).diagnostics for k in range(3, len(history), 5))


def test_degraded_cooling_is_diagnosed_and_prescribed() -> None:
    _, plant = run_event(PlantParameters(ua_w_k=20.0), requested_kw=10.0, record=True)
    history = plant.state.history
    codes = {f.code for k in range(3, len(history)) for f in assess(history[:k]).diagnostics}
    assert "COOLING_DEGRADED" in codes
    late = assess(history[:120])
    assert any("blower 370" in rx for rx in late.prescriptions)


def test_prognosis_estimates_time_to_complete() -> None:
    _, plant = run_event(requested_kw=10.0, record=True)
    prog = assess(plant.state.history[:60]).prognosis
    assert prog.minutes_to_event_complete == pytest.approx(18.0 - 60 * 5 / 60, abs=1.0)


def test_validation_mse() -> None:
    assert validation_mse([1, 2, 3], [1, 2, 5]) == pytest.approx(4 / 3)
