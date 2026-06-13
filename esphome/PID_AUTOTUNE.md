# EnergyOS — PID Autotune

## Wat is het?

De PI-controller stuurt het batterijvermogen zo dat het netto grid-vermogen (P1) op het
ingestelde setpoint blijft (standaard 50W import). De autotune bepaalt automatisch de
optimale gain-waarden via de **relay-methode** (Ziegler-Nichols).

---

## Hoe werkt de relay-methode?

In plaats van handmatig tunen stuurt de autotune de batterij afwisselend op maximaal
laden en ontladen rond het setpoint:

```
grid_w
  ↑
  │    ┌──────┐        ┌──────┐
  │    │      │        │      │
──┼────┤      ├────────┤      ├──── setpoint (50W)
  │    │      │        │      │
  │────┘      └────────┘      └────
  │
  └──────────────────────────────→ tijd

batterij: discharge → charge → discharge → charge ...
          ←── Pu ──→
```

Na 5 volledige oscillaties meet de ESP:
- **Pu** — oscillatieperiode (seconden)
- **Ku** — kritische gain (`4 × relay_amplitude / π × gemiddelde_amplitude`)

Ziegler-Nichols PI formules:
- **Kp** = 0.45 × Ku
- **Ki** = 0.54 × Ku / Pu

---

## Voorbereiding

| Voorwaarde | Waarom |
|---|---|
| SoC tussen 40% en 70% | Ruimte nodig voor zowel laden als ontladen |
| Stabiele omstandigheden | Geen grote verbruikers aan/uit tijdens meting |
| Modus = `Self-consumption` | Autotune werkt alleen in SC-modus |
| Strategies Active = AAN | Autotune schrijft naar de driver |
| Driver Enable = AAN | Driver moet actief zijn voor Modbus-writes |

---

## Procedure

### 1. Stel relay-amplitude in (optioneel)

Standaard: **2000W** totaal (±667W per batterij).

Pas aan via `eos_str_at_relay_amp` in de substitutions van `eos_strategies.yaml`.
Een hogere amplitude geeft een duidelijker signaal maar meer belasting.
Aanbevolen: 1500–3000W.

### 2. Zet modus op Self-consumption

In Home Assistant → EnergyOS modus → **Self-consumption**

### 3. Start autotune

Zet in de web UI (`http://marstek-3x.local`):

**Control tab → EOS PID Autotune → AAN**

### 4. Wacht op resultaat

Volg de voortgang via **EOS Autotune Status** (Status tab):

```
Gestart — wacht op eerste oscillatie...
Oscillatie 1/5...
Oscillatie 2/5...
...
Klaar! Ku=3.21 Pu=18.4s → Kp=1.44 Ki=0.094
```

Typische duur: **2–5 minuten** (afhankelijk van hoe snel het systeem oscilleert).

### 5. Gains worden automatisch toegepast

Na 5 oscillaties:
- **Kp** en **Ki** worden direct naar de `EOS PID Kp` / `EOS PID Ki` entities geschreven
- Autotune schakelt zichzelf uit
- Integraal wordt gereset
- PI-controller neemt het over met de nieuwe gains

---

## Handmatig bijstellen

Als het systeem na autotune nog nerveus is:

| Symptoom | Actie |
|---|---|
| Oscilleert snel | Kp verlagen met 20% |
| Reageert te traag | Kp verhogen met 20% |
| Steady-state offset (grid niet op setpoint) | Ki verhogen |
| Langzame oscillatie (minuten) | Ki verlagen |

Wijzig via **Control tab → EOS PID Kp / Ki**.

---

## Veiligheid tijdens autotune

| Beveiliging | Werking |
|---|---|
| SoC safety floor (15%) | Autotune stopt discharge, schakelt naar stop |
| SoC safety ceiling (99%) | Autotune stopt charge, schakelt naar stop |
| Watchdog (60s) | Als driver geen commando krijgt → power=0 |
| Autotune alleen in SC-modus | Andere modi worden niet onderbroken |
| Relay amplitude begrensd | Nooit meer dan `total_max_discharge/charge` |

---

## Parameters overzicht

| Parameter | Locatie | Standaard | Bereik |
|---|---|---|---|
| `eos_str_sc_target_w` | substitutions | 50 W | 0–500 W |
| `eos_str_sc_deadband_w` | substitutions | 150 W | 50–500 W |
| `eos_str_at_relay_amp` | substitutions | 2000 W | 500–7500 W |
| `eos_str_at_osc_target` | substitutions | 5 | 3–10 |
| `EOS PID Kp` | web UI / HA | 1.5 | 0.1–10.0 |
| `EOS PID Ki` | web UI / HA | 0.2 | 0.0–2.0 |

---

## Troubleshooting

**Autotune blijft hangen op "Oscillatie 1/5..."**
→ Grid-meting schommelt te weinig voor zero-crossing detectie.
Verhoog `eos_str_at_relay_amp` of check of P1-data correct binnenkomt
(`P1 Direct Bereikbaar` = groen?).

**Autotune geeft Ku < 0.5 of Pu > 120s**
→ Systeem reageert erg traag. Controleer of de driver daadwerkelijk schrijft
(Driver Enable aan?) en of Modbus-communicatie werkt.

**Na autotune nog steeds oscillatie**
→ EMA-filter alpha verlagen (`eos_str_grid_ema_alpha: "0.1"`) en
slew rate verlagen (`eos_str_slew_rate_w: "100"`).
