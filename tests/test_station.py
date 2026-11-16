import pytest

from ecoflow_nut.station import InvalidQuota, Reading, decode_quota
from tests.factories import at, reading

QUOTA = {"pd.soc": 87, "inv.acInVol": 229_500, "pd.wattsInSum": 52, "pd.wattsOutSum": 41, "bms_bmsStatus.soc": 87}


def test_decodes_the_quota():
    assert decode_quota(QUOTA, at(0)) == Reading(taken_at=at(0), soc=87, input_v=229.5, input_w=52, output_w=41)


def test_ac_input_decides_on_line():
    assert decode_quota(QUOTA, at(0)).on_line
    assert not decode_quota({**QUOTA, "inv.acInVol": 0}, at(0)).on_line


def test_drain_is_the_output_the_input_does_not_cover():
    assert reading(output_w=40, input_w=0).drain_w == 40
    assert reading(output_w=40, input_w=100).drain_w == 0


@pytest.mark.parametrize("change", [{"pd.soc": None}, {"pd.soc": 101}, {"inv.acInVol": "x"}, {"pd.wattsOutSum": True}])
def test_rejects_a_broken_quota(change):
    with pytest.raises(InvalidQuota):
        decode_quota({**QUOTA, **change}, at(0))
