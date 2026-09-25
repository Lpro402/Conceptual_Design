from pathlib import Path

import pytest

from mpro.software_twin import (CartridgeState, FaultType, MainSystemController, SystemState,
                                TransitionError)
from mpro.software_twin import scenario
from mpro.software_twin.storage import lic_threshold_v


def prepared(**handshake) -> MainSystemController:
    c = MainSystemController()
    c.wake()
    c.run_self_test()
    c.answer_environment(enclosed=False)
    c.confirm_deployment(diffuser_outside_confirmed=True)
    c.verify_connection()
    c.handshake(**handshake)
    return c


def transferring(kw: float = 10.0) -> MainSystemController:
    c = prepared()
    c.pour_water(1.8)
    c.confirm_fill()
    c.confirm_activation()
    c.complete_admission()
    c.prime()
    c.start_power_transfer(kw)
    return c


@pytest.mark.parametrize("path", scenario.all_scenarios(), ids=lambda p: p.stem)
def test_demonstration_scenario(path: Path) -> None:
    scenario.run(path)


def test_there_is_a_scenario_for_every_software_change() -> None:
    covered = " ".join(scenario.json.loads(p.read_text(encoding="utf-8"))["config2_changes"]
                       for p in scenario.all_scenarios())
    for change in ("1.1", "1.2", "2.1", "4.1", "5.2", "8.1", "9.1"):
        assert change in covered


def test_water_valve_stays_closed_during_fill_session() -> None:
    c = prepared()
    c.pour_water(1.0)
    c.pour_water(0.8)
    assert c.hal.actuators.cartridge_water_valve_open is False
    assert c.reaction_clock_s is None
    c.confirm_fill()
    assert c.reaction_clock_s is None           # the clock starts only at real admission
    c.confirm_activation()
    assert c.reaction_clock_s == 0.0
    assert c.hal.actuators.cartridge_water_valve_open is True


def test_wetted_cartridge_cannot_return_to_dry_ready() -> None:
    c = prepared()
    c.pour_water(1.8)
    c.confirm_fill()
    c.confirm_activation()
    with pytest.raises(TransitionError):
        c.cancel_fill()
    assert c.cartridges.selected.state is CartridgeState.ACTIVATING


def test_only_one_cartridge_is_ever_selected() -> None:
    c = prepared()
    assert [s for s in c.cartridge_states() if s is not CartridgeState.DRY_READY] == [CartridgeState.SELECTED]
    with pytest.raises(ValueError):
        c.cartridges.select()


def test_hvil_failure_never_triggers_protocol_fallback() -> None:
    c = MainSystemController()
    c.wake()
    c.run_self_test()
    c.answer_environment(enclosed=False)
    c.confirm_deployment(True)
    c.verify_connection()
    c.hal.sensors.hvil_closed = False
    c.handshake(iso15118_ok=False)
    assert c.state is SystemState.AWAIT_CONNECT
    assert c.ev.protocol is None


def test_boost_requires_thermal_margin() -> None:
    c = transferring(12.0)
    c.tick(60)
    assert c.power.reference_kw == pytest.approx(12.0)
    c.hal.sensors.temperature_c = 53.0
    assert c.boost_allowed is False


def test_isolation_warning_indicates_but_does_not_stop_transfer() -> None:
    c = transferring()
    c.hal.sensors.isolation_kohm = 150.0         # 375 Ω/V at 400 V: warning band
    c.tick(30)
    assert c.state is SystemState.ACTIVE_POWER
    assert c.isolation_warning


def test_critical_fault_after_wetting_follows_isolation_purge_lock() -> None:
    c = transferring()
    c.tick(60)
    c.inject_fault(FaultType.HYDROGEN_ALARM)
    assert c.state is SystemState.POWER_ISOLATION
    assert c.hal.actuators.gate_disable and c.hal.actuators.vent_open
    c.advance_shutdown()
    c.advance_shutdown()
    assert c.state is SystemState.FAULT_LOCKED
    assert c.history[-3:] == [SystemState.POWER_ISOLATION, SystemState.PURGE_COOLDOWN, SystemState.FAULT_LOCKED]


def test_self_test_threshold_is_temperature_compensated() -> None:
    assert lic_threshold_v(-25.0) < lic_threshold_v(25.0)
    c = MainSystemController()
    c.hal.sensors.ambient_c, c.hal.sensors.lic_voltage_v = -25.0, 3.05
    c.wake()
    c.run_self_test()
    assert c.state is SystemState.ENVIRONMENT_CHECK
    c2 = MainSystemController()
    c2.hal.sensors.lic_voltage_v = 3.05          # same reading at 25 °C is a real failure
    c2.wake()
    c2.run_self_test()
    assert c2.state is SystemState.FAULT_LOCKED


def test_hmi_minutes_estimate_during_transfer() -> None:
    c = transferring()
    c.tick(120)
    assert "דקות משוערות" in c.instruction and "--" not in c.instruction
