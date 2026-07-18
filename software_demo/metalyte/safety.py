"""Independent conceptual safety supervisor with override authority."""

from dataclasses import dataclass, field

from .event_log import ServiceLoggingManager
from .power import PowerControlManager
from .sensors import SimulatedHardwareAbstractionLayer
from .states import FaultType
from .thermal_fluid import ThermalFluidManager


# SIMULATED PLACEHOLDERS. These are not engineering limits.
MAX_TEMPERATURE_C = 65.0
MAX_HYDROGEN_PCT = 1.0
MIN_PRESSURE_BAR = 0.7
MAX_PRESSURE_BAR = 1.5
MIN_FLOW_LPM = 0.5


@dataclass
class IndependentSafetySupervisor:
    hal: SimulatedHardwareAbstractionLayer
    power: PowerControlManager
    thermal_fluid: ThermalFluidManager
    logger: ServiceLoggingManager
    latched_faults: list[FaultType] = field(default_factory=list)

    @property
    def fault_latched(self) -> bool:
        return bool(self.latched_faults)

    def inject(self, fault: FaultType) -> None:
        self._apply_fault_to_simulation(fault)
        if fault not in self.latched_faults:
            self.latched_faults.append(fault)
        self.override_to_safe_state(fault)

    def override_to_safe_state(self, fault: FaultType) -> None:
        self.power.emergency_disable()
        self.thermal_fluid.protective_shutdown()
        self.logger.log(f"Safety override: {fault.value}", "CRITICAL")

    def transfer_conditions_safe(self) -> bool:
        s = self.hal.sensors
        return (
            not self.fault_latched
            and s.hvil_closed
            and s.isolation_valid
            and not s.leak_detected
            and s.temperature_c < MAX_TEMPERATURE_C
            and s.hydrogen_pct < MAX_HYDROGEN_PCT
            and MIN_PRESSURE_BAR <= s.pressure_bar <= MAX_PRESSURE_BAR
            and s.electrolyte_flow_lpm >= MIN_FLOW_LPM
            and self.hal.pump_available
            and self.hal.fan_available
            and s.contactor_feedback_valid
        )

    def reset(self) -> None:
        self.latched_faults.clear()

    def _apply_fault_to_simulation(self, fault: FaultType) -> None:
        s = self.hal.sensors
        if fault is FaultType.HVIL_OPEN:
            s.hvil_closed = False
        elif fault is FaultType.ISOLATION_FAULT:
            s.isolation_valid = False
        elif fault is FaultType.OVERTEMPERATURE:
            s.temperature_c = 75.0
        elif fault is FaultType.HYDROGEN_ALARM:
            s.hydrogen_pct = 2.0
        elif fault is FaultType.LEAK:
            s.leak_detected = True
        elif fault is FaultType.ABNORMAL_PRESSURE:
            s.pressure_bar = 1.8
        elif fault is FaultType.LOSS_OF_FLOW:
            s.electrolyte_flow_lpm = 0.0
        elif fault is FaultType.PUMP_FAILURE:
            self.hal.pump_available = False
            self.hal.actuators.pump_on = False
            s.electrolyte_flow_lpm = 0.0
        elif fault is FaultType.FAN_FAILURE:
            self.hal.fan_available = False
            self.hal.actuators.fan_on = False
        elif fault is FaultType.CONTACTOR_MISMATCH:
            s.contactor_feedback_valid = False

