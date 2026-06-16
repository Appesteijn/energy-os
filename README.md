# Energy OS — v3 Modulaire Architectuur

Energy OS is een **besturingssysteem voor je thuis-energie**. Het kiest tussen
tegengestelde doelen (comfort, kosten, zelfverbruik, levensduur) en stuurt
warmtepomp + batterij + grid samen aan op basis van metingen en forecasts.

## Architectuur

```
┌───────────────────────────────────────────────────┐
│  05 Observability  │  beslissingen verklaren,     │
│                    │  alerts, anomaliedetectie    │
├────────────────────┼──────────────────────────────┤
│  04 Planner        │  24h-plan o.b.v. tarief +    │
│                    │  PV forecast + thermische    │
│                    │  massa                       │
├────────────────────┼──────────────────────────────┤
│  03 Dispatcher     │  real-time orchestrator,     │
│                    │  setpoints elke 60s          │
├────────────────────┼──────────────────────────────┤
│  02 Assets         │  capabilities per asset      │
│                    │  (kan_laden_W, kan_uitstellen)│
├────────────────────┼──────────────────────────────┤
│  01 Data           │  genormaliseerde metingen    │
│                    │  PV, grid, batterij, HP, tarief│
├────────────────────┼──────────────────────────────┤
│  00 Core           │  master switch, modus,       │
│                    │  profielen, doelen           │
└────────────────────┴──────────────────────────────┘
```

## Bestanden

| Bestand | Laag | Doel |
|---|---|---|
| `packages/eos_00_core.yaml` | 0 | Master switch, modus, profielen |
| `packages/eos_01_data.yaml` | 1 | Genormaliseerde sensoren |
| `packages/eos_02_assets.yaml` | 2 | Asset capabilities |
| `packages/eos_03_dispatcher.yaml` | 3 | Real-time orchestrator |
| `packages/eos_04_planner.yaml` | 4 | 24h vooruitplanning |
| `packages/eos_05_observability.yaml` | 5 | Verklaarbaarheid, alerts |
| `packages/eos_06_openquatt_bridge.yaml` | 6 | OpenQuatt koppeling: proxy-sensors, comfort floor, DHW-vensters |
| `dashboards/eos_dashboard.yaml` | UI | Lovelace dashboard (GEEN package!) |
| `esphome/oq_energy_os_bridge.yaml` | — | OpenQuatt-zijde HP cap brug |
| `esphome/eos_supervisor.yaml` | — | **Marstek ESP supervisor** (real-time dispatcher + HA-watchdog) |
| `esphome/SUPERVISOR.md` | — | Design doc supervisor module |
| `esphome/eos_battery_driver.yaml` | — | **Mijlpaal 1**: battery driver-laag + handmatige test-UI |
| `esphome/DRIVER_MILESTONE1.md` | — | Installatie + testgids voor Mijlpaal 1 |
| `esphome/eos_strategies.yaml` | — | **Mijlpaal 2**: strategy library (shadow + active) |
| `esphome/STRATEGIES_MILESTONE2.md` | — | Installatie + testgids voor Mijlpaal 2 |

## Afhankelijkheden

| Vereist | Levert |
|---|---|
| Marstek House Battery Control (v4.10+) | `input_select.house_battery_strategy`, batterij sensors |
| OpenQuatt (v0.29+) met `oq_energy_os_bridge.yaml` | HP power, supply temp, DHW; EOS HP cap extern schrijven |
| Enphase Envoy integratie | PV productie |
| ESP32-S3 P1 meter | Netto grid power (sensor.esp32_s3_zero_p1_netto_vermogen_watt) |
| Zonneplan integratie | `sensor.zonneplan_current_electricity_tariff` + forecast attributen |

## OpenQuatt-integratie

`eos_06_openquatt_bridge.yaml` koppelt Energy OS aan OpenQuatt voor gecombineerde warmtepomp- en batterijsturing.

### Wat het doet

| Functie | Detail |
|---|---|
| **Proxy-sensors** | Maakt `openquatt_ext_*`-entiteiten aan die OpenQuatt via HA leest (tarief nu/24h-gem, netto gridvermogen) |
| **DHW-vensters** | Schrijft elke 15 min de goedkoopste en duurste tariefvensters naar `input_datetime.house_battery_strategy_dynamic_*` zodat OpenQuatt DHW en legionella slim plant |
| **Comfort floor** | HP-cap wordt nooit lager dan een buitentemperatuurafhankelijk minimum (< -5 °C → 16, < 0 °C → 14, < 5 °C → 12, < 10 °C → 10, ≥ 10 °C → 6) |
| **PV-voorrang** | Als zon > 200 W én (zon − HP) > 400 W loopt de HP onbeperkt, ongeacht de batterijmodus |
| **HP cap brug** | Dispatcher schrijft de gewenste cap-waarde naar `number.openquatt_eos_hp_cap_ha` op de OpenQuatt-firmware |

### Activering HP cap brug

De HP cap brug vereist één firmware-aanpassing in OpenQuatt:

1. Voeg `oq_energy_os_bridge.yaml` toe als package in `openquatt_duo_lilygo_tconnect+cic.yaml` (al gedaan in deze build).
2. Compileer en flash de firmware.
3. Verwijder daarna het commentaar bij `number.set_value` in `script.eos_apply_hp_cap` in `eos_03_dispatcher.yaml`.

Zolang de firmware nog niet geflasht is werkt alles behalve de HP cap brug — comfort floor en PV-voorrang zijn al actief.

## Installatie

Zie [INSTALLATIE.md](INSTALLATIE.md).

## Migratie van v2

v2 bestond uit één bestand (`energy_os.yaml`). v3 is gesplitst in 6 modules met
hetzelfde gedrag plus nieuwe features:

- **Profielen** (Vakantie / Werkdag / Koud / Zonnig) die meerdere drempels tegelijk zetten
- **Asset capabilities** als first-class sensoren
- **24h planner** met tariefcurve forecast
- **"Waarom doet hij dit?"** verklaarbaarheidssensor
- **Anomaliedetectie** per asset

v2 entiteitnamen (`sensor.eos_*`, `input_*.eos_*`, `input_*.energy_os_*`)
blijven 1-op-1 behouden om dashboards en automations niet te breken.
