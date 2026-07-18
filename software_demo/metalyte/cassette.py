"""Three-cassette lifecycle model."""

from dataclasses import dataclass, field

from .states import CassetteState


@dataclass
class Cassette:
    cassette_id: int
    state: CassetteState = CassetteState.DRY_READY


@dataclass
class CassetteReactionManager:
    cassettes: list[Cassette] = field(
        default_factory=lambda: [Cassette(1), Cassette(2), Cassette(3)]
    )
    selected_id: int | None = None

    @property
    def selected(self) -> Cassette | None:
        if self.selected_id is None:
            return None
        return next(c for c in self.cassettes if c.cassette_id == self.selected_id)

    @property
    def remaining_events(self) -> int:
        return sum(c.state is CassetteState.DRY_READY for c in self.cassettes)

    def select(self, cassette_id: int | None = None) -> Cassette:
        if any(c.state in {CassetteState.SELECTED, CassetteState.ACTIVATING, CassetteState.ACTIVE} for c in self.cassettes):
            raise ValueError("Only one cassette may be selected or active")
        candidates = [c for c in self.cassettes if c.state is CassetteState.DRY_READY]
        if cassette_id is not None:
            candidates = [c for c in candidates if c.cassette_id == cassette_id]
        if not candidates:
            raise ValueError("No Ready cassette is available")
        cassette = candidates[0]
        cassette.state = CassetteState.SELECTED
        self.selected_id = cassette.cassette_id
        return cassette

    def activate_water(self) -> Cassette:
        cassette = self._require_selected(CassetteState.SELECTED)
        cassette.state = CassetteState.ACTIVATING
        return cassette

    def mark_active(self) -> Cassette:
        cassette = self._require_selected(CassetteState.ACTIVATING)
        cassette.state = CassetteState.ACTIVE
        return cassette

    def mark_spent(self) -> Cassette:
        cassette = self._require_selected(
            CassetteState.ACTIVE, CassetteState.ACTIVATING, CassetteState.SELECTED
        )
        cassette.state = CassetteState.SPENT
        self.selected_id = None
        return cassette

    def mark_faulted(self) -> Cassette | None:
        cassette = self.selected
        if cassette and cassette.state is not CassetteState.DRY_READY:
            cassette.state = CassetteState.FAULTED
            self.selected_id = None
            return cassette
        return None

    def reset(self) -> None:
        self.cassettes = [Cassette(1), Cassette(2), Cassette(3)]
        self.selected_id = None

    def _require_selected(self, *allowed: CassetteState) -> Cassette:
        cassette = self.selected
        if cassette is None or cassette.state not in allowed:
            expected = ", ".join(s.name for s in allowed)
            raise ValueError(f"Selected cassette must be in: {expected}")
        return cassette

