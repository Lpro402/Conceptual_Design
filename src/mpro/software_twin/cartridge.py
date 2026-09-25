"""Cartridge & Reaction Manager: three cartridges, one active, and the Config 2 fill session."""

from __future__ import annotations

from dataclasses import dataclass, field

from mpro import baseline

from .states import CartridgeState


@dataclass
class Cartridge:
    cartridge_id: int
    state: CartridgeState = CartridgeState.DRY_READY
    delivered_kwh: float = 0.0


@dataclass
class FillSession:
    """[1.1, 1.2] Water is collected in chamber 220 while the cartridge valve stays closed.

    Pouring may pause and resume without cancelling the session. A controller
    restart invalidates the measurement: water is never admitted automatically
    after a restart; a new measurement and a new confirmation are required.
    """

    measured_l: float = 0.0
    measurement_valid: bool = True
    confirmed: bool = False

    @property
    def target_l(self) -> float:
        return baseline.value("water", "target_l")

    @property
    def missing_l(self) -> float:
        return max(0.0, self.target_l - self.measured_l)

    @property
    def overfilled(self) -> bool:
        return self.measured_l > baseline.value("water", "reject_above_l")

    @property
    def ready(self) -> bool:
        return self.measurement_valid and baseline.value("water", "minimum_l") <= self.measured_l <= baseline.value("water", "reject_above_l")

    def pour(self, liters: float) -> None:
        if liters <= 0:
            raise ValueError("Poured volume must be positive")
        self.measured_l = round(self.measured_l + liters, 3)
        self.confirmed = False

    def restart(self) -> None:
        self.measurement_valid = False
        self.confirmed = False

    def remeasure(self, measured_l: float) -> None:
        self.measured_l = measured_l
        self.measurement_valid = True

    def progress_message(self) -> str:
        return f"Received {self.measured_l:.1f} of {self.target_l:.1f} L. Missing {self.missing_l:.1f} L."


@dataclass
class CartridgeManager:
    cartridges: list[Cartridge] = field(default_factory=lambda: [Cartridge(i) for i in (1, 2, 3)])
    selected_id: int | None = None

    @property
    def selected(self) -> Cartridge | None:
        if self.selected_id is None:
            return None
        return next(c for c in self.cartridges if c.cartridge_id == self.selected_id)

    @property
    def remaining_events(self) -> int:
        return sum(c.state is CartridgeState.DRY_READY for c in self.cartridges)

    @property
    def wetted(self) -> bool:
        c = self.selected
        return c is not None and c.state in {CartridgeState.ACTIVATING, CartridgeState.ACTIVE}

    def select(self, cartridge_id: int | None = None) -> Cartridge:
        if self.selected is not None:
            raise ValueError("Only one cartridge may be selected or active")
        candidates = [c for c in self.cartridges if c.state is CartridgeState.DRY_READY]
        if cartridge_id is not None:
            candidates = [c for c in candidates if c.cartridge_id == cartridge_id]
        if not candidates:
            raise ValueError("No DRY_READY cartridge is available")
        cartridge = candidates[0]
        cartridge.state = CartridgeState.SELECTED
        self.selected_id = cartridge.cartridge_id
        return cartridge

    def cancel_before_wetting(self) -> Cartridge:
        cartridge = self._require(CartridgeState.SELECTED)
        cartridge.state = CartridgeState.DRY_READY
        self.selected_id = None
        return cartridge

    def admit_water(self) -> Cartridge:
        cartridge = self._require(CartridgeState.SELECTED)
        cartridge.state = CartridgeState.ACTIVATING
        return cartridge

    def mark_active(self) -> Cartridge:
        cartridge = self._require(CartridgeState.ACTIVATING)
        cartridge.state = CartridgeState.ACTIVE
        return cartridge

    def mark_spent(self, delivered_kwh: float) -> Cartridge:
        cartridge = self._require(CartridgeState.ACTIVE, CartridgeState.ACTIVATING)
        cartridge.state = CartridgeState.SPENT
        cartridge.delivered_kwh = delivered_kwh
        self.selected_id = None
        return cartridge

    def mark_faulted(self) -> Cartridge | None:
        cartridge = self.selected
        if cartridge is None:
            return None
        if cartridge.state is CartridgeState.SELECTED:     # still dry: back to storage
            return self.cancel_before_wetting()
        cartridge.state = CartridgeState.FAULTED
        self.selected_id = None
        return cartridge

    def _require(self, *allowed: CartridgeState) -> Cartridge:
        cartridge = self.selected
        if cartridge is None or cartridge.state not in allowed:
            raise ValueError("Selected cartridge must be in: " + ", ".join(s.name for s in allowed))
        return cartridge
