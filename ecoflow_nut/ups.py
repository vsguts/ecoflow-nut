"""The station as a NUT UPS: its latest reading turned into NUT variables, with the admin's wake on top."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ecoflow_nut.station import Reading
from ecoflow_nut.wake import WakeFile

MFR = "EcoFlow"
# Several missed polls in a row: the station is offline or the cloud unreachable, not just slow once.
READING_LOST_AFTER = timedelta(minutes=2)
# A reading lost this close to the threshold leaves too little to wait for.
LOST_NEAR_LOW = 2
# Once reported, a low battery holds until the charge is this far above the threshold: a 14 % / 15 % jitter
# would otherwise clear it before the NAS acts on it.
LOW_RELEASE_MARGIN = 2


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Battery:
    low_soc: int
    capacity_wh: float


class StationUps:
    def __init__(
        self,
        model: str,
        battery: Battery,
        wake: WakeFile,
        *,
        confirm_polls: int = 2,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._model = model
        self._battery = battery
        self._wake = wake
        self._confirm_polls = confirm_polls
        self._clock = clock
        self._reading: Reading | None = None
        self._low_streak = 0
        self._low = False

    def update(self, reading: Reading) -> None:
        self._reading = reading
        low_soc = self._battery.low_soc
        if reading.on_line:
            self._low_streak, self._low = 0, False
        elif reading.soc <= low_soc:
            # One garbled reading must not take the NAS down: the charge has to stay low for several polls.
            self._low_streak += 1
            self._low = self._low or self._low_streak >= self._confirm_polls
        else:
            self._low_streak = 0
            if reading.soc >= low_soc + LOW_RELEASE_MARGIN:
                self._low = False

    def variables(self) -> dict[str, str] | None:
        reading, now = self._reading, self._clock()
        if reading is None:
            return None
        fresh = now - reading.taken_at <= READING_LOST_AFTER
        variables = {
            "device.mfr": MFR,
            "device.model": self._model,
            "device.type": "ups",
            "ups.mfr": MFR,
            "ups.model": self._model,
            "battery.charge": str(reading.soc),
            "battery.charge.low": str(self._battery.low_soc),
        }
        if fresh:
            variables["input.voltage"] = f"{reading.input_v:.0f}"
            variables["ups.realpower"] = str(reading.output_w)
            if reading.drain_w > 0:
                hours = reading.soc / 100 * self._battery.capacity_wh / reading.drain_w
                variables["battery.runtime"] = str(int(hours * 3600))
        variables["ups.status"] = self._status(reading, now, fresh)
        return variables

    def _status(self, reading: Reading, now: datetime, fresh: bool) -> str:
        if not fresh and self._lost_low(reading, now):
            return "OB LB"
        if reading.on_line:
            return "OL CHRG" if fresh and reading.input_w > reading.output_w and reading.soc < 100 else "OL"
        if self._low:
            return "OB LB"
        # Only a plain "on battery" is masked: a low battery always reaches the NAS.
        return "OL" if self._wake.active(now) else "OB"

    # Without readings the station may have lost its AC input at the same moment (a dead router takes the cloud
    # with it): assume it runs the whole output from the battery since the last reading.
    def _lost_low(self, reading: Reading, now: datetime) -> bool:
        low_soc = self._battery.low_soc
        if not reading.on_line and reading.soc <= low_soc + LOST_NEAR_LOW:
            return True
        hours = (now - reading.taken_at) / timedelta(hours=1)
        estimate = reading.soc - reading.output_w * hours / self._battery.capacity_wh * 100
        return estimate <= low_soc
