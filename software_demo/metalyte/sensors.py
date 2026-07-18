"""Simulated sensors, actuators, and hardware abstraction layer."""

from dataclasses import dataclass, field


@dataclass
class SensorSnapshot:
    # Every numeric value is a SIMULATED PLACEHOLDER.
    stack_voltage_v: float = 57.6
    stack_current_a: float = 0.0
    temperature_c: float = 25.0
    pressure_bar: float = 1.0
    electrolyte_flow_lpm: float = 0.0
    hydrogen_pct: float = 0.0
    leak_detected: bool = False
    hvil_closed: bool = True
    isolation_valid: bool = True
    contactor_feedback_valid: bool = True


@dataclass
class ActuatorCommands:
    water_valve_open: bool = False
    pump_on: bool = False
    fan_on: bool = False
    vent_on: bool = False
    input_contactor_closed: bool = False
    output_contactor_closed: bool = False
    converter_enabled: bool = False
    gate_disable: bool = True


@dataclass
class SimulatedHardwareAbstractionLayer:
    sensors: SensorSnapshot = field(default_factory=SensorSnapshot)
    actuators: ActuatorCommands = field(default_factory=ActuatorCommands)
    pump_available: bool = True
    fan_available: bool = True
    water_confirmed: bool = False

    def reset(self) -> None:
        self.sensors = SensorSnapshot()
        self.actuators = ActuatorCommands()
        self.pump_available = True
        self.fan_available = True
        self.water_confirmed = False

    def safe_outputs(self, keep_ventilation: bool = True) -> None:
        self.actuators.water_valve_open = False
        self.actuators.pump_on = False
        self.actuators.input_contactor_closed = False
        self.actuators.output_contactor_closed = False
        self.actuators.converter_enabled = False
        self.actuators.gate_disable = True
        self.actuators.vent_on = keep_ventilation and self.fan_available
        self.actuators.fan_on = keep_ventilation and self.fan_available
        self.sensors.stack_current_a = 0.0

