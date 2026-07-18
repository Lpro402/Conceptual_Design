"""Conceptual power-path manager; no real electrical I/O."""

from dataclasses import dataclass

from .sensors import SimulatedHardwareAbstractionLayer


@dataclass
class PowerControlManager:
    hal: SimulatedHardwareAbstractionLayer
    precharge_complete: bool = False
    requested_power_kw: float = 3.0  # SIMULATED PLACEHOLDER

    def precharge(self) -> None:
        self.hal.actuators.input_contactor_closed = True
        self.precharge_complete = True

    def enable_transfer(self) -> None:
        if not self.precharge_complete:
            raise ValueError("Pre-charge is incomplete")
        a = self.hal.actuators
        a.gate_disable = False
        a.converter_enabled = True
        a.output_contactor_closed = True
        self.hal.sensors.stack_current_a = 52.0  # SIMULATED PLACEHOLDER

    def derate(self) -> None:
        self.requested_power_kw = 1.5  # SIMULATED PLACEHOLDER
        self.hal.sensors.stack_current_a = 26.0

    def controlled_stop(self) -> None:
        self.hal.sensors.stack_current_a = 0.0
        self.hal.actuators.converter_enabled = False
        self.hal.actuators.output_contactor_closed = False
        self.hal.actuators.gate_disable = True

    def isolate(self) -> None:
        self.controlled_stop()
        self.hal.actuators.input_contactor_closed = False
        self.precharge_complete = False

    def emergency_disable(self) -> None:
        self.isolate()

    def reset(self) -> None:
        self.precharge_complete = False
        self.requested_power_kw = 3.0

