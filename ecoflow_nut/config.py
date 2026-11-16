from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ecoflow_nut.ecoflow_api import DEFAULT_API_URL, EcoFlowConfig
from ecoflow_nut.nut_server import DEFAULT_PORT, UpsConfig
from ecoflow_nut.ups import Battery
from ecoflow_nut.wake import DEFAULT_WAKE_FILE


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    ecoflow: EcoFlowConfig
    nut: UpsConfig
    battery: Battery
    model: str
    poll_interval: float
    wake_file: Path


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _number(env: Mapping[str, str], name: str, default: str, *, low: float, high: float) -> float:
    raw = env.get(name, "").strip() or default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low:g} and {high:g}, got {raw}")
    return value


def settings_from_env(env: Mapping[str, str]) -> Settings:
    return Settings(
        ecoflow=EcoFlowConfig(
            access_key=_required(env, "ECOFLOW_ACCESS_KEY"),
            secret_key=_required(env, "ECOFLOW_SECRET_KEY"),
            serial=_required(env, "ECOFLOW_SERIAL"),
            api_url=env.get("ECOFLOW_API_URL", "").strip() or DEFAULT_API_URL,
        ),
        nut=UpsConfig(
            port=int(_number(env, "NUT_PORT", str(DEFAULT_PORT), low=1, high=65535)),
            user=env.get("NUT_USER", "").strip() or UpsConfig.user,
            password=env.get("NUT_PASSWORD", "").strip() or UpsConfig.password,
        ),
        battery=Battery(
            low_soc=int(_number(env, "LOW_SOC", "15", low=1, high=90)),
            # RIVER 2 Max: 512 Wh.
            capacity_wh=_number(env, "BATTERY_CAPACITY_WH", "512", low=1, high=100_000),
        ),
        model=env.get("STATION_MODEL", "").strip() or "RIVER 2 Max",
        # Each poll is two API calls (device list, quota); 30 s keeps well inside the cloud's limits.
        poll_interval=_number(env, "POLL_INTERVAL", "30", low=5, high=300),
        wake_file=Path(env.get("WAKE_FILE", "").strip() or DEFAULT_WAKE_FILE),
    )
