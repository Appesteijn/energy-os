# Mijlpaal 2 — Strategy Library (shadow mode)

## Wat dit doet

Per EOS-modus berekent de ESP elke 5 seconden wat de batterij zou moeten doen,
en kan dat doorzetten naar de driver-laag uit Mijlpaal 1.

| EOS Modus | Strategie | Drv command | Power |
|---|---|---|---|
| Full Stop | full_stop | stop | 0 |
| Solar Only | charge_pv | charge | min(surplus, total_max_charge) |
| Verkoop Nu | sell | discharge | total_max_discharge |
| Laad Nu | charge | charge | total_max_charge |
| Peak Shaving | peak_shave | discharge (alleen bij grid > hard limit) | grid_excess |
| Self-consumption | delegate | idle | (Node-RED leidend) |
| Auto Dynamic | delegate | idle | (Node-RED leidend) |
| Auto Smart | delegate | idle | (Node-RED leidend) |
| Handmatig | delegate | idle | (Node-RED leidend) |

`delegate` = strategie wil dat Node-RED het overneemt; driver-command "idle" zet
de RS485 op disable zodat Marstek's eigen logica weer leidend wordt.

## Veilig migratiepad — 4 toestanden

```
┌──────────────────┬──────────────────────────────────────────┐
│ Strategies   OFF │ Pure shadow — alleen loggen              │
│ Driver       OFF │ Driver doet niets                        │
│ STARTSTATE       │ Node-RED leidend                         │
├──────────────────┼──────────────────────────────────────────┤
│ Strategies   ON  │ Strategy schrijft naar driver targets    │
│ Driver       OFF │ Driver schrijft NIET naar Modbus         │
│                  │ → vergelijk strategy-log met Node-RED    │
├──────────────────┼──────────────────────────────────────────┤
│ Strategies   OFF │ Driver alleen handmatig bediend          │
│ Driver       ON  │ (Mijlpaal 1 test-modus)                  │
├──────────────────┼──────────────────────────────────────────┤
│ Strategies   ON  │ ESP volledig leidend                     │
│ Driver       ON  │ Node-RED moet UIT — anders Modbus race   │
└──────────────────┴──────────────────────────────────────────┘
```

## Installatie

### 1. Bestand kopiëren
Plaats `eos_strategies.yaml` naast je bestaande Marstek YAML
(`Z:\esphome\eos_strategies.yaml`).

### 2. In packages opnemen

In `tconnect_marstek_3x.yaml`:
```yaml
packages:
  # ... bestaande marstek_m1, m2, m3, eos_supervisor, eos_battery_driver ...
  eos_strategies: !include eos_strategies.yaml   # NIEUW
```

### 3. Compile + OTA flash

```
esphome run tconnect_marstek_3x.yaml
```

### 4. Verifieer op `marstek-3x.local`

**Status tab** — nieuwe entiteiten:
- **EOS Strategy Active** — `full_stop`/`charge_pv`/`sell`/`charge`/`peak_shave`/`delegate`
- **EOS Strategy Decision** — leesbare één-zin reden
- **EOS Strategy Shadow Log** — laatste actie regel met `[SHADOW]` of `[ACTIVE]` prefix
- **EOS Strategy Target** — gewenste totale W

**Control tab** — twee nieuwe switches (default UIT):
- **EOS Strategies Active**
- **EOS Strategy Verbose Log**

## Test plan

### Test 1 — Shadow mode (Strategies OFF)
1. Direct na flash: alles UIT. Mode in HA = `Auto Dynamic`.
2. Verwacht in Status:
   - Strategy Active: `delegate`
   - Decision: "Auto Dynamic — gedelegeerd aan Node-RED"
   - Shadow Log: `[SHADOW] delegate: drv_cmd=idle power=0`
3. Wissel HA-modus naar `Solar Only`. Wacht 5s.
4. Verwacht:
   - Strategy Active: `charge_pv`
   - Decision: bevat huidige surplus + target
   - Shadow Log: `[SHADOW] charge_pv: drv_cmd=charge power=XXXX`
5. Driver doet niets, Node-RED blijft leidend. ✓

### Test 2 — Strategies aan, Driver uit (semi-actief)
1. Zet **EOS Strategies Active** → AAN
2. Driver Enable blijft UIT.
3. EOS modus = `Verkoop Nu`. Wacht 5s.
4. Verwacht op `marstek-3x.local`:
   - **EOS Driver Command** wijzigt naar `discharge` (geschreven door strategie)
   - **EOS Driver Target Discharge** wijzigt naar ~6000-7500 W
   - **EOS Driver State** toont nog steeds "UIT — Node-RED / HA is leidend"
   - Batterijen worden NIET fysiek bediend door driver
5. → Bewijst dat strategie correct in driver schrijft, maar Modbus is veilig

### Test 3 — Volledig actief (cutover, alleen als Node-RED uit)
**⚠️ Alleen doen als je klaar bent voor de switchover:**

1. HA → `input_select.house_battery_strategy` = `Full stop`
   (voorkomt Node-RED Modbus-race)
2. ESP web UI:
   - Strategies Active → AAN
   - Driver Enable → AAN
3. EOS modus = `Verkoop Nu`
4. Verwacht: alle 3 batterijen Forcible Mode = discharge, gaan ontladen
5. Trek de stekker (figuurlijk): zet EOS modus = `Full Stop`. Binnen 5s allemaal stop.

## Veiligheidsmechanismen

| Mechanisme | Effect |
|---|---|
| SoC safety floor (15%) | Stop discharge als avg SoC onder 15% komt |
| SoC safety ceiling (99%) | Stop charge als avg SoC boven 99% komt |
| Marstek cutoffs respecteren | Per-batterij `discharging_cutoff_capacity` / `charging_cutoff_capacity` |
| Min charge/discharge drempel | Onder 100W: stop ipv force |
| Driver hard limit | 2500 W per batterij (uit Mijlpaal 1) |
| Watchdog | 60s zonder cmd → stop (uit Mijlpaal 1) |
| Driver Enable + Strategies Active | Beide expliciet AAN nodig voor Modbus writes |

## Wat NIET in Mijlpaal 2

- ❌ Zelf de tariff/forecast laden — komt nog steeds van HA
- ❌ Self-consumption PID — Mijlpaal 3
- ❌ Per-batterij optimization beyond driver's basic distribution
- ❌ Multi-step planning / hysterese (planner is HA-side)

## Volgende stap

**Mijlpaal 3** — Self-consumption PID controller (in C++) zodat de "delegate"
strategies ook door de ESP afgehandeld kunnen worden. Daarna is Node-RED écht
niet meer nodig voor de hoofd-flow.

**Mijlpaal 4** — Cutover documentatie + Node-RED uitschakelen.

## Bekende beperkingen

- De strategie leest EOS modus via `id(eos_ha_mode)` — dat is een homeassistant
  text_sensor uit de supervisor. Als HA stil valt (supervisor in safe mode),
  blijft de strategie de laatste bekende modus gebruiken.
- Geen rate-limiting op driver-writes: bij wisseling van modus elke 5s nieuw
  commando, maar driver gebruikt idempotente Modbus-writes (alleen bij
  verschil), dus geen verkeers-spam.
