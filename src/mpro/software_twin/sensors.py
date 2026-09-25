"""Simulated hardware abstraction layer (HAL). No real I/O of any kind.

Reaction-side measurements (stack voltage/current, temperature, H₂) are written
by the chemical twin plant; interface-side signals are set by scenarios or the
operator. Every number is a SIMULATED PLACEHOLDER.
"""

from dataclasses import dataclass, field


@dataclass
class SensorSnapshot:
    # Reaction side (fed by the chemical twin plant)
    stack_voltage_v: float = 0.0
    stack_current_a: float = 0.0
    net_power_kw: float = 0.0
    temperature_c: float = 25.0
    electrolyte_flow_lpm: float = 0.0
    pressure_bar: float = 1.0
    hydrogen_pct_lel: float = 0.0
    leak_detected: bool = False
    # Environment and deployment
    ambient_c: float = 25.0
    vent_path_clear: bool = True
    cable_deployed: bool = True
    vent_deployed: bool = True
    # Vehicle interface
    hvil_closed: bool = True
    cp_voltage_v: float = 9.0            # IEC 61851 state B (vehicle connected)
    isolation_kohm: float = 2000.0       # IMD 490 reading
    output_voltage_v: float = 400.0      # vehicle-side DC voltage
    contactor_feedback_valid: bool = True
    # Water metering in chamber 220
    water_measured_l: float = 0.0
    # Storage
    lic_voltage_v: float = 3.8


@dataclass
class ActuatorCommands:
    cartridge_water_valve_open: bool = False
    pump_on: bool = False
    process_blower_on: bool = False
    tunnel_blower_on: bool = False       # blower 370 over fins 380 in tunnel 390
    vent_open: bool = False
    input_contactor_closed: bool = False
    output_contactor_closed: bool = False
    converter_enabled: bool = False
    gate_disable: bool = True
    aux_domains_on: bool = False         # [9.1] 660 power domains


@dataclass
class SimulatedHardwareAbstractionLayer:
    sensors: SensorSnapshot = field(default_factory=SensorSnapshot)
    actuators: ActuatorCommands = field(default_factory=ActuatorCommands)
    pump_available: bool = True
    blower_available: bool = True
    hvil_samples: list[bool] = field(default_factory=list)

    def reset(self) -> None:
        self.sensors = SensorSnapshot()
        self.actuators = ActuatorCommands()
        self.pump_available = True
        self.blower_available = True
        self.hvil_samples = []

    def sample_hvil(self, samples: int) -> list[bool]:
        """Sample HVIL continuity over the verification window."""
        self.hvil_samples = [self.sensors.hvil_closed] * samples
        return self.hvil_samples

    def safe_outputs(self, keep_ventilation: bool = True) -> None:
        a = self.actuators
        a.cartridge_water_valve_open = False
        a.pump_on = False
        a.input_contactor_closed = False
        a.output_contactor_closed = False
        a.converter_enabled = False
        a.gate_disable = True
        ventilate = keep_ventilation and self.blower_available
        a.process_blower_on = ventilate
        a.tunnel_blower_on = ventilate
        a.vent_open = True
        self.sensors.stack_current_a = 0.0
        self.sensors.net_power_kw = 0.0
