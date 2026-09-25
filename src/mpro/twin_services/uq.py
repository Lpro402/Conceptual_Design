"""Uncertainty quantification for the chemical twin.

Follows the digital-twin workflow taught in the data-science course: treat the
physics model as a simulator, sample its uncertain inputs with a space-filling
Latin hypercube, fit a Gaussian-process (Kriging) emulator to the responses,
and use the emulator for fast what-if, robustness and optimisation studies.
Implemented with NumPy only so it runs anywhere the twin runs.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import numpy as np

from mpro.chemical_twin import PlantParameters, run_event

# Uncertain factors of the chemical twin and their conceptual ranges.
FACTORS: dict[str, tuple[float, float]] = {
    "coulombic_efficiency": (0.92, 0.985),
    "conversion_efficiency": (0.90, 0.94),
    "usable_al_fraction": (0.80, 0.90),
    "heat_fraction": (0.10, 0.16),
    "ua_w_k": (45.0, 75.0),
    "ambient_c": (-25.0, 50.0),
    "water_l": (1.8, 2.2),
}

RESPONSES = ("delivered_energy_kwh", "duration_min", "peak_temperature_c", "hydrogen_l")


def latin_hypercube(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    """Space-filling LHS design in the unit cube: one sample per stratum per factor."""
    strata = (np.arange(n)[:, None] + rng.random((n, k))) / n
    for j in range(k):
        strata[:, j] = rng.permutation(strata[:, j])
    return strata


def scale(unit: np.ndarray, factors: dict[str, tuple[float, float]] = FACTORS) -> np.ndarray:
    lo = np.array([v[0] for v in factors.values()])
    hi = np.array([v[1] for v in factors.values()])
    return lo + unit * (hi - lo)


def simulate(x: np.ndarray, requested_kw: float = 10.0, factors: dict = FACTORS) -> np.ndarray:
    """Run the physics twin for every row of ``x`` (physical units)."""
    names = list(factors)
    out = np.empty((len(x), len(RESPONSES)))
    for i, row in enumerate(x):
        params = PlantParameters().with_(**dict(zip(names, row)))
        result, _ = run_event(params, requested_kw=requested_kw, dt_s=10.0)
        out[i] = [getattr(result, r) for r in RESPONSES]
    return out


@dataclass
class GaussianProcess:
    """Kriging emulator with a squared-exponential kernel and a constant mean.

    Length scales are chosen by maximising the log marginal likelihood over a
    small grid, which is robust and dependency-free for a handful of factors.
    """

    length_scale: np.ndarray | None = None
    noise: float = 1e-6
    _x: np.ndarray | None = None
    _alpha: np.ndarray | None = None
    _chol: np.ndarray | None = None
    _mean: float = 0.0
    _std: float = 1.0
    _signal: float = 1.0

    def _kernel(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        d = (a[:, None, :] - b[None, :, :]) / self.length_scale
        return self._signal * np.exp(-0.5 * np.sum(d * d, axis=-1))

    def _nll(self, x: np.ndarray, y: np.ndarray) -> float:
        k = self._kernel(x, x) + self.noise * np.eye(len(x))
        try:
            chol = np.linalg.cholesky(k)
        except np.linalg.LinAlgError:
            return np.inf
        alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y))
        return 0.5 * y @ alpha + np.sum(np.log(np.diag(chol)))

    def fit(self, x: np.ndarray, y: np.ndarray) -> "GaussianProcess":
        self._mean, self._std = float(y.mean()), float(y.std() or 1.0)
        yn = (y - self._mean) / self._std
        k = x.shape[1]
        best, best_ls = np.inf, np.full(k, 0.5)
        for base in (0.2, 0.35, 0.5, 0.8, 1.2, 2.0):
            ls = np.full(k, base)
            for j in range(k):                       # coordinate refinement per factor
                for mult in (0.5, 1.0, 2.0, 4.0):
                    trial = ls.copy()
                    trial[j] = base * mult
                    self.length_scale = trial
                    nll = self._nll(x, yn)
                    if nll < best:
                        best, best_ls, ls = nll, trial.copy(), trial.copy()
        self.length_scale = best_ls
        kxx = self._kernel(x, x) + self.noise * np.eye(len(x))
        self._chol = np.linalg.cholesky(kxx)
        self._alpha = np.linalg.solve(self._chol.T, np.linalg.solve(self._chol, yn))
        self._x = x
        return self

    def predict(self, x: np.ndarray, return_std: bool = False):
        ks = self._kernel(x, self._x)
        mean = ks @ self._alpha * self._std + self._mean
        if not return_std:
            return mean
        v = np.linalg.solve(self._chol, ks.T)
        var = np.clip(self._signal - np.sum(v * v, axis=0), 1e-12, None)
        return mean, np.sqrt(var) * self._std


def leave_one_out_rmse(x: np.ndarray, y: np.ndarray) -> float:
    """Jack-knife check of emulator adequacy (model validation as a statistical process)."""
    errors = []
    for i in range(len(x)):
        mask = np.arange(len(x)) != i
        gp = GaussianProcess().fit(x[mask], y[mask])
        errors.append(gp.predict(x[i:i + 1])[0] - y[i])
    return float(np.sqrt(np.mean(np.square(errors))))


@dataclass(frozen=True)
class RobustnessSummary:
    """Monte Carlo propagation of input uncertainty through the emulator."""

    response: str
    mean: float
    std: float
    p05: float
    p95: float
    probability_meets: float


def propagate(gp: GaussianProcess, response: str, requirement: tuple[str, float],
              n: int = 4000, seed: int = 7) -> RobustnessSummary:
    rng = np.random.default_rng(seed)
    samples = gp.predict(rng.random((n, len(FACTORS))))
    op, limit = requirement
    meets = samples >= limit if op == ">=" else samples <= limit
    return RobustnessSummary(response, float(samples.mean()), float(samples.std()),
                             float(np.percentile(samples, 5)), float(np.percentile(samples, 95)),
                             float(meets.mean()))


def expected_improvement(gp: GaussianProcess, candidates: np.ndarray, best: float) -> np.ndarray:
    """Expected improvement (maximisation) used for Bayesian-optimisation steps."""
    from math import erf, sqrt, pi

    mean, std = gp.predict(candidates, return_std=True)
    z = (mean - best) / std
    cdf = 0.5 * (1.0 + np.vectorize(erf)(z / sqrt(2.0)))
    pdf = np.exp(-0.5 * z * z) / sqrt(2.0 * pi)
    return (mean - best) * cdf + std * pdf


def factor_names() -> list[str]:
    known = {f.name for f in fields(PlantParameters)}
    assert set(FACTORS) <= known, "every UQ factor must be a PlantParameters field"
    return list(FACTORS)
