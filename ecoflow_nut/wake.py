"""Wake: report the station on line for a while, so a NAS sent to Safe Mode during an outage comes back.

DSM leaves Safe Mode only once the UPS is on line again. The server and this command share a file in the data
volume, so the wake survives neither more nor less than the container:

    docker compose exec nut python -m ecoflow_nut.wake           # on line for WAKE_FOR
    docker compose exec nut python -m ecoflow_nut.wake --cancel  # real status again
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Long enough for DSM to see the station on line and come back, short enough that a forgotten wake does not
# hide an outage for long; DSM set to wait for the low battery stays up afterwards.
WAKE_FOR = timedelta(minutes=10)
DEFAULT_WAKE_FILE = "/app/data/wake-until"


class WakeFile:
    def __init__(self, path: Path):
        self._path = path

    def until(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self._path.read_text().strip())
        except (FileNotFoundError, ValueError):
            return None

    def active(self, now: datetime) -> bool:
        until = self.until()
        return until is not None and now < until

    def start(self, now: datetime) -> datetime:
        until = now + WAKE_FOR
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(until.isoformat())
        return until

    def cancel(self) -> None:
        self._path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecoflow_nut.wake", description=__doc__.splitlines()[0])
    parser.add_argument("--cancel", action="store_true", help="report the real status again")
    args = parser.parse_args(argv)
    wake = WakeFile(Path(os.environ.get("WAKE_FILE", DEFAULT_WAKE_FILE)))
    if args.cancel:
        wake.cancel()
        print("Wake cancelled: the NAS sees the real status again.")
        return 0
    until = wake.start(datetime.now(UTC))
    print(f"The NAS sees the station on line until {until.astimezone():%H:%M:%S %Z} (a low battery still shows).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
