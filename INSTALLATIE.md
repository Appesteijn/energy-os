# EnergyOS v3 — Installatie

## Vereisten

| Component | Versie | Levert |
|---|---|---|
| Home Assistant | 2024.6+ | Template trigger sensors |
| Marstek House Battery Control package | v4.10+ | `input_select.house_battery_strategy`, batterijdata |
| OpenQuatt | v0.29+ | HP power, supply temp, DHW, cap interface |
| Enphase Envoy integratie | — | PV productie |
| ESP32-S3 P1 meter | — | Netto grid power |
| Zonneplan integratie | — | Tarief + forecast |

## Installatie

### Stap 1 — Schakel packages aan
In `configuration.yaml`:
```yaml
homeassistant:
  packages: !include_dir_named packages
```

### Stap 2 — Kopieer alle 6 packages
Naar `config/packages/`:
```
config/packages/eos_00_core.yaml
config/packages/eos_01_data.yaml
config/packages/eos_02_assets.yaml
config/packages/eos_03_dispatcher.yaml
config/packages/eos_04_planner.yaml
config/packages/eos_05_observability.yaml
```

> ⚠️ **Belangrijk:** alleen deze 6 bestanden in `config/packages/`!
> Het dashboard (`dashboards/eos_dashboard.yaml`) is GEEN package — als
> je hem in `packages/` zet krijg je de fout:
> `Invalid package definition 'eos_06_dashboard': expected dict for
> dictionary value @ data['title']`

### Stap 3 — Controleer entiteitnamen
Open `packages/eos_01_data.yaml` en pas indien nodig deze upstream entiteitnamen aan:

| Sensor | Default verwijzing | Vervang door |
|---|---|---|
| `eos_solar_power_w` | `sensor.kwh_meter_3_phase_vermogen_fase_3` | Jouw Enphase totaal-vermogen sensor |
| `eos_grid_power_w` | `sensor.esp32_s3_zero_p1_netto_vermogen_watt` | Jouw P1 netto sensor |
| `eos_battery_power_w` | `sensor.house_total_battery_power_in_w` | (Marstek package) |
| `eos_hp_power_w` | `sensor.openquatt_total_power_input` | Jouw OpenQuatt prefix |
| `eos_outside_temp_c` | `sensor.openquatt_outside_temperature_local_aggregated` | — |
| `eos_dhw_top_c` | `sensor.openquatt_cwt_ch1_dhw_tank_top` | — |
| `eos_tariff_eur_kwh` | `sensor.zonneplan_current_electricity_tariff` | — |

### Stap 4 — Herstart HA
Controleer **Developer Tools → YAML → Check configuration**.

### Stap 5 — Voeg het dashboard toe
1. Instellingen → Dashboards → Nieuw dashboard
2. ⋮ → Bewerk dashboard → ⋮ → Raw configuratie-editor
3. Plak inhoud van `dashboards/eos_dashboard.yaml`

Of als YAML-mode dashboard, in `configuration.yaml`:
```yaml
lovelace:
  dashboards:
    energy-os:
      mode: yaml
      title: Energy OS
      icon: mdi:lightning-bolt-circle
      show_in_sidebar: true
      filename: dashboards/eos_dashboard.yaml
```

### Stap 6 — Eerste run
1. **Energy OS Actief** = AAN
2. **Modus** = `Auto Dynamic`
3. **Profiel** = `Werkdag`
4. Wacht 1 minuut → kijk op tab NU → `sensor.eos_why` moet een zin tonen

## Modi

| Modus | Wat het doet |
|---|---|
| **Auto Dynamic** ⭐ | Marstek's Dynamic strategie aan + EOS coördineert HP cap |
| **Auto Smart** | EOS schakelt zelf strategie op tarief + SoC + grid |
| **Solar Only** | Forceer `Charge PV` |
| **Peak Shaving** | Forceer `Standby / peak shave` |
| **Self-consumption** | Forceer Self-consumption |
| **Full Stop** | Alles uit |
| **Handmatig** | Geen EOS interventie |

## Profielen

