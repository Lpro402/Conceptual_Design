"""Independent Safety Supervisor (conceptual model of the hardware channel 620).

It is *not* a task of the main controller: it reads critical signals directly
and can force GATE_DISABLE, open both contactors and latch a fault regardless of
mission state. [8.1/8.3] IMD 490 has two adjustable thresholds: a warning that
only indicates, and a block that prevents or stops power transfer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mpro import baseline

from .event_log import ServiceLoggingManager
from .sensors import SimulatedHardwareAbstractionLayer
from .states import FaultType, IsolationLevel

# SIMULATED PLACEHOLDERS following the ohm-per-volt approach of IEC 61851-23.
IMD_WARNING_OHM_PER_V = 500.0
IMD_BLOCK_OHM_PER_V = 100.0
MAX_HYDROGEN_PCT_LEL = 25.0
PRESSURE_WINDOW_BAR = (0.7, 1.5)
MIN_FLOW_LPM = 0.5


def isolation_level(isolation_kohm: float, voltage_v: float) -> IsolationLevel:
    ohm_per_v = isolation_kohm * 1000.0 / max(voltage_v, 1.0)
    if ohm_per_v < IMD_BLOCK_OHM_PER_V:
        return IsolationLevel.BLOCK
    if ohm_per_v < IMD_WARNING_OHM_PER_V:
        return IsolationLevel.WARNING
    return IsolationLevel.NORMAL


@dataclass
class IndependentSafetySupervisor:
    hal: SimulatedHardwareAbstractionLayer
    logger: ServiceLoggingManager
    latched_faults: list[FaultType] = field(default_factory=list)

    @property
    def fault_latched(self) -> bool:
        return bool(self.latched_faults)

    @property
    def isolation(self) -> IsolationLevel:
        s = self.hal.sensors
        return isolation_level(s.isolation_kohm, s.output_voltage_v)

    def trip(self, fault: FaultType) -> None:
        """Hard trip: independent of the main controller and of the mission state."""
        self._apply_to_simulation(fault)
        if fault not in self.latched_faults:
            self.latched_faults.append(fault)
        self.hal.safe_outputs(keep_ventilation=fault is not FaultType.FAN_FAILURE)
        self.logger.log(f"Safety trip: {fault.value}", "CRITICAL")

    def evaluate(self, reaction_running: bool) -> FaultType | None:
        """Continuous supervision; returns the fault it tripped on, if any."""
        s = self.hal.sensors
        checks = [
            (not s.hvil_closed, FaultType.HVIL_OPEN),
            (self.isolation is IsolationLevel.BLOCK, FaultType.ISOLATION_BLOCK),
            (s.temperature_c >= baseline.value("thermal", "shutdown_c"), FaultType.OVERTEMPERATURE),
            (s.hydrogen_pct_lel >= MAX_HYDROGEN_PCT_LEL, FaultType.HYDROGEN_ALARM),
            (s.leak_detected, FaultType.LEAK),
            (not s.contactor_feedback_valid, FaultType.CONTACTOR_MISMATCH),
        ]
        if reaction_running:
            low, high = PRESSURE_WINDOW_BAR
            checks += [
                (not low <= s.pressure_bar <= high, FaultType.ABNORMAL_PRESSURE),
                (s.electrolyte_flow_lpm < MIN_FLOW_LPM, FaultType.LOSS_OF_FLOW),
                (not self.hal.pump_available, FaultType.PUMP_FAILURE),
                (not self.hal.blower_available, FaultType.FAN_FAILURE),
            ]
        for failed, fault in checks:
            if failed:
                self.trip(fault)
                return fault
        return None

    def transfer_permitted(self) -> bool:
        s = self.hal.sensors
        return (not self.fault_latched and s.hvil_closed and self.isolation is not IsolationLevel.BLOCK
                and not s.leak_detected and s.contactor_feedback_valid)

    def reset(self) -> None:
        self.latched_faults.clear()

    def _apply_to_simulation(self, fault: FaultType) -> None:
        s = self.hal.sensors
        effects = {
            FaultType.HVIL_OPEN: lambda: setattr(s, "hvil_closed", False),
            FaultType.ISOLATION_BLOCK: lambda: setattr(s, "isolation_kohm", 20.0),
            FaultType.OVERTEMPERATURE: lambda: setattr(s, "temperature_c", 70.0),
            FaultType.HYDROGEN_ALARM: lambda: setattr(s, "hydrogen_pct_lel", 40.0),
            FaultType.LEAK: lambda: setattr(s, "leak_detected", True),
            FaultType.ABNORMAL_PRESSURE: lambda: setattr(s, "pressure_bar", 1.8),
            FaultType.LOSS_OF_FLOW: lambda: setattr(s, "electrolyte_flow_lpm", 0.0),
            FaultType.PUMP_FAILURE: lambda: setattr(self.hal, "pump_available", False),
            FaultType.FAN_FAILURE: lambda: setattr(self.hal, "blower_available", False),
            FaultType.CONTACTOR_MISMATCH: lambda: setattr(s, "contactor_feedback_valid", False),
        }
        if fault in effects:
            effects[fault]()
