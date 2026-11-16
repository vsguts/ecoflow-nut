from datetime import UTC, datetime, timedelta

from ecoflow_nut.station import Reading

BASE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
POLL = timedelta(seconds=30)


def at(poll: int) -> datetime:
    return BASE + poll * POLL


def reading(poll: int = 0, *, soc: int = 80, on_line: bool = True, input_w: int = 0, output_w: int = 40) -> Reading:
    return Reading(taken_at=at(poll), soc=soc, input_v=230.0 if on_line else 0.0, input_w=input_w, output_w=output_w)
