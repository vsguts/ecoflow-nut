"""Print the EcoFlow cloud's quota for the station as JSON, to check the field mapping in ecoflow_nut/station.py.

The device state goes to stderr, so stdout is a clean JSON file:
    docker compose run --rm -T nut python -m tools.dump_quota > river-2-max-on-line.json
"""

import asyncio
import json
import os
import sys

from ecoflow_nut.config import ConfigError, settings_from_env
from ecoflow_nut.ecoflow_api import EcoFlowApi, EcoFlowError


async def dump() -> int:
    config = settings_from_env(os.environ).ecoflow
    api = EcoFlowApi(config)
    try:
        devices = await api.devices()
        device = next((d for d in devices if d.get("sn") == config.serial), None)
        if device is None:
            bound = ", ".join(f"{d.get('productName')} ({d.get('sn')})" for d in devices) or "none"
            print(f"{config.serial} is not bound to this account. Bound devices: {bound}", file=sys.stderr)
            return 1
        quota = await api.quota()
    finally:
        await api.close()
    state = "online" if device.get("online") == 1 else "OFFLINE, the values are the last ones the cloud saw"
    print(f"{device.get('productName')}: {state}", file=sys.stderr)
    print(json.dumps(quota, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(dump()))
    except (ConfigError, EcoFlowError) as exc:
        sys.exit(f"Error: {exc}")
