import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from ecoflow_nut.client import StationClient
from ecoflow_nut.config import ConfigError, Settings, settings_from_env
from ecoflow_nut.ecoflow_api import EcoFlowError
from ecoflow_nut.nut_server import NutServer
from ecoflow_nut.station import Reading
from ecoflow_nut.ups import StationUps
from ecoflow_nut.wake import WakeFile

log = logging.getLogger(__name__)

Read = Callable[[datetime], Awaitable[Reading]]


async def poll_once(read: Read, ups: StationUps, failing: bool) -> bool:
    """Returns whether the station is failing now; logs only the changes, not every failed poll."""
    try:
        reading = await read(datetime.now(UTC))
    except EcoFlowError as exc:
        if not failing:
            log.warning("No reading, keeping the last one: %s", exc)
        return True
    if failing:
        log.info("Readings are back")
    ups.update(reading)
    return False


async def poll(read: Read, ups: StationUps, interval: float) -> None:
    failing = False
    while True:
        failing = await poll_once(read, ups, failing)
        await asyncio.sleep(interval)


async def run(settings: Settings) -> None:
    client = StationClient(settings.ecoflow)
    ups = StationUps(settings.model, settings.battery, WakeFile(settings.wake_file))
    # The first reading comes before the server listens: DSM never sees a UPS without data after a restart.
    await poll_once(client.read, ups, failing=False)
    try:
        await asyncio.gather(
            poll(client.read, ups, settings.poll_interval),
            NutServer(settings.nut, ups.variables).run(),
        )
    finally:
        await client.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = settings_from_env(os.environ)
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
