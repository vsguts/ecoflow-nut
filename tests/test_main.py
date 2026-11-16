import logging

import pytest

from ecoflow_nut.client import StationClient
from ecoflow_nut.ecoflow_api import EcoFlowError
from ecoflow_nut.main import poll_once
from ecoflow_nut.ups import Battery, StationUps
from ecoflow_nut.wake import WakeFile
from tests.factories import reading
from tests.fake_ecoflow import FakeCloud


def make_ups(tmp_path):
    return StationUps("RIVER 2 Max", Battery(15, 512), WakeFile(tmp_path / "wake"))


async def test_a_poll_feeds_the_ups(tmp_path):
    ups = make_ups(tmp_path)

    async def read(now):
        return reading(0, soc=70)

    assert await poll_once(read, ups, failing=False) is False
    assert ups._reading.soc == 70


async def test_failures_keep_the_last_reading_and_log_once(tmp_path, caplog):
    ups = make_ups(tmp_path)
    ups.update(reading(0, soc=70))

    async def read(now):
        raise EcoFlowError("offline")

    with caplog.at_level(logging.WARNING):
        assert await poll_once(read, ups, failing=False) is True
        assert await poll_once(read, ups, failing=True) is True
    assert len(caplog.records) == 1
    assert ups._reading.soc == 70


async def test_the_client_reads_an_online_station():
    async with FakeCloud() as cloud:
        cloud.quota = {"pd.soc": 64, "inv.acInVol": 0, "pd.wattsInSum": 0, "pd.wattsOutSum": 38}
        client = StationClient(cloud.config())
        try:
            r = await client.read(reading().taken_at)
        finally:
            await client.close()
    assert (r.soc, r.on_line, r.output_w) == (64, False, 38)


async def test_the_client_refuses_an_offline_station():
    async with FakeCloud() as cloud:
        cloud.devices = [{**cloud.devices[0], "online": 0}]
        client = StationClient(cloud.config())
        try:
            with pytest.raises(EcoFlowError, match="offline"):
                await client.read(reading().taken_at)
        finally:
            await client.close()
