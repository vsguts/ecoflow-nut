"""One reading of the station from the EcoFlow cloud quota.

The field names follow EcoFlow's RIVER 2 series documentation and are provisional until checked against a real
dump of this station (tools/dump_quota.py); AC input voltage is in mV, as on the DELTA Pro.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

SOC = "pd.soc"
AC_IN_MILLIVOLTS = "inv.acInVol"
INPUT_W = "pd.wattsInSum"
OUTPUT_W = "pd.wattsOutSum"
# Without AC input the station reports about 0 V; anything it can charge from is far above this.
MIN_AC_VOLTAGE = 180.0


class InvalidQuota(ValueError):
    pass


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


def _number(quota: Mapping[str, object], key: str) -> int | float:
    value = quota.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidQuota(f"{key} is missing or not a number: {value!r}")
    return value


def decode_quota(quota: Mapping[str, object], taken_at: datetime) -> Reading:
    soc = int(_number(quota, SOC))
    if not 0 <= soc <= 100:
        raise InvalidQuota(f"implausible SOC {soc}%")
    return Reading(
        taken_at=taken_at,
        soc=soc,
        input_v=_number(quota, AC_IN_MILLIVOLTS) / 1000,
        input_w=int(_number(quota, INPUT_W)),
        output_w=int(_number(quota, OUTPUT_W)),
    )
