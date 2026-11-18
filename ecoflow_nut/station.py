"""One reading of the station: what the NUT side needs from the values the station reports over Bluetooth."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Without AC input the station reports about 0 V; anything it can charge from is far above this.
MIN_AC_VOLTAGE = 180.0
MILLIVOLTS_PER_VOLT = 1000


class InvalidReading(ValueError):
    pass


class StationState(Protocol):
    """The fields of a connected station (eflib names); None until the station has reported them."""

    battery_level: float | None
    ac_input_voltage: int | None  # mV
    input_power: int | None
    output_power: int | None


@dataclass(frozen=True)
class Reading:
    taken_at: datetime
    soc: int
    input_v: float
    input_w: int
    output_w: int

    @property
    def on_line(self) -> bool:
        return self.input_v >= MIN_AC_VOLTAGE

    @property
    def drain_w(self) -> int:
        """What the battery gives: the output not covered by the input (solar, car charger, AC)."""
        return max(self.output_w - self.input_w, 0)


def _number(state: StationState, name: str) -> int | float:
    value = getattr(state, name, None)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidReading(f"{name} is missing or not a number: {value!r}")
    return value


def read_state(state: StationState, taken_at: datetime) -> Reading:
    soc = round(_number(state, "battery_level"))
    if not 0 <= soc <= 100:
        raise InvalidReading(f"implausible SOC {soc}%")
    return Reading(
        taken_at=taken_at,
        soc=soc,
        input_v=_number(state, "ac_input_voltage") / MILLIVOLTS_PER_VOLT,
        input_w=int(_number(state, "input_power")),
        output_w=int(_number(state, "output_power")),
    )
