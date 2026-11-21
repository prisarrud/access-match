from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from .schemas import PropertyEvidence


@dataclass(frozen=True)
class ActiveComparison:
    properties: list[PropertyEvidence]
    expires_at: float


class ComparisonStore:
    """Bounded, process-local storage for observations from an active comparison."""

    def __init__(
        self, *, ttl_seconds: float = 30 * 60, capacity: int = 128, clock: Callable[[], float] = monotonic,
    ):
        self._ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._clock = clock
        self._entries: dict[str, ActiveComparison] = {}

    def save(self, properties: list[PropertyEvidence]) -> str:
        now = self._clock()
        while self._entries:
            oldest_id = next(iter(self._entries))
            if len(self._entries) < self._capacity and self._entries[oldest_id].expires_at > now:
                break
            del self._entries[oldest_id]

        comparison_id = uuid4().hex
        self._entries[comparison_id] = ActiveComparison(properties, now + self._ttl_seconds)
        return comparison_id

    def get(self, comparison_id: str) -> ActiveComparison | None:
        entry = self._entries.get(comparison_id)
        if entry is not None and entry.expires_at <= self._clock():
            del self._entries[comparison_id]
            return None
        return entry
