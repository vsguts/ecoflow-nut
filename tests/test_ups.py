from datetime import timedelta

from ecoflow_nut.ups import READING_LOST_AFTER, Battery, StationUps
from ecoflow_nut.wake import WakeFile
from tests.factories import at, reading

BATTERY = Battery(low_soc=15, capacity_wh=512)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def make_ups(tmp_path, clock=None):
    return StationUps("RIVER 2 Max", BATTERY, WakeFile(tmp_path / "wake-until"), clock=clock or Clock(at(0)))


def status(ups, *readings):
    for r in readings:
        ups._clock.now = r.taken_at
        ups.update(r)
    return ups.variables()["ups.status"]


def test_no_reading_yet_means_no_data(tmp_path):
    assert make_ups(tmp_path).variables() is None


def test_on_line_and_charging(tmp_path):
    ups = make_ups(tmp_path)
    assert status(ups, reading(0)) == "OL"
    assert status(ups, reading(1, input_w=200, soc=60)) == "OL CHRG"
    assert status(ups, reading(2, input_w=200, soc=100)) == "OL"


def test_variables_describe_the_station(tmp_path):
    ups = make_ups(tmp_path)
    status(ups, reading(0, on_line=False, soc=50, output_w=40))
    variables = ups.variables()
    assert variables["device.model"] == "RIVER 2 Max"
    assert variables["battery.charge"] == "50"
    assert variables["battery.charge.low"] == "15"
    assert variables["input.voltage"] == "0"
    assert variables["ups.realpower"] == "40"
    # 50 % of 512 Wh at 40 W: 6.4 h
    assert variables["battery.runtime"] == str(int(6.4 * 3600))


def test_on_battery_turns_low_only_after_two_low_readings(tmp_path):
    ups = make_ups(tmp_path)
    assert status(ups, reading(0, on_line=False, soc=16)) == "OB"
    assert status(ups, reading(1, on_line=False, soc=15)) == "OB"
    assert status(ups, reading(2, on_line=False, soc=15)) == "OB LB"


def test_one_garbled_low_reading_does_not_count(tmp_path):
    ups = make_ups(tmp_path)
    assert status(ups, reading(0, on_line=False, soc=3), reading(1, on_line=False, soc=60)) == "OB"
    assert status(ups, reading(2, on_line=False, soc=15)) == "OB"


def test_a_low_battery_holds_until_the_charge_is_clearly_above(tmp_path):
    ups = make_ups(tmp_path)
    low = [reading(0, on_line=False, soc=15), reading(1, on_line=False, soc=15)]
    assert status(ups, *low, reading(2, on_line=False, soc=16)) == "OB LB"
    assert status(ups, reading(3, on_line=False, soc=17)) == "OB"


def test_the_ac_input_back_clears_a_low_battery(tmp_path):
    ups = make_ups(tmp_path)
    status(ups, reading(0, on_line=False, soc=15), reading(1, on_line=False, soc=15))
    assert status(ups, reading(2, soc=15, input_w=300)) == "OL CHRG"


def test_lost_readings_keep_the_last_status_while_the_battery_lasts(tmp_path):
    clock = Clock(at(0))
    ups = make_ups(tmp_path, clock)
    status(ups, reading(0, on_line=False, soc=80, output_w=40))
    clock.now = at(0) + READING_LOST_AFTER + timedelta(minutes=1)
    variables = ups.variables()
    assert variables["ups.status"] == "OB"
    assert "input.voltage" not in variables


def test_lost_readings_near_the_threshold_report_a_low_battery(tmp_path):
    clock = Clock(at(0))
    ups = make_ups(tmp_path, clock)
    status(ups, reading(0, on_line=False, soc=17))
    clock.now = at(0) + READING_LOST_AFTER + timedelta(seconds=1)
    assert ups.variables()["ups.status"] == "OB LB"


def test_lost_readings_assume_the_battery_carries_the_output(tmp_path):
    # A power cut may take the host's adapter down with the AC input: from 80 % at 40 W, 512 Wh reach 15 % in
    # 65 % × 512 / 40 = 8.32 h, even if the last reading was on line.
    clock = Clock(at(0))
    ups = make_ups(tmp_path, clock)
    status(ups, reading(0, soc=80, output_w=40))
    clock.now = at(0) + timedelta(hours=8)
    assert ups.variables()["ups.status"] == "OL"
    clock.now = at(0) + timedelta(hours=8.4)
    assert ups.variables()["ups.status"] == "OB LB"


def test_a_wake_masks_only_a_plain_on_battery(tmp_path):
    ups = make_ups(tmp_path)
    ups._wake.start(at(0))
    assert status(ups, reading(0, on_line=False, soc=60)) == "OL"
    assert status(ups, reading(1, on_line=False, soc=15), reading(2, on_line=False, soc=15)) == "OB LB"


def test_a_wake_ends_by_itself(tmp_path):
    ups = make_ups(tmp_path)
    until = ups._wake.start(at(0))
    ups._clock.now = until
    ups.update(reading(0, on_line=False, soc=60))
    assert ups.variables()["ups.status"] == "OB"
