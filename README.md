# ecoflow-nut

A read-only [Network UPS Tools](https://networkupstools.org) server for an EcoFlow RIVER 2 Max that powers a NAS
as its UPS. It reads the station over Bluetooth LE, with no cloud or internet involved, and answers NUT clients
such as Synology DSM ("Synology UPS server") and `upsc`.

Built for a station behind a home inverter: the station sees AC input as long as the inverter runs the house,
so the NAS only hears "on battery" once the inverter itself is empty, and goes to Standby (Safe Mode) on the
station's own low battery.

Why Bluetooth: EcoFlow's IoT Developer API refuses the RIVER 2 Max ("current device is not allowed to get device
info", code 1006). The model is missing from its list of supported devices.

## What NUT clients see

- `ups.status`:
  - `OL` while the station has AC input, `OL CHRG` while it also charges;
  - `OB` without AC input;
  - `OB LB` once the charge has stayed at or below `LOW_SOC` for two readings in a row. It holds until the
    charge is 2 points above the threshold, or the AC input is back.
- No reading for 2 minutes (the Bluetooth link lost, the adapter or the station gone): the last status holds,
  but it turns into `OB LB`
  - when the last reading was on battery within 2 points of the threshold, or
  - once the charge, estimated as if the battery had carried the whole output since the last reading, reaches
    the threshold.
- `battery.charge`, `battery.charge.low`, `battery.runtime` (at the current drain), `input.voltage`,
  `ups.realpower` (the station's output), maker and model.

Before the first reading the server answers `ERR DATA-STALE`. After a start it waits up to a minute for the
station's first report before it listens.

A NUT client that loses the UPS while it was last on battery assumes the worst at once: "last known to be on
battery and is unavailable - assuming critical". One failed poll is enough, and DSM polls every few seconds, so even
a 5-second restart can send the NAS to Safe Mode. With the station on AC input a restart is harmless: the last known
status is on line.

## Wake

DSM leaves Safe Mode only once the UPS is on line again. To bring the NAS back during an outage:

```bash
docker compose exec nut python -m ecoflow_nut.wake           # "on line" instead of a plain OB for 10 minutes
docker compose exec nut python -m ecoflow_nut.wake --cancel  # the real status again
```

A low battery still shows as `OB LB` during a wake. With DSM waiting for the low battery, the NAS then stays up
on battery.

## Setup

1. A Linux host within Bluetooth range of the station, with BlueZ running (`apt install bluez`). A USB adapter on
   a Realtek RTL8761B works once its firmware (`rtl_bt/rtl8761bu_fw.bin`, Debian's `firmware-realtek`) is in
   place. Check that the station shows up as `EF-R…`: `bluetoothctl --timeout 15 scan le`.
2. The station must be bound to an EcoFlow account in the EcoFlow app. Over Bluetooth it asks for that account's
   user ID, which a one-time login resolves (the password is asked for without echo and stored nowhere):

   ```bash
   docker compose run --rm nut python -m ecoflow_nut.user_id
   ```

3. `.env` next to `compose.yaml`:

   ```bash
   ECOFLOW_SERIAL=               # EcoFlow app > the device > settings; starts with R611 or R613
   ECOFLOW_USER_ID=              # from step 2
   # Optional, with their defaults:
   # LOW_SOC=15                  low battery threshold, %
   # BATTERY_CAPACITY_WH=512     RIVER 2 Max
   # STATION_MODEL=RIVER 2 Max
   # NUT_PORT=3493               keep in step with compose.yaml
   # NUT_USER=monuser
   # NUT_PASSWORD=secret         DSM always logs in as monuser/secret
   ```

4. `docker compose up -d --build`.
5. Check from any machine: `upsc ups@<host>`.
6. DSM > Control Panel > Hardware & Power > UPS: enable UPS support, type "Synology UPS server", server IP = the
   host, "Time before Synology NAS enters Standby Mode": "Same as server" (the low battery this server reports).
   Device Information should show EcoFlow RIVER 2 Max with its charge.

The server only reads: anyone who can reach the port sees the station's state, nobody can change anything. Who
may reach it is up to the network's rules.

### Things to know

- The station takes **one** Bluetooth connection at a time. While this server holds it, the EcoFlow app cannot
  reach the station over Bluetooth; over Wi-Fi and the cloud it still can.
- The Bluetooth protocol is reverse-engineered. A station firmware update may change it: turn automatic firmware
  updates off, and update the station only when eflib supports the new firmware.

## Field mapping

`ecoflow_nut/station.py` turns what eflib decodes into a reading: `battery_level`, `ac_input_voltage` (mV),
`input_power`, `output_power`. To see every field the station reports, stop the server (one connection at a time)
and dump them, on line and without AC input:

```bash
docker compose stop nut
docker compose run --rm -T nut python -m tools.dump_ble 20 > river-2-max-on-line.txt
docker compose start nut
```

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python tools/fetch_eflib.py
.venv/bin/pytest -q -W error
```

## Credits

The Bluetooth protocol comes from eflib, the library of [ha-ef-ble](https://github.com/rabits/ha-ef-ble)
(Apache-2.0). `tools/fetch_eflib.py` fetches it, pinned to one commit, into `eflib/` with its license, at build time.
eflib lives inside a Home Assistant integration and cannot be installed with pip on its own.

The NUT server comes from [luxpower-tg-bot](https://github.com/vsguts/luxpower-tg-bot), where it ran against DSM
first.
