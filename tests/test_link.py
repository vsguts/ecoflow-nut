import asyncio
import logging
from datetime import timedelta
from types import SimpleNamespace

from ecoflow_nut import link as link_module
from ecoflow_nut.link import StationLink
from tests.factories import BASE

GOOD = {"battery_level": 70.4, "ac_input_voltage": 0, "input_power": 0, "output_power": 38}


class FakeLink:
    def __init__(self, **state):
        self.state = SimpleNamespace(**state)
        self.callbacks = []
        self.closed = asyncio.Event()
        self.close_calls = 0

    def on_update(self, callback):
        self.callbacks.append(callback)

    def report(self, **change):
        vars(self.state).update(change)
        for callback in self.callbacks:
            callback()

    async def wait_closed(self):
        await self.closed.wait()

    async def close(self):
        self.close_calls += 1


class Clock:
    def __init__(self):
        self.now = BASE

    def __call__(self):
        return self.now


def make(connect, clock=None):
    readings = []
    station_link = StationLink(connect, readings.append, clock=clock or Clock(), retry_delay=timedelta(0))
    return station_link, readings


async def test_reports_become_readings_once_the_station_has_reported_everything():
    fake = FakeLink(battery_level=None, ac_input_voltage=None, input_power=None, output_power=None)

    async def connect():
        return fake

    station_link, readings = make(connect)
    session = asyncio.create_task(station_link.session())
    await asyncio.sleep(0)
    fake.report(battery_level=70.4)
    assert readings == [] and not station_link.first_reading.is_set()
    fake.report(**GOOD)
    assert [(r.soc, r.on_line, r.output_w) for r in readings] == [(70, False, 38)]
    assert station_link.first_reading.is_set()
    fake.closed.set()
    await session
    assert fake.close_calls == 1


async def test_a_quiet_link_is_dropped(monkeypatch):
    monkeypatch.setattr(link_module, "WATCH_STEP", timedelta(0))
    clock = Clock()
    fake = FakeLink(**GOOD)

    async def connect():
        return fake

    station_link, _ = make(connect, clock)
    session = asyncio.create_task(station_link.session())
    await asyncio.sleep(0)
    clock.now += link_module.STALL_AFTER + timedelta(seconds=1)
    await asyncio.wait_for(session, 1)
    assert fake.close_calls == 1


async def test_connect_failures_never_escape_and_log_once(caplog):
    async def connect():
        raise TimeoutError("no station in range")

    station_link, readings = make(connect)
    with caplog.at_level(logging.WARNING):
        await station_link.session()
        await station_link.session()
    assert readings == []
    assert len(caplog.records) == 1
