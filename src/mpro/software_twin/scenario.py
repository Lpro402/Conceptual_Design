"""Run declarative JSON demonstration scenarios against the software twin.

A scenario is a list of steps. Each step is ``[action, {kwargs}]`` where the
action is a controller method, ``set`` (write simulated sensor values) or
``expect`` (assert state, cartridge states, blocker text or log content).
"""

from __future__ import annotations

import json
from pathlib import Path

from .controller import MainSystemController
from .states import FaultType

SCENARIO_DIR = Path(__file__).resolve().parents[3] / "scenarios"


class ScenarioFailure(AssertionError):
    pass


def _expect(ctrl: MainSystemController, spec: dict, step_no: int) -> None:
    def fail(what: str) -> None:
        raise ScenarioFailure(f"step {step_no}: {what}")

    if "state" in spec and ctrl.state.name != spec["state"]:
        fail(f"state {ctrl.state.name} != {spec['state']}")
    if "cartridges" in spec and [c.name for c in ctrl.cartridge_states()] != spec["cartridges"]:
        fail(f"cartridges {[c.name for c in ctrl.cartridge_states()]} != {spec['cartridges']}")
    if "blocker_contains" in spec and spec["blocker_contains"] not in (ctrl.blocker or ""):
        fail(f"blocker {ctrl.blocker!r} lacks {spec['blocker_contains']!r}")
    if spec.get("no_blocker") and ctrl.blocker:
        fail(f"unexpected blocker {ctrl.blocker!r}")
    if "log_contains" in spec and not any(spec["log_contains"] in r.message for r in ctrl.logger.records):
        fail(f"log lacks {spec['log_contains']!r}")
    if "min_energy_kwh" in spec and ctrl.delivered_kwh < spec["min_energy_kwh"]:
        fail(f"energy {ctrl.delivered_kwh:.2f} < {spec['min_energy_kwh']}")
    for name, expected in spec.get("actuators", {}).items():
        if getattr(ctrl.hal.actuators, name) != expected:
            fail(f"actuator {name} != {expected}")
    if "protocol" in spec and ctrl.ev.protocol != spec["protocol"]:
        fail(f"protocol {ctrl.ev.protocol} != {spec['protocol']}")


def run(scenario: dict | Path, controller: MainSystemController | None = None) -> MainSystemController:
    if isinstance(scenario, Path):
        scenario = json.loads(scenario.read_text(encoding="utf-8"))
    ctrl = controller or MainSystemController()
    for number, step in enumerate(scenario["steps"], start=1):
        action, kwargs = step[0], (step[1] if len(step) > 1 else {})
        if action == "expect":
            _expect(ctrl, kwargs, number)
        elif action == "set":
            for key, val in kwargs.items():
                target = ctrl.hal if key in {"pump_available", "blower_available"} else ctrl.hal.sensors
                setattr(target, key, val)
        elif action == "inject_fault":
            ctrl.inject_fault(FaultType[kwargs["fault"]])
        else:
            getattr(ctrl, action)(**kwargs)
    return ctrl


def all_scenarios() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("*.json"))
