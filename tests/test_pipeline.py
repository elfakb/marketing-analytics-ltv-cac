"""Data-integrity and metric tests.  Run:  pytest -q"""
import numpy as np
import pandas as pd
import pytest

from src import generate_data, marts, metrics


@pytest.fixture(scope="module")
def data():
    campaigns, customers, orders = generate_data.generate()
    campaigns["date"] = pd.to_datetime(campaigns["date"])
    customers["signup_date"] = pd.to_datetime(customers["signup_date"])
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    return campaigns, customers, orders


def test_safe_division_returns_nan_not_inf():
    out = metrics.sdiv(pd.Series([10.0, 5.0]), pd.Series([0.0, 2.0]))
    assert np.isnan(out.iloc[0]) and out.iloc[1] == 2.5


def test_kpi_formulas():
    df = pd.DataFrame([dict(spend=100.0, impressions=10000, clicks=200, leads=40, conversions=10,
                            new_customers=8, revenue=1000.0, cogs=400.0)])
    k = metrics.add_kpis(df).iloc[0]
    assert k.ctr == pytest.approx(0.02) and k.cpc == pytest.approx(0.5)
    assert k.cpl == pytest.approx(2.5) and k.cpa == pytest.approx(10.0)
    assert k.cvr == pytest.approx(0.05) and k.cac == pytest.approx(12.5)
    assert k.roas == pytest.approx(10.0) and k.profit == pytest.approx(500.0)


def test_funnel_consistency(data):
    c, _, _ = data
    assert (c["clicks"] <= c["impressions"]).all()
    assert (c["conversions"] <= c["clicks"]).all()
    assert (c["leads"] >= c["new_customers"]).all()
    assert (c[["spend", "impressions", "clicks", "revenue", "cogs"]] >= 0).all().all()


def test_organic_has_no_spend(data):
    c, _, _ = data
    assert c.loc[c["channel"] == "Organic", "spend"].eq(0).all()


def test_reconciliation_between_tables(data):
    c, cu, o = data
    assert c["new_customers"].sum() == len(cu)
    assert c["conversions"].sum() == len(o)
    assert c["revenue"].sum() == pytest.approx(o["revenue"].sum(), rel=1e-6)
    assert set(o["customer_id"]) <= set(cu["customer_id"])
    assert cu["customer_id"].is_unique and o["order_id"].is_unique


def test_orders_not_before_signup_and_within_period(data):
    _, cu, o = data
    m = o.merge(cu[["customer_id", "signup_date"]], on="customer_id")
    assert (m["order_date"] >= m["signup_date"]).all()
    assert o["order_date"].max() <= pd.Timestamp("2025-12-31")


def test_ltv_is_censored_not_zero(data):
    c, cu, o = data
    e = marts.enrich_customers(cu, o, c)
    immature = e["observed_days"] < 180
    assert e.loc[immature, "ltv_180"].isna().all()
    assert e.loc[~immature, "ltv_180"].notna().all()
    assert (e["ltv_90"].dropna() >= -1e-9).all()   # gross profit can't be negative here


def test_generation_is_deterministic():
    a = generate_data.generate(seed=7)[2]
    b = generate_data.generate(seed=7)[2]
    pd.testing.assert_frame_equal(a, b)
