"""
Retail Analytics — Live Dashboard v2 (Phase 4b)
=================================================
Reads the scoreboard JSON files written by live_scoreboard_writer.ipynb (v2)
and displays them, auto-refreshing every 5 seconds.

New in this version, on top of the original dashboard:
  - Revenue trend line chart (15-minute windows) — fixes the "only ever climbs"
    problem with a single lifetime total, by showing the actual shape of
    activity over time.
  - Order status funnel (pending -> processing -> completed)
  - Revenue by state (geographic breakdown)
  - Average order fulfillment time
  - Recent orders feed (last 10, live)

SETUP
-----
1. Put this file in the same folder as live_scoreboard_writer.ipynb
   (your spark_projects folder).
2. pip install streamlit pandas plotly
3. Have live_scoreboard_writer.ipynb (v2) running.
4. Run from a terminal: streamlit run dashboard_app.py
"""

import json
from pathlib import Path

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Retail Analytics — Live Dashboard", layout="wide")

SCOREBOARD_DIR = Path("dashboard_scoreboard")


def load_json(filename):
    """Read a scoreboard file. Returns None if it doesn't exist yet or is mid-write."""
    path = SCOREBOARD_DIR / filename
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Spark may be overwriting this file at the exact instant we read it —
        # just skip this refresh cycle, the next one will pick up the completed write.
        return None


@st.fragment(run_every="5s")
def live_dashboard():
    overall = load_json("overall_stats.json")
    products = load_json("product_revenue.json")
    states = load_json("state_revenue.json")
    fulfillment = load_json("fulfillment_stats.json")
    trend = load_json("revenue_trend.json")
    recent = load_json("recent_orders.json")

    if overall is None or products is None:
        st.info(
            "Waiting for data — make sure `live_scoreboard_writer.ipynb` is running "
            "and has processed at least one batch."
        )
        return

    st.caption(f"Last updated: {overall.get('last_updated', 'unknown')}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Orders", f"{overall['total_orders']:,}")
    col2.metric("Total Revenue", f"₹{overall['total_revenue']:,.2f}")
    col3.metric("Avg Order Value", f"₹{overall['avg_order_value']:,.2f}")
    if fulfillment and fulfillment.get("avg_fulfillment_minutes") is not None:
        col4.metric("Avg Fulfillment Time", f"{fulfillment['avg_fulfillment_minutes']:.1f} min")
    else:
        col4.metric("Avg Fulfillment Time", "—")

    st.divider()

    st.subheader("Revenue Trend (hourly)")
    if trend:
        trend_df = pd.DataFrame(trend)
        trend_df["window_start"] = pd.to_datetime(trend_df["window_start"])
        chart = alt.Chart(trend_df).mark_line(point=True).encode(
            x=alt.X("window_start:T", title="Time", axis=alt.Axis(format="%b %d, %I:%M %p")),
            y=alt.Y("revenue:Q", title="Revenue (₹)"),
            tooltip=[
                alt.Tooltip("window_start:T", title="Hour", format="%b %d, %Y %I:%M %p"),
                alt.Tooltip("revenue:Q", title="Revenue", format=",.2f"),
            ],
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.write("Not enough data yet for a trend — need at least one completed time window.")

    st.divider()

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Revenue by Product")
        if products:
            df = pd.DataFrame(products).set_index("product_name")
            st.bar_chart(df["revenue"])
        else:
            st.write("No product data yet.")

    with right:
        st.subheader("Order Status Funnel")
        by_status = overall.get("by_status", [])
        if by_status:
            status_order = {"pending": 0, "processing": 1, "on-hold": 2, "completed": 3}
            status_df = pd.DataFrame(by_status)
            status_df["_order"] = status_df["status"].map(status_order).fillna(99)
            status_df = status_df.sort_values("_order")
            fig = go.Figure(go.Funnel(
                y=status_df["status"],
                x=status_df["order_count"],
                textinfo="value+percent initial",
            ))
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No order data yet.")

    st.divider()

    left2, right2 = st.columns(2)

    with left2:
        st.subheader("Revenue by State")
        if states:
            state_df = pd.DataFrame(states).set_index("state")
            st.bar_chart(state_df["revenue"])
        else:
            st.write("No geographic data yet.")

    with right2:
        st.subheader("Recent Orders")
        if recent:
            recent_df = pd.DataFrame(recent).iloc[::-1]  # most recent first
            st.dataframe(recent_df, use_container_width=True, hide_index=True)
        else:
            st.write("No orders yet.")

    st.divider()

    st.subheader("🤖 AI Insights")
    ai_summary = load_json("ai_summary.json")
    if ai_summary and ai_summary.get("summary"):
        st.info(ai_summary["summary"])
        st.caption(f"Generated: {ai_summary.get('last_updated', 'unknown')}")
    else:
        st.write("No AI summary yet — make sure `ai_summary_writer.ipynb` is running.")

    st.divider()
    st.subheader("All Products")
    if products:
        st.dataframe(pd.DataFrame(products), use_container_width=True, hide_index=True)


st.title("Retail Analytics — Live Dashboard")
st.caption("Auto-refreshes every 5 seconds from the Spark scoreboard.")

live_dashboard()