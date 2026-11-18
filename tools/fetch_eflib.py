"""Fetch eflib, the EcoFlow BLE protocol library of ha-ef-ble, pinned to one commit.

eflib lives inside a Home Assistant integration whose package imports Home Assistant, so it cannot be installed
with pip; this copies just the library (Apache-2.0, its LICENSE alongside) next to ecoflow_nut:

    python tools/fetch_eflib.py [dest]    # dest defaults to the repository root
"""

import io
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

# Bump deliberately: the protocol is reverse-engineered and a newer eflib may behave differently.
COMMIT = "2117ce459a57226fcde32788ced85dd96c0e32ba"
ARCHIVE = f"https://codeload.github.com/rabits/ha-ef-ble/tar.gz/{COMMIT}"
ROOT = f"ha-ef-ble-{COMMIT}/"
LIBRARY = ROOT + "custom_components/ef_ble/eflib/"


def fetch(dest: Path) -> Path:
    target = dest / "eflib"
    with urllib.request.urlopen(ARCHIVE, timeout=60) as response:
        data = io.BytesIO(response.read())
    shutil.rmtree(target, ignore_errors=True)
    with tarfile.open(fileobj=data, mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith(LIBRARY):
                path = target / member.name.removeprefix(LIBRARY)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
        (target / "LICENSE").write_bytes(archive.extractfile(ROOT + "LICENSE").read())
    (target / "SOURCE").write_text(
        f"https://github.com/rabits/ha-ef-ble/tree/{COMMIT}/custom_components/ef_ble/eflib\n"
    )
    return target


if __name__ == "__main__":
    print(f"eflib {COMMIT[:7]} -> {fetch(Path(sys.argv[1] if len(sys.argv) > 1 else '.'))}")