Profielen zetten in één klik de doel-gewichten:

| Profiel | Comfort | Kosten | Zelfverbruik | Comfortband |
|---|---|---|---|---|
| **Werkdag** | 8 | 7 | 6 | ±0.5°C |
| **Weekend Thuis** | 9 | 5 | 8 | ±0.3°C |
| **Vakantie** | 3 | 10 | 9 | ±1.5°C |
| **Koude Piek** | 10 | 2 | 3 | ±0.3°C |
| **Zonnige Dag** | 7 | 5 | 10 | ±0.8°C |
| **Aangepast** | — | — | — | jouw sliders |

## Drie views

- **NU**: realtime energiestromen, modus, "waarom doet hij dit?"
- **VANDAAG**: 24h plan, grafieken, KPI's, anomalieën
- **TUNING**: alle drempels en gewichten op één plek

## Optioneel: ESPHome HP cap brug

Voor directe HP throttling vanuit EOS (anders blijft het bij `input_number`):

1. Voeg in jouw OpenQuatt YAML toe:
   ```yaml
   packages:
     energy_os_bridge:
       <<: !include openquatt/oq_energy_os_bridge.yaml
   ```
2. Kopieer `esphome/oq_energy_os_bridge.yaml` naar de OpenQuatt build directory
3. Flash de firmware
4. In `eos_03_dispatcher.yaml` → uncomment de regel die schrijft naar `number.openquatt_eos_hp_cap_ha`

## Optioneel: quatt_stooklijn comfort-guard

[quatt_stooklijn](https://github.com/Appesteijn/stooklijn) is een HA custom
component die een gemeten thermisch model van het huis leert (warmteverlies,
thermische massa, zonnewinst). Geïnstalleerd verrijkt het Energy OS met
**prijsgestuurd thermisch uitlopen**: bij een duur tarief knijpt EOS de
warmtepomp alléén zolang het huis veilig kan uitlopen op zijn thermische massa —
de zon-forecast telt mee, dus voorspelde zon verlengt de uitlooptijd.

**Niet geïnstalleerd?** Er verandert niets: alle templates vallen via `float(-1)`
terug op de bestaande heuristiek. Geen harde dependency.

1. Installeer quatt_stooklijn (HACS of handmatig). Na convergentie van het
   RC-model (~2 dagen) verschijnt `sensor.quatt_warmteanalyse_veilige_uitlooptijd`
   (veilige uitlooptijd in minuten tot de comfort-vloer).
2. In de quatt_stooklijn-opties: stel de **comfort-vloer** in (laagste
   acceptabele binnentemp, default 19 °C) en wijs optioneel de **EOS
   throttle-entity** aan op `input_number.eos_hp_cap_override` — dan sluit
   stooklijn door EOS geknepen periodes uit van zijn COP/warmteverlies-analyse.
3. In Energy OS: stel `input_number.eos_comfort_coast_margin_min` in (default
   45 min). EOS knijpt de WP bij duur tarief alleen zolang de uitlooptijd boven
   deze marge ligt; daaronder krijgt comfort voorrang en draait de WP weer vrij.

Verrijkte capabilities (met automatische fallback):

| Capability | Met quatt_stooklijn | Zonder |
|---|---|---|
| `eos_asset_hp_cop_estimate` | gemeten COP (`geschatte_actuele_cop`) | Carnot-heuristiek |
| `eos_asset_hp_can_defer_min` | fysieke coast-tijd (`veilige_uitlooptijd`) | buitentemp-buckets |
| Dure-tarief throttle | comfort-guard op coast-tijd | alleen batterij-SoC |

## Volgende ontwikkelstappen

- **Solar forecast integratie** in planner (laag 4) — koppel Solcast/Forecast.Solar
- **DHW timing** als losse asset — plan DHW in goedkope solar-uren
- **MILP optimalisatie** als AppDaemon Python module bovenop laag 4
- **Anomalie-baselines** per asset (geleerd profiel ipv vaste drempels)
- **Verklaringslog** — historie van alle EOS beslissingen
