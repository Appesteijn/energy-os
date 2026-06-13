# EnergyOS Supervisor (ESP32 firmware module)

## Wat is dit

Een ESPHome-package die je toevoegt aan **de bestaande Marstek LilyGO ESP32-S3** YAML.
Hij draait een real-time dispatcher + HA-watchdog **naast** de Modbus-batterijaansturing,
zonder iets aan die bestaande functionaliteit te veranderen.

## Hardware

| Onderdeel | Status |
|---|---|
| LilyGO T-Connect ESP32-S3 | bestaand, draait Marstek YAML |
| 3× UART naar batterijen | bestaand, GPIO4/5, 6/7, 17/18 |
| WiFi → HA native API | bestaand |
| **Extra hardware nodig** | **geen** |

CPU/RAM impact is verwaarloosbaar: ~12 HA-state subscriptions en twee timer-loops.

## Wat het doet

```
HA (brein)                                    Marstek ESP (ruggengraat)
┌────────────────────┐                       ┌──────────────────────────┐
│ EnergyOS v3        │                       │ eos_supervisor.yaml      │
│ Laag 0–5           │                       │ ─ HA heartbeat watchdog  │
│ (Plan + Policy)    │   ◄── sensors ──── ── │ ─ Beslissingsboom        │
│                    │   ── setpoint ──► ──  │ ─ Lokale fallback        │
└────────────────────┘                       └──────────────────────────┘
         │                                          │       │
         │                                          │       └─► Modbus → batterijen (bestaand)
         ▼                                          ▼
   input_number.                              input_number.
   eos_hp_cap_                                eos_hp_cap_
   override   ◄────── 30s push ───────────────override
         │                                  (homeassistant.action)
         ▼
   OpenQuatt ESP
   (leest cap via
    eos_bridge.yaml)
```

## Datastroom

### Van HA → Supervisor (subscribe via `homeassistant` platform)

| ESPHome sensor | HA entity |
|---|---|
| `eos_ha_tariff_eur_kwh` | `sensor.eos_tariff_eur_kwh` |
| `eos_ha_grid_power_w` | `sensor.eos_grid_power_w` |
| `eos_ha_solar_surplus_w` | `sensor.eos_solar_surplus_w` |
| `eos_ha_battery_soc` | `sensor.eos_battery_soc_estimate_pct` |
| `eos_ha_grid_hard_limit_w` | `input_number.eos_grid_hard_limit_w` |
| `eos_ha_tariff_cheap` | `input_number.eos_tariff_cheap` |
| `eos_ha_tariff_expensive` | `input_number.eos_tariff_expensive` |
| `eos_ha_min_soc` | `input_number.eos_min_soc_for_eve_discharge` |
| `eos_ha_mode` | `input_select.energy_os_mode` |
| `eos_ha_tariff_level` | `sensor.eos_tariff_level` |

Elke ontvangen update zet `eos_ha_last_seen_ms = millis()`.

### Van Supervisor → HA

| ESPHome entity | HA gebruik |
|---|---|
| `number.marstek_3x_eos_hp_cap_berekend` | Read-only display van wat supervisor wil |
| `text_sensor.marstek_3x_eos_supervisor_decision` | Decision code (1, 3, 11, …) |
| `text_sensor.marstek_3x_eos_supervisor_reason` | Eén-zin verklaring |
| `binary_sensor.marstek_3x_eos_ha_alive` | HA-heartbeat status |
| `binary_sensor.marstek_3x_eos_safe_mode_actief` | Safe mode actief? |

Plus elke 30s: `homeassistant.action: input_number.set_value` voor `input_number.eos_hp_cap_override`,
maar alleen als (a) HA leeft, (b) de "Push naar HA" switch aan staat, en (c) de waarde veranderd is.

## Beslissingsboom

```
Decision codes:
   0  INIT
   1  SAFE_MODE          → HP cap = 12   (HA stilte > 5 min)
   2  MANUAL             → HP cap = 20
   3  GRID_HARD_LIMIT    → HP cap = 10   (grid > hard limit)
   4  FULL_STOP          → HP cap = 20
   5  SOLAR_ONLY         → HP cap = 20
   6  PEAK_SHAVING       → HP cap = 20
   7  SELF_CONSUMPTION   → HP cap = 20
  10  AUTO_NORMAL        → HP cap = 20
  11  AUTO_TARIFF_HIGH   → HP cap = 8    (verkoop batterij)
  12  AUTO_TARIFF_LOW    → HP cap = 6    (laad batterij)
```

Voorrangsvolgorde: SAFE_MODE > MANUAL > GRID_HARD > modus-specifiek.

## Safe mode

Wordt actief wanneer:
- HA-data niet ververst > 300 seconden (telde alle 4 sensor on_value triggers samen)
- OF de "EOS Force Safe Mode" switch aanstaat

Effect:
- Decision = 1
- HP cap = 12 (matig — comfort blijft, maar geen pieken)
- Push naar HA blijft uit tot HA terug is
- Web UI banner toont reden + leeftijd van HA-stilte

Wat NIET in safe mode:
- Directe Modbus-write naar batterijen (Marstek strategie blijft via HA's selector)
- Direct contact met OpenQuatt ESP (cap reist via HA's input_number)

→ **Voor true HA-down resilience op HP cap is een spiegel-watchdog op de OpenQuatt
firmware nodig** (volgende stap, los van dit bestand).

## Web UI

Op `http://marstek_3x.local/` zie je:

| Tabblad | Wat je ziet |
|---|---|
| Status | Decision · Reason · HA alive · Safe mode · HP cap |
| Control | Force Safe Mode · Push naar HA aan/uit |
| Diagnostic | Bestaande WiFi/uptime/etc + UART logging |

## Installatie

1. Kopieer `eos_supervisor.yaml` naast je bestaande Marstek YAML
2. In de bestaande YAML voeg toe onderaan het `packages:` blok:
   ```yaml
   packages:
     # ... marstek_m1, m2, m3 ...
     eos_supervisor: !include eos_supervisor.yaml
   ```
3. Voor zekerheid: voeg óók `sorting_groups` toe in `web_server` als ze er nog niet staan
   (Status, Control, Diagnostic — bij jou al aanwezig)
4. Compile + flash (OTA werkt prima)
5. Open `http://marstek_3x.local/` → zie de nieuwe "EOS …" entiteiten
6. In HA → controleer of `binary_sensor.marstek_3x_eos_ha_alive` na ~10s op AAN staat

## Toekomstige uitbreidingen (los van dit bestand)

| Feature | Wat | Waar |
|---|---|---|
| OpenQuatt watchdog spiegel | HA-stilte detectie ook op OpenQuatt | Nieuwe `oq_eos_safety.yaml` |
| Direct Modbus safe-mode | Force batterij naar Self-consumption bij safe mode | Uitbreiding eos_supervisor.yaml |
| ESP→ESP HP cap push | Marstek ESP schrijft direct naar OpenQuatt webserver | http_request component |
| Lokale tariff cache | 24h forecast offline beschikbaar | Globals + JSON van HA |

## Resource verbruik

Geschat (gemeten op identieke hardware):

| Resource | Voor | Na | Marge |
|---|---|---|---|
| RAM heap free | ~150 KB | ~145 KB | ruim |
| CPU idle | ~85% | ~83% | ruim |
| Flash | ~1.4 MB | ~1.5 MB | ruim |
| WiFi traffic | minimaal | +12 sensors | verwaarloosbaar |

Geen risico op interferentie met de 1-seconden Modbus polling van de 3 batterijen.
