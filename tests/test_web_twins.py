"""Keep the browser twins consistent with the Python twins and the shared baseline."""

import re
from pathlib import Path

from mpro import baseline
from mpro.software_twin.states import MISSION_SEQUENCE, SystemState

DOCS = Path(__file__).resolve().parents[1] / "docs"
HMI = (DOCS / "index.html").read_text(encoding="utf-8")
APP = (DOCS / "assets" / "app.js").read_text(encoding="utf-8")
CHEM = (DOCS / "chemical-twin" / "index.html").read_text(encoding="utf-8")
INTEGRATION = (DOCS / "integration-twin" / "index.html").read_text(encoding="utf-8")
HUB = (DOCS / "hub.html").read_text(encoding="utf-8")


def js_array(source: str, name: str) -> list[str]:
    body = re.search(rf"const {name} = \[(.*?)\];", source, re.S).group(1)
    return re.findall(r'"([A-Z_]+)"', body)


def test_web_hmi_state_order_matches_python_mission_sequence() -> None:
    assert js_array(APP, "STATE_ORDER") == [s.name for s in MISSION_SEQUENCE]


def test_web_hmi_defines_every_python_state() -> None:
    for state in SystemState:
        assert re.search(rf"\b{state.name}: \{{ title:", APP), state.name


def test_web_hmi_keeps_public_entry_points() -> None:
    for element_id in ("primary-action", "emergency-action", "lcd-primary-action", "lcd-emergency-action",
                       "architecture-runtime-state", "architecture-state-flow", "fault-select", "inject-fault",
                       "cassette-grid", "event-log"):
        assert f'id="{element_id}"' in HMI
    assert 'get("scenario") !== "charging"' in APP
    assert '["mission", "lcd", "architecture", "diagnostics", "service"]' in APP


def test_web_hmi_uses_baseline_operating_point() -> None:
    op = baseline.load()["operating_point"]
    assert f"nominalKw: {op['net_power_nominal_kw']:g}" in APP
    assert f"boostKw: {op['net_power_boost_kw']:g}" in APP
    assert f"stackV: {op['stack_voltage_nominal_v']}" in APP
    assert "57.6" not in APP + HMI


def test_chemical_twin_config_matches_baseline() -> None:
    config = re.search(r"const CONFIG = Object\.freeze\(\{(.*?)\}\);", CHEM, re.S).group(1)
    values = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", config)}
    b = baseline.load()
    assert values["targetEnergyKWh"] == b["operating_point"]["usable_energy_per_event_kwh"]
    assert values["nominalPowerKW"] == b["operating_point"]["net_power_nominal_kw"]
    assert values["boostPowerKW"] == b["operating_point"]["net_power_boost_kw"]
    assert values["nominalStackVoltageV"] == b["operating_point"]["stack_voltage_nominal_v"]
    assert values["activeAlKg"] == b["chemistry"]["aluminum_mass_kg"]
    assert values["dryKohG"] == b["chemistry"]["koh_charge_g"]
    assert values["derateTempC"] == b["thermal"]["derate_c"]
    assert values["shutdownTempC"] == b["thermal"]["shutdown_c"]
    assert values["boostDisableTempC"] == b["thermal"]["boost_disable_c"]


def test_chemical_twin_implements_configuration_2() -> None:
    assert js_array(CHEM, "STATE_ORDER")[:4] == ["DRY_READY", "SELECTED", "FILL_SESSION", "WATER_ADMISSION"]
    for marker in ("evaluateGates", "superviseIsolation", "cancelFill", "DIN 70121", "renderTwinLayers",
                   "Reaction clock starts now"):
        assert marker in CHEM


def test_twin_pages_link_to_each_other() -> None:
    for href in ('href="./"', 'href="chemical-twin/"', 'href="control-twin/"', 'href="integration-twin/"'):
        assert href in HUB
    assert 'href="chemical-twin/"' in HMI and 'href="integration-twin/"' in HMI
    assert 'href="../hub.html"' in CHEM and 'href="../hub.html"' in INTEGRATION


def test_pages_load_scripts_only_from_approved_sources() -> None:
    for page in (HMI, CHEM, INTEGRATION, HUB):
        for src in re.findall(r'<script[^>]+src="([^"]+)"', page):
            assert src.startswith(("assets/", "https://cdnjs.cloudflare.com/")), src


def test_hmi_screen_twin_shows_the_configuration_2_operator_messages() -> None:
    from mpro.software_twin.hmi import MESSAGES

    body = re.search(r"const HMI_HE = \{(.*?)\};", APP, re.S).group(1)
    web = dict(re.findall(r'(\w+): "([^"]+)"', body))
    python = {state.name: text.replace("{measured:.1f}", "{measured}") for state, text in MESSAGES.items()}
    assert web == python
    for element_id in ("lcd-operator-he", "lcd-fill", "lcd-permissive-vent", "lcd-permissive-env"):
        assert f'id="{element_id}"' in HMI
