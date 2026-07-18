"""Conceptual thermal/fluid controls for the academic demonstrator."""

from dataclasses import dataclass

from .sensors import SimulatedHardwareAbstractionLayer


@dataclass
class ThermalFluidManager:
    hal: SimulatedHardwareAbstractionLayer
    priming_complete: bool = False

    def admit_water(self) -> None:
        self.hal.actuators.water_valve_open = True
        self.hal.water_confirmed = True

    def prime(self) -> None:
        if not self.hal.water_confirmed:
            raise ValueError("Water activation is not confirmed")
        if not self.hal.pump_available or not self.hal.fan_available:
            raise ValueError("Pump and fan must be available")
        a = self.hal.actuators
        a.pump_on = True
        a.fan_on = True
        a.vent_on = True
        self.hal.sensors.electrolyte_flow_lpm = 2.2  # SIMULATED PLACEHOLDER
        self.priming_complete = True

    def begin_purge(self) -> None:
        a = self.hal.actuators
        a.water_valve_open = False
        a.pump_on = False
        a.fan_on = self.hal.fan_available
        a.vent_on = self.hal.fan_available
        self.hal.sensors.electrolyte_flow_lpm = 0.0

    def complete_purge(self) -> None:
        self.hal.actuators.fan_on = False
        self.hal.actuators.vent_on = False

    def protective_shutdown(self) -> None:
        self.hal.safe_outputs(keep_ventilation=True)

    def reset(self) -> None:
        self.priming_complete = False

