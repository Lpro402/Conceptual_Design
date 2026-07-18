"""Behavioral tests for the academic Tier-0 demonstrator."""

import pytest

from metalyte.cassette import CassetteReactionManager
from metalyte.controller import MainSystemController, TransitionError
from metalyte.states import CassetteState, FaultType, SystemState


def advance_to_transfer(controller: MainSystemController) -> None:
    controller.wake_up()
    controller.run_self_test()
    controller.connect_vehicle()
    controller.select_cassette()
    controller.add_water()
    controller.prime()
    controller.precharge()
    controller.start_power_transfer()


def complete_event(controller: MainSystemController) -> None:
    advance_to_transfer(controller)
    controller.stop()
    controller.advance_shutdown()
    assert controller.state is SystemState.PURGE_COOLDOWN
    controller.advance_shutdown()


def test_successful_normal_rescue_sequence() -> None:
    controller = MainSystemController()
    complete_event(controller)

    assert controller.state is SystemState.READY
    assert controller.remaining_events == 2
    assert controller.hal.actuators.converter_enabled is False
    assert controller.hal.actuators.output_contactor_closed is False


def test_power_transfer_blocked_before_self_test() -> None:
    controller = MainSystemController()

    with pytest.raises(TransitionError):
        controller.start_power_transfer()

    assert controller.state is SystemState.STANDBY


def test_power_transfer_blocked_without_valid_isolation() -> None:
    controller = MainSystemController()
    controller.wake_up()
    controller.run_self_test()
    controller.connect_vehicle()
    controller.select_cassette()
    controller.add_water()
    controller.prime()
    controller.hal.sensors.isolation_valid = False

    with pytest.raises(TransitionError):
        controller.precharge()

    assert controller.state is SystemState.PRE_CHARGE
    assert controller.hal.actuators.converter_enabled is False


def test_estop_overrides_main_controller() -> None:
    controller = MainSystemController()
    advance_to_transfer(controller)

    controller.inject_fault(FaultType.E_STOP)

    assert controller.state is SystemState.EMERGENCY_SHUTDOWN
    assert controller.safety.fault_latched
    assert controller.hal.actuators.converter_enabled is False
    assert controller.hal.actuators.input_contactor_closed is False
    assert controller.hal.actuators.output_contactor_closed is False
    assert controller.hal.actuators.water_valve_open is False
    assert controller.hal.actuators.gate_disable is True


def test_pump_failure_causes_safe_shutdown() -> None:
    controller = MainSystemController()
    advance_to_transfer(controller)

    controller.inject_fault(FaultType.PUMP_FAILURE)

    assert controller.state is SystemState.EMERGENCY_SHUTDOWN
    assert FaultType.PUMP_FAILURE in controller.safety.latched_faults
    assert controller.hal.actuators.pump_on is False
    assert controller.hal.actuators.converter_enabled is False
    assert controller.hal.sensors.electrolyte_flow_lpm == 0.0


def test_only_one_cassette_can_be_selected_or_active() -> None:
    manager = CassetteReactionManager()
    selected = manager.select(1)

    with pytest.raises(ValueError):
        manager.select(2)

    assert selected.state is CassetteState.SELECTED
    assert sum(c.state is CassetteState.SELECTED for c in manager.cassettes) == 1


def test_cassette_becomes_spent_after_completed_event() -> None:
    controller = MainSystemController()
    advance_to_transfer(controller)
    controller.stop()
    controller.advance_shutdown()

    assert controller.cassette_manager.cassettes[0].state is CassetteState.SPENT
    assert controller.state is SystemState.PURGE_COOLDOWN


def test_service_required_after_three_events() -> None:
    controller = MainSystemController()

    complete_event(controller)
    complete_event(controller)
    complete_event(controller)

    assert controller.state is SystemState.SERVICE_REQUIRED
    assert controller.remaining_events == 0
    assert all(
        cassette.state is CassetteState.SPENT
        for cassette in controller.cassette_manager.cassettes
    )


def test_fault_remains_latched_until_reset() -> None:
    controller = MainSystemController()
    controller.inject_fault(FaultType.ISOLATION_FAULT)
    controller.advance_shutdown()

    assert controller.state is SystemState.FAULT_LOCKED
    assert controller.safety.fault_latched
    with pytest.raises(TransitionError):
        controller.wake_up()

    controller.reset_demonstrator()
    assert controller.state is SystemState.STANDBY
    assert controller.safety.fault_latched is False


def test_purge_occurs_before_ready_or_service_required() -> None:
    controller = MainSystemController()
    complete_event(controller)

    purge_index = controller.state_history.index(SystemState.PURGE_COOLDOWN)
    ready_index = controller.state_history.index(SystemState.READY)
    assert purge_index < ready_index

