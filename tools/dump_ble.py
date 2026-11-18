"""Connect to the station, let it report for a while and print every field eflib decodes, to check the mapping
in ecoflow_nut/station.py. Stop ecoflow-nut first: the station takes one BLE connection at a time.

    docker compose run --rm -T nut python -m tools.dump_ble [seconds] > river-2-max-on-line.txt
"""

import asyncio
import os
import sys

from ecoflow_nut.ble import connector
from ecoflow_nut.config import ConfigError, settings_from_env


async def dump(seconds: float) -> None:
    station = settings_from_env(os.environ).station
    link = await connector(station.serial, station.user_id)()
    try:
        await asyncio.sleep(seconds)
        print(link.state)
    finally:
        await link.close()


if __name__ == "__main__":
    try:
        asyncio.run(dump(float(sys.argv[1]) if len(sys.argv) > 1 else 20))
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
