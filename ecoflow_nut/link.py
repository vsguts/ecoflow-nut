"""Keeps a link to the station open and turns what it reports into readings.

The transport (ecoflow_nut.ble) only opens one link; this loop reconnects, watches for a link that stays up but
goes quiet, and logs changes rather than every failed attempt.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ecoflow_nut.station import InvalidReading, Reading, StationState, read_state

log = logging.getLogger(__name__)

# The station reports several times a second; a minute of silence means a link that is up only on paper.
STALL_AFTER = timedelta(minutes=1)
RETRY_DELAY = timedelta(seconds=20)
WATCH_STEP = timedelta(seconds=5)
# The station reports several times a second, but StationUps counts readings: it wants a low charge confirmed by
# readings some time apart, not by two packets of the same second.
READING_EVERY = timedelta(seconds=10)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Link(Protocol):
    state: StationState

    def on_update(self, callback: Callable[[], None]) -> None: ...

    async def wait_closed(self) -> None: ...

    async def close(self) -> None: ...


class StationLink:
    def __init__(
        self,
        connect: Callable[[], Awaitable[Link]],
        on_reading: Callable[[Reading], None],
        *,
        clock: Callable[[], datetime] = _utc_now,
        retry_delay: timedelta = RETRY_DELAY,
    ):
        self._connect = connect
        self._on_reading = on_reading
        self._clock = clock
        self._retry_delay = retry_delay
        self._last_update = clock()
        self._last_reading: datetime | None = None
        self._last_error: str | None = None
        self.first_reading = asyncio.Event()

    async def run(self) -> None:
        while True:
            await self.session()
            await asyncio.sleep(self._retry_delay.total_seconds())

    async def session(self) -> None:
        """One link from connect to its loss; never raises, so the loop keeps going whatever the transport does."""
        try:
            link = await self._connect()
        # A daemon's supervisor: BlueZ, bleak and eflib each raise their own types, and every one means "retry".
        except Exception as exc:  # noqa: BLE001
            self._failed(exc)
            return
        log.info("Connected to the station")
        self._last_error = None
        self._last_update = self._clock()
        link.on_update(lambda: self._publish(link.state))
        try:
            await self._watch(link)
        finally:
            await link.close()

    def _publish(self, state: StationState) -> None:
        now = self._clock()
        self._last_update = now
        if self._last_reading is not None and now - self._last_reading < READING_EVERY:
            return
        try:
            reading = read_state(state, now)
        except InvalidReading:
            return  # Right after connecting, until every part of the station has reported once.
        self._last_reading = now
        self._on_reading(reading)
        self.first_reading.set()

    async def _watch(self, link: Link) -> None:
        closed = asyncio.ensure_future(link.wait_closed())
        try:
            while True:
                done, _ = await asyncio.wait({closed}, timeout=WATCH_STEP.total_seconds())
                if done:
                    log.warning("Lost the link to the station")
                    return
                if self._clock() - self._last_update > STALL_AFTER:
                    log.warning("The station has gone quiet; reconnecting")
                    return
        finally:
            closed.cancel()

    def _failed(self, exc: Exception) -> None:
        error = f"{type(exc).__name__}: {exc}"
        if error != self._last_error:
            log.warning("Cannot connect to the station: %s", error)
        self._last_error = error
