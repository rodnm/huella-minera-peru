"""Area-level small-area model (Fay & Herriot, 1979) on the arcsine scale.

    y_i = x_i'β + u_i + e_i,    u_i ~ N(0, σ²),    e_i ~ N(0, D_i) with D_i known

σ² comes from restricted maximum likelihood. The estimate shrinks each survey value towards the regression:
θ_i = γ_i·y_i + (1 − γ_i)·x_i'β with γ_i = σ²/(σ² + D_i), so a district with few households leans on its predictors
and a district without households takes the prediction alone. Error follows Prasad & Rao (1990) with the REML
correction of Datta & Lahiri (2000).
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar


@dataclass
class Model:
    beta: np.ndarray
    cov_beta: np.ndarray
    sigma2: float
    var_sigma2: float


@dataclass
class Prediction:
    theta: np.ndarray
    gamma: np.ndarray
    mse: np.ndarray


def to_theta(rate):
    return np.arcsin(np.sqrt(rate))


def to_rate(theta):
    return np.sin(np.clip(theta, 0, np.pi / 2)) ** 2


def _gls(y, X, D, sigma2):
    weights = 1 / (sigma2 + D)
    information = (X * weights[:, None]).T @ X
    beta = np.linalg.solve(information, (X * weights[:, None]).T @ y)
    return beta, information, weights


def fit(y: np.ndarray, X: np.ndarray, D: np.ndarray) -> Model:
    """REML over σ² for the sampled districts; β is the matching generalized least squares estimate."""

    def restricted_deviance(sigma2):
        beta, information, weights = _gls(y, X, D, sigma2)
        residual = y - X @ beta
        return (-np.log(weights).sum() + np.linalg.slogdet(information)[1] + (weights * residual ** 2).sum())

    upper = max(float(np.var(y)) * 4, 1e-3)
    sigma2 = float(minimize_scalar(restricted_deviance, bounds=(0.0, upper), method="bounded",
                                   options={"xatol": 1e-7}).x)
    beta, information, weights = _gls(y, X, D, sigma2)
    return Model(beta=beta, cov_beta=np.linalg.inv(information), sigma2=sigma2,
                 var_sigma2=2 / (weights ** 2).sum())


def predict(model: Model, X: np.ndarray, y: np.ndarray, D: np.ndarray) -> Prediction:
    """Estimate every district. ``y`` is NaN and ``D`` is ignored for a district without sample."""
    sampled = ~np.isnan(y)
    synthetic = X @ model.beta
    gamma = np.zeros(len(y))
    gamma[sampled] = model.sigma2 / (model.sigma2 + D[sampled]) if model.sigma2 > 0 else 0.0
    theta = synthetic.copy()
    theta[sampled] = gamma[sampled] * y[sampled] + (1 - gamma[sampled]) * synthetic[sampled]

    regression_error = np.einsum("ij,jk,ik->i", X, model.cov_beta, X)
    mse = model.sigma2 + regression_error
    g1 = gamma[sampled] * D[sampled]
    g2 = (1 - gamma[sampled]) ** 2 * regression_error[sampled]
    g3 = D[sampled] ** 2 / (model.sigma2 + D[sampled]) ** 3 * model.var_sigma2
    mse[sampled] = g1 + g2 + 2 * g3
    return Prediction(theta=theta, gamma=gamma, mse=mse)


def benchmark(rate, population, department, targets: dict) -> np.ndarray:
    """Scale the rates of each department so their population-weighted mean equals its direct survey rate.

    ENAHO is representative by department, so the district estimates are made to add up to it.
    """
    rate = np.asarray(rate, dtype=float).copy()
    population = np.asarray(population, dtype=float)
    department = np.asarray(department)
    for code, target in targets.items():
        members = department == code
        if not members.any():
            continue
        current = np.average(rate[members], weights=population[members])
        if current > 0:
            rate[members] *= target / current
    return np.clip(rate, 0, 1)
