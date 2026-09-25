import numpy as np
import pytest

from mpro.control_twin import PI, simulate_dc_link, simulate_power_tracking, simulate_thermal_boost
from mpro.control_twin.loops import RAMP_W_PER_S, dc_link_metrics, step_metrics


def test_power_loop_tracks_nominal_then_boost_without_overshoot() -> None:
    resp = simulate_power_tracking()
    nominal = step_metrics(resp, 0.0, 3.0, 10_000.0)
    boost = step_metrics(resp, 3.0, 6.0, 12_000.0)
    assert nominal["overshoot_pct"] < 2.0 and boost["overshoot_pct"] < 2.0
    assert nominal["settling_s"] < 1.0 and boost["settling_s"] < 0.5


def test_power_reference_respects_the_ramp_limit() -> None:
    resp = simulate_power_tracking()
    assert step_metrics(resp, 0.0, 3.0, 10_000.0)["max_dpdt_w_per_s"] <= RAMP_W_PER_S * 1.05


def test_current_loop_is_faster_than_power_loop() -> None:
    resp = simulate_power_tracking()
    lag = np.max(np.abs(resp["i_ref"] - resp["i_out"]))
    assert lag < 1.0                                   # amps: inner loop follows its reference closely


def test_pi_anti_windup_limits_integrator_growth() -> None:
    with_aw, without_aw = PI(1.0, 10.0, -1.0, 1.0, True), PI(1.0, 10.0, -1.0, 1.0, False)
    for _ in range(1000):
        with_aw.step(5.0, 0.01)
        without_aw.step(5.0, 0.01)
    assert with_aw.integral < 1.0 < without_aw.integral


def test_lic_reduces_the_dc_link_dip_and_returns_to_small_average_current() -> None:
    with_lic = dc_link_metrics(simulate_dc_link(True))
    without = dc_link_metrics(simulate_dc_link(False))
    assert with_lic["fast_dip_v"] < 0.75 * without["fast_dip_v"]
    assert abs(with_lic["lic_mean_a_last_2s"]) < 0.1 * 140.0      # buffer, not an energy source
    assert 80.0 <= with_lic["final_v"] <= 110.0


def test_thermal_feed_forward_reduces_boost_overshoot() -> None:
    peak = {}
    for ff in (True, False):
        resp = simulate_thermal_boost(ff, t_end=600.0)
        peak[ff] = resp["temperature_c"][resp.t >= 300.0].max()
    assert peak[True] <= peak[False]
    assert peak[True] < 52.0


def test_every_loop_mode_is_defined() -> None:
    from mpro.control_twin import LOOP_MODES

    assert len(LOOP_MODES) == 8
    assert all(len(v) == 3 for v in LOOP_MODES.values())
    assert LOOP_MODES["FAULT"][0] == "Hard disable"


@pytest.mark.parametrize("fn", [simulate_power_tracking, simulate_dc_link])
def test_simulations_are_finite(fn) -> None:
    resp = fn()
    assert all(np.isfinite(sig).all() for sig in resp.signals.values())
