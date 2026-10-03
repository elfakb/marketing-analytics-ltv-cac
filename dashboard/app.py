"""Marketing Performance Dashboard (Streamlit).  Run: streamlit run dashboard/app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import marts, metrics
from src.config import DATA_RAW

st.set_page_config(page_title="Marketing Performance", page_icon="📣", layout="wide")

COLORS = {"Google": "#4285F4", "Meta": "#7B61FF", "TikTok": "#FF3B6B", "Email": "#F4A300", "Organic": "#2BB673"}
LTV_DAYS = 90
TRY = lambda v: "–" if pd.isna(v) else f"₺{v:,.0f}"


def clean(fig, h=360):
    fig.update_layout(template="plotly_white", height=h, margin=dict(t=40, b=10, l=10, r=10),
                      legend=dict(orientation="h", y=-0.2, title=None))
    return fig


@st.cache_data(show_spinner="Loading data…")
def load():
    if not (DATA_RAW / "campaigns_daily.csv").exists():
        from src import generate_data
        generate_data.main()
    campaigns, customers, orders = marts.load_raw()
    return campaigns, marts.enrich_customers(customers, orders, campaigns)


campaigns, cust = load()

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filters")
lo, hi = campaigns["date"].min().date(), campaigns["date"].max().date()
period = st.sidebar.date_input("Date range", (lo, hi), min_value=lo, max_value=hi)
channels = st.sidebar.multiselect("Channels", list(COLORS), default=list(COLORS))
st.sidebar.caption("Synthetic data · TRY · LTV = gross profit in the first 90 days after first order.")
if len(period) != 2 or not channels:
    st.stop()

d0, d1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
df = campaigns[campaigns["date"].between(d0, d1) & campaigns["channel"].isin(channels)]
camp_all = campaigns[campaigns["channel"].isin(channels)]

# ---------------------------------------------------------------- header + KPIs
st.title("Marketing Performance")
t = metrics.totals(df)
cols = st.columns(6)
for c, (label, value) in zip(cols, [
        ("Spend", TRY(t["spend"])), ("Revenue", TRY(t["revenue"])), ("Profit", TRY(t["profit"])),
        ("ROAS (paid)", f"{t['roas']:.2f}x" if pd.notna(t["roas"]) else "–"),
        ("CAC (paid)", TRY(t["cac"])), ("Conversions", f"{t['conversions']:,.0f}")]):
    c.metric(label, value, border=True)

overview, channel_tab, campaign_tab, segment_tab = st.tabs(["Overview", "Channels", "Campaigns", "Segments"])

# ---------------------------------------------------------------- overview
with overview:
    m = metrics.aggregate(df.assign(month=df["date"].dt.to_period("M").dt.to_timestamp()), "month")
    fig = go.Figure()
    fig.add_bar(x=m["month"], y=m["spend"], name="Spend", marker_color="#E4572E")
    fig.add_bar(x=m["month"], y=m["revenue"], name="Revenue", marker_color="#9DB4C0")
    fig.add_scatter(x=m["month"], y=m["profit"], name="Profit", mode="lines+markers",
                    line=dict(color="#2A6F97", width=3))
    fig.update_layout(barmode="group", title="Monthly spend, revenue and profit (₺)")
    st.plotly_chart(clean(fig, 380), width="stretch")

    ch = metrics.aggregate(df, "channel")
    cp = metrics.aggregate(df, ["channel", "campaign_name"])
    tr = marts.conversion_trap(cust, camp_all, LTV_DAYS)
    notes = [f"Most profitable channel: **{ch.loc[ch['profit'].idxmax(), 'channel']}**."]
    for r in ch[ch["profit"] < 0].itertuples():
        notes.append(f"**{r.channel}** loses money ({TRY(r.profit)}) even though its ROAS is {r.roas:.1f}x.")
    for r in cp[cp["profit"] < 0].sort_values("profit").itertuples():
        notes.append(f"**{r.channel} / {r.campaign_name}** is unprofitable ({TRY(r.profit)}).")
    for r in tr[tr["quadrant"] == "Conversion trap"].itertuples():
        notes.append(f"**{r.channel} / {r.campaign_name}** converts well ({r.cvr:.1%}) but customers are worth "
                     f"only {TRY(r.ltv)} in 90 days.")
    st.subheader("Key takeaways")
    for n in notes:
        st.markdown(f"- {n}")

# ---------------------------------------------------------------- channels
with channel_tab:
    ue = marts.unit_economics(cust, camp_all, "channel", LTV_DAYS)[["channel", "ltv", "ltv_cac"]]
    ch = ch.merge(ue, on="channel", how="left")
    a, b = st.columns(2)
    f = px.bar(ch.sort_values("profit"), x="profit", y="channel", orientation="h", color="channel",
               color_discrete_map=COLORS, title="Profit (₺)")
    a.plotly_chart(clean(f, 300).update_layout(showlegend=False), width="stretch")
    paid = ch[ch["spend"] > 0].sort_values("roas")
    f = px.bar(paid, x="roas", y="channel", orientation="h", color="channel", color_discrete_map=COLORS,
               title="ROAS (paid channels)", text=paid["roas"].round(1))
    b.plotly_chart(clean(f, 300).update_layout(showlegend=False), width="stretch")
    st.dataframe(
        ch[["channel", "spend", "revenue", "profit", "cvr", "cac", "roas", "ltv", "ltv_cac"]]
        .sort_values("profit", ascending=False),
        hide_index=True, width="stretch",
        column_config={"channel": "Channel",
                       "spend": st.column_config.NumberColumn("Spend", format="₺%.0f"),
                       "revenue": st.column_config.NumberColumn("Revenue", format="₺%.0f"),
                       "profit": st.column_config.NumberColumn("Profit", format="₺%.0f"),
                       "cvr": st.column_config.NumberColumn("Conv. rate", format="percent"),
                       "cac": st.column_config.NumberColumn("CAC", format="₺%.0f"),
                       "roas": st.column_config.NumberColumn("ROAS", format="%.2fx"),
                       "ltv": st.column_config.NumberColumn("LTV 90d", format="₺%.0f"),
                       "ltv_cac": st.column_config.NumberColumn("LTV:CAC", format="%.2f")})
    st.caption("ROAS and CAC are empty for Organic (no media spend).")

# ---------------------------------------------------------------- campaigns
with campaign_tab:
    cp["label"] = cp["channel"] + " · " + cp["campaign_name"]
    d = cp.sort_values("revenue")
    f = go.Figure()
    f.add_bar(y=d["label"], x=d["revenue"], orientation="h", name="Revenue", marker_color="#9DB4C0")
    f.add_bar(y=d["label"], x=d["profit"], orientation="h", name="Profit", marker_color="#2A6F97")
    f.update_layout(barmode="group", title="Revenue vs profit by campaign (₺)")
    st.plotly_chart(clean(f, 480), width="stretch")

    if len(tr):
        tr["label"] = tr["channel"] + " · " + tr["campaign_name"]
        q = {"Conversion trap": "#C0392B", "Star": "#1E8449", "Hidden gem": "#2E86C1", "Underperformer": "#95A5A6"}
        f = px.scatter(tr, x="cvr", y="ltv", color="quadrant", color_discrete_map=q, text="campaign_name",
                       size=np.clip(tr["spend"], 20000, None), hover_name="label",
                       title="Conversion rate vs 90-day LTV")
        f.add_vline(x=tr.attrs["cvr_threshold"], line_dash="dash", line_color="#aaa")
        f.add_hline(y=tr.attrs["ltv_threshold"], line_dash="dash", line_color="#aaa")
        f.update_traces(textposition="top center")
        f.update_layout(xaxis_tickformat=".0%", xaxis_title="Conversion rate", yaxis_title="LTV 90d per customer (₺)")
        st.plotly_chart(clean(f, 440), width="stretch")
        st.caption("Dashed lines = averages of acquisition campaigns. High conversion + low LTV = conversion trap.")

# ---------------------------------------------------------------- segments
with segment_tab:
    cs = marts.channel_segment_matrix(cust[cust["signup_date"].between(d0, d1)], camp_all, LTV_DAYS)
    cs = cs[cs["acquisition_channel"].isin(channels)]
    if cs.empty:
        st.info("No customers for this selection.")
    else:
        piv = cs.pivot_table(index="segment", columns="acquisition_channel", values="net_ltv")
        piv = piv[[c for c in COLORS if c in piv.columns]]
        piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]
        f = px.imshow(piv, aspect="auto", text_auto=".0f", color_continuous_scale="RdYlGn",
                      color_continuous_midpoint=0, title="Net 90-day LTV per customer (LTV − CAC, ₺)")
        f.update_layout(xaxis_title=None, yaxis_title=None, coloraxis_showscale=False)
        st.plotly_chart(clean(f, 440), width="stretch")
        st.caption("Green = profitable, red = loses money. Channel CAC is applied to all segments of the channel.")