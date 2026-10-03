"""Analytical layer: load raw data, compute LTV, unit economics and marts.

LTV definition
--------------
LTV_w = gross profit (revenue - COGS) a customer generates in the first `w`
days after the first order, *before* acquisition cost. Customers whose
observation window is shorter than `w` days are right-censored and get NaN
(they are excluded, never treated as zero).  Net LTV = LTV - CAC.

CAC for LTV comparisons is computed on the SAME matured cohort
(spend up to the cohort cut-off / new customers up to the cut-off).
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from src import metrics
from src.config import (DATA_PROCESSED, DATA_RAW, DB_PATH, END_DATE,
                        LTV_WINDOWS, POWERBI_DIR)

END = pd.Timestamp(END_DATE)


# --------------------------------------------------------------------------- load
def load_raw(path=DATA_RAW):
    campaigns = pd.read_csv(path / "campaigns_daily.csv", parse_dates=["date"])
    customers = pd.read_csv(path / "customers.csv", parse_dates=["signup_date"])
    orders = pd.read_csv(path / "orders.csv", parse_dates=["order_date"])
    return campaigns, customers, orders


def campaign_dim(campaigns: pd.DataFrame) -> pd.DataFrame:
    return (campaigns[["campaign_id", "channel", "campaign_name", "objective"]]
            .drop_duplicates().sort_values("campaign_id").reset_index(drop=True))


# --------------------------------------------------------------------------- LTV
def enrich_customers(customers: pd.DataFrame, orders: pd.DataFrame,
                     campaigns: pd.DataFrame) -> pd.DataFrame:
    """Add acquisition channel/campaign names and LTV / order counts per window."""
    dim = campaign_dim(campaigns).rename(columns={
        "campaign_id": "acquisition_campaign_id", "channel": "acquisition_channel",
        "campaign_name": "acquisition_campaign", "objective": "acquisition_objective"})
    out = customers.merge(dim, on="acquisition_campaign_id", how="left")

    o = orders.merge(customers[["customer_id", "signup_date"]], on="customer_id")
    o["days_since"] = (o["order_date"] - o["signup_date"]).dt.days
    o["gross_profit"] = o["revenue"] - o["cogs"]

    observed = (END - out["signup_date"]).dt.days + 1
    out["observed_days"] = observed
    for w in LTV_WINDOWS:
        agg = (o[o["days_since"] < w].groupby("customer_id")
               .agg(**{f"revenue_{w}": ("revenue", "sum"),
                       f"ltv_{w}": ("gross_profit", "sum"),
                       f"orders_{w}": ("order_id", "count")}).reset_index())
        out = out.merge(agg, on="customer_id", how="left")
        mature = observed >= w
        for col in (f"revenue_{w}", f"ltv_{w}", f"orders_{w}"):
            out[col] = out[col].fillna(0.0)
            out.loc[~mature, col] = np.nan
        out[f"repeat_{w}"] = np.where(mature, (out[f"orders_{w}"] >= 2).astype(float), np.nan)
    first = o[o["order_type"] == "first"].set_index("customer_id")
    out["first_order_revenue"] = out["customer_id"].map(first["revenue"])
    out["first_order_returned"] = out["customer_id"].map(first["is_returned"]).astype(bool)
    return out


# --------------------------------------------------------------------------- unit economics
def unit_economics(customers: pd.DataFrame, campaigns: pd.DataFrame,
                   by: str = "channel", window: int = 90) -> pd.DataFrame:
    """CAC, LTV, LTV:CAC and net LTV per group on the matured cohort.

    by = 'channel' | 'campaign_id'  (customers must carry acquisition_* columns)
    """
    cutoff = END - pd.Timedelta(days=window - 1)
    key_c = "acquisition_channel" if by == "channel" else "acquisition_campaign_id"
    cust = customers[customers["signup_date"] <= cutoff]
    g = (cust.groupby(key_c)
         .agg(new_customers=("customer_id", "count"),
              ltv=(f"ltv_{window}", "mean"),
              revenue_per_customer=(f"revenue_{window}", "mean"),
              repeat_rate=(f"repeat_{window}", "mean"),
              first_order_return_rate=("first_order_returned", "mean"))
         .rename_axis(by).reset_index())
    spend = (campaigns[campaigns["date"] <= cutoff].groupby(by)["spend"].sum()
             .rename("spend").reset_index())
    out = g.merge(spend, on=by, how="left")
    out["cac"] = metrics.sdiv(out["spend"], out["new_customers"])
    out["ltv_cac"] = metrics.sdiv(out["ltv"], out["cac"])
    out["net_ltv"] = out["ltv"] - out["cac"]
    if by == "campaign_id":
        out = out.merge(campaign_dim(campaigns), on="campaign_id", how="left")
    return out


def channel_segment_matrix(customers: pd.DataFrame, campaigns: pd.DataFrame,
                           window: int = 90, segment_col: str = "segment") -> pd.DataFrame:
    """Channel x segment: customers, LTV, repeat rate and net LTV.

    NOTE: media spend is not observable by segment, so the *channel* CAC is
    applied to every segment of that channel (documented limitation).
    """
    cutoff = END - pd.Timedelta(days=window - 1)
    cust = customers[customers["signup_date"] <= cutoff]
    g = (cust.groupby(["acquisition_channel", segment_col])
         .agg(customers=("customer_id", "count"), ltv=(f"ltv_{window}", "mean"),
              repeat_rate=(f"repeat_{window}", "mean")).reset_index())
    ue = unit_economics(customers, campaigns, "channel", window)[["channel", "cac"]]
    g = g.merge(ue, left_on="acquisition_channel", right_on="channel").drop(columns="channel")
    g["net_ltv"] = g["ltv"] - g["cac"]
    g["ltv_cac"] = metrics.sdiv(g["ltv"], g["cac"])
    return g


def conversion_trap(customers: pd.DataFrame, campaigns: pd.DataFrame,
                    window: int = 90, min_customers: int = 100) -> pd.DataFrame:
    """Quadrant classification of acquisition campaigns: conversion rate vs LTV.

    Thresholds = unweighted mean across eligible campaigns.
      High CVR + Low LTV  -> 'Conversion trap'
      High CVR + High LTV -> 'Star'
      Low CVR  + High LTV -> 'Hidden gem'
      Low CVR  + Low LTV  -> 'Underperformer'
    Campaigns with no (or few) new customers (e.g. Winback) are excluded.
    """
    perf = metrics.aggregate(campaigns, ["campaign_id", "channel", "campaign_name"])
    ue = unit_economics(customers, campaigns, "campaign_id", window)
    df = perf[["campaign_id", "channel", "campaign_name", "cvr", "conversions", "spend", "profit"]].merge(
        ue[["campaign_id", "new_customers", "ltv", "cac", "ltv_cac", "net_ltv", "repeat_rate"]],
        on="campaign_id")
    df = df[df["new_customers"] >= min_customers].copy()
    cvr_t, ltv_t = df["cvr"].mean(), df["ltv"].mean()
    hc, hl = df["cvr"] >= cvr_t, df["ltv"] >= ltv_t
    df["quadrant"] = np.select(
        [hc & ~hl, hc & hl, ~hc & hl], ["Conversion trap", "Star", "Hidden gem"], "Underperformer")
    df.attrs["cvr_threshold"], df.attrs["ltv_threshold"] = cvr_t, ltv_t
    return df.sort_values(["quadrant", "ltv"], ascending=[True, False]).reset_index(drop=True)


# Campaigns whose volume is capped by demand / list size, not by media budget.
NON_SCALABLE = ("GG01", "EM01")   # Brand search, Email welcome series


def reallocation_scenario(ue: pd.DataFrame, cut_pct: float = 0.30, efficiency: float = 0.60,
                          cut_below: float = 2.0, top_n: int = 3) -> dict:
    """Illustrative what-if: shift budget from low LTV:CAC to high LTV:CAC campaigns.

    Scope: paid *Acquisition* campaigns only (Retargeting/Retention CAC is not
    meaningful because their spend mostly drives repeat orders), and receivers
    must be scalable with media budget (not Brand search / Email welcome).

      cut      : campaigns with LTV:CAC < `cut_below` lose `cut_pct` of spend
                 -> lose cut_pct of their customers (and their LTV)
      reinvest : freed budget split equally across top-N receivers; extra spend
                 buys customers at only `efficiency` x historical efficiency
                 (diminishing returns)

    Uses the matured cohort of the horizon in `ue` (e.g. 180d) -> conservative,
    ignores value beyond that horizon. A scenario, NOT a forecast.
    """
    paid = ue[(ue["cac"] > 0) & (ue["objective"] == "Acquisition")]
    losers = paid[paid["ltv_cac"] < cut_below]
    winners = (paid[(paid["ltv_cac"] >= cut_below) & ~paid["campaign_id"].isin(NON_SCALABLE)]
               .nlargest(top_n, "ltv_cac"))
    freed = float((losers["spend"] * cut_pct).sum())
    profit_lost = float((losers["new_customers"] * cut_pct * (losers["ltv"] - losers["cac"])).sum())
    gain = 0.0
    if len(winners) and freed > 0:
        share = freed / len(winners)
        added = share / winners["cac"] * efficiency
        gain = float((added * winners["ltv"]).sum() - freed)
    return {"cut_campaigns": losers["campaign_id"].tolist(),
            "receiving_campaigns": winners["campaign_id"].tolist(),
            "freed_budget": freed, "profit_lost_from_cuts": profit_lost,
            "reinvestment_net_gain": gain, "net_profit_change": gain - profit_lost,
            "cut_pct": cut_pct, "efficiency": efficiency}


# --------------------------------------------------------------------------- exports
def build_all(write: bool = True):
    campaigns, customers, orders = load_raw()
    cust = enrich_customers(customers, orders, campaigns)
    dim = campaign_dim(campaigns)

    marts = {
        "mart_channel": metrics.aggregate(campaigns, "channel"),
        "mart_campaign": metrics.aggregate(campaigns, ["campaign_id", "channel", "campaign_name", "objective"]),
        "mart_monthly_channel": metrics.aggregate(
            campaigns.assign(month=campaigns["date"].dt.to_period("M").dt.to_timestamp()),
            ["month", "channel"]),
        "mart_channel_unit_economics": unit_economics(cust, campaigns, "channel", 90),
        "mart_campaign_unit_economics": unit_economics(cust, campaigns, "campaign_id", 90),
        "mart_campaign_unit_economics_180": unit_economics(cust, campaigns, "campaign_id", 180),
        "mart_channel_segment": channel_segment_matrix(cust, campaigns, 90),
        "mart_conversion_trap": conversion_trap(cust, campaigns, 90),
    }
    if not write:
        return campaigns, cust, orders, marts

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in marts.items():
        df.to_csv(DATA_PROCESSED / f"{name}.csv", index=False)
    cust.to_csv(DATA_PROCESSED / "customers_enriched.csv", index=False)

    # ---- Power BI star schema ----
    date_dim = pd.DataFrame({"date": pd.date_range(campaigns["date"].min(), END)})
    date_dim["year"] = date_dim["date"].dt.year
    date_dim["month_num"] = date_dim["date"].dt.month
    date_dim["month"] = date_dim["date"].dt.strftime("%Y-%m")
    date_dim["quarter"] = "Q" + date_dim["date"].dt.quarter.astype(str)
    date_dim["weekday"] = date_dim["date"].dt.day_name()
    fact_cols = ["date", "campaign_id", "spend", "impressions", "clicks", "leads",
                 "conversions", "new_customers", "revenue", "cogs"]
    cust_dim_cols = ["customer_id", "signup_date", "acquisition_campaign_id", "age_group",
                     "category_pref", "segment", "city_tier", "device", "ltv_90", "ltv_180",
                     "revenue_90", "orders_90", "repeat_90", "first_order_revenue"]
    pbi = {"dim_date": date_dim, "dim_campaign": dim,
           "dim_customer": cust[cust_dim_cols],
           "fact_campaign_daily": campaigns[fact_cols],
           "fact_orders": orders,
           "mart_channel_segment": marts["mart_channel_segment"],
           "mart_conversion_trap": marts["mart_conversion_trap"]}
    for name, df in pbi.items():
        df.to_csv(POWERBI_DIR / f"{name}.csv", index=False)

    # ---- SQLite for the SQL scripts ----
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        dt = lambda df, cols: df.assign(**{c: df[c].dt.strftime("%Y-%m-%d") for c in cols})
        dt(campaigns, ["date"]).to_sql("campaigns_daily", con, index=False)
        dim.to_sql("dim_campaign", con, index=False)
        dt(cust, ["signup_date"]).to_sql("customers", con, index=False)
        dt(orders, ["order_date"]).assign(is_returned=orders["is_returned"].astype(int)).to_sql(
            "orders", con, index=False)
    print(f"marts -> {DATA_PROCESSED} | Power BI CSVs -> {POWERBI_DIR} | SQLite -> {DB_PATH}")
    return campaigns, cust, orders, marts


if __name__ == "__main__":
    build_all()
