"""User-instruction mapping for the local dashboard."""

from dataclasses import dataclass

from .states import SystemState


INSTRUCTIONS = {
    SystemState.STANDBY: "Wake the demonstrator to begin.",
    SystemState.WAKE_UP_SELF_TEST: "Run the simulated self-test.",
    SystemState.VEHICLE_CONNECTION: "Connect the simulated vehicle.",
    SystemState.CASSETTE_SELECTION: "Select one dry Ready cassette.",
    SystemState.WATER_ACTIVATION: "Confirm simulated water addition.",
    SystemState.PRIMING: "Prime the simulated fluid and ventilation paths.",
    SystemState.PRE_CHARGE: "Complete pre-charge, then start power transfer.",
    SystemState.POWER_TRANSFER: "Energy transfer is simulated. Stop when complete.",
    SystemState.DERATING: "Power is derated; monitor or stop the event.",
    SystemState.RAMP_DOWN: "Advance the controlled shutdown sequence.",
    SystemState.PURGE_COOLDOWN: "Complete purge/cooldown before disconnecting.",
    SystemState.READY: "A further rescue event is available.",
    SystemState.SERVICE_REQUIRED: "Three events are complete; simulated service is required.",
    SystemState.FAULT_LOCKED: "Fault is latched. Reset the demonstrator.",
    SystemState.EMERGENCY_SHUTDOWN: "Emergency shutdown active; advance to the locked state.",
}


@dataclass
class HMIManager:
    def instruction_for(self, state: SystemState) -> str:
        return INSTRUCTIONS[state]

