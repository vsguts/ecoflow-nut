import asyncio
import logging
import os
import sys
from datetime import timedelta

from ecoflow_nut.ble import connector
from ecoflow_nut.config import ConfigError, Settings, settings_from_env
from ecoflow_nut.link import StationLink
from ecoflow_nut.nut_server import NutServer
from ecoflow_nut.ups import StationUps
from ecoflow_nut.wake import WakeFile

log = logging.getLogger(__name__)

# Scan, handshake and the first report of every part of the station take about 10 s.
FIRST_READING_WAIT = timedelta(minutes=1)


async def run(settings: Settings) -> None:
    ups = StationUps(settings.model, settings.battery, WakeFile(settings.wake_file))
    link = StationLink(connector(settings.station.serial, settings.station.user_id), ups.update)
    linking = asyncio.create_task(link.run())
    # The first reading comes before the server listens: DSM never sees a UPS without data after a restart.
    try:
        await asyncio.wait_for(link.first_reading.wait(), FIRST_READING_WAIT.total_seconds())
    except TimeoutError:
        log.warning("No reading yet; serving without data until the station reports")
    await asyncio.gather(linking, NutServer(settings.nut, ups.variables).run())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = settings_from_env(os.environ)
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
