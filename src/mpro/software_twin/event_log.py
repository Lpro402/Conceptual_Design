"""Service & Logging Manager: timestamped in-memory event log."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class EventRecord:
    timestamp: str
    level: str
    message: str


@dataclass
class ServiceLoggingManager:
    records: list[EventRecord] = field(default_factory=list)

    def log(self, message: str, level: str = "INFO") -> None:
        self.records.append(EventRecord(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=level,
            message=message,
        ))

    def clear(self) -> None:
        self.records.clear()
