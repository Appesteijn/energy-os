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

### Optioneel — quatt_stooklijn

De [quatt_stooklijn](https://github.com/Appesteijn) HA custom component verrijkt
Energy OS met een gemeten thermisch model van het huis. Niet vereist — zonder de
component vallen alle onderstaande punten terug op de bestaande heuristiek.

| Levert | Gebruikt in |
|---|---|
| `sensor.quatt_warmteanalyse_veilige_uitlooptijd` — veilige uitlooptijd (min) tot de comfort-vloer, incl. zon-forecast | **Comfort-guard** op de dure-tarief throttle (dispatcher) + `eos_asset_hp_can_defer_min` |
| `sensor.quatt_warmteanalyse_geschatte_actuele_cop` — gemeten COP | `eos_asset_hp_cop_estimate` (vervangt Carnot-heuristiek) |

Met de comfort-guard knijpt Energy OS bij een duur tarief de warmtepomp alléén
zolang het huis veilig kan uitlopen op zijn thermische massa — instelbaar via
`input_number.eos_comfort_coast_margin_min`. Een zonnige middag (zon-forecast)
verlengt automatisch hoe lang de WP geknepen mag blijven.

## Installatie

Zie [INSTALLATIE.md](INSTALLATIE.md).

## Tests

De Jinja-logica van de comfort-guard wordt geborgd met geautomatiseerde tests
(zie [tests/](tests/)). Ze renderen de échte package-YAML en controleren onder
meer dat EOS zónder quatt_stooklijn exact het oorspronkelijke gedrag houdt.

```bash
pip install -r tests/requirements.txt
pytest -q
```

CI draait deze automatisch bij elke push/PR.

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
