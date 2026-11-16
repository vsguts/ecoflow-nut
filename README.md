# ecoflow-nut

A read-only [Network UPS Tools](https://networkupstools.org) server for an EcoFlow power station that powers a NAS
as its UPS. It reads the station from the EcoFlow cloud (IoT Developer API) and answers NUT clients such as
Synology DSM ("Synology UPS server") and `upsc`.

Built for a RIVER 2 Max behind a home inverter: the station sees AC input as long as the inverter runs the house,
so the NAS only hears "on battery" once the inverter itself is empty, and goes to Standby (Safe Mode) on the
station's own low battery.

## What NUT clients see

- `ups.status`:
  - `OL` while the station has AC input, `OL CHRG` while it also charges;
  - `OB` without AC input;
  - `OB LB` once the charge has stayed at or below `LOW_SOC` for two readings in a row. It holds until the
    charge is 2 points above the threshold, or the AC input is back.
- No reading for 2 minutes (the station offline, or the cloud or the internet gone): the last status holds,
  but it turns into `OB LB`
  - when the last reading was on battery within 2 points of the threshold, or
  - once the charge, estimated as if the battery had carried the whole output since the last reading, reaches
    the threshold. A dead router can take the cloud away together with the AC input, so the estimate assumes
    the worst.
- `battery.charge`, `battery.charge.low`, `battery.runtime` (at the current drain), `input.voltage`,
  `ups.realpower` (the station's output), maker and model.

Before the first reading the server answers `ERR DATA-STALE`; it reads the station once before it starts to
listen.

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

1. EcoFlow developer access: sign in at the [EcoFlow developer portal](https://developer-eu.ecoflow.com) with the
   account the station is bound to, apply to become a developer (approval takes up to 5 working days), then
   create an Access Key / Secret Key pair. The serial number is in the EcoFlow app under the device's settings.
2. `.env` next to `compose.yaml`:

   ```bash
   ECOFLOW_ACCESS_KEY=
   ECOFLOW_SECRET_KEY=
   ECOFLOW_SERIAL=
   # Optional, with their defaults:
   # ECOFLOW_API_URL=https://api-e.ecoflow.com   (https://api-a.ecoflow.com for accounts in the Americas)
   # LOW_SOC=15                  low battery threshold, %
   # BATTERY_CAPACITY_WH=512     RIVER 2 Max
   # STATION_MODEL=RIVER 2 Max
   # POLL_INTERVAL=30            seconds; each poll is two API calls
   # NUT_PORT=3493               keep in step with compose.yaml
   # NUT_USER=monuser
   # NUT_PASSWORD=secret         DSM always logs in as monuser/secret
   ```

   The Secret Key controls the station, not just reads it: keep it out of chats and repositories.
3. `docker compose up -d --build`.
4. Check from any machine: `upsc ups@<host>`.
5. DSM > Control Panel > Hardware & Power > UPS: enable UPS support, type "Synology UPS server", server IP = the
   host, "Time before Synology NAS enters Standby Mode": "Same as server" (the low battery this server reports). Device Information should show
   EcoFlow RIVER 2 Max with its charge.

The server only reads: anyone who can reach the port sees the station's state, nobody can change anything. Who
may reach it is up to the network's rules.

## Field mapping

`ecoflow_nut/station.py` maps the cloud's quota onto a reading: `pd.soc`, `inv.acInVol` (mV), `pd.wattsInSum`,
`pd.wattsOutSum`. The names come from EcoFlow's RIVER 2 series documentation and are provisional until checked
against a real station: dump what the cloud reports, on line and without AC input:

```bash
docker compose run --rm -T nut python -m tools.dump_quota > river-2-max-on-line.json
```

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q -W error
```

The NUT server and the EcoFlow API client come from
[luxpower-tg-bot](https://github.com/vsguts/luxpower-tg-bot), where they ran against DSM first.
