import numpy as np
import pandas as pd
import pytest

from brillo.fay_herriot import benchmark, fit, predict, to_rate, to_theta


def simulate(n=1500, sigma2=0.01, seed=7):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    D = rng.uniform(0.002, 0.05, n)
    y = X @ np.array([0.6, 0.1]) + rng.normal(0, np.sqrt(sigma2), n) + rng.normal(0, np.sqrt(D))
    return X, y, D


def test_fit_recovers_coefficients_and_area_variance():
    X, y, D = simulate()
    model = fit(y, X, D)
    assert model.beta == pytest.approx([0.6, 0.1], abs=0.02)
    assert model.sigma2 == pytest.approx(0.01, abs=0.003)


def test_weight_on_the_survey_rises_as_its_error_falls():
    X, y, D = simulate()
    model = fit(y, X, D)
    D2 = np.full(len(y), 1e-6)
    assert predict(model, X, y, D2).gamma == pytest.approx(np.ones(len(y)), abs=0.01)
    D3 = np.full(len(y), 1e3)
    assert predict(model, X, y, D3).gamma == pytest.approx(np.zeros(len(y)), abs=0.01)


def test_a_district_without_sample_gets_the_synthetic_prediction_and_more_error():
    X, y, D = simulate()
    model = fit(y, X, D)
    y2 = y.copy()
    y2[0] = np.nan
    out = predict(model, X, y2, D)
    assert out.gamma[0] == 0
    assert out.theta[0] == pytest.approx(X[0] @ model.beta)
    assert out.mse[0] > model.sigma2
    assert np.median(out.mse[1:]) < model.sigma2


def test_rates_transform_back_and_stay_inside_zero_and_one():
    assert to_rate(to_theta(np.array([0.0, 0.25, 1.0]))) == pytest.approx([0, 0.25, 1])
    assert to_rate(np.array([-0.2, 2.0])) == pytest.approx([0, 1])


def test_benchmark_matches_each_department_total_and_never_exceeds_one():
    df = pd.DataFrame({"rate": [0.2, 0.4, 0.9], "population": [100.0, 100.0, 50.0], "department": ["01", "01", "02"]})
    out = benchmark(df["rate"], df["population"], df["department"], {"01": 0.45, "02": 1.2})
    assert np.average(out[:2], weights=[100, 100]) == pytest.approx(0.45)
    assert out[2] == 1
