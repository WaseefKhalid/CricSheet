import streamlit as st
import pandas as pd
import plotly.express as px

COLORS = px.colors.qualitative.Bold


def _safe_merge_season(deliveries: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Merge deliveries with season info safely, avoiding duplicate columns."""
    match_cols = [c for c in ["match_id", "season"] if c in matches.columns]
    merged = deliveries.merge(matches[match_cols], on="match_id", how="left")
    if "season_x" in merged.columns:
        merged = merged.rename(columns={"season_x": "season"}).drop(columns=["season_y"], errors="ignore")
    return merged


def plot_runs_per_season(deliveries: pd.DataFrame, matches: pd.DataFrame):
    st.markdown("**Total Runs per Season**")
    if deliveries.empty or matches.empty:
        st.info("No data available.")
        return
    try:
        merged = _safe_merge_season(deliveries, matches)
        if "season" not in merged.columns:
            st.info("Season data not available.")
            return
        merged["total_ball_runs"] = merged["runs_off_bat"].fillna(0) + merged["extras"].fillna(0)
        runs = (
            merged.groupby("season")["total_ball_runs"]
            .sum()
            .reset_index()
            .rename(columns={"total_ball_runs": "total_runs"})
            .sort_values("season")
        )
        runs["total_runs"] = runs["total_runs"].astype(int)
        fig = px.bar(runs, x="season", y="total_runs", color="season",
                     color_discrete_sequence=COLORS, text="total_runs")
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render runs per season chart: {e}")


def plot_wickets_per_season(deliveries: pd.DataFrame, matches: pd.DataFrame):
    st.markdown("**Total Wickets per Season**")
    if deliveries.empty or matches.empty:
        st.info("No data available.")
        return
    try:
        merged = _safe_merge_season(deliveries, matches)
        if "season" not in merged.columns:
            st.info("Season data not available.")
            return
        wickets_df = merged[
            merged["wicket_type"].notna() & (merged["wicket_type"].astype(str).str.strip() != "")
        ]
        wickets = (
            wickets_df.groupby("season").size()
            .reset_index(name="wickets")
            .sort_values("season")
        )
        fig = px.line(wickets, x="season", y="wickets", markers=True,
                      color_discrete_sequence=["#00b4d8"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render wickets per season chart: {e}")


def plot_win_by_method(matches: pd.DataFrame):
    st.markdown("**Win Method Distribution**")
    if matches.empty:
        st.info("No data available.")
        return
    try:
        df = matches.copy()
        df["method"] = "By Runs"
        if "winner_wickets" in df.columns:
            df["winner_wickets"] = pd.to_numeric(df["winner_wickets"], errors="coerce")
            df.loc[df["winner_wickets"].notna() & (df["winner_wickets"] > 0), "method"] = "By Wickets"
        if "winner" in df.columns:
            df.loc[df["winner"].isna() | (df["winner"].astype(str).str.strip() == ""), "method"] = "No Result"
        counts = df["method"].value_counts().reset_index()
        counts.columns = ["method", "count"]
        fig = px.pie(counts, names="method", values="count",
                     color_discrete_sequence=COLORS, hole=0.4)
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render win method chart: {e}")


def plot_toss_impact(matches: pd.DataFrame):
    st.markdown("**Toss Decision Frequency**")
    if matches.empty or "toss_decision" not in matches.columns:
        st.info("No data available.")
        return
    try:
        counts = matches["toss_decision"].dropna().value_counts().reset_index()
        counts.columns = ["decision", "count"]
        fig = px.pie(counts, names="decision", values="count",
                     color_discrete_sequence=["#1DB954", "#00b4d8"], hole=0.4)
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render toss chart: {e}")


def plot_top_batsmen(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data available.")
        return
    try:
        top = df.head(10).copy()
        top[y] = pd.to_numeric(top[y], errors="coerce").fillna(0)
        fig = px.bar(top, x=x, y=y, color=x, text=y,
                     color_discrete_sequence=COLORS, title=title)
        fig.update_layout(showlegend=False, xaxis_tickangle=-35,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render chart: {e}")


def plot_top_bowlers(df: pd.DataFrame):
    if df.empty:
        st.info("No data available.")
        return
    try:
        top = df.head(10).copy()
        fig = px.bar(top, x="player", y="wickets", color="player", text="wickets",
                     color_discrete_sequence=COLORS, title="Top 10 Wicket Takers")
        fig.update_layout(showlegend=False, xaxis_tickangle=-35,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render bowlers chart: {e}")
