# Tests

Energy OS is een pure Home Assistant YAML-repo zonder runtime. Deze tests laden
de échte package-YAML, halen de Jinja-templates eruit en renderen ze met een
HA-achtige omgeving. Zo wordt de **quatt_stooklijn comfort-guard** geborgd,
inclusief de graceful fallback (zonder quatt_stooklijn gedraagt EOS zich exact
als vroeger).

## Draaien

```bash
pip install -r tests/requirements.txt
pytest -q
```

CI draait deze tests automatisch bij elke push en pull request
(`.github/workflows/tests.yml`).

## Wat wordt getest

- `test_comfort_guard.py`
  - Dispatcher "duur"-tak: WP alleen knijpen zolang de veilige uitlooptijd boven
    `eos_comfort_coast_margin_min` ligt; daaronder krijgt comfort voorrang.
  - Grid-overschrijding en lege batterij hebben voorrang op de comfort-guard.
  - `eos_asset_hp_cop_estimate` gebruikt de gemeten COP, met Carnot-fallback.
  - `eos_asset_hp_can_defer_min` gebruikt de coast-tijd, met buitentemp-fallback.
  - `eos_comfort_coast_margin_min` bestaat in core met de juiste defaults.
