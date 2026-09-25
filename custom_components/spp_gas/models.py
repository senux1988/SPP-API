"""Data models for the SPP Gas integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SppGasPoint:
    """SPP delivery point."""

    id: str
    name: str
    pod: str | None
    address: str | None
    meter: str | None

    @property
    def label(self) -> str:
        """Return a user-friendly point label."""
        parts = [self.name]
        if self.address:
            parts.append(self.address)
        if self.pod:
            parts.append(self.pod)
        return " - ".join(part for part in parts if part)


@dataclass(frozen=True)
class SppGasReading:
    """Dated gas meter reading."""

    date: str
    value: float
    meter: str | None
    consumption: float | None
    raw: dict[str, Any]
