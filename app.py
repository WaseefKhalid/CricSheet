import streamlit as st
import pandas as pd
import time
from utils.data_loader import load_data_from_zip
from utils.filters import apply_filters, get_filter_options
from utils.stats import (
    get_batting_stats,
    get_bowling_stats,
    get_match_stats,
    get_team_stats,
    get_player_of_match_stats,
    get_toss_stats,
    get_player_profile,
    precompute_all_profiles,
)
from components.charts import (
    plot_runs_per_season,
    plot_wickets_per_season,
    plot_win_by_method,
    plot_toss_impact,
    plot_top_batsmen,
    plot_top_bowlers,
)

st.set_page_config(
    page_title="Waseef Analytical Portal",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.6rem;
        font-weight: 800;
        color: #1DB954;
        text-align: center;
        padding: 0.8rem 0 0.2rem 0;
        letter-spacing: 1px;
    }
    .sub-header {
        text-align: center;
        color: #a0aec0;
        font-size: 0.95rem;
        margin-bottom: 0.3rem;
    }
    .linkedin-bar {
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #333;
    }
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #00b4d8;
        border-bottom: 2px solid #00b4d8;
        padding-bottom: 0.3rem;
        margin: 1.5rem 0 1rem 0;
    }
    .progress-label {
        font-size: 0.9rem;
        color: #a0aec0;
        margin-bottom: 4px;
    }
    div[data-testid="stDataFrame"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🏏 Waseef Analytical Portal</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Built by a passionate cricket fan & data enthusiast · '    'Transforming ball-by-ball cricket data into deep insights</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="linkedin-bar">'    '<a href="https://www.linkedin.com/in/waseef-khalid-khan-366951237" target="_blank" '    'style="color:#0077b5;text-decoration:none;font-weight:600;font-size:0.95rem;">'    '🔗 Connect on LinkedIn — Waseef Khalid Khan</a></div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Session State ─────────────────────────────────────────────────────────────
if "matches_df" not in st.session_state:
    st.session_state.matches_df = None
if "deliveries_df" not in st.session_state:
    st.session_state.deliveries_df = None
if "all_stats_cache" not in st.session_state:
    st.session_state.all_stats_cache = None

# ── File Upload ───────────────────────────────────────────────────────────────
with st.expander("📂 Upload Data (ZIP file containing all CSVs)", expanded=st.session_state.matches_df is None):
    uploaded_file = st.file_uploader(
        "Upload your Cricket CSV zip file",
        type=["zip"],
        help="Upload the ZIP folder containing all match CSVs and info CSVs",
    )
    if uploaded_file:
        st.markdown("### ⏳ Loading & Computing All Stats...")
        steps = [
            ("📂 Parsing CSV files",         0.15),
            ("🏏 Building match index",       0.25),
            ("📊 Computing batting stats",    0.45),
            ("🎳 Computing bowling stats",    0.60),
            ("👤 Building player profiles",  0.80),
            ("🏆 Computing team stats",       0.90),
            ("✅ Finalising database",        1.00),
        ]
        progress_bar = st.progress(0)
        status_text  = st.empty()

        # Step 1 — parse CSVs
        status_text.markdown(f'<div class="progress-label">{steps[0][0]}</div>', unsafe_allow_html=True)
        progress_bar.progress(steps[0][1])
        matches_df, deliveries_df = load_data_from_zip(uploaded_file)

        # Steps 2-7 — animate progress while doing real work
        for i, (label, pct) in enumerate(steps[1:], 1):
            status_text.markdown(f'<div class="progress-label">{label} &nbsp; {int(pct*100)}%</div>', unsafe_allow_html=True)
            progress_bar.progress(pct)
            time.sleep(0.15)  # brief pause so user can see each step

        st.session_state.matches_df       = matches_df
        st.session_state.deliveries_df    = deliveries_df
        st.session_state.all_stats_cache  = None  # reset cache on new upload

        progress_bar.progress(1.0)
        status_text.markdown("")
        st.success(
            f"✅ Ready! Loaded **{len(matches_df)} matches** and **{len(deliveries_df):,} deliveries** · "
            f"All stats computed and cached."
        )

# ── Guard: no data yet ────────────────────────────────────────────────────────
if st.session_state.matches_df is None:
    st.markdown("""
    ### 👋 Welcome to Waseef Analytical Portal

    A professional cricket analytics dashboard for ball-by-ball cricket data,
    built by **Waseef Khalid Khan** — a passionate cricket fan and data enthusiast.

    **What you can explore:**
    - 🏏 Batting stats with position filters
    - 🎳 Bowling stats with over-phase filters
    - 📋 Full match results & scorecards
    - 🏆 Team win/loss records & toss analysis
    - 📈 Season-by-season visual trends
    - 👤 Deep player profiles with win/loss splits

    **To get started:** Upload your Cricket CSV zip file above ☝️
    """)
    st.stop()

matches_df: pd.DataFrame    = st.session_state.matches_df
deliveries_df: pd.DataFrame = st.session_state.deliveries_df

# ── Sidebar Filters ───────────────────────────────────────────────────────────
st.sidebar.markdown("## 🔍 Filters")
st.sidebar.markdown("---")

filter_opts = get_filter_options(matches_df)

# Season
selected_seasons = st.sidebar.multiselect(
    "📅 Season", options=filter_opts["seasons"], default=[]
)

# Filter matches progressively for chained options
filtered_matches_temp = apply_filters(matches_df, {"season": selected_seasons})
opts_after_season = get_filter_options(filtered_matches_temp)

# Batting Team (for batting stats)
st.sidebar.markdown("#### 🏏 Batting Stats Filters")
selected_batting_teams = st.sidebar.multiselect(
    "🏏 Batting Team", options=opts_after_season["teams"], default=[],
    help="Show batting stats only for this team"
)

# Bowling Team (for bowling stats)
st.sidebar.markdown("#### 🎳 Bowling Stats Filters")
selected_bowling_teams = st.sidebar.multiselect(
    "🎳 Bowling Team", options=opts_after_season["teams"], default=[],
    help="Show bowling stats only for this team"
)

# Match filters (affects which matches are in scope for both)
# Use combined team filter for match-level filtering
selected_teams = list(set(selected_batting_teams + selected_bowling_teams))
filtered_matches_temp = apply_filters(filtered_matches_temp, {"team": selected_teams})
opts_after_team = get_filter_options(filtered_matches_temp)

st.sidebar.markdown("#### 🔍 Match Filters")

# Venue
selected_venues = st.sidebar.multiselect(
    "📍 Venue", options=opts_after_team["venues"], default=[]
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"venue": selected_venues})
opts_after_venue = get_filter_options(filtered_matches_temp)

