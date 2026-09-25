"""[9.1] Storage supervision in SYSTEM_STANDBY: wake sources, awake limit, D-BIT interval.

The controller wakes only from defined sources, runs the periodic built-in test
(D-BIT) within a maximum awake time and returns to sleep with unneeded 660
power domains switched off. The D-BIT interval shortens when the LIC voltage
drops faster than expected, and self-test thresholds are compensated for
temperature to limit false alarms at the -25 / +50 °C extremes.
The awake limit applies to the storage check only — never to water filling or
to post-event purge and cooldown.
"""

from __future__ import annotations

from dataclasses import dataclass

WAKE_SOURCES = frozenset({"USER_WAKE", "DBIT_TIMER", "SERVICE_PORT"})

# SIMULATED PLACEHOLDERS — not validated storage parameters.
MAX_AWAKE_S = 120.0
NOMINAL_DBIT_INTERVAL_H = 168.0
MIN_DBIT_INTERVAL_H = 24.0
EXPECTED_LIC_DROP_MV_PER_DAY = 5.0
LIC_MIN_V_AT_25C = 3.2
LIC_TEMP_COEFF_V_PER_C = 0.004     # colder cell reads lower; threshold follows


def lic_threshold_v(ambient_c: float) -> float:
    """Temperature-compensated LIC self-test threshold."""
    return LIC_MIN_V_AT_25C - LIC_TEMP_COEFF_V_PER_C * (25.0 - ambient_c)


@dataclass
class StorageSupervisor:
    dbit_interval_h: float = NOMINAL_DBIT_INTERVAL_H
    awake: bool = False
    awake_s: float = 0.0

    def accept_wake(self, source: str) -> bool:
        if source not in WAKE_SOURCES:
            return False
        self.awake, self.awake_s = True, 0.0
        return True

    def elapse(self, seconds: float, storage_check: bool = True) -> bool:
        """Advance awake time; returns True when the storage check must go back to sleep."""
        self.awake_s += seconds
        return storage_check and self.awake_s >= MAX_AWAKE_S

    def sleep(self) -> None:
        self.awake, self.awake_s = False, 0.0

    def update_interval(self, lic_drop_mv_per_day: float) -> float:
        if lic_drop_mv_per_day > 1.5 * EXPECTED_LIC_DROP_MV_PER_DAY:
            self.dbit_interval_h = max(MIN_DBIT_INTERVAL_H, self.dbit_interval_h / 2.0)
        else:
            self.dbit_interval_h = NOMINAL_DBIT_INTERVAL_H
        return self.dbit_interval_h

    @staticmethod
    def lic_ok(lic_voltage_v: float, ambient_c: float) -> bool:
        return lic_voltage_v >= lic_threshold_v(ambient_c)
