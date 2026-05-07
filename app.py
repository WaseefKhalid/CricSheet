import streamlit as st
import pandas as pd
import time
import os
from utils.data_loader import load_data_from_zip
from utils.filters import apply_filters, get_filter_options
from utils.stats import (
    get_batting_stats,
    get_bowling_stats,
    get_match_stats,
    get_team_stats,
    get_player_of_match_stats,
    get_toss_stats,
    get_batting_order_stats,
    get_player_profile,
    precompute_all_profiles,
)
from components.charts import (
    plot_top_batsmen,
    plot_top_bowlers,
)

# ── Auto-discover leagues from data/ folder ──────────────────────────────────
# Just drop any ZIP file into /data — it appears automatically as a league option
# Display name is derived from the filename: "psl_data.zip" → "PSL Data"
def _discover_leagues(data_dir="data"):
    """Scan data/ folder and return {display_name: file_path} for all ZIPs found."""
    leagues = {}
    if not os.path.exists(data_dir):
        return leagues
    for fname in sorted(os.listdir(data_dir)):
        if fname.lower().endswith(".zip"):
            path = os.path.join(data_dir, fname)
            # Build a clean display name from filename
            # "psl_data.zip" → "PSL Data"
            # "ipl_2024.zip" → "IPL 2024"
            # "t20_internationals.zip" → "T20 Internationals"
            name = fname.replace(".zip", "").replace("_", " ").replace("-", " ")
            name = " ".join(w.upper() if len(w) <= 4 else w.capitalize() for w in name.split())
            leagues[name] = path
    return leagues

AVAILABLE_LEAGUES = _discover_leagues()