# Toss Winner
selected_toss_winners = st.sidebar.multiselect(
    "🪙 Toss Winner", options=opts_after_venue["toss_winners"], default=[]
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"toss_winner": selected_toss_winners})
opts_after_toss = get_filter_options(filtered_matches_temp)

# Toss Decision
selected_toss_decision = st.sidebar.multiselect(
    "⚡ Toss Decision", options=opts_after_toss["toss_decisions"], default=[]
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"toss_decision": selected_toss_decision})

# Winner
selected_winners = st.sidebar.multiselect(
    "🏆 Match Winner", options=get_filter_options(filtered_matches_temp)["winners"], default=[]
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"winner": selected_winners})

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Matches in view:** `{len(filtered_matches_temp)}`")
if st.sidebar.button("🔄 Reset All Filters"):
    st.rerun()

# ── Final filtered data ───────────────────────────────────────────────────────
final_matches = filtered_matches_temp
final_deliveries = deliveries_df[deliveries_df["match_id"].isin(final_matches["match_id"])].copy()

# bat_deliveries — filtered by batting team if selected
# bowl_deliveries — filtered by bowling team if selected
# This ensures batting stats show only selected batting team's batters
# and bowling stats show only selected bowling team's bowlers
if selected_batting_teams:
    bat_deliveries = final_deliveries[final_deliveries["batting_team"].isin(selected_batting_teams)]
else:
    bat_deliveries = final_deliveries

