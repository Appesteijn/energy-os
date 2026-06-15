"""Tests voor de quatt_stooklijn comfort-guard brug in Energy OS.

Energy OS is een pure HA-YAML repo zonder runtime. Deze tests laden de échte
package-YAML, halen de relevante Jinja-templates eruit en renderen ze met een
HA-achtige omgeving (`states()`, `float`/`int` filters met default). Zo wordt
zowel de comfort-guard logica als de graceful fallback (zonder quatt_stooklijn)
geborgd — en breekt de test als iemand de YAML-templates per ongeluk sloopt.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from jinja2 import Environment

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "packages"


class _Loader(yaml.SafeLoader):
    pass


# HA gebruikt custom YAML-tags (!include, !secret, !input ...) — negeer ze.
_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def _load(path: pathlib.Path):
    with open(path) as fh:
        return yaml.load(fh, Loader=_Loader)


def _find_key(node, key):
    """Yield alle waarden voor een dict-key, recursief."""
    if isinstance(node, dict):
        if key in node:
            yield node[key]
        for value in node.values():
            yield from _find_key(value, key)
    elif isinstance(node, list):
        for item in node:
            yield from _find_key(item, key)


def _find_sensor_state(node, name):
    """De 'state'-template van een template-sensor met gegeven 'name'."""
    if isinstance(node, dict):
        if node.get("name") == name and "state" in node:
            return node["state"]
        for value in node.values():
            found = _find_sensor_state(value, name)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_sensor_state(item, name)
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------- #
#  HA-achtige Jinja-omgeving                                                   #
# --------------------------------------------------------------------------- #


def _ha_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ha_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _make_render(states: dict):
    env = Environment()
    env.filters["float"] = _ha_float
    env.filters["int"] = _ha_int
    env.globals["states"] = lambda e: states.get(e, "unknown")
    env.globals["state_attr"] = lambda e, a: states.get(f"{e}.{a}")

    def render(template: str, **ctx) -> str:
        return env.from_string(template).render(**ctx).strip()

    return render


# --------------------------------------------------------------------------- #
#  Templates uit de echte YAML                                                 #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def desired_cap() -> str:
    disp = _load(PKG / "eos_03_dispatcher.yaml")
    caps = list(_find_key(disp, "desired_cap"))
    assert len(caps) == 1, f"verwacht 1 desired_cap-template, kreeg {len(caps)}"
    return caps[0]


@pytest.fixture(scope="module")
def cop_state() -> str:
    assets = _load(PKG / "eos_02_assets.yaml")
    state = _find_sensor_state(assets, "eos_asset_hp_cop_estimate")
    assert state is not None, "eos_asset_hp_cop_estimate niet gevonden"
    return state


@pytest.fixture(scope="module")
def defer_state() -> str:
    assets = _load(PKG / "eos_02_assets.yaml")
    state = _find_sensor_state(assets, "eos_asset_hp_can_defer_min")
    assert state is not None, "eos_asset_hp_can_defer_min niet gevonden"
    return state


# Resolved dispatcher-context (Dynamic-modus, drempels al ingevuld).
BASE = dict(
    grid=0, hard_lim=16000, bat_low=False, level="duur",
    hp_full=20, hp_sell=8, hp_charge=6, hp_peak=10,
)
COAST = "sensor.quatt_warmteanalyse_veilige_uitlooptijd"
MARGIN = "input_number.eos_comfort_coast_margin_min"
COP = "sensor.quatt_warmteanalyse_geschatte_actuele_cop"


# --------------------------------------------------------------------------- #
#  Comfort-guard (dispatcher "duur"-tak)                                       #
# --------------------------------------------------------------------------- #


class TestComfortGuard:
    def test_duur_zonder_stooklijn_throttlet(self, desired_cap):
        """Geen stooklijn (coast unknown) → fallback → knijp zoals vroeger."""
        render = _make_render({})
        assert render(desired_cap, **BASE) == "8"  # hp_sell

    def test_duur_ruime_coast_throttlet(self, desired_cap):
        """Coast ruim boven marge → veilig knijpen."""
        render = _make_render({COAST: "120", MARGIN: "45"})
        assert render(desired_cap, **BASE) == "8"

    def test_duur_lage_coast_vrij_voor_comfort(self, desired_cap):
        """Coast onder marge → comfort wint, WP draait vrij."""
        render = _make_render({COAST: "30", MARGIN: "45"})
        assert render(desired_cap, **BASE) == "20"  # hp_full

    def test_duur_coast_op_marge_vrij(self, desired_cap):
        """Coast gelijk aan marge telt niet als veilig (strikt groter)."""
        render = _make_render({COAST: "45", MARGIN: "45"})
        assert render(desired_cap, **BASE) == "20"

    def test_goedkoop_laadt(self, desired_cap):
        """Goedkoop tarief → laden, comfort-guard niet van toepassing."""
        render = _make_render({COAST: "30", MARGIN: "45"})
        assert render(desired_cap, **{**BASE, "level": "goedkoop"}) == "6"

    def test_grid_overschrijding_heeft_voorrang(self, desired_cap):
        """Grid boven hard limit gaat vóór de comfort-guard."""
        render = _make_render({COAST: "10", MARGIN: "45"})
        assert render(desired_cap, **{**BASE, "grid": 99999}) == "10"  # hp_peak

    def test_normaal_tarief_vrij(self, desired_cap):
        render = _make_render({})
        assert render(desired_cap, **{**BASE, "level": "normaal"}) == "20"

    def test_batterij_leeg_geen_throttle(self, desired_cap):
        """bat_low → duur-tak vervalt → WP vrij (bestaand gedrag)."""
        render = _make_render({COAST: "120", MARGIN: "45"})
        assert render(desired_cap, **{**BASE, "bat_low": True}) == "20"


# --------------------------------------------------------------------------- #
#  Asset-capabilities (COP + defer-time)                                       #
# --------------------------------------------------------------------------- #


class TestCopEstimate:
    def test_zonder_stooklijn_carnot_fallback(self, cop_state):
        render = _make_render(
            {"sensor.eos_outside_temp_c": "7", "sensor.eos_hp_supply_temp_c": "35"}
        )
        assert 3.0 < float(render(cop_state)) < 6.0  # Carnot-heuristiek

    def test_met_stooklijn_gemeten_cop(self, cop_state):
        render = _make_render({COP: "3.42"})
        assert float(render(cop_state)) == pytest.approx(3.42)


class TestDeferMin:
    def test_zonder_stooklijn_buckets(self, defer_state):
        render = _make_render({"sensor.eos_outside_temp_c": "2"})
        assert int(render(defer_state)) == 40  # bucket 0..5°C

    def test_met_stooklijn_coast(self, defer_state):
        render = _make_render({COAST: "95"})
        assert int(render(defer_state)) == 95


# --------------------------------------------------------------------------- #
#  Core-config                                                                 #
# --------------------------------------------------------------------------- #


class TestCoreConfig:
    def test_comfort_margin_input_number_bestaat(self):
        core = _load(PKG / "eos_00_core.yaml")
        inp = core["input_number"]["eos_comfort_coast_margin_min"]
        assert inp["initial"] == 45
        assert inp["min"] == 0
        assert inp["max"] >= 45
