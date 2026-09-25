"""Power & LIC Manager: pre-charge, power reference, Boost permission and isolation."""

from __future__ import annotations

from dataclasses import dataclass

from mpro import baseline

from .sensors import SimulatedHardwareAbstractionLayer


@dataclass
class PowerControlManager:
    hal: SimulatedHardwareAbstractionLayer
    precharge_complete: bool = False
    reference_kw: float = 0.0

    @property
    def nominal_kw(self) -> float:
        return baseline.value("operating_point", "net_power_nominal_kw")

    @property
    def boost_kw(self) -> float:
        return baseline.value("operating_point", "net_power_boost_kw")

    def precharge(self) -> None:
        self.hal.actuators.input_contactor_closed = True
        self.precharge_complete = True

    def enable_transfer(self, requested_kw: float) -> None:
        if not self.precharge_complete:
            raise ValueError("Pre-charge is incomplete")
        a = self.hal.actuators
        a.gate_disable = False
        a.converter_enabled = True
        a.output_contactor_closed = True
        self.reference_kw = min(requested_kw, self.nominal_kw)

    def limit(self, requested_kw: float, boost_allowed: bool, derate_factor: float = 1.0) -> float:
        """Approved reference: Boost only with thermal permission, scaled by derating."""
        ceiling = self.boost_kw if boost_allowed else self.nominal_kw
        self.reference_kw = max(0.0, min(requested_kw, ceiling) * derate_factor)
        return self.reference_kw

    def controlled_stop(self) -> None:
        self.reference_kw = 0.0
        a = self.hal.actuators
        a.converter_enabled = False
        a.output_contactor_closed = False
        a.gate_disable = True
        self.hal.sensors.stack_current_a = 0.0
        self.hal.sensors.net_power_kw = 0.0

    def isolate(self) -> None:
        self.controlled_stop()
        self.hal.actuators.input_contactor_closed = False
        self.precharge_complete = False