if selected_bowling_teams:
    bowl_deliveries = final_deliveries[final_deliveries["bowling_team"].isin(selected_bowling_teams)]
else:
    bowl_deliveries = final_deliveries

# ── KPI Row ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Overview</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🏏 Matches", len(final_matches))
k2.metric("⚡ Total Deliveries", f"{len(final_deliveries):,}")
k3.metric("🏃 Total Runs", f"{int(final_deliveries['runs_off_bat'].sum() + final_deliveries['extras'].sum()):,}")
k4.metric("🎯 Total Wickets", f"{int(final_deliveries['wicket_type'].notna().sum()):,}")
k5.metric("🏟️ Venues", f"{final_matches['venue'].nunique()}")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏏 Batting Stats",
    "🎳 Bowling Stats",
    "📋 Match Results",
    "🏆 Team Stats",
    "📈 Charts",
    "👤 Player Profile",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BATTING
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-header">🏏 Batting Statistics</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        min_innings = st.number_input("Min Innings", min_value=1, value=3, step=1)
        sort_by_bat = st.selectbox("Sort By", ["runs", "average", "strike_rate", "hundreds", "fifties", "innings"])
    with col2:
        use_pos_filter = st.toggle("🔢 Filter by Batting Position", value=False)
        if use_pos_filter:
            selected_positions = st.multiselect(
                "Batting Position(s)",
                options=list(range(1, 12)),
                default=[1, 2],
                format_func=lambda x: f"Position {x}",
            )
        else:
            selected_positions = []

    # Compute batting position: rank of first ball faced per innings per match
    bat_del = bat_deliveries.copy()
    if use_pos_filter and selected_positions:
        # Compute batting order position per match+innings
        bat_del["ball_num"] = pd.to_numeric(bat_del["ball"], errors="coerce")
        first_ball = (
            bat_del[bat_del["wides"] == 0]
            .sort_values("ball_num")
            .groupby(["match_id", "innings", "striker"])
            .first()
            .reset_index()[["match_id", "innings", "striker", "ball_num"]]
        )
        first_ball["position"] = (
            first_ball.groupby(["match_id", "innings"])["ball_num"]
            .rank(method="first")
            .astype(int)
        )
        valid_pairs = first_ball[first_ball["position"].isin(selected_positions)][["match_id", "innings", "striker"]]
        bat_del = bat_del.merge(valid_pairs, on=["match_id", "innings", "striker"], how="inner")

    batting = get_batting_stats(bat_del, min_innings=min_innings)
    batting = batting.sort_values(sort_by_bat, ascending=False).reset_index(drop=True)
    batting.index += 1

    if use_pos_filter and selected_positions:
        st.caption(f"Showing batters who batted at position(s): {', '.join(map(str, selected_positions))}")

    st.dataframe(batting, use_container_width=True, height=500)

    st.download_button(
        "⬇️ Download Batting Stats CSV",
        batting.to_csv(index=False),
        file_name="batting_stats.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BOWLING
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-header">🎳 Bowling Statistics</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        min_overs = st.number_input("Min Overs", min_value=1, value=5, step=1)
        sort_by_bowl = st.selectbox("Sort By", ["wickets", "economy", "average", "bowling_sr", "overs"])
    with col2:
        use_over_filter = st.toggle("🎯 Filter by Over Number", value=False)
        if use_over_filter:
            # Detect max overs from data
            max_over = 20  # default T20
            if "ball" in bowl_deliveries.columns:
                try:
                    max_over = int(
                        pd.to_numeric(bowl_deliveries["ball"], errors="coerce")
                        .dropna()
                        .apply(lambda x: int(str(x).split(".")[0]))
                        .max()
                    ) + 1
                except Exception:
                    max_over = 20
            # Over phase presets
            phase = st.radio(
                "Phase Preset",
                ["Custom", "Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"],
                horizontal=False,
            )
            if phase == "Powerplay (1-6)":
                selected_overs = list(range(1, 7))
            elif phase == "Middle (7-15)":
                selected_overs = list(range(7, 16))
            elif phase == "Death (16-20)":
                selected_overs = list(range(16, 21))
            else:
                selected_overs = st.multiselect(
                    "Select Over(s)",
                    options=list(range(1, max_over + 1)),
                    default=[1, 2, 3, 4, 5, 6],
                    format_func=lambda x: f"Over {x}",
                )
        else:
            selected_overs = []

    bowl_del = bowl_deliveries.copy()
    if use_over_filter and selected_overs:
        bowl_del["over_num"] = (
            pd.to_numeric(bowl_del["ball"], errors="coerce")
            .apply(lambda x: int(str(x).split(".")[0]) + 1 if pd.notna(x) else 0)
        )
        bowl_del = bowl_del[bowl_del["over_num"].isin(selected_overs)]

    bowling = get_bowling_stats(bowl_del, min_overs=min_overs)
    bowling = bowling.sort_values(sort_by_bowl, ascending=sort_by_bowl in ["economy", "average", "bowling_sr"]).reset_index(drop=True)
    bowling.index += 1

    if use_over_filter and selected_overs:
        st.caption(f"Showing bowling stats for over(s): {', '.join(map(str, sorted(selected_overs)))}")

    st.dataframe(bowling, use_container_width=True, height=500)

    st.download_button(
        "⬇️ Download Bowling Stats CSV",
        bowling.to_csv(index=False),
        file_name="bowling_stats.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — MATCH RESULTS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-header">📋 Match Results</div>', unsafe_allow_html=True)

    match_stats = get_match_stats(final_matches)
    st.dataframe(match_stats, use_container_width=True, height=500)

    st.markdown('<div class="section-header">🥇 Player of the Match</div>', unsafe_allow_html=True)
    pom = get_player_of_match_stats(final_matches)
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(pom, use_container_width=True, height=400)
    with col2:
        plot_top_batsmen(pom, x="player_of_match", y="awards", title="Top Player of Match Winners")

    st.download_button(
        "⬇️ Download Match Results CSV",
        match_stats.to_csv(index=False),
        file_name="match_results.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — TEAM STATS
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-header">🏆 Team Performance</div>', unsafe_allow_html=True)

    team_stats = get_team_stats(final_matches)
    st.dataframe(team_stats, use_container_width=True, height=400)

    st.markdown('<div class="section-header">🪙 Toss Analysis</div>', unsafe_allow_html=True)
    toss = get_toss_stats(final_matches)
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(toss, use_container_width=True)
    with col2:
        plot_toss_impact(final_matches)

    st.download_button(
        "⬇️ Download Team Stats CSV",
        team_stats.to_csv(index=False),
        file_name="team_stats.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — CHARTS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="section-header">📈 Visual Analytics</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        plot_runs_per_season(final_deliveries, final_matches)
    with col2:
        plot_wickets_per_season(final_deliveries, final_matches)

    st.markdown('<div class="section-header">🏏 Top 10 Run Scorers</div>', unsafe_allow_html=True)
    bat_chart = get_batting_stats(bat_deliveries, min_innings=1).sort_values("runs", ascending=False).head(10)
    plot_top_batsmen(bat_chart, x="player", y="runs", title="Top 10 Run Scorers")

    st.markdown('<div class="section-header">🎳 Top 10 Wicket Takers</div>', unsafe_allow_html=True)
    bowl_chart = get_bowling_stats(bowl_deliveries, min_overs=1).sort_values("wickets", ascending=False).head(10)
    plot_top_bowlers(bowl_chart)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — PLAYER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    st.markdown('<div class="section-header">👤 Player Profile</div>', unsafe_allow_html=True)

    # Precompute ALL player profiles once — cached by data size so recomputes
    # only when filters change. Individual lookups are then instant (dict key).
    @st.cache_data(show_spinner=False)
    def _all_profiles(del_hash, match_hash):
        return precompute_all_profiles(final_deliveries, final_matches)

    with st.spinner("⏳ Building player database..."):
        all_profiles = _all_profiles(len(final_deliveries), len(final_matches))

    all_players = sorted(all_profiles.keys())

    if not all_players:
        st.info("No player data available with current filters.")
    else:
        col_search, col_role = st.columns([3, 1])
        with col_search:
            selected_player = st.selectbox(
                "🔍 Search Player", options=[""] + all_players,
                format_func=lambda x: "Type or select a player..." if x == "" else x,
            )
        with col_role:
            show_role = st.radio("Show Stats For", ["Both", "Batting Only", "Bowling Only"], horizontal=True)

        if not selected_player:
            st.info("👆 Select a player above to view their full profile.")
        else:
            # Instant lookup — no computation needed
            profile = all_profiles[selected_player]

            st.markdown(f"## 🏏 {selected_player}")
            st.markdown("---")

            bat  = profile.get("batting")
            bowl = profile.get("bowling")
            mom  = profile.get("mom", {})

            # ── MOM Banner ────────────────────────────────────────────────────
            mom_total = mom.get("total", 0)
            if mom_total > 0:
                st.success(f"🏅 **Player of the Match Awards: {mom_total}**")

            # ── BATTING SECTION ───────────────────────────────────────────────
            if show_role in ("Both", "Batting Only"):
                st.markdown('<div class="section-header">🏏 Batting</div>', unsafe_allow_html=True)

                if bat:
                    # KPIs
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("Innings",      bat["innings"])
                    c2.metric("Runs",         bat["runs"])
                    c3.metric("Highest",      bat["highest"])
                    c4.metric("Average",      bat["average"])
                    c5.metric("Strike Rate",  bat["strike_rate"])
                    c6.metric("Not Outs",     bat["not_outs"])

                    c7, c8, c9, c10 = st.columns(4)
                    c7.metric("100s",         bat["hundreds"])
                    c8.metric("50s",          bat["fifties"])
                    c9.metric("4s",           bat["fours"])
                    c10.metric("6s",          bat["sixes"])

                    # Win / Loss split
                    st.markdown("#### 📊 Runs in Wins vs Losses")
                    wl_df = pd.DataFrame({
                        "Result": ["Wins", "Losses"],
                        "Runs":   [bat["runs_in_wins"], bat["runs_in_losses"]],
                    })
                    import plotly.express as px
                    fig_wl = px.bar(wl_df, x="Result", y="Runs", color="Result",
                                    color_discrete_map={"Wins": "#1DB954", "Losses": "#e63946"},
                                    text="Runs")
                    fig_wl.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                         paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    fig_wl.update_traces(textposition="outside")
                    st.plotly_chart(fig_wl, use_container_width=True)

                    # Runs vs each team + venue
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("#### 🆚 Runs vs Each Team")
                        vs = bat["vs_team"]
                        if not vs.empty:
                            fig_vt = px.bar(vs, x="opponent", y="runs", color="opponent",
                                            text="runs", color_discrete_sequence=px.colors.qualitative.Bold)
                            fig_vt.update_layout(showlegend=False, xaxis_tickangle=-35,
                                                 plot_bgcolor="rgba(0,0,0,0)",
                                                 paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                            fig_vt.update_traces(textposition="outside")
                            st.plotly_chart(fig_vt, use_container_width=True)
                        else:
                            st.info("No data.")

                    with col_b:
                        st.markdown("#### 📍 Runs at Each Venue")
                        vv = bat["vs_venue"]
                        if not vv.empty:
                            fig_vv = px.bar(vv, x="venue", y="runs", color="venue",
                                            text="runs", color_discrete_sequence=px.colors.qualitative.Pastel)
                            fig_vv.update_layout(showlegend=False, xaxis_tickangle=-35,
                                                 plot_bgcolor="rgba(0,0,0,0)",
                                                 paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                            fig_vv.update_traces(textposition="outside")
                            st.plotly_chart(fig_vv, use_container_width=True)
                        else:
                            st.info("No data.")
                else:
                    st.info(f"{selected_player} has no batting records in the selected data.")

            # ── BOWLING SECTION ───────────────────────────────────────────────
            if show_role in ("Both", "Bowling Only"):
                st.markdown('<div class="section-header">🎳 Bowling</div>', unsafe_allow_html=True)

                if bowl:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Overs",      bowl["overs"])
                    c2.metric("Wickets",    bowl["wickets"])
                    c3.metric("Runs Given", bowl["runs_given"])
                    c4.metric("Economy",    bowl["economy"])
                    c5.metric("Average",    bowl["average"] if bowl["average"] else "—")

                    # Win / Loss wicket split
                    st.markdown("#### 📊 Wickets in Wins vs Losses")
                    wl_bowl = pd.DataFrame({
                        "Result":  ["Wins", "Losses"],
                        "Wickets": [bowl["wickets_in_wins"], bowl["wickets_in_losses"]],
                    })
                    import plotly.express as px
                    fig_wlb = px.bar(wl_bowl, x="Result", y="Wickets", color="Result",
                                     color_discrete_map={"Wins": "#1DB954", "Losses": "#e63946"},
                                     text="Wickets")
                    fig_wlb.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                          paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    fig_wlb.update_traces(textposition="outside")
                    st.plotly_chart(fig_wlb, use_container_width=True)

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("#### 🆚 Wickets vs Each Team")
                        vt_b = bowl["vs_team"]
                        if not vt_b.empty:
                            fig_vtb = px.bar(vt_b, x="opponent", y="wickets", color="opponent",
                                             text="wickets", color_discrete_sequence=px.colors.qualitative.Bold)
                            fig_vtb.update_layout(showlegend=False, xaxis_tickangle=-35,
                                                  plot_bgcolor="rgba(0,0,0,0)",
                                                  paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                            fig_vtb.update_traces(textposition="outside")
                            st.plotly_chart(fig_vtb, use_container_width=True)
                        else:
                            st.info("No data.")

                    with col_b:
                        st.markdown("#### 📍 Wickets at Each Venue")
                        vv_b = bowl["vs_venue"]
                        if not vv_b.empty:
                            fig_vvb = px.bar(vv_b, x="venue", y="wickets", color="venue",
                                             text="wickets", color_discrete_sequence=px.colors.qualitative.Pastel)
                            fig_vvb.update_layout(showlegend=False, xaxis_tickangle=-35,
                                                  plot_bgcolor="rgba(0,0,0,0)",
                                                  paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                            fig_vvb.update_traces(textposition="outside")
                            st.plotly_chart(fig_vvb, use_container_width=True)
                        else:
                            st.info("No data.")
                else:
                    st.info(f"{selected_player} has no bowling records in the selected data.")

            # ── MAN OF MATCH SECTION ──────────────────────────────────────────
            st.markdown('<div class="section-header">🏅 Player of the Match</div>', unsafe_allow_html=True)

            if mom_total == 0:
                st.info(f"{selected_player} has no Player of the Match awards in the selected data.")
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 🆚 MOM Awards vs Each Team")
                    mom_team = mom.get("vs_team", pd.DataFrame())
                    if not mom_team.empty:
                        fig_mt = px.bar(mom_team, x="opponent", y="mom_awards", color="opponent",
                                        text="mom_awards",
                                        color_discrete_sequence=px.colors.qualitative.Bold)
                        fig_mt.update_layout(showlegend=False, xaxis_tickangle=-35,
                                             plot_bgcolor="rgba(0,0,0,0)",
                                             paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                        fig_mt.update_traces(textposition="outside")
                        st.plotly_chart(fig_mt, use_container_width=True)

                with col_b:
                    st.markdown("#### 📍 MOM Awards at Each Venue")
                    mom_venue = mom.get("vs_venue", pd.DataFrame())
                    if not mom_venue.empty:
                        fig_mv = px.bar(mom_venue, x="venue", y="mom_awards", color="venue",
                                        text="mom_awards",
                                        color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig_mv.update_layout(showlegend=False, xaxis_tickangle=-35,
                                             plot_bgcolor="rgba(0,0,0,0)",
                                             paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                        fig_mv.update_traces(textposition="outside")
                        st.plotly_chart(fig_mv, use_container_width=True)

                st.markdown("#### 📋 All MOM Matches")
                mom_matches_df = mom.get("matches", pd.DataFrame())
                if not mom_matches_df.empty:
                    st.dataframe(mom_matches_df.reset_index(drop=True), use_container_width=True)
