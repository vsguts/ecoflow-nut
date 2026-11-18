from types import SimpleNamespace

import pytest

from ecoflow_nut.station import InvalidReading, Reading, read_state
from tests.factories import at, reading

STATE = {"battery_level": 86.62, "ac_input_voltage": 229_500, "input_power": 52, "output_power": 41}


def state(**change) -> SimpleNamespace:
    return SimpleNamespace(**{**STATE, **change})


def test_reads_the_station_state():
    assert read_state(state(), at(0)) == Reading(taken_at=at(0), soc=87, input_v=229.5, input_w=52, output_w=41)


def test_ac_input_decides_on_line():
    assert read_state(state(), at(0)).on_line
    assert not read_state(state(ac_input_voltage=0), at(0)).on_line


def test_drain_is_the_output_the_input_does_not_cover():
    assert reading(output_w=40, input_w=0).drain_w == 40
    assert reading(output_w=40, input_w=100).drain_w == 0


@pytest.mark.parametrize(
    "change",
    [{"battery_level": None}, {"battery_level": 101}, {"ac_input_voltage": "x"}, {"output_power": True}],
)
def test_rejects_a_state_it_cannot_trust(change):
    with pytest.raises(InvalidReading):
        read_state(state(**change), at(0))
