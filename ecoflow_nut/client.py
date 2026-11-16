from datetime import datetime

from ecoflow_nut.ecoflow_api import EcoFlowApi, EcoFlowConfig, EcoFlowError
from ecoflow_nut.station import InvalidQuota, Reading, decode_quota

ONLINE = 1


class StationClient:
    def __init__(self, config: EcoFlowConfig):
        self._serial = config.serial
        self._api = EcoFlowApi(config)

    async def read(self, taken_at: datetime) -> Reading:
        await self._ensure_online()
        try:
            return decode_quota(await self._api.quota(), taken_at)
        except InvalidQuota as exc:
            raise EcoFlowError(str(exc)) from exc

    async def close(self) -> None:
        await self._api.close()

    # The cloud answers an offline station's quota with its last values: a lost AC input would never show.
    async def _ensure_online(self) -> None:
        devices = await self._api.devices()
        station = next((d for d in devices if d.get("sn") == self._serial), None)
        if station is None:
            raise EcoFlowError(f"station {self._serial} is not bound to this EcoFlow account")
        if station.get("online") != ONLINE:
            raise EcoFlowError(f"station {self._serial} is offline")
