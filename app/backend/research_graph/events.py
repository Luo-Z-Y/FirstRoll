from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchEvent:
    """A bounded, public progress event safe to expose to the browser."""

    kind: str
    message: str


def event(kind: str, message: str) -> tuple[ResearchEvent, ...]:
    return (ResearchEvent(kind=kind, message=message),)
