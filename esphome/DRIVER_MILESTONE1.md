# Mijlpaal 1 — Battery Driver op productie-Marstek

## Wat je krijgt

Een veilige driver-laag op de Marstek LilyGO T-Connect die:

- Standaard UIT staat (Node-RED blijft leidend)
- Handmatige test-knoppen biedt (Force Stop, Test Charge 500W, Test Discharge 500W)
- Idempotente Modbus-writes doet (alleen bij wijziging)
- Watchdog heeft (60s zonder commando → stop)
- Power-distributie over 3 batterijen (equal of SoC-aware)
- Hard limit van 2500 W per batterij

## Installatie

### Stap 1 — Bestand kopiëren

Plaats `eos_battery_driver.yaml` naast je bestaande `marstek_3x.yaml`
(in de map waar ook `marstek_battery_block.yaml` staat).

### Stap 2 — Aan packages toevoegen

In `marstek_3x.yaml` onderaan `packages:` blok:

```yaml
packages:
  marstek_m1: !include
    file: marstek_battery_block.yaml
    vars: { ... }
  marstek_m1_v3_cells: !include
    file: marstek_v3_cells.yaml
    vars: { ... }
  marstek_m2: !include
    file: marstek_battery_block.yaml
    vars: { ... }
  marstek_m2_extras: !include
    file: marstek_v141_extras.yaml
    vars: { ... }
  marstek_m3: !include
    file: marstek_battery_block.yaml
    vars: { ... }
  marstek_m3_extras: !include
    file: marstek_v141_extras.yaml
    vars: { ... }

  # ── NIEUW ──
  eos_battery_driver: !include eos_battery_driver.yaml
```

### Stap 3 — Compile + flash (OTA)

```
esphome run marstek_3x.yaml
```

Geen breaking changes — alle bestaande entities blijven werken.

### Stap 4 — Verifieer

Op `http://marstek_3x.local/` zie je 5 nieuwe items in **Control**:

| Entity | Doel |
|---|---|
| EOS Driver Enable | Master switch (default UIT) |
| EOS Driver Command | idle / stop / charge / discharge / emergency_stop |
| EOS Driver Distribution | equal of soc_aware |
| EOS Driver Target Charge | Doelvermogen laden (W) |
| EOS Driver Target Discharge | Doelvermogen ontladen (W) |
| EOS Force Stop All (knop) | Noodknop, werkt altijd |
| EOS Test Charge 500W (knop) | Quick test |
| EOS Test Discharge 500W (knop) | Quick test |

En in **Status**:

| Entity | Doel |
|---|---|
| EOS Driver State | "UIT — Node-RED leidend" of actieve modus |
| EOS Driver Last Action | "Charge 500W (m1=167 m2=167 m3=166, equal)" |
| EOS Driver Applied Total | Som van geschreven setpoints (W) |
| EOS Applied M1/M2/M3 | Per batterij wat is geschreven |

## Eerste test (zorgvuldig!)

### Voorbereiding
1. **Zet HA's `input_select.house_battery_strategy` op `Full stop`**
   → Node-RED stopt met schrijven naar 42010/42020/42021.
2. **Maak een tijdvenster** waarin schommelingen geen probleem zijn (overdag, batterij niet vol).
3. **Open marstek_3x.local** en houd het tabblad open zodat je status realtime ziet.

### Test 1 — Idle (RS485 disable)
1. Driver Enable → AAN
2. Command → `idle`
3. Verifieer: na ~5s tonen alle 3 `m*_rs485_control_mode` op je web UI **disable**
4. Verwacht: batterijen volgen Marstek's eigen logica (hetzelfde gedrag als Full stop in HA)

### Test 2 — Stop
1. Command → `stop`
2. Verifieer: RS485 op alle 3 = **enable**, forcible = **stop**
3. Verwacht: batterijen exact 0 W (geen laden, geen ontladen)

### Test 3 — Charge 500W
1. Target Charge → 500 (W)
2. Command → `charge` (of klik "Test Charge 500W")
3. Verifieer in 10s:
   - `forcible_charge_discharge` per batterij = **charge**
   - `forcible_charge_power` per batterij ≈ 167 W (500 ÷ 3)
   - `Battery Power` per batterij gaat richting +167 W (laden)
   - Totaal grid-import zou ~500 W moeten stijgen (los van overige verbruik)

### Test 4 — Watchdog
1. Met command op `charge` actief
2. Wacht 60 seconden ZONDER iets aan te raken (geen target/command te wijzigen)
3. ⚠️ De watchdog telt vanaf het laatste 5s-loop-tick, niet vanaf user input — dus
   in praktijk gaat hij pas in als de driver-loop zelf vastloopt. In normaal gebruik
   blijft hij actief omdat elke loop `last_cmd_ms` ververst.
4. Voor echte watchdog-test: zet command op een lege string via API (advanced).

### Test 5 — Force Stop knop
1. Met command op `charge` of `discharge` actief
2. Klik **EOS Force Stop All**
3. Verifieer binnen 1s: alle batterijen RS485=disable, forcible=stop, power=0

### Test 6 — SoC-aware distribution
1. Distribution → `soc_aware`
2. Target Charge → 1500 W
3. Command → `charge`
4. Verifieer: batterij met laagste SoC krijgt het meeste vermogen
5. Schakel terug naar `equal` na test

## Wat doet het NIET (Mijlpaal 1)

- ❌ Geen Self-consumption PID
- ❌ Geen automatische strategie-switch op tarief/SoC
- ❌ Geen integratie met EnergyOS modus-selector
- ❌ Geen grid-meting input (alleen handmatige target)
- ❌ Geen tarieflogica

Dat komt in Mijlpaal 2 (easy strategies) en 3 (PID).

## Veiligheid samenvatting

| Mechanisme | Effect |
|---|---|
| Default Enable=OFF | Driver heeft 0 invloed na boot |
| Watchdog 60s | Stop bij hangende loop |
| Hard limit 2500 W/batt | Geen overpower mogelijk |
| Emergency Stop button | Werkt altijd, ook bij driver=UIT |
| Idempotente writes | Geen onnodig Modbus-verkeer |
| Idle = RS485 disable | Marstek's eigen safety neemt over |

## Wat als er iets misgaat

| Symptoom | Actie |
|---|---|
| Batterij niet reageren | Check `m*_rs485_control_mode` = enable, `m*_user_work_mode` = manual |
| Batterij in fault state | Klik Emergency Stop, check `m*_inverter_state` |
| Driver loop niet zichtbaar | Check logs voor lambda compile-errors |
| Modbus errors | Check `m*_modbus_status` (al aanwezig), kabel/terminator nakijken |
| Conflict met Node-RED | Zet HA `house_battery_strategy` op Full stop voordat je driver activeert |

## Volgende stappen na Mijlpaal 1

Zodra je tevreden bent met handmatig testen:

- **Mijlpaal 2**: 6 easy strategies (charge_pv, zero_import, charge, sell, peak_shave, stop) — schakelbaar via EOS modus
- **Mijlpaal 3**: Self-consumption PID — vereist grid_power_w input via HA-sensor
- **Mijlpaal 4**: Switchover — Node-RED uit, ESP enige master
