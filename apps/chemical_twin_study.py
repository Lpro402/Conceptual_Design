"""Chemical-twin study: scenarios, uncertainty quantification and robust operating window.

Run with ``python apps/chemical_twin_study.py``. Figures and a JSON summary are
written to ``exports/chemical_twin/`` (generated output, ignored by git).

Workflow (digital-twin practice from the data-science course):
1. deterministic mission scenarios on the physics twin;
2. space-filling Latin hypercube over the uncertain factors;
3. Gaussian-process emulator + leave-one-out validation;
4. Monte Carlo propagation → probability of meeting the 3 kWh event;
5. one expected-improvement step to locate the most robust ambient/power window.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from mpro.chemical_twin import PlantParameters, run_event  # noqa: E402
from mpro.chemical_twin.chemistry import energy_balance_check  # noqa: E402
from mpro.twin_services import uq  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "exports" / "chemical_twin"

SCENARIOS = {
    "Nominal 10 kW, 25 °C": (PlantParameters(), 10.0),
    "Boost 12 kW, 25 °C": (PlantParameters(), 12.0),
    "Hot 50 °C, Boost requested": (PlantParameters(ambient_c=50.0), 12.0),
    "Cold -25 °C, 10 kW": (PlantParameters(ambient_c=-25.0), 10.0),
    "Max water 2.2 L": (PlantParameters(water_l=2.2), 10.0),
}


def scenario_figure() -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    results = {}
    for label, (params, kw) in SCENARIOS.items():
        result, plant = run_event(params, requested_kw=kw, record=True)
        results[label] = asdict(result)
        h = plant.state.history
        t = [p["t_s"] / 60 for p in h]
        axes[0].plot(t, [p["power_kw"] for p in h], label=label)
        axes[1].plot(t, [p["temperature_c"] for p in h])
        axes[2].plot(t, [p["energy_kwh"] for p in h])
    for ax, title in zip(axes, ("EV power [kW]", "Core temperature [°C]", "Delivered energy [kWh]")):
        ax.set_title(title)
        ax.set_xlabel("time [min]")
        ax.grid(alpha=0.3)
    for y in (52, 55, 65):
        axes[1].axhline(y, ls="--", lw=0.8, color="grey")
    axes[2].axhline(3.0, ls="--", lw=0.8, color="grey")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "scenarios.png", dpi=160)
    plt.close(fig)
    return results


def uq_study(n: int = 60, seed: int = 11) -> dict:
    rng = np.random.default_rng(seed)
    unit = uq.latin_hypercube(n, len(uq.FACTORS), rng)
    y = uq.simulate(uq.scale(unit))
    summary = {}
    requirements = {"delivered_energy_kwh": (">=", 2.95), "peak_temperature_c": ("<=", 55.0),
                    "duration_min": ("<=", 20.0)}
    emulators = {}
    for j, response in enumerate(uq.RESPONSES):
        gp = uq.GaussianProcess().fit(unit, y[:, j])
        emulators[response] = gp
        entry = {"loo_rmse": uq.leave_one_out_rmse(unit, y[:, j]),
                 "length_scales": dict(zip(uq.FACTORS, gp.length_scale.round(2).tolist()))}
        if response in requirements:
            entry["propagation"] = asdict(uq.propagate(gp, response, requirements[response]))
        summary[response] = entry

    # Main-effect profiles from the emulator (other factors at mid-range).
    fig, axes = plt.subplots(1, len(uq.FACTORS), figsize=(18, 3.2), sharey=True)
    grid = np.linspace(0, 1, 40)
    gp = emulators["delivered_energy_kwh"]
    for k, (ax, (name, (lo, hi))) in enumerate(zip(axes, uq.FACTORS.items())):
        pts = np.full((40, len(uq.FACTORS)), 0.5)
        pts[:, k] = grid
        mean, std = gp.predict(pts, return_std=True)
        x = lo + grid * (hi - lo)
        ax.plot(x, mean)
        ax.fill_between(x, mean - 2 * std, mean + 2 * std, alpha=0.25)
        ax.set_title(name, fontsize=9)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("energy [kWh]")
    fig.tight_layout()
    fig.savefig(OUT / "emulator_profiles.png", dpi=160)
    plt.close(fig)

    # One expected-improvement step: most promising untested setting for energy.
    candidates = rng.random((3000, len(uq.FACTORS)))
    ei = uq.expected_improvement(gp, candidates, float(y[:, 0].max()))
    best = uq.scale(candidates[np.argmax(ei)][None, :])[0]
    summary["next_experiment_by_expected_improvement"] = dict(zip(uq.FACTORS, best.round(3).tolist()))
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "scenarios": scenario_figure(),
        "uncertainty": uq_study(),
        "first_principles_energy_balance": asdict(energy_balance_check(3.0 / 0.92)),
    }
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["uncertainty"]["delivered_energy_kwh"], indent=2))
    print(f"Outputs written to {OUT}")


if __name__ == "__main__":
    main()
