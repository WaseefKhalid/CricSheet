import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = px.colors.qualitative.Bold

def plot_runs_per_season(deliveries: pd.DataFrame, matches: pd.DataFrame):
    st.markdown("**Total Runs per Season**")
    if deliveries.empty or matches.empty:
        st.info("No data available.")
        return

    merged = deliveries.merge(matches[["match_id", "season"]], on="match_id", how="left")
    runs = merged.groupby("season").apply(
        lambda g: g["runs_off_bat"].sum() + g["extras"].sum()
    ).reset_index(name="total_runs")
    runs = runs.sort_values("season")

    fig = px.bar(runs, x="season", y="total_runs", color="season",
                 color_discrete_sequence=COLORS, text="total_runs")
    fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def plot_wickets_per_season(deliveries: pd.DataFrame, matches: pd.DataFrame):
    st.markdown("**Total Wickets per Season**")
    if deliveries.empty or matches.empty:
        st.info("No data available.")
        return

    merged = deliveries.merge(matches[["match_id", "season"]], on="match_id", how="left")
    wickets = (
        merged[merged["wicket_type"].notna() & (merged["wicket_type"] != "")]
        .groupby("season")
        .size()
        .reset_index(name="wickets")
        .sort_values("season")
    )

    fig = px.line(wickets, x="season", y="wickets", markers=True,
                  color_discrete_sequence=["#00b4d8"])
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font_color="white")
    st.plotly_chart(fig, use_container_width=True)


def plot_win_by_method(matches: pd.DataFrame):
    st.markdown("**Win Method Distribution**")
    if matches.empty:
        st.info("No data available.")
        return

    df = matches.copy()
    df["method"] = "Runs"
    df.loc[df["winner_wickets"].notna() & (df["winner_wickets"] > 0), "method"] = "Wickets"
    df.loc[df["winner"].isna() | (df["winner"] == ""), "method"] = "No Result"

    counts = df["method"].value_counts().reset_index()
    counts.columns = ["method", "count"]

    fig = px.pie(counts, names="method", values="count",
                 color_discrete_sequence=COLORS, hole=0.4)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font_color="white")
    st.plotly_chart(fig, use_container_width=True)


def plot_toss_impact(matches: pd.DataFrame):
    st.markdown("**Toss Decision Frequency**")
    if matches.empty or "toss_decision" not in matches.columns:
        st.info("No data available.")
        return

    counts = matches["toss_decision"].value_counts().reset_index()
    counts.columns = ["decision", "count"]

    fig = px.pie(counts, names="decision", values="count",
                 color_discrete_sequence=["#1DB954", "#00b4d8"], hole=0.4)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font_color="white")
    st.plotly_chart(fig, use_container_width=True)


def plot_top_batsmen(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data available.")
        return

    top = df.head(10)
    fig = px.bar(top, x=x, y=y, color=x, text=y,
                 color_discrete_sequence=COLORS, title=title)
    fig.update_layout(showlegend=False, xaxis_tickangle=-35,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font_color="white")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def plot_top_bowlers(df: pd.DataFrame):
    if df.empty:
        st.info("No data available.")
        return

    top = df.head(10)
    fig = px.bar(top, x="player", y="wickets", color="player", text="wickets",
                 color_discrete_sequence=COLORS, title="Top 10 Wicket Takers")
    fig.update_layout(showlegend=False, xaxis_tickangle=-35,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font_color="white")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