st.set_page_config(
    page_title="Waseef Analytical Portal",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal CSS — only what Streamlit reliably supports ──────────────────────
st.markdown("""
<style>
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
_active = st.session_state.get("active_league")

_, col, _ = st.columns([1, 3, 1])
with col:
    st.markdown("<h1 style='text-align:center;'>🏏 Waseef Analytical Portal</h1>", unsafe_allow_html=True)
    if _active:
        st.markdown(f"<p style='text-align:center;color:#1DB954;font-weight:600;'>📊 {_active}</p>", unsafe_allow_html=True)
    else:
        st.markdown("<p style='text-align:center;color:#8b949e;'>Transforming ball-by-ball cricket data into deep insights</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>🔗 <a href='https://www.linkedin.com/in/waseef-khalid-khan-366951237' target='_blank'>Connect on LinkedIn — Waseef Khalid Khan</a></p>", unsafe_allow_html=True)
st.divider()

# ── Session State ─────────────────────────────────────────────────────────────
if "matches_df" not in st.session_state:
    st.session_state.matches_df = None
if "deliveries_df" not in st.session_state:
    st.session_state.deliveries_df = None
if "cached" not in st.session_state:
    st.session_state.cached = None
if "active_league" not in st.session_state:
    st.session_state.active_league = None


def _compute_and_cache(matches_df, deliveries_df, progress_bar, status_text):
    """Compute all stats and store in session state."""
    def _step(msg, pct):
        status_text.markdown(
            f'<div class="progress-label">{msg} &nbsp;&nbsp; <b>{int(pct*100)}%</b></div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress(pct)

    _step("🏏 Computing batting stats...", 0.20)
    batting_all = get_batting_stats(deliveries_df, min_innings=1)

    _step("🎳 Computing bowling stats...", 0.38)
    bowling_all = get_bowling_stats(deliveries_df, min_overs=1)

    _step("📋 Computing match & team results...", 0.54)
    match_stats_all     = get_match_stats(matches_df)
    team_stats_all      = get_team_stats(matches_df)
    toss_stats_all      = get_toss_stats(matches_df)
    bat_order_stats_all = get_batting_order_stats(matches_df, deliveries_df)
    pom_stats_all       = get_player_of_match_stats(matches_df)

    _step("👤 Building all player profiles...", 0.75)
    all_profiles = precompute_all_profiles(deliveries_df, matches_df)

    _step("✅ Finalising & indexing...", 0.93)
    deliveries_df = deliveries_df.set_index("match_id", drop=False)

    st.session_state.matches_df    = matches_df
    st.session_state.deliveries_df = deliveries_df
    st.session_state.cached = {
        "batting_all":     batting_all,
        "bowling_all":     bowling_all,
        "match_stats":     match_stats_all,
        "team_stats":      team_stats_all,
        "toss_stats":      toss_stats_all,
        "bat_order_stats": bat_order_stats_all,
        "pom_stats":       pom_stats_all,
        "all_profiles":    all_profiles,
    }
    progress_bar.progress(1.0)
    status_text.markdown("")


# ── LEAGUE SELECTOR — shown when no league loaded or user wants to switch ──────
def _load_league(league_name, zip_path):
    """Load a league zip and compute all stats."""
    st.markdown(f"### ⏳ Loading **{league_name}** — please wait...")
    pb = st.progress(0)
    st_txt = st.empty()
    st_txt.markdown(
        '<div class="progress-label">📂 Reading data file... &nbsp; <b>5%</b></div>',
        unsafe_allow_html=True,
    )
    pb.progress(0.05)
    with open(zip_path, "rb") as f:
        matches_df, deliveries_df = load_data_from_zip(f)
    _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
    st.session_state.active_league = league_name
    st.rerun()


# Show league picker if no league loaded yet OR user clicks switch
show_picker = (
    st.session_state.matches_df is None or
    st.session_state.active_league is None
)

# Switch league button in sidebar (only after data is loaded)
if not show_picker and st.session_state.active_league:
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Switch League"):
        st.session_state.matches_df    = None
        st.session_state.deliveries_df = None
        st.session_state.cached        = None
        st.session_state.active_league = None
        st.rerun()

if show_picker:
    st.markdown("---")
    if AVAILABLE_LEAGUES:
        st.markdown("## 🏏 Select a League to Explore")
        st.markdown("Choose which cricket league you want to analyse:")
        st.markdown("")

        # Show league cards in a grid
        import zipfile
        from datetime import datetime
        cols = st.columns(min(len(AVAILABLE_LEAGUES), 3))
        for i, (league_name, zip_path) in enumerate(AVAILABLE_LEAGUES.items()):
            with cols[i % 3]:
                # Match count
                try:
                    with zipfile.ZipFile(zip_path) as z:
                        n_matches = len([f for f in z.namelist() if f.endswith("_info.csv")])
                except Exception:
                    n_matches = 0

                # Last updated date from file modification time
                try:
                    mod_time = os.path.getmtime(zip_path)
                    updated  = datetime.fromtimestamp(mod_time).strftime("%d %b %Y")
                except Exception:
                    updated = "Unknown"

                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #0d1f2d 0%, #0a1628 100%);
                    border-radius: 14px;
                    padding: 1.5rem 1.2rem 1rem 1.2rem;
                    border: 1px solid #1a3550;
                    text-align: center;
                    margin-bottom: 0.5rem;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
                    transition: all 0.2s;
                ">
                    <div style="font-size:2.2rem;margin-bottom:0.4rem;">🏏</div>
                    <div style="font-size:1.2rem;font-weight:800;color:#ffffff;
                                margin-bottom:0.5rem;letter-spacing:-0.3px;">
                        {league_name}
                    </div>
                    <div style="display:inline-block;background:rgba(29,185,84,0.12);
                                border:1px solid rgba(29,185,84,0.3);border-radius:20px;
                                padding:0.2rem 0.8rem;font-size:0.82rem;color:#1DB954;
                                font-weight:600;margin-bottom:0.4rem;">
                        {n_matches} matches
                    </div>
                    <div style="color:#8b949e;font-size:0.78rem;margin-top:0.3rem;">
                        🕒 {updated}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"▶ Load {league_name}", key=f"load_{i}", use_container_width=True):
                    _load_league(league_name, zip_path)

        # Upload option — only shown to admin (password protected)
        st.markdown("---")
        with st.expander("🔐 Admin: Upload a new league"):
            admin_pass = st.text_input("Admin password", type="password", key="admin_pass")
            if admin_pass == st.secrets.get("ADMIN_PASSWORD", "waseef123"):
                uploaded_file = st.file_uploader("Upload Cricket CSV zip", type=["zip"])
                custom_name   = st.text_input("League name", placeholder="e.g. SA20, LPL, MLC...")
                if uploaded_file and custom_name:
                    if st.button("Load uploaded data"):
                        st.markdown(f"### ⏳ Loading **{custom_name}**...")
                        pb = st.progress(0)
                        st_txt = st.empty()
                        pb.progress(0.05)
                        matches_df, deliveries_df = load_data_from_zip(uploaded_file)
                        _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
                        st.session_state.active_league = custom_name
                        st.rerun()
            elif admin_pass:
                st.error("❌ Incorrect password")
    else:
        # No leagues in data/ folder — show upload
        st.markdown("## 👋 Welcome to Waseef Analytical Portal")
        st.markdown("No pre-loaded leagues found. Upload a cricket CSV zip to get started.")
        uploaded_file = st.file_uploader("Upload Cricket CSV zip", type=["zip"])
        custom_name   = st.text_input("League name", placeholder="e.g. PSL, IPL, T20I...")
        if uploaded_file and custom_name:
            if st.button("Load"):
                pb = st.progress(0)
                st_txt = st.empty()
                pb.progress(0.05)
                matches_df, deliveries_df = load_data_from_zip(uploaded_file)
                _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
                st.session_state.active_league = custom_name
                st.rerun()
    st.stop()

# ── Guard ─────────────────────────────────────────────────────────────────────
if st.session_state.matches_df is None or st.session_state.cached is None:
    st.stop()

matches_df: pd.DataFrame    = st.session_state.matches_df
deliveries_df: pd.DataFrame = st.session_state.deliveries_df
_cache = st.session_state.cached  # precomputed stats dict

# ── Sidebar Filters ───────────────────────────────────────────────────────────
st.sidebar.markdown("## 🔍 Filters")
st.sidebar.markdown("---")

filter_opts = get_filter_options(matches_df)

# Season
selected_seasons = st.sidebar.multiselect(
    "📅 Season", options=filter_opts["seasons"], default=[]
)
filtered_matches_temp = apply_filters(matches_df, {"season": selected_seasons})
opts_after_season = get_filter_options(filtered_matches_temp)

# ── MAIN TEAM FILTER — filters everything at once ─────────────────────────
st.sidebar.markdown("#### 🏆 Team")
selected_main_team = st.sidebar.multiselect(
    "🏆 Team (All Stats)",
    options=opts_after_season["teams"],
    default=[],
    help="Filters ALL tabs — batting, bowling, matches, team stats, player profiles",
)
if selected_main_team:
    filtered_matches_temp = apply_filters(filtered_matches_temp, {"team": selected_main_team})

opts_after_main_team = get_filter_options(filtered_matches_temp)

# ── ADVANCED: separate batting/bowling team overrides ─────────────────────
with st.sidebar.expander("⚙️ Advanced Team Filters", expanded=False):
    st.caption("Override main team filter for specific stat tabs")
    selected_batting_teams = st.multiselect(
        "🏏 Batting Team (override)",
        options=opts_after_main_team["teams"], default=[],
        help="Show batting stats only for this team",
    )
    selected_bowling_teams = st.multiselect(
        "🎳 Bowling Team (override)",
        options=opts_after_main_team["teams"], default=[],
        help="Show bowling stats only for this team",
    )

# Effective team filters: advanced overrides take priority, else use main team
eff_batting_teams = selected_batting_teams if selected_batting_teams else selected_main_team
eff_bowling_teams = selected_bowling_teams if selected_bowling_teams else selected_main_team

selected_teams = list(set(eff_batting_teams + eff_bowling_teams))
if selected_teams:
    filtered_matches_temp = apply_filters(
        apply_filters(matches_df, {"season": selected_seasons}),
        {"team": selected_teams}
    )

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

# Use match_id index for fast filtering instead of scanning all rows
valid_match_ids = set(final_matches["match_id"].tolist())
final_deliveries = deliveries_df[deliveries_df["match_id"].isin(valid_match_ids)]

# For batting/bowling team filters, use precomputed player lists from cache
# instead of scanning delivery rows — just filter the cached stats by player name
# Filter deliveries to only rows where selected team is batting/bowling
# This ensures stats show ONLY that team's own players, not opposition
if eff_batting_teams:
    bat_deliveries = final_deliveries[final_deliveries["batting_team"].isin(eff_batting_teams)]
else:
    bat_deliveries = final_deliveries

if eff_bowling_teams:
    bowl_deliveries = final_deliveries[final_deliveries["bowling_team"].isin(eff_bowling_teams)]
else:
    bowl_deliveries = final_deliveries

# Precompute valid player sets once — used by all tabs below
# These are the team's OWN players only (batting_team = team → only their batters)
valid_bat_players  = set(bat_deliveries["striker"].dropna().unique()) if eff_batting_teams else None
valid_bowl_players = set(bowl_deliveries["bowler"].dropna().unique()) if eff_bowling_teams else None

# For player profile tab: union of both to get all squad members
valid_team_players = None
if selected_main_team:
    _bat_p  = valid_bat_players  or set()
    _bowl_p = valid_bowl_players or set(final_deliveries["bowler"].dropna().unique())
    valid_team_players = _bat_p | _bowl_p

# ── KPI Row ───────────────────────────────────────────────────────────────────
st.subheader("📊 Overview")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🏏 Matches", len(final_matches))
k2.metric("⚡ Total Deliveries", f"{len(final_deliveries):,}")
k3.metric("🏃 Total Runs", f"{int(final_deliveries['runs_off_bat'].sum() + final_deliveries['extras'].sum()):,}")
k4.metric("🎯 Total Wickets", f"{int(final_deliveries['wicket_type'].notna().sum()):,}")
k5.metric("🏟️ Venues", f"{final_matches['venue'].nunique()}")

# Data range row
if "date" in final_matches.columns:
    _dates = final_matches["date"].dropna().sort_values()
    if not _dates.empty:
        _earliest = _dates.iloc[0]
        _latest   = _dates.iloc[-1]
        _fmt = lambda d: pd.Timestamp(d).strftime("%d %b %Y") if pd.notna(d) else "—"
        dr1, dr2, dr3 = st.columns(3)
        dr1.markdown(f"📅 **Earliest match:** {_fmt(_earliest)}")
        dr2.markdown(f"📅 **Latest match:** {_fmt(_latest)}")
        dr3.markdown(f"📆 **Data span:** {int((_latest - _earliest).days / 365.25)} years")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏏 Batting Stats",
    "🎳 Bowling Stats",
    "🏅 MOM Analysis",
    "🏆 Team Stats",
    "📊 League Analysis",
    "👤 Player Profile",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BATTING
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("🏏 Batting Statistics")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        min_innings = st.number_input("Min Innings", min_value=1, value=3, step=1, key="min_inn")
    with col2:
        sort_by_bat = st.selectbox("Sort By", ["runs", "average", "strike_rate", "hundreds", "fifties", "innings"], key="sort_bat")
    with col3:
        use_pos_filter = st.toggle("🔢 Filter by Batting Position", value=False)
        if use_pos_filter:
            selected_positions = st.multiselect(
                "Position(s)",
                options=list(range(1, 12)),
                default=[1, 2],
                format_func=lambda x: f"#{x}",
            )
        else:
            selected_positions = []

    # Compute batting position: rank of first ball faced per innings per match
    bat_del = bat_deliveries.reset_index(drop=True).copy()
    if use_pos_filter and selected_positions:
        try:
            bat_del["ball_num"] = pd.to_numeric(bat_del["ball"], errors="coerce")
            # Get first ball each batter faced per match+innings
            legal = bat_del[bat_del["wides"] == 0][["match_id", "innings", "striker", "ball_num"]].copy()
            legal = legal.dropna(subset=["ball_num"])
            first_ball = (
                legal.sort_values("ball_num")
                .drop_duplicates(subset=["match_id", "innings", "striker"], keep="first")
                .reset_index(drop=True)
            )
            # Rank batters by their first ball in each innings = batting position
            first_ball["position"] = (
                first_ball.sort_values("ball_num")
                .groupby(["match_id", "innings"])["ball_num"]
                .rank(method="first")
                .astype(int)
            )
            valid_pairs = (
                first_ball[first_ball["position"].isin(selected_positions)]
                [["match_id", "innings", "striker"]]
            )
            bat_del = bat_del.merge(valid_pairs, on=["match_id", "innings", "striker"], how="inner")
        except Exception as e:
            st.warning(f"Position filter error: {e}")

    if use_pos_filter and selected_positions:
        # MUST recompute from position-filtered deliveries
        # Using cache here would show total career runs, not runs at that position
        batting_base = get_batting_stats(bat_del.reset_index(drop=True), min_innings=1)
    else:
        # No position filter — use precomputed cache (fast)
        batting_base = _cache["batting_all"].copy()

    # Apply batting team filter
    if valid_bat_players is not None:
        batting_base = batting_base[batting_base["player"].isin(valid_bat_players)]

    batting = batting_base[batting_base["innings"] >= min_innings].copy()
    batting = batting.sort_values(sort_by_bat, ascending=False).reset_index(drop=True)
    batting.index += 1

    if use_pos_filter and selected_positions:
        st.caption(f"📍 Stats at position(s) {', '.join(map(str, selected_positions))} only")

    col_th, col_dl = st.columns([6,1])
    with col_th:
        st.markdown(f"**Batters** — {len(batting)} players")
    with col_dl:
        st.download_button("⬇️ CSV", batting.to_csv(index=False), file_name="batting_stats.csv", mime="text/csv")
    st.dataframe(batting, use_container_width=True, height=500)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BOWLING
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("🎳 Bowling Statistics")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        min_overs = st.number_input("Min Overs", min_value=1, value=5, step=1, key="min_ovs")
        sort_by_bowl = st.selectbox("Sort By", ["wickets", "economy", "average", "bowling_sr", "overs"], key="sort_bowl")
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

    if use_over_filter and selected_overs:
        # MUST recompute from over-filtered deliveries
        # Cache has career totals — need stats only within selected overs
        bowling_base = get_bowling_stats(bowl_del.reset_index(drop=True), min_overs=1)
        # Apply team filter on top
        if valid_bowl_players is not None:
            bowling_base = bowling_base[bowling_base["player"].isin(valid_bowl_players)]
    else:
        # No over filter — use precomputed cache (fast)
        bowling_base = _cache["bowling_all"].copy()
        if valid_bowl_players is not None:
            bowling_base = bowling_base[bowling_base["player"].isin(valid_bowl_players)]

    bowling = bowling_base[bowling_base["overs"] >= min_overs].copy()
    bowling = bowling.sort_values(sort_by_bowl, ascending=sort_by_bowl in ["economy", "average", "bowling_sr"]).reset_index(drop=True)
    bowling.index += 1

    if use_over_filter and selected_overs:
        st.caption(f"🎯 Stats for overs: {', '.join(map(str, sorted(selected_overs)))}")

    col_th, col_dl = st.columns([6,1])
    with col_th:
        st.markdown(f"**Bowlers** — {len(bowling)} players")
    with col_dl:
        st.download_button("⬇️ CSV", bowling.to_csv(index=False), file_name="bowling_stats.csv", mime="text/csv")
    st.dataframe(bowling, use_container_width=True, height=500)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — PLAYER OF MATCH ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    import plotly.express as px

    st.subheader("🏅 Player of the Match Analysis")

    filtered_match_ids = set(final_matches["match_id"].tolist())
    match_detail = _cache["match_stats"].copy()
    match_detail = match_detail[match_detail["match_id"].isin(filtered_match_ids)]
    match_detail = match_detail[
        match_detail["player_of_match"].notna() &
        (match_detail["player_of_match"].astype(str).str.strip() != "")
    ]

    # For/Against toggle when team selected
    if selected_main_team:
        pom_mode = st.radio(
            "Show awards:",
            ["🏆 For (team players)", "⚔️ Against (opposition)", "📋 All"],
            horizontal=True, key="pom_mode"
        )
        team_players = valid_team_players or set()
        if "For" in pom_mode:
            match_detail = match_detail[match_detail["player_of_match"].isin(team_players)]
        elif "Against" in pom_mode:
            match_detail = match_detail[~match_detail["player_of_match"].isin(team_players)]

    if match_detail.empty:
        st.info("No Player of the Match data for current selection.")
        st.stop()

    # ── 1. Overall leaderboard ────────────────────────────────────────────────
    st.subheader("🥇 Overall Leaderboard")
    pom_counts = (
        match_detail["player_of_match"]
        .value_counts()
        .reset_index()
    )
    pom_counts.columns = ["player", "awards"]
    pom_counts.index   = range(1, len(pom_counts) + 1)

    col1, col2 = st.columns([2, 3])
    with col1:
        st.dataframe(pom_counts, use_container_width=True, height=400)
    with col2:
        fig_lb = px.bar(
            pom_counts.head(15), x="player", y="awards",
            color="awards", color_continuous_scale=["#1a3550","#1DB954"],
            text="awards", title="Top 15 Player of Match Winners"
        )
        fig_lb.update_layout(showlegend=False, xaxis_tickangle=-35,
                             plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                             font_color="white", coloraxis_showscale=False)
        fig_lb.update_traces(textposition="outside")
        st.plotly_chart(fig_lb, use_container_width=True)

    # ── 2. Player drill-down ──────────────────────────────────────────────────
    st.subheader("🔍 Player Deep Dive")
    player_list = pom_counts["player"].tolist()
    selected_pom_player = st.selectbox(
        "Select a player to see all their MOM details",
        options=[None] + player_list,
        format_func=lambda x: "— Select player —" if x is None else x,
        key="pom_player_select"
    )

    if selected_pom_player:
        player_awards = match_detail[match_detail["player_of_match"] == selected_pom_player].copy()

        # Determine opponent for each match
        def get_opponent(row, player_team_map):
            t = player_team_map.get(row["match_id"])
            if t is None: return "Unknown"
            return row["team2"] if row["team1"] == t else row["team1"]

        # 4-source team lookup for selected player
        _bat   = final_deliveries[final_deliveries["striker"]      == selected_pom_player][["match_id","batting_team"]].drop_duplicates("match_id").rename(columns={"batting_team":"t"})
        _nonst = final_deliveries[final_deliveries["non_striker"]   == selected_pom_player][["match_id","batting_team"]].drop_duplicates("match_id").rename(columns={"batting_team":"t"})
        _bowl  = final_deliveries[final_deliveries["bowler"]        == selected_pom_player][["match_id","bowling_team"]].drop_duplicates("match_id").rename(columns={"bowling_team":"t"})
        _dis   = pd.DataFrame()
        if "player_dismissed" in final_deliveries.columns:
            _dis = final_deliveries[final_deliveries["player_dismissed"] == selected_pom_player][["match_id","batting_team"]].drop_duplicates("match_id").rename(columns={"batting_team":"t"})
        _all_lu = pd.concat([_bat, _nonst, _dis, _bowl]).drop_duplicates("match_id", keep="first")
        pt_map = dict(zip(_all_lu["match_id"], _all_lu["t"]))
        player_awards["player_team"] = player_awards["match_id"].map(pt_map)
        player_awards["opponent"] = player_awards.apply(
            lambda r: r["team2"] if r["team1"] == r.get("player_team") else r["team1"], axis=1
        )

        total = len(player_awards)
        st.markdown(f"**{selected_pom_player}** has won **{total}** Player of the Match award{'s' if total != 1 else ''}")

        # KPI row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Awards", total)
        if "opponent" in player_awards.columns:
            best_opp = player_awards["opponent"].value_counts().idxmax() if not player_awards["opponent"].empty else "—"
            k2.metric("Most vs", best_opp)
        if "venue" in player_awards.columns:
            best_venue = player_awards["venue"].value_counts().idxmax() if not player_awards["venue"].empty else "—"
            k3.metric("Best Venue", best_venue[:20] + "..." if len(str(best_venue)) > 20 else best_venue)
        if "season" in player_awards.columns:
            best_season = player_awards["season"].value_counts().idxmax() if not player_awards["season"].empty else "—"
            k4.metric("Best Season", best_season)

        col_a, col_b, col_c = st.columns(3)

        # vs each opponent
        with col_a:
            st.markdown("**🆚 Awards vs Each Team**")
            if "opponent" in player_awards.columns:
                vs_opp = player_awards["opponent"].value_counts().reset_index()
                vs_opp.columns = ["opponent","awards"]
                vs_opp.index += 1
                st.dataframe(vs_opp, use_container_width=True, height=300)
                fig_opp = px.bar(vs_opp, x="opponent", y="awards",
                                 color="awards", color_continuous_scale=["#1a3550","#1DB954"],
                                 text="awards")
                fig_opp.update_layout(showlegend=False, xaxis_tickangle=-35,
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                      font_color="white", coloraxis_showscale=False)
                fig_opp.update_traces(textposition="outside")
                st.plotly_chart(fig_opp, use_container_width=True)

        # at each venue
        with col_b:
            st.markdown("**📍 Awards at Each Venue**")
            if "venue" in player_awards.columns:
                vs_venue = player_awards["venue"].value_counts().reset_index()
                vs_venue.columns = ["venue","awards"]
                vs_venue.index += 1
                st.dataframe(vs_venue, use_container_width=True, height=300)
                fig_ven = px.bar(vs_venue, x="venue", y="awards",
                                 color="awards", color_continuous_scale=["#1a3550","#00b4d8"],
                                 text="awards")
                fig_ven.update_layout(showlegend=False, xaxis_tickangle=-35,
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                      font_color="white", coloraxis_showscale=False)
                fig_ven.update_traces(textposition="outside")
                st.plotly_chart(fig_ven, use_container_width=True)

        # per season
        with col_c:
            st.markdown("**📅 Awards per Season**")
            if "season" in player_awards.columns:
                vs_season = player_awards["season"].value_counts().reset_index()
                vs_season.columns = ["season","awards"]
                vs_season = vs_season.sort_values("season").reset_index(drop=True)
                vs_season.index += 1
                st.dataframe(vs_season, use_container_width=True, height=300)
                fig_sea = px.bar(vs_season, x="season", y="awards",
                                 color="awards", color_continuous_scale=["#1a3550","#f59e0b"],
                                 text="awards")
                fig_sea.update_layout(showlegend=False, xaxis_tickangle=-35,
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                      font_color="white", coloraxis_showscale=False)
                fig_sea.update_traces(textposition="outside")
                st.plotly_chart(fig_sea, use_container_width=True)

        # ── Full match log ────────────────────────────────────────────────────
        st.subheader(f"📋 All {selected_pom_player} MOM Matches")
        safe_cols = [c for c in ["date","season","event","venue","team1","team2",
                                  "opponent","winner","toss_winner","toss_decision"] if c in player_awards.columns]
        st.dataframe(
            player_awards[safe_cols].sort_values("date", ascending=False).reset_index(drop=True),
            use_container_width=True, height=400
        )

    st.divider()

    # ── Build enriched MOM dataframe with opponent + team ─────────────────────
    # Get player's team per match from deliveries (safe — no merge issues)
    pom_enriched = match_detail.copy()
    # ── Build match_id → {player → team} from _info.csv squad lists ────────
    # Uses the players dict stored from _info.csv — exact squad per match
    # This is the MOST accurate source: Virat only in RCB matches, Rohit only in MI
    match_roster: dict = {}

    if "players" in final_matches.columns:
        for _, mrow in final_matches.iterrows():
            mid         = mrow["match_id"]
            squad_dict  = mrow.get("players", {})
            if not isinstance(squad_dict, dict):
                continue
            match_roster[mid] = {}
            for team, player_list in squad_dict.items():
                if isinstance(player_list, list):
                    for p in player_list:
                        if p and str(p).strip():
                            match_roster[mid][str(p).strip()] = team

    # Fallback from deliveries for matches where players dict is missing
    if not match_roster:
        for _, row in (
            final_deliveries[["match_id","striker","batting_team"]]
            .drop_duplicates(["match_id","striker"])
            .itertuples(index=False)
        ):
            if row.match_id not in match_roster:
                match_roster[row.match_id] = {}
            if row.striker not in match_roster[row.match_id]:
                match_roster[row.match_id][row.striker] = row.batting_team

    def _get_pom_team(row):
        player = row["player_of_match"]
        mid    = row["match_id"]
        t1     = str(row.get("team1", "") or "")
        t2     = str(row.get("team2", "") or "")
        found  = match_roster.get(mid, {}).get(player)
        if found in (t1, t2):
            return found
        # Try stripped name match
        for p, team in match_roster.get(mid, {}).items():
            if str(p).strip() == str(player).strip():
                return team
        return None

    pom_enriched["pom_team"] = pom_enriched.apply(_get_pom_team, axis=1)
    pom_enriched["opponent"] = pom_enriched.apply(
        lambda r: r["team2"] if str(r.get("team1","")) == str(r.get("pom_team","")) else r.get("team1",""), axis=1
    )

    st.divider()

    # ── helper: small styled bar chart ───────────────────────────────────────
    def _mini_bar(df, x, y, color):
        f = px.bar(df, x=x, y=y, color=y,
                   color_continuous_scale=["#1a3550", color],
                   text=y)
        f.update_layout(showlegend=False, xaxis_tickangle=-35,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color="white", coloraxis_showscale=False,
                        margin=dict(t=10,b=10,l=0,r=0))
        f.update_traces(textposition="outside")
        return f

    # ── 3. Most MOM FOR each team (top 5 players per team) ───────────────────
    st.subheader("🏆 Most MOM — For Each Team (Top 5 Players)")
    st.caption("Top 5 players with most MOM awards while playing FOR each team")

    if "pom_team" in pom_enriched.columns:
        teams_sorted = (
            pom_enriched["pom_team"].dropna().value_counts()
            .index.tolist()
        )
        rows = []
        for team in teams_sorted:
            tdf = pom_enriched[pom_enriched["pom_team"] == team]
            top5 = tdf["player_of_match"].value_counts().head(5).reset_index()
            top5.columns = ["player","awards"]
            top5["team"] = team
            rows.append(top5)

        if rows:
            for_team_df = pd.concat(rows, ignore_index=True)
            # Pivot style: team | rank1 | rank2...
            pivot_for = []
            for team in teams_sorted:
                tslice = for_team_df[for_team_df["team"]==team].reset_index(drop=True)
                row = {"Team": team}
                for i, r in tslice.iterrows():
                    row[f"#{i+1}"] = f"{r['player']} ({r['awards']})"
                pivot_for.append(row)
            pivot_for_df = pd.DataFrame(pivot_for).fillna("—")
            pivot_for_df.index += 1
            st.dataframe(pivot_for_df, use_container_width=True, height=320)

    # ── 4. Most MOM AGAINST each team (top 5 players) ────────────────────────
    st.divider()
    st.subheader("⚔️ Most MOM — Against Each Team (Top 5 Players)")
    st.caption("Top 5 players with most MOM awards when playing AGAINST each team")

    if "opponent" in pom_enriched.columns:
        opp_sorted = (
            pom_enriched["opponent"].dropna().value_counts()
            .index.tolist()
        )
        rows_ag = []
        for opp in opp_sorted:
            odf = pom_enriched[pom_enriched["opponent"] == opp]
            top5 = odf["player_of_match"].value_counts().head(5).reset_index()
            top5.columns = ["player","awards"]
            top5["opponent"] = opp
            rows_ag.append(top5)

        if rows_ag:
            against_df = pd.concat(rows_ag, ignore_index=True)
            pivot_ag = []
            for opp in opp_sorted:
                tslice = against_df[against_df["opponent"]==opp].reset_index(drop=True)
                row = {"Opponent": opp}
                for i, r in tslice.iterrows():
                    row[f"#{i+1}"] = f"{r['player']} ({r['awards']})"
                pivot_ag.append(row)
            pivot_ag_df = pd.DataFrame(pivot_ag).fillna("—")
            pivot_ag_df.index += 1
            st.dataframe(pivot_ag_df, use_container_width=True, height=320)

    # ── 5. Most MOM at each venue (top 5 players) ────────────────────────────
    st.divider()
    st.subheader("📍 Most MOM — At Each Venue (Top 5 Players)")
    st.caption("Top 5 players with most MOM awards at each venue")

    if "venue" in pom_enriched.columns:
        venues_sorted = (
            pom_enriched["venue"].dropna().value_counts()
            .index.tolist()
        )
        rows_v = []
        for venue in venues_sorted:
            vdf = pom_enriched[pom_enriched["venue"] == venue]
            top5 = vdf["player_of_match"].value_counts().head(5).reset_index()
            top5.columns = ["player","awards"]
            top5["venue"] = venue
            rows_v.append(top5)

        if rows_v:
            venue_df = pd.concat(rows_v, ignore_index=True)
            pivot_v = []
            for venue in venues_sorted:
                tslice = venue_df[venue_df["venue"]==venue].reset_index(drop=True)
                row = {"Venue": venue}
                for i, r in tslice.iterrows():
                    row[f"#{i+1}"] = f"{r['player']} ({r['awards']})"
                pivot_v.append(row)
            pivot_v_df = pd.DataFrame(pivot_v).fillna("—")
            pivot_v_df.index += 1
            st.dataframe(pivot_v_df, use_container_width=True, height=320)

    st.download_button(
        "⬇️ Download MOM Data CSV",
        pom_counts.to_csv(index=False),
        file_name="player_of_match.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — TEAM STATS
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    import plotly.express as px

    # Active teams for filtering
    active_teams = set()
    if "team1" in final_matches.columns: active_teams.update(final_matches["team1"].dropna().unique())
    if "team2" in final_matches.columns: active_teams.update(final_matches["team2"].dropna().unique())

    # ── Team selector for dashboard ───────────────────────────────────────────
    all_team_list = sorted(active_teams) if active_teams else sorted(
        list(deliveries_df["batting_team"].dropna().unique())
    )
    dashboard_team = st.selectbox(
        "🔍 Select a team for detailed dashboard (optional)",
        options=[None] + all_team_list,
        format_func=lambda x: "— View all teams overview —" if x is None else x,
        key="dashboard_team"
    )

    # ── OVERVIEW — shown always ───────────────────────────────────────────────
    st.subheader("🏆 Team Performance Overview")
    team_stats = _cache["team_stats"]
    if active_teams:
        team_stats = team_stats[team_stats["team"].isin(active_teams)]
    st.dataframe(team_stats, use_container_width=True, height=350)

    # ── TEAM DASHBOARD — shown when team selected ─────────────────────────────
    if dashboard_team:
        st.divider()
        st.subheader(f"📊 {dashboard_team} — Full Team Dashboard")

        # Filter deliveries and matches for this team
        tm_bat_del  = final_deliveries[final_deliveries["batting_team"]  == dashboard_team]
        tm_bowl_del = final_deliveries[final_deliveries["bowling_team"]  == dashboard_team]
        tm_matches  = final_matches[
            (final_matches["team1"] == dashboard_team) |
            (final_matches["team2"] == dashboard_team)
        ]

        # ── KPIs ─────────────────────────────────────────────────────────────
        tm_won    = int((tm_matches["winner"] == dashboard_team).sum()) if "winner" in tm_matches.columns else 0
        tm_played = len(tm_matches)
        tm_runs   = int(tm_bat_del["runs_off_bat"].sum() + tm_bat_del["extras"].sum())
        tm_wkts   = int(tm_bowl_del["wicket_type"].notna().sum())
        tm_winpct = round(tm_won / tm_played * 100, 1) if tm_played > 0 else 0

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Matches", tm_played)
        k2.metric("Won", tm_won)
        k3.metric("Win %", f"{tm_winpct}%")
        k4.metric("Runs Scored", f"{tm_runs:,}")
        k5.metric("Wickets Taken", f"{tm_wkts:,}")

        st.divider()

        # ── SUB TABS ──────────────────────────────────────────────────────────
        t1, t2, t3, t4, t5 = st.tabs([
            "🏏 Top Batters",
            "🎳 Top Bowlers",
            "📍 Venue Stats",
            "🆚 vs Each Team",
            "🪙 Toss & Bat Order",
        ])

        # ── TOP BATTERS ───────────────────────────────────────────────────────
        with t1:
            st.subheader(f"🏏 Top Run Scorers — {dashboard_team}")
            tm_bat_stats = get_batting_stats(tm_bat_del.reset_index(drop=True), min_innings=1)
            tm_bat_stats = tm_bat_stats.sort_values("runs", ascending=False).reset_index(drop=True)
            tm_bat_stats.index += 1

            col1, col2 = st.columns([3, 2])
            with col1:
                st.dataframe(tm_bat_stats, use_container_width=True, height=450)
            with col2:
                top10 = tm_bat_stats.head(10)
                fig = px.bar(top10, x="player", y="runs", color="runs",
                             color_continuous_scale=["#1a3550","#1DB954"],
                             text="runs", title="Top 10 Run Scorers")
                fig.update_layout(showlegend=False, xaxis_tickangle=-35,
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                  font_color="white", coloraxis_showscale=False)
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)

            st.download_button("⬇️ Download Batting CSV",
                tm_bat_stats.to_csv(index=False), file_name=f"{dashboard_team}_batting.csv")

        # ── TOP BOWLERS ───────────────────────────────────────────────────────
        with t2:
            st.subheader(f"🎳 Top Wicket Takers — {dashboard_team}")
            tm_bowl_stats = get_bowling_stats(tm_bowl_del.reset_index(drop=True), min_overs=1)
            tm_bowl_stats = tm_bowl_stats.sort_values("wickets", ascending=False).reset_index(drop=True)
            tm_bowl_stats.index += 1

            col1, col2 = st.columns([3, 2])
            with col1:
                st.dataframe(tm_bowl_stats, use_container_width=True, height=450)
            with col2:
                top10b = tm_bowl_stats.head(10)
                fig2 = px.bar(top10b, x="player", y="wickets", color="wickets",
                              color_continuous_scale=["#1a3550","#00b4d8"],
                              text="wickets", title="Top 10 Wicket Takers")
                fig2.update_layout(showlegend=False, xaxis_tickangle=-35,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                   font_color="white", coloraxis_showscale=False)
                fig2.update_traces(textposition="outside")
                st.plotly_chart(fig2, use_container_width=True)

            st.download_button("⬇️ Download Bowling CSV",
                tm_bowl_stats.to_csv(index=False), file_name=f"{dashboard_team}_bowling.csv")

        # ── VENUE STATS ───────────────────────────────────────────────────────
        with t3:
            st.subheader(f"📍 Venue Performance — {dashboard_team}")
            if "venue" in tm_matches.columns:
                venue_df = tm_matches.copy()
                venue_df["won"] = (venue_df["winner"] == dashboard_team).astype(int)
                venue_stats = (
                    venue_df.groupby("venue")
                    .agg(matches=("match_id","count"), won=("won","sum"))
                    .reset_index()
                )
                venue_stats["lost"]  = venue_stats["matches"] - venue_stats["won"]
                venue_stats["win_%"] = (venue_stats["won"] / venue_stats["matches"] * 100).round(1)
                venue_stats = venue_stats.sort_values("matches", ascending=False).reset_index(drop=True)
                venue_stats.index += 1

                col1, col2 = st.columns([2, 3])
                with col1:
                    st.dataframe(venue_stats, use_container_width=True, height=400)
                with col2:
                    fig3 = px.bar(venue_stats, x="venue", y=["won","lost"],
                                  barmode="stack",
                                  color_discrete_map={"won":"#1DB954","lost":"#e63946"},
                                  title="Won vs Lost at each Venue")
                    fig3.update_layout(xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)",
                                       paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    st.plotly_chart(fig3, use_container_width=True)

                # Runs at each venue
                if "venue" in tm_bat_del.columns:
                    v_runs = (
                        tm_bat_del.groupby("venue")
                        .agg(runs=("runs_off_bat","sum"), balls=("wides","count"))
                        .reset_index()
                    )
                    st.markdown("**Runs Scored at Each Venue**")
                    st.dataframe(v_runs.sort_values("runs", ascending=False).reset_index(drop=True),
                                 use_container_width=True, height=250)
            else:
                st.info("Venue data not available.")

        # ── VS EACH TEAM ──────────────────────────────────────────────────────
        with t4:
            st.subheader(f"🆚 {dashboard_team} vs Each Opponent")
            vs_df = tm_matches.copy()
            vs_df["opponent"] = vs_df.apply(
                lambda r: r["team2"] if r["team1"] == dashboard_team else r["team1"], axis=1
            )
            vs_df["won"] = (vs_df["winner"] == dashboard_team).astype(int)

            vs_stats = (
                vs_df.groupby("opponent")
                .agg(matches=("match_id","count"), won=("won","sum"))
                .reset_index()
            )
            vs_stats["lost"]  = vs_stats["matches"] - vs_stats["won"]
            vs_stats["win_%"] = (vs_stats["won"] / vs_stats["matches"] * 100).round(1)
            vs_stats = vs_stats.sort_values("matches", ascending=False).reset_index(drop=True)
            vs_stats.index += 1

            col1, col2 = st.columns([2, 3])
            with col1:
                st.dataframe(vs_stats, use_container_width=True, height=400)
            with col2:
                fig4 = px.bar(vs_stats, x="opponent", y="win_%",
                              color="win_%",
                              color_continuous_scale=["#e63946","#f59e0b","#1DB954"],
                              text="win_%", title="Win % vs Each Opponent")
                fig4.update_layout(showlegend=False, xaxis_tickangle=-35,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                   font_color="white", coloraxis_showscale=False)
                fig4.update_traces(textposition="outside")
                st.plotly_chart(fig4, use_container_width=True)

            st.download_button("⬇️ Download vs Teams CSV",
                vs_stats.to_csv(index=False), file_name=f"{dashboard_team}_vs_teams.csv")

        # ── TOSS & BAT ORDER ─────────────────────────────────────────────────
        with t5:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🪙 Toss Analysis")
                toss_tm = _cache["toss_stats"]
                toss_tm = toss_tm[toss_tm["toss_winner"] == dashboard_team]
                if not toss_tm.empty:
                    st.dataframe(toss_tm, use_container_width=True)
                    fig5 = px.pie(
                        toss_tm, values="toss_wins",
                        names="toss_winner",
                        title="Toss Decisions",
                        color_discrete_sequence=["#1DB954","#00b4d8"]
                    )
                    fig5.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    st.plotly_chart(fig5, use_container_width=True)

            with col2:
                st.subheader("🏏 Bat First vs Second")
                bat_ord_tm = _cache["bat_order_stats"]
                bat_ord_tm = bat_ord_tm[bat_ord_tm["team"] == dashboard_team]
                if not bat_ord_tm.empty:
                    st.dataframe(bat_ord_tm, use_container_width=True)
                    melt_tm = bat_ord_tm[["team","win%_bat_first","win%_bat_second"]].melt(
                        id_vars="team", var_name="method", value_name="win_%"
                    )
                    melt_tm["method"] = melt_tm["method"].map({
                        "win%_bat_first":"Bat First","win%_bat_second":"Bat Second"
                    })
                    fig6 = px.bar(melt_tm, x="method", y="win_%",
                                  color="method",
                                  color_discrete_map={"Bat First":"#1DB954","Bat Second":"#00b4d8"},
                                  text="win_%", title="Win % by Innings")
                    fig6.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                       paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                    fig6.update_traces(textposition="outside")
                    st.plotly_chart(fig6, use_container_width=True)

    else:
        # ── OVERVIEW CHARTS (no team selected) ───────────────────────────────
        st.subheader("🏏 Batting First vs Batting Second")
        bat_order = _cache["bat_order_stats"]
        if active_teams:
            bat_order = bat_order[bat_order["team"].isin(active_teams)]
        st.caption("Win records when batting first vs chasing")
        st.dataframe(bat_order, use_container_width=True, height=350)

        if not bat_order.empty:
            col1, col2 = st.columns(2)
            with col1:
                melt = bat_order[["team","win%_bat_first","win%_bat_second"]].melt(
                    id_vars="team", var_name="innings", value_name="win_%"
                )
                melt["innings"] = melt["innings"].map({"win%_bat_first":"Bat First","win%_bat_second":"Bat Second"})
                fig = px.bar(melt, x="team", y="win_%", color="innings", barmode="group",
                             color_discrete_map={"Bat First":"#1DB954","Bat Second":"#00b4d8"}, text_auto=".1f")
                fig.update_layout(xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                melt2 = bat_order[["team","bat_first","bat_second"]].melt(
                    id_vars="team", var_name="innings", value_name="matches"
                )
                melt2["innings"] = melt2["innings"].map({"bat_first":"Bat First","bat_second":"Bat Second"})
                fig2 = px.bar(melt2, x="team", y="matches", color="innings", barmode="group",
                              color_discrete_map={"Bat First":"#1DB954","Bat Second":"#00b4d8"}, text_auto=True)
                fig2.update_layout(xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)",
                                   paper_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig2, use_container_width=True)

        st.subheader("🪙 Toss Analysis")
        toss = _cache["toss_stats"]
        if active_teams:
            toss = toss[toss["toss_winner"].isin(active_teams)]
        st.dataframe(toss, use_container_width=True)

    st.download_button(
        "⬇️ Download Team Stats CSV",
        team_stats.to_csv(index=False),
        file_name="team_stats.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — LEAGUE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    import plotly.express as px
    st.subheader("📊 League Analysis")
    st.caption("Aggregated league-wide trends across all filtered matches")

    # ── Prepare phase-level data ──────────────────────────────────────────────
    del_df = final_deliveries.copy().reset_index(drop=True)
    del_df["ball_num"] = pd.to_numeric(del_df["ball"], errors="coerce")
    del_df["over_num"] = del_df["ball_num"].apply(
        lambda x: int(str(x).split(".")[0]) + 1 if pd.notna(x) else 0
    )
    del_df["phase"] = pd.cut(
        del_df["over_num"],
        bins=[0, 6, 15, 20, 999],
        labels=["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)", "Super (20+)"],
        right=True
    )
    del_df["total_runs"] = del_df["runs_off_bat"].fillna(0) + del_df["extras"].fillna(0)
    del_df["is_wicket"]  = del_df["wicket_type"].notna() & (del_df["wicket_type"] != "")
    del_df["is_legal"]   = (del_df["wides"] == 0) & (del_df["noballs"] == 0)

    # Per-innings aggregates
    inn_agg = (
        del_df.groupby(["match_id","innings"])
        .agg(
            runs    =("total_runs","sum"),
            wickets =("is_wicket","sum"),
            balls   =("is_legal","sum"),
        )
        .reset_index()
    )
    inn_agg = inn_agg.merge(
        final_matches[["match_id","winner","team1","team2"]],
        on="match_id", how="left"
    )
    # Identify batting team per innings
    bat_team = (
        del_df.groupby(["match_id","innings"])["batting_team"]
        .first().reset_index()
    )
    inn_agg = inn_agg.merge(bat_team, on=["match_id","innings"], how="left")
    inn_agg["won"] = inn_agg["batting_team"] == inn_agg["winner"]

    inn1 = inn_agg[pd.to_numeric(inn_agg["innings"], errors="coerce") == 1]
    inn2 = inn_agg[pd.to_numeric(inn_agg["innings"], errors="coerce") == 2]

    # ── KPI Row ───────────────────────────────────────────────────────────────
    st.subheader("🏏 Innings Averages")
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Avg 1st Inn Score",   f"{inn1['runs'].mean():.1f}"  if not inn1.empty else "—")
    c2.metric("Avg 1st Inn (Wins)",  f"{inn1[inn1['won']]['runs'].mean():.1f}" if not inn1[inn1["won"]].empty else "—")
    c3.metric("Avg 2nd Inn Score",   f"{inn2['runs'].mean():.1f}"  if not inn2.empty else "—")
    c4.metric("Avg 2nd Inn (Wins)",  f"{inn2[inn2['won']]['runs'].mean():.1f}" if not inn2[inn2["won"]].empty else "—")
    c5.metric("Highest 1st Inn",     f"{int(inn1['runs'].max())}"  if not inn1.empty else "—")
    c6.metric("Lowest 1st Inn",      f"{int(inn1['runs'].min())}"  if not inn1.empty else "—")

    # ── 1st inn score distribution ────────────────────────────────────────────
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📈 1st Innings Score Distribution**")
        fig_dist = px.histogram(
            inn1, x="runs", nbins=30,
            color_discrete_sequence=["#1DB954"],
            labels={"runs":"Score","count":"Matches"},
        )
        fig_dist.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_dist, use_container_width=True)
    with col2:
        st.markdown("**📊 Win % by 1st Innings Score Range**")
        inn1c = inn1.copy()
        inn1c["score_band"] = pd.cut(inn1c["runs"],
            bins=[0,120,140,160,180,200,999],
            labels=["<120","120-140","140-160","160-180","180-200","200+"])
        win_by_band = (
            inn1c.groupby("score_band", observed=True)
            .agg(matches=("match_id","count"), wins=("won","sum"))
            .reset_index()
        )
        win_by_band["win_%"] = (win_by_band["wins"]/win_by_band["matches"]*100).round(1)
        fig_band = px.bar(win_by_band, x="score_band", y="win_%",
                          color="win_%",
                          color_continuous_scale=["#e63946","#f59e0b","#1DB954"],
                          text="win_%",
                          labels={"score_band":"Score Range","win_%":"Win %"})
        fig_band.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                               coloraxis_showscale=False)
        fig_band.update_traces(textposition="outside")
        st.plotly_chart(fig_band, use_container_width=True)

    # ── Phase analysis ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Phase-wise Analysis (All Matches)")

    phase_agg = (
        del_df[del_df["phase"].notna()]
        .groupby("phase", observed=True)
        .agg(
            total_runs  =("total_runs","sum"),
            total_balls =("is_legal","sum"),
            total_wkts  =("is_wicket","sum"),
            matches     =("match_id","nunique"),
        )
        .reset_index()
    )
    phase_agg["avg_runs_per_match"]  = (phase_agg["total_runs"]  / phase_agg["matches"]).round(1)
    phase_agg["avg_wkts_per_match"]  = (phase_agg["total_wkts"]  / phase_agg["matches"]).round(2)
    phase_agg["run_rate"]            = (phase_agg["total_runs"]  / phase_agg["total_balls"] * 6).round(2).where(phase_agg["total_balls"]>0, 0)
    phase_agg["wkt_every_n_balls"]   = (phase_agg["total_balls"] / phase_agg["total_wkts"]).round(1).where(phase_agg["total_wkts"]>0, 0)
    phase_agg = phase_agg[phase_agg["phase"] != "Super (20+)"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**💨 Avg Runs per Match by Phase**")
        fig_pr = px.bar(phase_agg, x="phase", y="avg_runs_per_match",
                        color="phase",
                        color_discrete_sequence=["#1DB954","#00b4d8","#e63946"],
                        text="avg_runs_per_match")
        fig_pr.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_pr.update_traces(textposition="outside")
        st.plotly_chart(fig_pr, use_container_width=True)
    with col2:
        st.markdown("**🎳 Avg Wickets per Match by Phase**")
        fig_pw = px.bar(phase_agg, x="phase", y="avg_wkts_per_match",
                        color="phase",
                        color_discrete_sequence=["#1DB954","#00b4d8","#e63946"],
                        text="avg_wkts_per_match")
        fig_pw.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_pw.update_traces(textposition="outside")
        st.plotly_chart(fig_pw, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**📈 Run Rate by Phase**")
        fig_rr = px.bar(phase_agg, x="phase", y="run_rate",
                        color="phase",
                        color_discrete_sequence=["#1DB954","#00b4d8","#e63946"],
                        text="run_rate")
        fig_rr.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_rr.update_traces(textposition="outside")
        st.plotly_chart(fig_rr, use_container_width=True)
    with col4:
        st.markdown("**⚡ 1 Wicket Every N Balls by Phase**")
        fig_wb = px.bar(phase_agg, x="phase", y="wkt_every_n_balls",
                        color="phase",
                        color_discrete_sequence=["#1DB954","#00b4d8","#e63946"],
                        text="wkt_every_n_balls")
        fig_wb.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_wb.update_traces(textposition="outside")
        st.plotly_chart(fig_wb, use_container_width=True)

    # Phase table
    st.dataframe(
        phase_agg[["phase","avg_runs_per_match","run_rate","avg_wkts_per_match","wkt_every_n_balls"]]
        .rename(columns={
            "phase":"Phase",
            "avg_runs_per_match":"Avg Runs/Match",
            "run_rate":"Run Rate",
            "avg_wkts_per_match":"Avg Wkts/Match",
            "wkt_every_n_balls":"Balls/Wicket",
        }),
        use_container_width=True, hide_index=True
    )

    # ── Over-by-over run rate ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📉 Over-by-Over Run Rate")
    over_agg = (
        del_df[del_df["over_num"].between(1,20)]
        .groupby("over_num")
        .agg(
            runs  =("total_runs","sum"),
            balls =("is_legal","sum"),
            wkts  =("is_wicket","sum"),
            match_count=("match_id","nunique"),
        )
        .reset_index()
    )
    over_agg["run_rate"]      = (over_agg["runs"] / over_agg["balls"] * 6).round(2).where(over_agg["balls"]>0,0)
    over_agg["avg_runs"]      = (over_agg["runs"] / over_agg["match_count"]).round(1)
    over_agg["avg_wkts"]      = (over_agg["wkts"] / over_agg["match_count"]).round(2)

    col1, col2 = st.columns(2)
    with col1:
        fig_or = px.line(over_agg, x="over_num", y="run_rate", markers=True,
                         color_discrete_sequence=["#1DB954"],
                         labels={"over_num":"Over","run_rate":"Run Rate"},
                         title="Run Rate per Over")
        fig_or.add_vline(x=6.5,  line_dash="dash", line_color="#8b949e", annotation_text="PP end")
        fig_or.add_vline(x=15.5, line_dash="dash", line_color="#8b949e", annotation_text="Middle end")
        fig_or.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_or, use_container_width=True)
    with col2:
        fig_ow = px.bar(over_agg, x="over_num", y="avg_wkts",
                        color="avg_wkts",
                        color_continuous_scale=["#1a3550","#e63946"],
                        labels={"over_num":"Over","avg_wkts":"Avg Wickets"},
                        title="Avg Wickets per Over")
        fig_ow.add_vline(x=6.5,  line_dash="dash", line_color="#8b949e")
        fig_ow.add_vline(x=15.5, line_dash="dash", line_color="#8b949e")
        fig_ow.update_layout(showlegend=False, coloraxis_showscale=False,
                             plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_ow, use_container_width=True)

    # ── Toss & Venue ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🪙 Toss Impact & Venue Trends")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Toss Decision → Win Rate**")
        if "toss_decision" in final_matches.columns and "winner" in final_matches.columns:
            toss_win = final_matches.copy()
            toss_win["toss_won_match"] = toss_win["toss_winner"] == toss_win["winner"]
            td = toss_win.groupby("toss_decision").agg(
                matches=("match_id","count"),
                wins=("toss_won_match","sum")
            ).reset_index()
            td["win_%"] = (td["wins"]/td["matches"]*100).round(1)
            fig_td = px.bar(td, x="toss_decision", y="win_%",
                            color="toss_decision",
                            color_discrete_map={"bat":"#1DB954","field":"#00b4d8"},
                            text="win_%", title="Win % after Toss Decision")
            fig_td.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            fig_td.update_traces(textposition="outside")
            st.plotly_chart(fig_td, use_container_width=True)

    with col2:
        st.markdown("**Avg 1st Innings Score by Venue**")
        if "venue" in del_df.columns or "venue" in inn1.columns:
            inn1v = inn1.merge(
                final_matches[["match_id","venue"]].drop_duplicates(), on="match_id", how="left"
            )
            venue_avg = (
                inn1v.groupby("venue")["runs"]
                .agg(avg="mean", count="count")
                .reset_index()
            )
            venue_avg = venue_avg[venue_avg["count"] >= 3].sort_values("avg", ascending=False)
            venue_avg["avg"] = venue_avg["avg"].round(1)
            fig_va = px.bar(venue_avg, x="venue", y="avg",
                            color="avg",
                            color_continuous_scale=["#1a3550","#f59e0b"],
                            text="avg", title="Avg 1st Inn Score by Venue (min 3 matches)")
            fig_va.update_layout(showlegend=False, xaxis_tickangle=-35,
                                  coloraxis_showscale=False,
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            fig_va.update_traces(textposition="outside")
            st.plotly_chart(fig_va, use_container_width=True)

    # ── Season trends ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📅 Season-by-Season Trends")
    if "season" in final_matches.columns:
        season_del = del_df.merge(
            final_matches[["match_id","season"]], on="match_id", how="left"
        )
        season_agg = (
            season_del.groupby("season")
            .agg(
                runs    =("total_runs","sum"),
                wickets =("is_wicket","sum"),
                matches =("match_id","nunique"),
                balls   =("is_legal","sum"),
            )
            .reset_index()
            .sort_values("season")
        )
        season_agg["avg_score"]   = (season_agg["runs"] / season_agg["matches"] / 2).round(1)
        season_agg["run_rate"]    = (season_agg["runs"] / season_agg["balls"] * 6).round(2)
        season_agg["avg_wkts"]    = (season_agg["wickets"] / season_agg["matches"] / 2).round(2)

        col1, col2, col3 = st.columns(3)
        with col1:
            fig_sa = px.line(season_agg, x="season", y="avg_score", markers=True,
                             color_discrete_sequence=["#1DB954"],
                             title="Avg Innings Score per Season")
            fig_sa.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", xaxis_tickangle=-45)
            st.plotly_chart(fig_sa, use_container_width=True)
        with col2:
            fig_rrs = px.line(season_agg, x="season", y="run_rate", markers=True,
                              color_discrete_sequence=["#00b4d8"],
                              title="Run Rate per Season")
            fig_rrs.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", xaxis_tickangle=-45)
            st.plotly_chart(fig_rrs, use_container_width=True)
        with col3:
            fig_ws = px.line(season_agg, x="season", y="avg_wkts", markers=True,
                             color_discrete_sequence=["#e63946"],
                             title="Avg Wickets per Innings per Season")
            fig_ws.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", xaxis_tickangle=-45)
            st.plotly_chart(fig_ws, use_container_width=True)

    st.download_button(
        "⬇️ Download Phase Analysis CSV",
        phase_agg.to_csv(index=False),
        file_name="league_phase_analysis.csv",
        mime="text/csv",
    )

# TAB 5 — LEAGUE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    import plotly.express as px
    st.subheader("📊 League Analysis")
    st.caption("Aggregated league-wide trends across all filtered matches")

    del_df = final_deliveries.copy().reset_index(drop=True)
    del_df["ball_num"] = pd.to_numeric(del_df["ball"], errors="coerce")
    del_df["over_num"] = del_df["ball_num"].apply(
        lambda x: int(str(x).split(".")[0]) + 1 if pd.notna(x) else 0
    )
    del_df["phase"] = pd.cut(
        del_df["over_num"], bins=[0,6,15,20,999],
        labels=["Powerplay (1-6)","Middle (7-15)","Death (16-20)","Super (20+)"], right=True
    )
    del_df["total_runs"] = del_df["runs_off_bat"].fillna(0) + del_df["extras"].fillna(0)
    del_df["is_wicket"]  = del_df["wicket_type"].notna() & (del_df["wicket_type"] != "")
    del_df["is_legal"]   = (del_df["wides"] == 0) & (del_df["noballs"] == 0)

    inn_agg = (
        del_df.groupby(["match_id","innings"])
        .agg(runs=("total_runs","sum"), wickets=("is_wicket","sum"), balls=("is_legal","sum"))
        .reset_index()
    )
    inn_agg = inn_agg.merge(final_matches[["match_id","winner","team1","team2"]], on="match_id", how="left")
    bat_team = del_df.groupby(["match_id","innings"])["batting_team"].first().reset_index()
    inn_agg  = inn_agg.merge(bat_team, on=["match_id","innings"], how="left")
    inn_agg["won"] = inn_agg["batting_team"] == inn_agg["winner"]
    inn1 = inn_agg[pd.to_numeric(inn_agg["innings"], errors="coerce") == 1]
    inn2 = inn_agg[pd.to_numeric(inn_agg["innings"], errors="coerce") == 2]

    # KPIs
    st.subheader("🏏 Innings Averages")
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Avg 1st Inn Score",  f"{inn1['runs'].mean():.1f}"  if not inn1.empty else "—")
    c2.metric("Avg 1st Inn (Wins)", f"{inn1[inn1['won']]['runs'].mean():.1f}" if not inn1[inn1['won']].empty else "—")
    c3.metric("Avg 2nd Inn Score",  f"{inn2['runs'].mean():.1f}"  if not inn2.empty else "—")
    c4.metric("Avg 2nd Inn (Wins)", f"{inn2[inn2['won']]['runs'].mean():.1f}" if not inn2[inn2['won']].empty else "—")
    c5.metric("Highest 1st Inn",    f"{int(inn1['runs'].max())}"  if not inn1.empty else "—")
    c6.metric("Lowest 1st Inn",     f"{int(inn1['runs'].min())}"  if not inn1.empty else "—")

    # Score distribution + win % by band
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📈 1st Innings Score Distribution**")
        fig_dist = px.histogram(inn1, x="runs", nbins=30, color_discrete_sequence=["#1DB954"])
        fig_dist.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_dist, use_container_width=True)
    with col2:
        st.markdown("**📊 Win % by 1st Innings Score Range**")
        inn1c = inn1.copy()
        inn1c["score_band"] = pd.cut(inn1c["runs"], bins=[0,120,140,160,180,200,999],
            labels=["<120","120-140","140-160","160-180","180-200","200+"])
        wb = inn1c.groupby("score_band", observed=True).agg(
            matches=("match_id","count"), wins=("won","sum")).reset_index()
        wb["win_%"] = (wb["wins"]/wb["matches"]*100).round(1)
        fig_band = px.bar(wb, x="score_band", y="win_%", color="win_%",
                          color_continuous_scale=["#e63946","#f59e0b","#1DB954"], text="win_%")
        fig_band.update_layout(showlegend=False, coloraxis_showscale=False,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_band.update_traces(textposition="outside")
        st.plotly_chart(fig_band, use_container_width=True)

    # Phase analysis
    st.divider()
    st.subheader("🎯 Phase-wise Analysis")
    phase_agg = (
        del_df[del_df["phase"].notna() & (del_df["phase"] != "Super (20+)")]
        .groupby("phase", observed=True)
        .agg(total_runs=("total_runs","sum"), total_balls=("is_legal","sum"),
             total_wkts=("is_wicket","sum"), matches=("match_id","nunique"))
        .reset_index()
    )
    phase_agg["avg_runs_per_match"] = (phase_agg["total_runs"]/phase_agg["matches"]).round(1)
    phase_agg["avg_wkts_per_match"] = (phase_agg["total_wkts"]/phase_agg["matches"]).round(2)
    phase_agg["run_rate"]           = (phase_agg["total_runs"]/phase_agg["total_balls"]*6).round(2).where(phase_agg["total_balls"]>0,0)
    phase_agg["balls_per_wicket"]   = (phase_agg["total_balls"]/phase_agg["total_wkts"]).round(1).where(phase_agg["total_wkts"]>0,0)

    col1,col2,col3,col4 = st.columns(4)
    COLORS3 = ["#1DB954","#00b4d8","#e63946"]
    for col, metric, title in [
        (col1,"avg_runs_per_match","Avg Runs/Match"),
        (col2,"run_rate","Run Rate"),
        (col3,"avg_wkts_per_match","Avg Wkts/Match"),
        (col4,"balls_per_wicket","Balls/Wicket"),
    ]:
        with col:
            fig = px.bar(phase_agg, x="phase", y=metric, color="phase",
                         color_discrete_sequence=COLORS3, text=metric, title=title)
            fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

    st.dataframe(phase_agg[["phase","avg_runs_per_match","run_rate","avg_wkts_per_match","balls_per_wicket"]]
        .rename(columns={"phase":"Phase","avg_runs_per_match":"Avg Runs/Match",
                         "run_rate":"Run Rate","avg_wkts_per_match":"Avg Wkts/Match",
                         "balls_per_wicket":"Balls/Wicket"}),
        use_container_width=True, hide_index=True)

    # Over-by-over
    st.divider()
    st.subheader("📉 Over-by-Over Trends")
    ov_agg = (
        del_df[del_df["over_num"].between(1,20)]
        .groupby("over_num")
        .agg(runs=("total_runs","sum"), balls=("is_legal","sum"),
             wkts=("is_wicket","sum"), mc=("match_id","nunique"))
        .reset_index()
    )
    ov_agg["run_rate"] = (ov_agg["runs"]/ov_agg["balls"]*6).round(2).where(ov_agg["balls"]>0,0)
    ov_agg["avg_wkts"] = (ov_agg["wkts"]/ov_agg["mc"]).round(3)
    col1, col2 = st.columns(2)
    with col1:
        fig_or = px.line(ov_agg, x="over_num", y="run_rate", markers=True,
                         color_discrete_sequence=["#1DB954"], title="Run Rate per Over")
        fig_or.add_vline(x=6.5,  line_dash="dash", line_color="#8b949e", annotation_text="PP end")
        fig_or.add_vline(x=15.5, line_dash="dash", line_color="#8b949e", annotation_text="Death start")
        fig_or.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_or, use_container_width=True)
    with col2:
        fig_ow = px.bar(ov_agg, x="over_num", y="avg_wkts", color="avg_wkts",
                        color_continuous_scale=["#1a3550","#e63946"], title="Avg Wickets per Over")
        fig_ow.add_vline(x=6.5,  line_dash="dash", line_color="#8b949e")
        fig_ow.add_vline(x=15.5, line_dash="dash", line_color="#8b949e")
        fig_ow.update_layout(showlegend=False, coloraxis_showscale=False,
                             plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig_ow, use_container_width=True)

    # Toss + Venue
    st.divider()
    st.subheader("🪙 Toss & Venue Analysis")
    col1, col2 = st.columns(2)
    with col1:
        if "toss_decision" in final_matches.columns and "winner" in final_matches.columns:
            tw = final_matches.copy()
            tw["toss_won_match"] = tw["toss_winner"] == tw["winner"]
            td = tw.groupby("toss_decision").agg(matches=("match_id","count"),wins=("toss_won_match","sum")).reset_index()
            td["win_%"] = (td["wins"]/td["matches"]*100).round(1)
            fig_td = px.bar(td, x="toss_decision", y="win_%", color="toss_decision",
                            color_discrete_map={"bat":"#1DB954","field":"#00b4d8"}, text="win_%",
                            title="Win % after Toss Decision")
            fig_td.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                  paper_bgcolor="rgba(0,0,0,0)", font_color="white")
            fig_td.update_traces(textposition="outside")
            st.plotly_chart(fig_td, use_container_width=True)
    with col2:
        inn1v = inn1.merge(final_matches[["match_id","venue"]].drop_duplicates(), on="match_id", how="left")
        va = inn1v.groupby("venue")["runs"].agg(avg="mean",count="count").reset_index()
        va = va[va["count"] >= 3].sort_values("avg", ascending=False)
        va["avg"] = va["avg"].round(1)
        fig_va = px.bar(va, x="venue", y="avg", color="avg",
                        color_continuous_scale=["#1a3550","#f59e0b"], text="avg",
                        title="Avg 1st Inn Score by Venue (min 3 matches)")
        fig_va.update_layout(showlegend=False, xaxis_tickangle=-35, coloraxis_showscale=False,
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        fig_va.update_traces(textposition="outside")
        st.plotly_chart(fig_va, use_container_width=True)

    # Season trends
    st.divider()
    st.subheader("📅 Season-by-Season Trends")
    if "season" in final_matches.columns:
        sd = del_df.merge(final_matches[["match_id","season"]], on="match_id", how="left")
        sa = sd.groupby("season").agg(
            runs=("total_runs","sum"), wickets=("is_wicket","sum"),
            matches=("match_id","nunique"), balls=("is_legal","sum")
        ).reset_index().sort_values("season")
        sa["avg_score"] = (sa["runs"]/sa["matches"]/2).round(1)
        sa["run_rate"]  = (sa["runs"]/sa["balls"]*6).round(2)
        sa["avg_wkts"]  = (sa["wickets"]/sa["matches"]/2).round(2)
        col1,col2,col3 = st.columns(3)
        for col, y, color, title in [
            (col1,"avg_score","#1DB954","Avg Innings Score"),
            (col2,"run_rate","#00b4d8","Run Rate"),
            (col3,"avg_wkts","#e63946","Avg Wickets/Inn"),
        ]:
            with col:
                fig = px.line(sa, x="season", y=y, markers=True,
                              color_discrete_sequence=[color], title=title)
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                  font_color="white", xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

    st.download_button("⬇️ Download Phase CSV", phase_agg.to_csv(index=False),
                       file_name="league_analysis.csv", mime="text/csv")

# TAB 6 — PLAYER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    st.subheader("👤 Player Profile")

    # Precompute ALL player profiles once — cached by data size so recomputes
    # only when filters change. Individual lookups are then instant (dict key).
    # Instant — loaded from cache computed at upload time
    all_profiles = _cache["all_profiles"]

    # Filter player list to selected main team if active
    if valid_team_players is not None:
        all_players = sorted([p for p in all_profiles.keys() if p in valid_team_players])
    else:
        all_players = sorted(all_profiles.keys())

    if not all_players:
        st.info("No player data available with current filters.")
    else:
        col_search, col_role = st.columns([3, 1])
        with col_search:
            selected_player = st.selectbox(
                "🔍 Search Player",
                options=[None] + all_players,
                format_func=lambda x: "— Type or select a player —" if x is None else x,
                index=0,
            )
        with col_role:
            show_role = st.radio("Show Stats For", ["Both", "Batting Only", "Bowling Only"], horizontal=True)

        if selected_player is None:
            st.info("👆 Select a player above to view their full profile.")
        else:
            # Instant lookup — no computation needed
            profile = all_profiles.get(selected_player, {})

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
                st.subheader("🏏 Batting")

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

                    # ── Batting Position Breakdown ────────────────────────
                    if show_role in ("Batting Only",):
                        st.subheader("📊 Stats by Batting Position")
                        pos_stats = bat.get("position_stats", pd.DataFrame())
                        if not pos_stats.empty:
                            pos_stats.index = pos_stats["position"]
                            pos_display = pos_stats.drop(columns=["position"]).rename(columns={
                                "innings":      "Innings",
                                "runs":         "Runs",
                                "highest":      "Highest",
                                "average":      "Average",
                                "strike_rate":  "Strike Rate",
                                "balls":        "Balls",
                                "not_outs":     "Not Outs",
                            })
                            col_pos1, col_pos2 = st.columns([2, 2])
                            with col_pos1:
                                st.caption("Stats computed only from innings batted at each position")
                                st.dataframe(pos_display, use_container_width=True, height=350)
                            with col_pos2:
                                import plotly.express as px
                                fig_pos = px.bar(
                                    pos_stats, x="position", y="runs",
                                    color="average",
                                    color_continuous_scale=["#1a3550","#1DB954"],
                                    text="runs",
                                    title="Runs by Batting Position",
                                    labels={"position":"Position","runs":"Runs","average":"Avg"},
                                    category_orders={"position": sorted(pos_stats["position"].tolist())},
                                )
                                fig_pos.update_layout(
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    font_color="white",
                                    xaxis=dict(tickmode="linear", dtick=1),
                                )
                                fig_pos.update_traces(textposition="outside")
                                st.plotly_chart(fig_pos, use_container_width=True)

                                # SR by position
                                fig_sr = px.bar(
                                    pos_stats, x="position", y="strike_rate",
                                    color="strike_rate",
                                    color_continuous_scale=["#1a3550","#00b4d8"],
                                    text="strike_rate",
                                    title="Strike Rate by Batting Position",
                                    labels={"position":"Position","strike_rate":"SR"},
                                )
                                fig_sr.update_layout(
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    font_color="white",
                                    xaxis=dict(tickmode="linear", dtick=1),
                                )
                                fig_sr.update_traces(textposition="outside")
                                st.plotly_chart(fig_sr, use_container_width=True)
                        else:
                            st.info("No position data available.")

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
                    # ── Top 10 Innings ────────────────────────────────────
                    st.subheader("🏆 Top 10 Innings")
                    top_inn = bat.get("top_innings", pd.DataFrame())
                    if not top_inn.empty:
                        top_inn.index += 1
                        st.dataframe(top_inn, use_container_width=True, height=380)
                    else:
                        st.info("No innings data available.")

                    # ── Partnership Analysis ──────────────────────────────
                    st.subheader("🤝 Partnership Analysis")
                    partnerships = bat.get("partnerships", pd.DataFrame())
                    if not partnerships.empty:
                        # Min runs filter
                        p_col1, p_col2 = st.columns([1, 3])
                        with p_col1:
                            min_p_runs = st.number_input(
                                "Min Total Runs together",
                                min_value=0, value=50, step=10,
                                key="min_p_runs"
                            )
                        # Apply filter + sort by avg descending
                        p_filtered = (
                            partnerships[partnerships["total_runs"] >= min_p_runs]
                            .sort_values("avg", ascending=False)
                            .reset_index(drop=True)
                        )
                        p_filtered.index += 1

                        col_p1, col_p2 = st.columns([2, 1])
                        with col_p1:
                            st.caption(f"{len(p_filtered)} partners with ≥ {min_p_runs} runs together — sorted by Avg ↓")
                            st.dataframe(
                                p_filtered.rename(columns={
                                    "partner":      "Partner",
                                    "partnerships": "Innings",
                                    "total_runs":   "Total Runs",
                                    "avg":          "Avg ↓",
                                    "best":         "Best Stand",
                                    "sr":           "SR",
                                }),
                                use_container_width=True,
                                height=400,
                            )
                        with col_p2:
                            import plotly.express as px
                            top_p = p_filtered.head(10).copy()
                            fig_p = px.bar(
                                top_p, x="partner", y="avg",
                                color="avg",
                                color_continuous_scale=["#1a3550","#1DB954"],
                                text="avg",
                                title="Top 10 by Avg",
                                labels={"partner":"Partner","avg":"Avg"},
                            )
                            fig_p.update_layout(
                                showlegend=False, xaxis_tickangle=-35,
                                plot_bgcolor="rgba(0,0,0,0)",
                                paper_bgcolor="rgba(0,0,0,0)",
                                font_color="white",
                                coloraxis_showscale=False,
                            )
                            fig_p.update_traces(textposition="outside")
                            st.plotly_chart(fig_p, use_container_width=True)
                    else:
                        st.info("No partnership data available.")

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
                st.subheader("🎳 Bowling")

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

                    # ── Top 10 Bowling Figures ────────────────────────────
                    st.subheader("🏆 Top 10 Bowling Figures")
                    top_fig = bowl.get("top_figures", pd.DataFrame())
                    if not top_fig.empty:
                        top_fig.index += 1
                        st.dataframe(top_fig, use_container_width=True, height=380)
                    else:
                        st.info("No bowling figures data available.")

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
            st.subheader("🏅 Player of the Match")

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
