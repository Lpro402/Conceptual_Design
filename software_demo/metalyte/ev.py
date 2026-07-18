"""Simulated EV communication boundary (not CCS2 or PLC)."""

from dataclasses import dataclass


@dataclass
class EVCommunicationManager:
    connected: bool = False
    handshake_valid: bool = False

    def connect(self) -> None:
        self.connected = True
        self.handshake_valid = True

    def disconnect(self) -> None:
        self.connected = False
        self.handshake_valid = False

