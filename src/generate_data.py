"""Synthetic e-commerce marketing data generator (fashion + cosmetics, Turkey).

The data is SYNTHETIC. It is seeded (reproducible) and every behavioural
assumption is encoded in the CAMPAIGNS table and `interaction()` below, so the
logic is transparent and can be criticised / changed.

Outputs (data/raw):
  campaigns_daily.csv : date x campaign performance (spend, impressions, clicks,
                        leads, conversions, new_customers, revenue, cogs)
  customers.csv       : one row per newly acquired customer + segment attributes
  orders.csv          : first + repeat orders, attributed (last-click) to a campaign

Run:  python -m src.generate_data
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import DATA_RAW, END_DATE, SEED, START_DATE

AGE_GROUPS = ["18-24", "25-34", "35-44", "45+"]
CATEGORIES = ["Fashion", "Cosmetics"]

# ----- global economics (TRY) ------------------------------------------------
BASE_AOV = {"Fashion": 900.0, "Cosmetics": 450.0}      # list price per order
COGS_RATIO = {"Fashion": 0.50, "Cosmetics": 0.42}      # COGS / list price
AGE_AOV = dict(zip(AGE_GROUPS, [0.80, 1.00, 1.15, 1.05]))
AGE_REPEAT = dict(zip(AGE_GROUPS, [0.90, 1.15, 1.10, 0.80]))
CAT_REPEAT = {"Fashion": 1.0, "Cosmetics": 1.30}
METRO_AOV = 1.10
BASE_REPEAT_180D = 0.90   # expected repeat orders / 180 days for an "average" customer


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    channel: str
    campaign_name: str
    objective: str          # Acquisition | Retargeting | Retention | Organic
    target_new: int         # expected NEW customers per year
    cvr: float              # conversions / clicks
    ctr: float              # clicks / impressions
    cpa: float              # TRY per attributed conversion (0 = unpaid)
    lead_rate: float        # leads / clicks
    discount: float         # average discount on orders attributed to it
    return_rate: float      # share of orders returned
    repeat_factor: float    # multiplier on customers' repeat-purchase rate
    age_mix: tuple          # P(18-24, 25-34, 35-44, 45+)
    p_cosmetics: float
    p_metro: float
    p_mobile: float


CAMPAIGNS = [
    # --- Google ---------------------------------------------------------------
    Campaign("GG01", "Google", "Search - Brand", "Acquisition", 900, 0.12, 0.080, 40, 0.25, 0.03, 0.08, 1.10, (.10, .35, .30, .25), .40, .60, .55),
    Campaign("GG02", "Google", "Search - Generic", "Acquisition", 1200, 0.040, 0.035, 330, 0.20, 0.06, 0.09, 0.90, (.12, .33, .30, .25), .35, .55, .50),
    Campaign("GG03", "Google", "Shopping", "Acquisition", 1100, 0.055, 0.012, 150, 0.15, 0.10, 0.09, 1.00, (.15, .35, .30, .20), .30, .55, .60),
    # --- Meta -----------------------------------------------------------------
    Campaign("MT01", "Meta", "Prospecting", "Acquisition", 1000, 0.030, 0.009, 230, 0.12, 0.12, 0.12, 0.90, (.25, .40, .25, .10), .55, .55, .85),
    Campaign("MT02", "Meta", "Lookalike", "Acquisition", 900, 0.040, 0.011, 190, 0.15, 0.10, 0.12, 1.00, (.20, .40, .27, .13), .50, .60, .85),
    Campaign("MT03", "Meta", "Retargeting", "Retargeting", 500, 0.050, 0.015, 60, 0.10, 0.15, 0.12, 1.10, (.20, .38, .27, .15), .50, .60, .85),
    # --- TikTok ---------------------------------------------------------------
    Campaign("TT01", "TikTok", "Spark Ads", "Acquisition", 1200, 0.060, 0.022, 110, 0.09, 0.25, 0.20, 0.35, (.62, .28, .07, .03), .65, .50, .95),
    Campaign("TT02", "TikTok", "Influencer Collab", "Acquisition", 700, 0.055, 0.015, 150, 0.10, 0.22, 0.17, 0.45, (.55, .32, .10, .03), .70, .55, .95),
    # --- Email ----------------------------------------------------------------
    Campaign("EM01", "Email", "Welcome Series", "Acquisition", 400, 0.100, 0.030, 40, 0.45, 0.12, 0.07, 1.60, (.10, .32, .38, .20), .50, .60, .70),
    Campaign("EM02", "Email", "Newsletter", "Retention", 200, 0.040, 0.025, 30, 0.30, 0.10, 0.07, 1.50, (.08, .30, .40, .22), .50, .60, .70),
    Campaign("EM03", "Email", "Winback", "Retention", 0, 0.025, 0.020, 60, 0.05, 0.18, 0.07, 1.00, (.15, .35, .30, .20), .50, .60, .70),
    # --- Organic (no media spend) --------------------------------------------
    Campaign("OR01", "Organic", "SEO", "Organic", 1300, 0.035, 0.030, 0, 0.18, 0.04, 0.07, 1.30, (.15, .35, .30, .20), .45, .55, .65),
    Campaign("OR02", "Organic", "Social Organic", "Organic", 500, 0.025, 0.010, 0, 0.12, 0.06, 0.10, 1.00, (.35, .38, .18, .09), .60, .60, .90),
]
CAMP = {c.campaign_id: c for c in CAMPAIGNS}

# Attribution of REPEAT orders (last click). Winback only when customer is >=60d old.
REPEAT_ATTRIBUTION = {"EM02": .15, "EM03": .08, "MT03": .22, "GG01": .20, "OR01": .22, "OR02": .13}


def seasonality(dates: pd.DatetimeIndex) -> np.ndarray:
    """Daily demand weight: monthly pattern x weekday x Black Friday / 11.11 spikes."""
    month_w = {1: .85, 2: .90, 3: .95, 4: 1.0, 5: 1.05, 6: .90,
               7: .85, 8: .85, 9: 1.0, 10: 1.05, 11: 1.45, 12: 1.15}
    dow_w = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.05, 5: 1.10, 6: 1.10}
    w = np.array([month_w[d.month] * dow_w[d.dayofweek] for d in dates])
    w = w * np.where((dates >= "2025-11-24") & (dates <= "2025-12-01"), 1.4, 1.0)
    w = w * np.where(dates == "2025-11-11", 1.5, 1.0)
    return w


def interaction(channel, name, age, cat):
    """Channel x segment effects -> (aov multiplier, repeat multiplier), vectorised."""
    n = len(age)
    aov, rep = np.ones(n), np.ones(n)
    ch, nm = np.asarray(channel), np.asarray(name)
    # TikTok: works for young cosmetics buyers, poor for 35+
    rep[(ch == "TikTok") & (age == "18-24") & (cat == "Cosmetics")] *= 1.9
    rep[(ch == "TikTok") & np.isin(age, ["35-44", "45+"])] *= 0.6
    # Meta: strong with 25-34 cosmetics
    m = (ch == "Meta") & (age == "25-34") & (cat == "Cosmetics")
    rep[m] *= 1.25
    aov[m] *= 1.10
    # Email: best with 35-44
    rep[(ch == "Email") & (age == "35-44")] *= 1.25
    # Google Shopping: bigger baskets for 35+ fashion buyers
    aov[(ch == "Google") & (nm == "Shopping") & (cat == "Fashion") & np.isin(age, ["35-44", "45+"])] *= 1.20
    # Organic: older customers repeat less
    rep[(ch == "Organic") & (age == "45+")] *= 0.85
    return aov, rep


def generate(seed: int = SEED):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(START_DATE, END_DATE)
    end = pd.Timestamp(END_DATE)
    w = seasonality(dates)

    # ---------------- 1) customers -------------------------------------------
    parts = []
    for c in CAMPAIGNS:
        if c.target_new == 0:
            continue
        counts = rng.poisson(c.target_new * w / w.sum())
        n = counts.sum()
        df = pd.DataFrame({"signup_date": np.repeat(dates.values, counts),
                           "acquisition_campaign_id": c.campaign_id})
        df["age_group"] = rng.choice(AGE_GROUPS, n, p=c.age_mix)
        df["category_pref"] = rng.choice(CATEGORIES, n, p=[1 - c.p_cosmetics, c.p_cosmetics])
        df["city_tier"] = rng.choice(["Metro", "Other"], n, p=[c.p_metro, 1 - c.p_metro])
        df["device"] = rng.choice(["Mobile", "Desktop"], n, p=[c.p_mobile, 1 - c.p_mobile])
        parts.append(df)
    cust = pd.concat(parts, ignore_index=True).sort_values("signup_date", kind="stable").reset_index(drop=True)
    cust.insert(0, "customer_id", [f"C{i:05d}" for i in range(1, len(cust) + 1)])
    cust["segment"] = cust["age_group"] + " | " + cust["category_pref"]
    n_c = len(cust)

    camp_of = cust["acquisition_campaign_id"].map(CAMP)
    ch = camp_of.map(lambda c: c.channel).to_numpy()
    nm = camp_of.map(lambda c: c.campaign_name).to_numpy()
    age = cust["age_group"].to_numpy()
    cat = cust["category_pref"].to_numpy()
    aov_int, rep_int = interaction(ch, nm, age, cat)

    aov_mult = (cust["age_group"].map(AGE_AOV).to_numpy()
                * np.where(cust["city_tier"] == "Metro", METRO_AOV, 1.0) * aov_int)
    base_aov = cust["category_pref"].map(BASE_AOV).to_numpy()
    frailty = rng.gamma(2.0, 0.5, n_c)                       # customer heterogeneity, mean 1
    mu180 = (BASE_REPEAT_180D * camp_of.map(lambda c: c.repeat_factor).to_numpy()
             * cust["age_group"].map(AGE_REPEAT).to_numpy()
             * cust["category_pref"].map(CAT_REPEAT).to_numpy() * rep_int * frailty)

    # ---------------- 2) orders ----------------------------------------------
    horizon = (end - cust["signup_date"]).dt.days.to_numpy()
    n_rep = np.where(horizon >= 3, rng.poisson(mu180 / 180.0 * horizon), 0)
    idx_rep = np.repeat(np.arange(n_c), n_rep)
    off = rng.integers(2, horizon[idx_rep] + 1)
    ids, p = list(REPEAT_ATTRIBUTION), np.array(list(REPEAT_ATTRIBUTION.values()))
    attr = rng.choice(ids, len(idx_rep), p=p / p.sum())
    attr = np.where((attr == "EM03") & (off < 60), "EM02", attr)

    o_first = pd.DataFrame({"cust_idx": np.arange(n_c),
                            "order_date": cust["signup_date"].to_numpy(),
                            "campaign_id": cust["acquisition_campaign_id"].to_numpy(),
                            "order_type": "first"})
    o_rep = pd.DataFrame({"cust_idx": idx_rep,
                          "order_date": cust["signup_date"].to_numpy()[idx_rep] + pd.to_timedelta(off, "D").to_numpy(),
                          "campaign_id": attr, "order_type": "repeat"})
    orders = pd.concat([o_first, o_rep], ignore_index=True)
    ci = orders["cust_idx"].to_numpy()
    sigma = 0.30
    list_price = base_aov[ci] * aov_mult[ci] * rng.lognormal(-sigma ** 2 / 2, sigma, len(orders))
    disc = orders["campaign_id"].map(lambda k: CAMP[k].discount).to_numpy()
    ret_p = orders["campaign_id"].map(lambda k: CAMP[k].return_rate).to_numpy()
    returned = rng.random(len(orders)) < ret_p
    cogs_ratio = pd.Series(cat[ci]).map(COGS_RATIO).to_numpy()
    orders["is_returned"] = returned
    orders["revenue"] = np.where(returned, 0.0, list_price * (1 - disc)).round(2)
    orders["cogs"] = np.where(returned, 0.0, list_price * cogs_ratio).round(2)
    orders["customer_id"] = cust["customer_id"].to_numpy()[ci]
    orders = orders.sort_values(["order_date", "customer_id"], kind="stable").reset_index(drop=True)
    orders.insert(0, "order_id", [f"O{i:06d}" for i in range(1, len(orders) + 1)])
    orders = orders[["order_id", "customer_id", "order_date", "campaign_id", "order_type",
                     "is_returned", "revenue", "cogs"]]

    # ---------------- 3) campaign-daily table --------------------------------
    cal = pd.MultiIndex.from_product([[c.campaign_id for c in CAMPAIGNS], dates],
                                     names=["campaign_id", "date"]).to_frame(index=False)
    new_c = (cust.groupby(["acquisition_campaign_id", "signup_date"]).size()
             .rename("new_customers").reset_index()
             .rename(columns={"acquisition_campaign_id": "campaign_id", "signup_date": "date"}))
    agg_o = (orders.groupby(["campaign_id", "order_date"])
             .agg(conversions=("order_id", "count"), revenue=("revenue", "sum"), cogs=("cogs", "sum"))
             .reset_index().rename(columns={"order_date": "date"}))
    d = cal.merge(new_c, how="left").merge(agg_o, how="left").fillna(0)
    d["new_customers"] = d["new_customers"].astype(int)
    d["conversions"] = d["conversions"].astype(int)

    spec = d["campaign_id"].map(CAMP)
    cvr = spec.map(lambda c: c.cvr).to_numpy()
    ctr = spec.map(lambda c: c.ctr).to_numpy()
    cpa = spec.map(lambda c: c.cpa).to_numpy()
    lead_rate = spec.map(lambda c: c.lead_rate).to_numpy()
    n = len(d)
    clicks = np.ceil((d["conversions"].to_numpy() + rng.uniform(0, 0.8, n)) / cvr * rng.lognormal(0, 0.12, n))
    clicks = np.maximum(clicks, d["conversions"].to_numpy())
    d["clicks"] = clicks.astype(int)
    d["impressions"] = np.maximum(np.round(clicks / ctr * rng.lognormal(0, 0.10, n)), clicks).astype(int)
    d["spend"] = np.round(clicks * cpa * cvr * rng.lognormal(0, 0.12, n), 2)   # = clicks x CPC
    d["leads"] = np.maximum(np.round(clicks * lead_rate * rng.lognormal(0, 0.10, n)),
                            d["new_customers"].to_numpy()).astype(int)
    meta = pd.DataFrame([{"campaign_id": c.campaign_id, "channel": c.channel,
                          "campaign_name": c.campaign_name, "objective": c.objective} for c in CAMPAIGNS])
    d = d.merge(meta, on="campaign_id")
    d["revenue"] = d["revenue"].round(2)
    d["cogs"] = d["cogs"].round(2)
    d = d[["date", "campaign_id", "channel", "campaign_name", "objective", "spend", "impressions",
           "clicks", "leads", "conversions", "new_customers", "revenue", "cogs"]]
    d = d.sort_values(["date", "campaign_id"]).reset_index(drop=True)

    cust = cust[["customer_id", "signup_date", "acquisition_campaign_id", "age_group",
                 "category_pref", "segment", "city_tier", "device"]]
    return d, cust, orders


def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    campaigns, customers, orders = generate()
    campaigns.to_csv(DATA_RAW / "campaigns_daily.csv", index=False)
    customers.to_csv(DATA_RAW / "customers.csv", index=False)
    orders.to_csv(DATA_RAW / "orders.csv", index=False)
    print(f"campaigns_daily: {len(campaigns):,} rows | customers: {len(customers):,} | orders: {len(orders):,}")


if __name__ == "__main__":
    main()
