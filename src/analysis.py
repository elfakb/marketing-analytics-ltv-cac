"""Generate figures (reports/figures) and an auto-written findings report.

Run:  python -m src.analysis
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import marts, metrics
from src.config import FIGURES, REPORTS

PALETTE = {"Google": "#4285F4", "Meta": "#7B61FF", "TikTok": "#FF3B6B",
           "Email": "#F4A300", "Organic": "#2BB673"}
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "font.size": 9})
fmt_k = lambda v: f"{v/1000:,.0f}K"


def fig_channel(ch):
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    d = ch.sort_values("profit", ascending=False)
    ax[0].bar(d["channel"], d["profit"], color=[PALETTE[c] for c in d["channel"]])
    ax[0].axhline(0, color="k", lw=.8)
    ax[0].set_title("Profit by channel (revenue - COGS - spend, TRY)")
    ax[0].yaxis.set_major_formatter(lambda v, _: fmt_k(v))
    paid = ch[ch["spend"] > 0].sort_values("roas", ascending=False)
    ax[1].bar(paid["channel"], paid["roas"], color=[PALETTE[c] for c in paid["channel"]])
    for i, v in enumerate(paid["roas"]):
        ax[1].text(i, v, f"{v:.1f}x", ha="center", va="bottom")
    ax[1].set_title("ROAS by paid channel (Organic excluded: no spend)")
    fig.tight_layout(); fig.savefig(FIGURES / "01_channel_profit_roas.png"); plt.close(fig)


def fig_rank(camp):
    d = camp.sort_values("revenue", ascending=True)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(y + .2, d["revenue"], .4, label="Revenue", color="#9DB4C0")
    ax.barh(y - .2, d["profit"], .4, label="Profit", color="#2A6F97")
    ax.set_yticks(y, [f"{c} - {n}" for c, n in zip(d["channel"], d["campaign_name"])])
    ax.axvline(0, color="k", lw=.8)
    ax.xaxis.set_major_formatter(lambda v, _: fmt_k(v))
    ax.set_title("Revenue is not profit: campaigns ranked by revenue (TRY)")
    ax.legend(loc="lower right"); fig.tight_layout()
    fig.savefig(FIGURES / "02_campaign_revenue_vs_profit.png"); plt.close(fig)


def fig_heatmap(cs):
    p = cs.pivot_table(index="segment", columns="acquisition_channel", values="net_ltv")
    p = p[[c for c in ["Organic", "Email", "Google", "Meta", "TikTok"] if c in p.columns]]
    p = p.loc[p.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    vmax = np.nanmax(np.abs(p.values))
    im = ax.imshow(p.values, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(p.shape[1]), p.columns); ax.set_yticks(range(p.shape[0]), p.index)
    ax.grid(False)
    for i in range(p.shape[0]):
        for j in range(p.shape[1]):
            v = p.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:,.0f}", ha="center", va="center", fontsize=8)
    ax.set_title("Net 90-day LTV per customer (LTV - channel CAC, TRY)")
    fig.colorbar(im, ax=ax, shrink=.8); fig.tight_layout()
    fig.savefig(FIGURES / "03_channel_segment_heatmap.png"); plt.close(fig)


def fig_trap(tr):
    fig, ax = plt.subplots(figsize=(8, 5.2))
    cvr_t, ltv_t = tr.attrs["cvr_threshold"], tr.attrs["ltv_threshold"]
    ax.scatter(tr["cvr"] * 100, tr["ltv"], s=np.clip(tr["spend"] / 1500, 60, 600),
               c=[PALETTE[c] for c in tr["channel"]], alpha=.8, edgecolor="k")
    for _, r in tr.iterrows():
        off = {"Social Organic": (-4, -14), "Prospecting": (8, -14)}.get(r["campaign_name"], (6, 5))
        ax.annotate(r["campaign_name"], (r["cvr"] * 100, r["ltv"]), xytext=off,
                    textcoords="offset points", fontsize=8)
    ax.axvline(cvr_t * 100, ls="--", color="grey"); ax.axhline(ltv_t, ls="--", color="grey")
    xl, yl = ax.get_xlim(), ax.get_ylim()
    ax.text(xl[1], yl[0], "CONVERSION TRAP ", ha="right", va="bottom", color="#c0392b", weight="bold")
    ax.text(xl[1], yl[1], "STARS ", ha="right", va="top", color="#1e8449", weight="bold")
    ax.set_xlabel("Conversion rate (conversions / clicks, %)"); ax.set_ylabel("90-day LTV per customer (gross profit, TRY)")
    ax.set_title("High conversion != high value  (bubble size = spend)")
    fig.tight_layout(); fig.savefig(FIGURES / "04_conversion_vs_ltv.png"); plt.close(fig)


def fig_monthly(mm):
    m = mm.groupby("month")[["spend", "revenue", "profit"]].sum()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(m.index.strftime("%b"), m["revenue"], marker="o", label="Revenue", color="#2A6F97")
    ax.plot(m.index.strftime("%b"), m["profit"], marker="o", label="Profit", color="#2BB673")
    ax.plot(m.index.strftime("%b"), m["spend"], marker="o", label="Spend", color="#E4572E")
    ax.yaxis.set_major_formatter(lambda v, _: fmt_k(v)); ax.legend()
    ax.set_title("Monthly trend (TRY) - Black Friday / 11.11 peak in November")
    fig.tight_layout(); fig.savefig(FIGURES / "05_monthly_trend.png"); plt.close(fig)


def money(v):
    return f"{v:,.0f} TRY"


def write_findings(campaigns, cust, marts_):
    ch, camp = marts_["mart_channel"], marts_["mart_campaign"]
    ue_ch, ue_c = marts_["mart_channel_unit_economics"], marts_["mart_campaign_unit_economics"]
    cs, tr = marts_["mart_channel_segment"], marts_["mart_conversion_trap"]
    tot = metrics.totals(campaigns)
    L = ["# Findings (auto-generated by `python -m src.analysis`)", "",
         "> Data is synthetic; numbers below are produced by the pipeline with seed 42.", "",
         "## 1. Portfolio", "",
         f"- Spend **{money(tot['spend'])}**, revenue **{money(tot['revenue'])}**, profit **{money(tot['profit'])}**",
         f"- Paid ROAS **{tot['roas']:.2f}x** (blended incl. organic: {tot['blended_roas']:.2f}x); "
         f"paid CAC **{tot['cac']:.0f} TRY** (blended: {tot['blended_cac']:.0f} TRY)",
         f"- {int(tot['conversions']):,} conversions, {int(tot['new_customers']):,} new customers", "",
         "## 2. Channels", ""]
    for _, r in ch.sort_values("profit", ascending=False).iterrows():
        roas = f"{r['roas']:.2f}x" if pd.notna(r["roas"]) else "n/a (no spend)"
        L.append(f"- **{r['channel']}**: profit {money(r['profit'])}, ROAS {roas}, CVR {r['cvr']:.1%}, CAC {r['cac']:.0f} TRY")
    neg = ch[ch["profit"] < 0]["channel"].tolist()
    if neg:
        L += ["", f"**Loss-making channel(s): {', '.join(neg)}** - they look fine on ROAS/CPA but do not recover COGS + media."]
    L += ["", "## 3. Revenue vs profit (campaigns)", ""]
    c2 = camp.copy()
    c2["rev_rank"] = c2["revenue"].rank(ascending=False).astype(int)
    c2["profit_rank"] = c2["profit"].rank(ascending=False).astype(int)
    c2["shift"] = c2["rev_rank"] - c2["profit_rank"]
    L.append("Top 3 by revenue: " + ", ".join(f"{r.channel} / {r.campaign_name}" for r in c2.nsmallest(3, "rev_rank").itertuples()))
    L.append("")
    L.append("Top 3 by profit: " + ", ".join(f"{r.channel} / {r.campaign_name}" for r in c2.nsmallest(3, "profit_rank").itertuples()))
    L.append("")
    for r in c2.sort_values("shift").head(3).itertuples():
        L.append(f"- **{r.channel} / {r.campaign_name}** is #{r.rev_rank} by revenue but #{r.profit_rank} by profit "
                 f"(revenue {money(r.revenue)}, profit {money(r.profit)})")
    L += ["", "## 4. High conversion but low LTV", "",
          f"Thresholds (mean of eligible campaigns): CVR {tr.attrs['cvr_threshold']:.2%}, 90-day LTV {tr.attrs['ltv_threshold']:.0f} TRY", ""]
    for q in ["Conversion trap", "Star", "Hidden gem", "Underperformer"]:
        sub = tr[tr["quadrant"] == q]
        if len(sub):
            L.append(f"- **{q}**: " + "; ".join(
                f"{r.channel} / {r.campaign_name} (CVR {r.cvr:.1%}, LTV {r.ltv:.0f}, repeat {r.repeat_rate:.0%})" for r in sub.itertuples()))
    L += ["", "## 5. Channel x segment (net 90-day LTV per customer, cells with >= 50 customers)", ""]
    big = cs[cs["customers"] >= 50]
    for chn, g in big.groupby("acquisition_channel"):
        b, w = g.loc[g["net_ltv"].idxmax()], g.loc[g["net_ltv"].idxmin()]
        L.append(f"- **{chn}** best: {b['segment']} ({b['net_ltv']:.0f} TRY, n={int(b['customers'])}); "
                 f"worst: {w['segment']} ({w['net_ltv']:.0f} TRY, n={int(w['customers'])})")
    L += ["", "## 6. Unit economics by channel (matured 90-day cohort)", "",
          "| Channel | New customers | CAC | LTV 90d | LTV:CAC | Repeat rate | 1st-order return rate |", "|---|---|---|---|---|---|---|"]
    for r in ue_ch.sort_values("ltv", ascending=False).itertuples():
        lc = f"{r.ltv_cac:.2f}" if pd.notna(r.ltv_cac) else "n/a"
        L.append(f"| {r.channel} | {r.new_customers:,} | {r.cac:.0f} | {r.ltv:.0f} | {lc} | {r.repeat_rate:.0%} | {r.first_order_return_rate:.0%} |")
    ue180 = marts_["mart_campaign_unit_economics_180"]
    names = dict(zip(camp["campaign_id"], camp["campaign_name"]))
    base = marts.reallocation_scenario(ue180)
    L += ["", "## 7. Budget reallocation what-if (illustrative, 180-day matured cohort)", "",
          f"Cut {base['cut_pct']:.0%} of spend from paid acquisition campaigns with LTV:CAC < 2.0 "
          f"({', '.join(names[i] for i in base['cut_campaigns']) or 'none'}) and move it to the best scalable ones "
          f"({', '.join(names[i] for i in base['receiving_campaigns']) or 'none'}). "
          "Brand search and email welcome are excluded as receivers (volume is demand-capped, not budget-capped).", "",
          f"- Budget moved: {money(base['freed_budget'])}",
          f"- Profit given up by acquiring fewer customers in cut campaigns: {money(base['profit_lost_from_cuts'])}", "",
          "Net profit change depends on how efficiently the extra spend converts (diminishing returns):", "",
          "| Efficiency of extra spend | Net profit change (TRY) |", "|---|---|"]
    for eff in (0.4, 0.6, 0.8, 1.0):
        r = marts.reallocation_scenario(ue180, efficiency=eff)
        L.append(f"| {eff:.0%} of historical | {r['net_profit_change']:+,.0f} |")
    L += ["", "_Scenario, not a forecast: it covers the matured 180-day cohort only and assumes the stated efficiency._"]
    (REPORTS / "findings.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return base


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    campaigns, cust, orders, m = marts.build_all(write=True)
    fig_channel(m["mart_channel"]); fig_rank(m["mart_campaign"])
    fig_heatmap(m["mart_channel_segment"]); fig_trap(m["mart_conversion_trap"])
    fig_monthly(m["mart_monthly_channel"])
    write_findings(campaigns, cust, m)
    print(f"figures -> {FIGURES}\nreport  -> {REPORTS / 'findings.md'}")


if __name__ == "__main__":
    main()
