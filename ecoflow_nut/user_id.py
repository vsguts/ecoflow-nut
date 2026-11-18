"""Print the EcoFlow account's user ID, which the station asks for over Bluetooth (ECOFLOW_USER_ID).

Logs in to the EcoFlow cloud once, as the app does; the password is asked for without echo and kept nowhere:

    docker compose run --rm nut python -m ecoflow_nut.user_id [--region api-e]
"""

import argparse
import asyncio
import getpass
import sys

import aiohttp

from eflib.login import EcoFlowLogin, Region


async def user_id(identifier: str, password: str, region: str) -> str:
    async with aiohttp.ClientSession() as session:
        result = await EcoFlowLogin(session).login(identifier, password, region)
    if result.user_id is None:
        raise SystemExit(result.error or "Login failed")
    return result.user_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecoflow_nut.user_id", description=__doc__.splitlines()[0])
    parser.add_argument("--region", choices=[r.value for r in Region], default=Region.AUTO.value)
    args = parser.parse_args(argv)
    identifier = input("EcoFlow account e-mail: ")
    password = getpass.getpass("Password: ")
    print(f"ECOFLOW_USER_ID={asyncio.run(user_id(identifier, password, args.region))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
