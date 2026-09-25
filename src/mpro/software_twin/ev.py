"""EV Communication Manager: CP/PP checks and ISO 15118 → DIN 70121 fallback (simulated).

[8.1] Only a *communication* failure of ISO 15118 triggers a DIN 70121 attempt.
HVIL or isolation failures never trigger a protocol switch — they are safety
events owned by the independent supervisor. No real PLC/SLAC stack exists here.
"""

from __future__ import annotations

from dataclasses import dataclass

# SIMULATED PLACEHOLDERS: IEC 61851 control-pilot state B is nominally 9 V.
CP_STATE_B_RANGE_V = (8.0, 10.0)


class HandshakeFailed(RuntimeError):
    """Both protocols failed; no power transfer may start."""


@dataclass
class EVCommunicationManager:
    connected: bool = False
    protocol: str | None = None

    @staticmethod
    def cp_valid(cp_voltage_v: float) -> bool:
        low, high = CP_STATE_B_RANGE_V
        return low <= cp_voltage_v <= high

    def handshake(self, iso15118_ok: bool = True, din70121_ok: bool = True) -> str:
        if iso15118_ok:
            self.protocol = "ISO 15118"
        elif din70121_ok:
            self.protocol = "DIN 70121"
        else:
            self.protocol = None
            raise HandshakeFailed("ISO 15118 and DIN 70121 communication both failed")
        self.connected = True
        return self.protocol

    def disconnect(self) -> None:
        self.connected = False
        self.protocol = None
