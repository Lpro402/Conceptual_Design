from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "docs" / "assets" / "app.js").read_text(encoding="utf-8")


def test_public_hmi_is_english_and_ltr() -> None:
    assert '<html lang="en" dir="ltr">' in INDEX
    assert "Operation" in INDEX
    assert "LCD Display" in INDEX
    assert "Diagnostics & Fault Simulation" in INDEX
    assert "Readiness, Service & Recycling" in INDEX


def test_public_hmi_exposes_core_controls() -> None:
    for element_id in (
        "primary-action",
        "emergency-action",
        "lcd-primary-action",
        "lcd-emergency-action",
        "lcd-energy-path",
        "fault-select",
        "inject-fault",
        "cassette-grid",
        "event-log",
    ):
        assert f'id="{element_id}"' in INDEX


def test_public_hmi_contains_required_states_and_faults() -> None:
    for state in (
        "STANDBY",
        "POWER_TRANSFER",
        "DERATING",
        "EMERGENCY_SHUTDOWN",
        "FAULT_LOCKED",
        "SERVICE_REQUIRED",
    ):
        assert state in APP

    for fault in (
        "E_STOP",
        "ISOLATION_FAULT",
        "HYDROGEN_ALARM",
        "PUMP_FAILURE",
        "CONTACTOR_MISMATCH",
    ):
        assert fault in APP


def test_public_hmi_keeps_academic_disclaimer() -> None:
    assert "ACADEMIC SIMULATION ONLY" in INDEX
    assert "NO REAL HARDWARE, VEHICLE OR CCS2 CONTROL" in INDEX


def test_lcd_standalone_view_is_supported() -> None:
    assert "initializeRequestedView" in APP
    assert 'view === "lcd"' in APP
    assert "lcd-standalone" in APP
