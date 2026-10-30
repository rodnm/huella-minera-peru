"""The three findings: light, poverty and the "paradox" districts, plus the mines that opened during the series."""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def cross_section(panel: pd.DataFrame, year: int = 2018, mining_years: tuple[int, int] = (2016, 2018),
                  exclude: set[str] = frozenset()) -> pd.DataFrame:
    """Districts with 2018 poverty, their light that year and whether they produced in ``mining_years``."""
    produced = panel[panel.year.between(*mining_years)].groupby("ubigeo")["mining"].any()
    cs = panel[(panel.year == year) & panel.poverty.notna() & ~panel.ubigeo.isin(exclude)].copy()
    cs["mining"] = cs["ubigeo"].map(produced).fillna(False).astype(bool)
    cs["light_outside_per_capita"] = cs["light_outside_mines"] / cs["population_2020"]
    return cs.reset_index(drop=True)


def paradox_districts(cs: pd.DataFrame, quantile: float = 0.75) -> pd.DataFrame:
    """Mining districts among the brightest per person in the country yet poorer than their department's median.

    INEI publishes poverty as a 95 % interval. ``confirmed`` means its lower bound is above the median, so the
    district is poorer even at the low end; otherwise only the midpoint is above and the case is merely possible.
    """
    bright = cs["light_per_capita"] > cs["light_per_capita"].quantile(quantile)
    median = cs.groupby("department")["poverty"].transform("median")
    out = cs[cs["mining"] & bright & (cs["poverty"] > median)].copy()
    out["confirmed"] = out["poverty_low"] > median[out.index]
    return out


def mine_openings(panel: pd.DataFrame, first: int, last: int, before: int = 2, after: int = 3) -> pd.DataFrame:
    """Districts whose first production year falls in [first, last]: mean light before vs after the opening."""
    start = panel[panel["mining"]].groupby("ubigeo")["year"].min()
    start = start[start.between(first, last)]
    rows = []
    for ubigeo, year in start.items():
        light = panel[panel.ubigeo == ubigeo].set_index("year")["light_sum"]
        pre = light.reindex(range(year - before, year)).mean()
        post = light.reindex(range(year + 1, year + 1 + after)).mean()
        rows.append({"ubigeo": ubigeo, "start": int(year), "light_before": pre, "light_after": post,
                     "ratio": post / pre if pre > 0 else np.nan})
    return pd.DataFrame(rows, columns=["ubigeo", "start", "light_before", "light_after", "ratio"])


def gaps(cs: pd.DataFrame) -> dict:
    """Mining gaps within department (fixed effects, robust errors): light, light per person and poverty."""
    d = cs.assign(log_light=np.log1p(cs.light_sum), log_lpc=np.log1p(cs.light_per_capita * 1000),
                  log_pop=np.log(cs.population_2020), log_area=np.log(cs.area_km2))
    models = {
        "light": "log_light ~ mining + log_area + log_pop + C(department)",
        "poverty": "poverty ~ mining + log_pop + log_area + C(department)",
        "poverty_same_light": "poverty ~ mining + log_lpc + log_pop + log_area + C(department)",
    }
    out = {}
    for name, formula in models.items():
        fit = smf.ols(formula, d).fit(cov_type="HC1")
        out[name] = {"coef": float(fit.params["mining[T.True]"]), "t": float(fit.tvalues["mining[T.True]"]),
                     "n": int(fit.nobs), "formula": formula}
    return out


def mining_groups(panel: pd.DataFrame, before: int = 2014, after: int = 2018) -> pd.Series:
    """Classify districts by when production starts, relative to the 2013 and 2018 poverty maps.

    establecida: already producing up to ``before``. abre_entre_mapas: first production after ``before`` and up to
    ``after``. abre_despues: first production after ``after``, which should show no effect on a 2013-2018 change and
    so works as a placebo. sin_mina: no production in the whole series.
    """
    first = panel[panel["mining"]].groupby("ubigeo")["year"].min()
    groups = pd.Series("sin_mina", index=sorted(panel["ubigeo"].unique()), name="group")
    groups[first[first <= before].index] = "establecida"
    groups[first[(first > before) & (first <= after)].index] = "abre_entre_mapas"
    groups[first[first > after].index] = "abre_despues"
    return groups


def poverty_change_effects(d: pd.DataFrame, reference: str = "sin_mina") -> dict:
    """Change in poverty of each group against districts without a mine, in percentage points.

    Controls: starting poverty (poorer districts fall more anyway), population, area, natural region and department;
    errors are clustered by province. This is an association between two estimated maps, not a causal effect.
    """
    fit = smf.ols(f"change ~ C(group, Treatment('{reference}')) + start + log_pop + log_area + C(region) + C(department)",
                  d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["province"])[0]})
    out = {}
    for group in d["group"].unique():
        if group == reference:
            continue
        key = f"C(group, Treatment('{reference}'))[T.{group}]"
        low, high = fit.conf_int().loc[key]
        out[group] = {"coef": float(fit.params[key]), "low": float(low), "high": float(high),
                      "t": float(fit.tvalues[key]), "n": int((d["group"] == group).sum())}
    return out
