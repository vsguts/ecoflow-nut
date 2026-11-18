import pytest

from ecoflow_nut.config import ConfigError, settings_from_env

ENV = {"ECOFLOW_SERIAL": "R611", "ECOFLOW_USER_ID": "1234"}


def test_defaults_fit_a_river_2_max_watched_by_dsm():
    settings = settings_from_env(ENV)
    assert (settings.station.serial, settings.station.user_id) == ("R611", "1234")
    assert (settings.nut.port, settings.nut.user, settings.nut.password) == (3493, "monuser", "secret")
    assert (settings.battery.low_soc, settings.battery.capacity_wh) == (15, 512)
    assert settings.model == "RIVER 2 Max"
    assert str(settings.wake_file) == "/app/data/wake-until"


def test_overrides():
    settings = settings_from_env({**ENV, "NUT_PORT": "13493", "LOW_SOC": "10", "BATTERY_CAPACITY_WH": "1024"})
    assert (settings.nut.port, settings.battery.low_soc, settings.battery.capacity_wh) == (13493, 10, 1024)


@pytest.mark.parametrize(
    "change",
    [{"ECOFLOW_SERIAL": " "}, {"ECOFLOW_USER_ID": ""}, {"LOW_SOC": "0"}, {"LOW_SOC": "x"}, {"NUT_PORT": "70000"}],
)
def test_rejects_bad_settings(change):
    with pytest.raises(ConfigError):
        settings_from_env({**ENV, **change})
