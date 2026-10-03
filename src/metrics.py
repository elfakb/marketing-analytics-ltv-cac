"""Marketing KPI formulas.

All ratios are NaN-safe: a zero denominator returns NaN instead of inf, so
unpaid channels (Organic, spend = 0) do not produce meaningless ROAS / CAC.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SUM_COLS = ["spend", "impressions", "clicks", "leads",
            "conversions", "new_customers", "revenue", "cogs"]


def sdiv(num, den):
    """Safe division -> NaN where denominator is 0 / NaN."""
    num = pd.Series(num) if not isinstance(num, pd.Series) else num
    den = pd.Series(den, index=num.index) if not isinstance(den, pd.Series) else den
    return num / den.replace(0, np.nan)


def add_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Add KPI columns to a frame that has the SUM_COLS base columns.

    CTR  = clicks / impressions
    CPC  = spend / clicks
    CPL  = spend / leads
    CPA  = spend / conversions          (cost per attributed order)
    CVR  = conversions / clicks         (click -> order)
    CAC  = spend / new_customers        (cost per *new* customer)
    ROAS = revenue / spend
    Gross profit = revenue - COGS ; Profit = revenue - COGS - spend
    """
    d = df.copy()
    d["ctr"] = sdiv(d["clicks"], d["impressions"])
    d["cpc"] = sdiv(d["spend"], d["clicks"])
    d["cpl"] = sdiv(d["spend"], d["leads"])
    d["cpa"] = sdiv(d["spend"], d["conversions"])
    d["cvr"] = sdiv(d["conversions"], d["clicks"])
    d["cac"] = sdiv(d["spend"], d["new_customers"])
    d["roas"] = sdiv(d["revenue"], d["spend"])
    d["gross_profit"] = d["revenue"] - d["cogs"]
    d["profit"] = d["gross_profit"] - d["spend"]
    d["profit_margin"] = sdiv(d["profit"], d["revenue"])
    return d


def aggregate(df: pd.DataFrame, by) -> pd.DataFrame:
    """Group a campaign-daily frame, sum base columns, add KPIs."""
    g = df.groupby(by, observed=True)[SUM_COLS].sum().reset_index()
    return add_kpis(g)


def totals(df: pd.DataFrame) -> dict:
    """Portfolio-level KPIs as a dict (for dashboard KPI cards).

    ROAS / CAC are reported on PAID campaigns only (objective != Organic),
    because organic revenue has no media spend and would inflate the ratios.
    Blended versions (all revenue / all customers) are returned as well.
    """
    s = df[SUM_COLS].sum()
    paid = df[df["objective"] != "Organic"][SUM_COLS].sum() if "objective" in df else s
    spend, rev = s["spend"], s["revenue"]
    return {
        "spend": spend,
        "revenue": rev,
        "profit": rev - s["cogs"] - spend,
        "roas": paid["revenue"] / spend if spend else np.nan,            # paid ROAS
        "blended_roas": rev / spend if spend else np.nan,
        "cac": spend / paid["new_customers"] if paid["new_customers"] else np.nan,   # paid CAC
        "blended_cac": spend / s["new_customers"] if s["new_customers"] else np.nan,
        "conversions": s["conversions"],
        "new_customers": s["new_customers"],
    }
