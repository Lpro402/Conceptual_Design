"""Enumerations used by the deterministic concept state machine."""

from enum import Enum, auto


class SystemState(Enum):
    STANDBY = auto()
    WAKE_UP_SELF_TEST = auto()
    VEHICLE_CONNECTION = auto()
    CASSETTE_SELECTION = auto()
    WATER_ACTIVATION = auto()
    PRIMING = auto()
    PRE_CHARGE = auto()
    POWER_TRANSFER = auto()
    DERATING = auto()
    RAMP_DOWN = auto()
    PURGE_COOLDOWN = auto()
    READY = auto()
    SERVICE_REQUIRED = auto()
    FAULT_LOCKED = auto()
    EMERGENCY_SHUTDOWN = auto()


class CassetteState(Enum):
    DRY_READY = auto()
    SELECTED = auto()
    ACTIVATING = auto()
    ACTIVE = auto()
    SPENT = auto()
    FAULTED = auto()


class FaultType(Enum):
    E_STOP = "E-Stop"
    HVIL_OPEN = "HVIL open"
    ISOLATION_FAULT = "Isolation fault"
    OVERTEMPERATURE = "Overtemperature"
    HYDROGEN_ALARM = "Hydrogen alarm"
    LEAK = "Leak detected"
    ABNORMAL_PRESSURE = "Abnormal pressure"
    LOSS_OF_FLOW = "Loss of electrolyte flow"
    PUMP_FAILURE = "Pump failure"
    FAN_FAILURE = "Fan failure"
    CONTACTOR_MISMATCH = "Contactor feedback mismatch"

