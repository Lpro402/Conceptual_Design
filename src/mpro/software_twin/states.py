"""Enumerations of the Configuration 2 software state machine (design 4.6 + Nidbach 4 updates)."""

from enum import Enum, auto


class SystemState(Enum):
    SYSTEM_STANDBY = auto()       # [9.1] sleep with defined wake sources
    SELF_TEST = auto()            # [9.1] temperature-compensated thresholds
    ENVIRONMENT_CHECK = auto()    # [4.1, 5.2] enclosed space / wall / vent obstruction
    AWAIT_DEPLOY = auto()         # [2.1] cable + vent signals + explicit driver confirmation
    AWAIT_CONNECT = auto()        # [8.1] HVIL continuity window, CP levels, isolation
    EV_HANDSHAKE = auto()         # [8.1] ISO 15118 with DIN 70121 fallback on comm failure
    FILL_SESSION = auto()         # [1.1, 1.2] batch filling into chamber 220, valve closed
    CONFIRM_ACTIVATION = auto()   # irreversible activation confirmation
    WATER_ADMISSION = auto()      # reaction clock starts at real admission
    PRIME_FLOW_CHECK = auto()     # KOH dissolution, flow, air, gas path, thermal readiness
    PRECHARGE = auto()
    ACTIVE_POWER = auto()         # 10 kW nominal, 12 kW thermal-limited Boost
    DERATED = auto()
    RAMP_DOWN = auto()
    PURGE_COOLDOWN = auto()
    SAFE_TO_DISCONNECT = auto()
    SERVICE_REQUIRED = auto()
    POWER_ISOLATION = auto()      # critical fault after wetting
    FAULT_LOCKED = auto()


# Nominal mission order used by HMIs and progress indicators.
MISSION_SEQUENCE = (
    SystemState.SYSTEM_STANDBY,
    SystemState.SELF_TEST,
    SystemState.ENVIRONMENT_CHECK,
    SystemState.AWAIT_DEPLOY,
    SystemState.AWAIT_CONNECT,
    SystemState.EV_HANDSHAKE,
    SystemState.FILL_SESSION,
    SystemState.CONFIRM_ACTIVATION,
    SystemState.WATER_ADMISSION,
    SystemState.PRIME_FLOW_CHECK,
    SystemState.PRECHARGE,
    SystemState.ACTIVE_POWER,
    SystemState.RAMP_DOWN,
    SystemState.PURGE_COOLDOWN,
    SystemState.SAFE_TO_DISCONNECT,
)

WET_STATES = frozenset({
    SystemState.WATER_ADMISSION, SystemState.PRIME_FLOW_CHECK, SystemState.PRECHARGE,
    SystemState.ACTIVE_POWER, SystemState.DERATED, SystemState.RAMP_DOWN,
})


class CartridgeState(Enum):
    DRY_READY = auto()
    SELECTED = auto()        # also covers FILL_SESSION: still dry, reversible
    ACTIVATING = auto()      # water admitted: irreversible
    ACTIVE = auto()
    SPENT = auto()
    FAULTED = auto()


class FaultType(Enum):
    E_STOP = "E-Stop"
    HVIL_OPEN = "HVIL open"
    ISOLATION_BLOCK = "Isolation below block threshold"
    OVERTEMPERATURE = "Overtemperature"
    HYDROGEN_ALARM = "Hydrogen alarm"
    LEAK = "Leak detected"
    ABNORMAL_PRESSURE = "Abnormal pressure"
    LOSS_OF_FLOW = "Loss of electrolyte flow"
    PUMP_FAILURE = "Pump failure"
    FAN_FAILURE = "Blower failure"
    CONTACTOR_MISMATCH = "Contactor feedback mismatch"
    SELF_TEST_FAILED = "Self-test failed"


class IsolationLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"   # indication only; continue if every other condition is safe
    BLOCK = "block"       # blocks or stops transfer via the independent supervisor
