"""Deterministic Tier-0 mission controller for the local demonstrator."""

from dataclasses import dataclass, field

from .cassette import CassetteReactionManager
from .event_log import ServiceLoggingManager
from .ev import EVCommunicationManager
from .hmi import HMIManager
from .power import PowerControlManager
from .safety import IndependentSafetySupervisor
from .sensors import SimulatedHardwareAbstractionLayer
from .states import CassetteState, FaultType, SystemState
from .thermal_fluid import ThermalFluidManager


class TransitionError(RuntimeError):
    """Raised when an explicitly guarded state transition is rejected."""


@dataclass
class MainSystemController:
    hal: SimulatedHardwareAbstractionLayer = field(
        default_factory=SimulatedHardwareAbstractionLayer
    )
    logger: ServiceLoggingManager = field(default_factory=ServiceLoggingManager)
    cassette_manager: CassetteReactionManager = field(
        default_factory=CassetteReactionManager
    )
    ev: EVCommunicationManager = field(default_factory=EVCommunicationManager)
    hmi: HMIManager = field(default_factory=HMIManager)
    state: SystemState = SystemState.STANDBY
    self_test_passed: bool = False
    state_history: list[SystemState] = field(default_factory=lambda: [SystemState.STANDBY])

    def __post_init__(self) -> None:
        self.power = PowerControlManager(self.hal)
        self.thermal_fluid = ThermalFluidManager(self.hal)
        self.safety = IndependentSafetySupervisor(
            self.hal, self.power, self.thermal_fluid, self.logger
        )
        self.logger.log("Demonstrator initialized in STANDBY")

    @property
    def instruction(self) -> str:
        return self.hmi.instruction_for(self.state)

    @property
    def active_faults(self) -> list[str]:
        return [f.value for f in self.safety.latched_faults]

    @property
    def remaining_events(self) -> int:
        return self.cassette_manager.remaining_events

    def wake_up(self) -> None:
        self._require_state(SystemState.STANDBY, SystemState.READY)
        if self.safety.fault_latched:
            raise TransitionError("A latched fault blocks wake-up")
        self.self_test_passed = False
        self._transition(SystemState.WAKE_UP_SELF_TEST, "Wake-up requested")

    def run_self_test(self) -> None:
        self._require_state(SystemState.WAKE_UP_SELF_TEST)
        s = self.hal.sensors
        passed = (
            not self.safety.fault_latched
            and s.hvil_closed
            and s.isolation_valid
            and not s.leak_detected
            and self.hal.pump_available
            and self.hal.fan_available
            and s.contactor_feedback_valid
        )
        self.self_test_passed = passed
        if not passed:
            self.inject_fault(FaultType.ISOLATION_FAULT)
            return
        self._transition(SystemState.VEHICLE_CONNECTION, "Self-test passed")

    def connect_vehicle(self) -> None:
        self._require_state(SystemState.VEHICLE_CONNECTION)
        if not self.self_test_passed:
            raise TransitionError("Self-test must pass before vehicle connection")
        self.ev.connect()
        self._transition(SystemState.CASSETTE_SELECTION, "Simulated vehicle connected")

    def select_cassette(self, cassette_id: int | None = None) -> None:
        self._require_state(SystemState.CASSETTE_SELECTION)
        try:
            cassette = self.cassette_manager.select(cassette_id)
        except ValueError as exc:
            raise TransitionError(str(exc)) from exc
        self._transition(
            SystemState.WATER_ACTIVATION,
            f"Cassette {cassette.cassette_id} selected",
        )

    def add_water(self) -> None:
        self._require_state(SystemState.WATER_ACTIVATION)
        self.cassette_manager.activate_water()
        self.thermal_fluid.admit_water()
        self._transition(SystemState.PRIMING, "Water activation confirmed")

    def prime(self) -> None:
        self._require_state(SystemState.PRIMING)
        try:
            self.thermal_fluid.prime()
        except ValueError as exc:
            raise TransitionError(str(exc)) from exc
        self.cassette_manager.mark_active()
        self._transition(SystemState.PRE_CHARGE, "Priming complete")

    def precharge(self) -> None:
        self._require_state(SystemState.PRE_CHARGE)
        if not self._base_transfer_guards(ignore_precharge=True):
            raise TransitionError("Pre-charge guards are not satisfied")
        self.power.precharge()
        self.logger.log("Simulated pre-charge complete")

    def start_power_transfer(self) -> None:
        self._require_state(SystemState.PRE_CHARGE)
        if not self._base_transfer_guards(ignore_precharge=False):
            raise TransitionError("POWER_TRANSFER guards are not satisfied")
        self.power.enable_transfer()
        self._transition(SystemState.POWER_TRANSFER, "Simulated power transfer enabled")

    def request_derating(self) -> None:
        self._require_state(SystemState.POWER_TRANSFER)
        self.power.derate()
        self._transition(SystemState.DERATING, "Derating requested")

    def stop(self) -> None:
        self._require_state(SystemState.POWER_TRANSFER, SystemState.DERATING)
        self.power.controlled_stop()
        self._transition(SystemState.RAMP_DOWN, "Controlled stop requested")

    def advance_shutdown(self) -> None:
        if self.state is SystemState.RAMP_DOWN:
            self.power.isolate()
            self.thermal_fluid.begin_purge()
            cassette = self.cassette_manager.mark_spent()
            self._transition(
                SystemState.PURGE_COOLDOWN,
                f"Cassette {cassette.cassette_id} marked SPENT; purge started",
            )
            return
        if self.state is SystemState.PURGE_COOLDOWN:
            self.thermal_fluid.complete_purge()
            next_state = (
                SystemState.READY
                if self.remaining_events > 0
                else SystemState.SERVICE_REQUIRED
            )
            self._transition(next_state, "Purge/cooldown complete")
            return
        if self.state is SystemState.EMERGENCY_SHUTDOWN:
            self._transition(SystemState.FAULT_LOCKED, "Emergency state secured; fault latched")
            return
        raise TransitionError("No shutdown step is available in the current state")

    def inject_fault(self, fault: FaultType) -> None:
        self.safety.inject(fault)
        selected = self.cassette_manager.selected
        if selected and selected.state in {
            CassetteState.ACTIVATING,
            CassetteState.ACTIVE,
        }:
            self.cassette_manager.mark_faulted()
        self._transition(SystemState.EMERGENCY_SHUTDOWN, fault.value, level="CRITICAL")

    def reset_demonstrator(self) -> None:
        self.hal.reset()
        self.power.reset()
        self.thermal_fluid.reset()
        self.safety.reset()
        self.ev.disconnect()
        self.cassette_manager.reset()
        self.self_test_passed = False
        self.logger.clear()
        self.state = SystemState.STANDBY
        self.state_history = [SystemState.STANDBY]
        self.logger.log("Demonstrator reset to STANDBY")

    def _base_transfer_guards(self, ignore_precharge: bool) -> bool:
        selected = self.cassette_manager.selected
        return bool(
            self.self_test_passed
            and self.ev.connected
            and self.ev.handshake_valid
            and selected is not None
            and selected.state is CassetteState.ACTIVE
            and self.hal.water_confirmed
            and self.thermal_fluid.priming_complete
            and self.safety.transfer_conditions_safe()
            and (ignore_precharge or self.power.precharge_complete)
        )

    def _require_state(self, *allowed: SystemState) -> None:
        if self.state not in allowed:
            expected = ", ".join(s.name for s in allowed)
            raise TransitionError(
                f"Action not allowed in {self.state.name}; expected {expected}"
            )

    def _transition(self, state: SystemState, message: str, level: str = "INFO") -> None:
        self.state = state
        self.state_history.append(state)
        self.logger.log(f"{state.name}: {message}", level)

