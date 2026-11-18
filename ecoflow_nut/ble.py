"""The station over Bluetooth LE, through eflib (EcoFlow's protocol as reverse-engineered by ha-ef-ble).

Only reads: nothing here sends the station a command. The station takes one BLE connection at a time.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from bleak import BleakScanner

import eflib
from eflib.devices import river2, river2_max
from eflib.props.raw_data_field import raw_field

SCAN_TIMEOUT = 30.0


class StationNotFound(Exception):
    pass


class RiverStation(river2_max.Device):
    """RIVER 2 Max, plus the AC input voltage that eflib decodes but does not expose."""

    ac_input_voltage = raw_field(river2.pb_inv.ac_in_vol)


async def find_station(serial: str, timeout: float = SCAN_TIMEOUT) -> RiverStation:
    wanted = serial.encode()
    found: asyncio.Future = asyncio.get_running_loop().create_future()

    def detected(device, advertisement) -> None:
        if not found.done() and eflib.sn_from_advertisement(advertisement) == wanted:
            found.set_result((device, advertisement))

    async with BleakScanner(detected):
        try:
            device, advertisement = await asyncio.wait_for(found, timeout)
        except TimeoutError:
            raise StationNotFound(f"no station {serial} in range within {timeout:.0f} s") from None
    if not RiverStation.check(wanted):
        raise StationNotFound(f"{serial} is not a RIVER 2 Max")
    return RiverStation(device, advertisement, serial)


@dataclass
class BleLink:
    state: RiverStation

    def on_update(self, callback: Callable[[], None]) -> None:
        self.state.on_packet_parsed(lambda _packet: callback())

    async def wait_closed(self) -> None:
        await self.state.wait_disconnected()

    async def close(self) -> None:
        # Also after a failed handshake: the connection object exists and holds BlueZ until disconnected.
        if self.state.connection_state is not None:
            await self.state.disconnect()


def connector(serial: str, user_id: str) -> Callable[[], Awaitable[BleLink]]:
    async def connect() -> BleLink:
        station = await find_station(serial)
        # StationLink owns reconnecting: it rescans, so a station that moved or rebooted is found again.
        station.with_disabled_reconnect()
        link = BleLink(station)
        try:
            await station.connect(user_id=user_id, max_attempts=1)
            state = await station.wait_until_authenticated_or_error(raise_on_error=True)
            if not state.authenticated:
                raise ConnectionError(f"the station did not authenticate us: {state.name}")
        except BaseException:
            await link.close()
            raise
        return link

    return connect
