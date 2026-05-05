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
    plot_runs_per_season,
    plot_wickets_per_season,
    plot_win_by_method,
    plot_toss_impact,
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

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');

    /* ── Global ── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #080b12; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1117 0%, #0a0e1a 100%);
        border-right: 1px solid #1a2332;
    }
    section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #58a6ff !important;
        font-size: 0.85rem !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 700 !important;
    }

    /* ── Hero Header ── */
    .hero-wrapper {
        background: linear-gradient(135deg, #0d1117 0%, #0f1923 50%, #0d1117 100%);
        border-bottom: 1px solid #1a2332;
        padding: 2.5rem 2rem 1.5rem 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .hero-wrapper::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(ellipse at center, rgba(29,185,84,0.06) 0%, transparent 60%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(135deg, #1DB954 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -1px;
        line-height: 1.1;
        margin-bottom: 0.5rem;
    }
    .hero-sub {
        color: #8b949e;
        font-size: 0.95rem;
        font-weight: 400;
        margin-bottom: 0.8rem;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(29,185,84,0.1);
        border: 1px solid rgba(29,185,84,0.3);
        border-radius: 20px;
        padding: 0.3rem 1rem;
        font-size: 0.85rem;
        color: #1DB954;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .linkedin-link {
        color: #58a6ff !important;
        text-decoration: none;
        font-size: 0.85rem;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        transition: color 0.2s;
    }

    /* ── KPI Cards ── */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #0d1f2d 0%, #0a1628 100%);
        border: 1px solid #1a3550;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(29,185,84,0.15);
        border-color: rgba(29,185,84,0.3);
    }
    div[data-testid="metric-container"] label {
        color: #8b949e !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600 !important;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.9rem !important;
        font-weight: 800 !important;
    }

    /* ── Section Headers ── */
    .section-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        padding: 0.6rem 0 0.6rem 1rem;
        margin: 1.8rem 0 1rem 0;
        border-left: 3px solid #1DB954;
        background: linear-gradient(90deg, rgba(29,185,84,0.08) 0%, transparent 100%);
        border-radius: 0 8px 8px 0;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #0d1117;
        border-bottom: 1px solid #1a2332;
        gap: 0;
        padding: 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #8b949e;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.75rem 1.2rem;
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
        letter-spacing: 0.3px;
    }
    .stTabs [aria-selected="true"] {
        color: #1DB954 !important;
        border-bottom: 2px solid #1DB954 !important;
        background: rgba(29,185,84,0.05) !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #ffffff !important;
        background: rgba(255,255,255,0.04) !important;
    }

    /* ── DataFrames ── */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        border: 1px solid #1a2332;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #1DB954 0%, #17a349 100%);
        color: #000000;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
        font-size: 0.9rem;
        transition: all 0.2s;
        box-shadow: 0 4px 15px rgba(29,185,84,0.3);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(29,185,84,0.5);
        background: linear-gradient(135deg, #22d160 0%, #1DB954 100%);
    }

    /* ── Expanders ── */
    .streamlit-expanderHeader {
        background: #0d1f2d !important;
        border: 1px solid #1a3550 !important;
        border-radius: 8px !important;
        color: #c9d1d9 !important;
        font-weight: 600 !important;
    }

    /* ── Selectboxes & Multiselects ── */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background: #0d1f2d !important;
        border: 1px solid #1a3550 !important;
        border-radius: 8px !important;
        color: #c9d1d9 !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #1DB954, #00d4ff) !important;
        border-radius: 4px;
    }

    /* ── Progress label ── */
    .progress-label {
        font-size: 0.95rem;
        color: #c9d1d9;
        font-weight: 500;
        padding: 0.4rem 0;
    }

    /* ── Toggle ── */
    .stToggle label { color: #c9d1d9 !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0d1117; }
    ::-webkit-scrollbar-thumb { background: #1a3550; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #1DB954; }

    /* ── Hide Streamlit branding ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 0 !important; max-width: 100% !important; }

    /* ── Filter Panel ── */
    .filter-panel {
        background: linear-gradient(135deg, #0d1f2d 0%, #0a1628 100%);
        border: 1px solid #1a3550;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .filter-label {
        font-size: 0.72rem;
        font-weight: 700;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 0.3rem;
    }

    /* ── Stat Cards Row ── */
    .stat-row {
        display: flex;
        gap: 0.8rem;
        margin-bottom: 1.2rem;
        flex-wrap: wrap;
    }
    .stat-card {
        flex: 1;
        min-width: 100px;
        background: linear-gradient(135deg, #0d1f2d 0%, #0a1628 100%);
        border: 1px solid #1a3550;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        text-align: center;
    }
    .stat-card-val {
        font-size: 1.6rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.1;
    }
    .stat-card-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.2rem;
    }
    .stat-card-accent { border-top: 2px solid #1DB954; }
    .stat-card-accent2 { border-top: 2px solid #00d4ff; }
    .stat-card-accent3 { border-top: 2px solid #f59e0b; }

    /* ── Table Header ── */
    .table-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.8rem;
    }
    .table-title {
        font-size: 1rem;
        font-weight: 700;
        color: #ffffff;
    }
    .table-count {
        font-size: 0.78rem;
        color: #8b949e;
        background: #1a2332;
        padding: 0.2rem 0.6rem;
        border-radius: 10px;
    }

    /* ── Number inputs ── */
    .stNumberInput > div > div > input {
        background: #0d1f2d !important;
        border: 1px solid #1a3550 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    /* ── Caption ── */
    .stCaption { color: #1DB954 !important; font-weight: 500 !important; }

    /* ── Download button ── */
    .stDownloadButton > button {
        background: transparent !important;
        border: 1px solid #1a3550 !important;
        color: #8b949e !important;
        font-size: 0.82rem !important;
        box-shadow: none !important;
    }
    .stDownloadButton > button:hover {
        border-color: #1DB954 !important;
        color: #1DB954 !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* ── Sidebar labels ── */
    .stSidebar .stMarkdown h4 {
        color: #58a6ff !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 1rem !important;
    }

    /* ── Radio buttons ── */
    .stRadio label { color: #c9d1d9 !important; font-size: 0.88rem !important; }
    .stRadio [data-testid="stMarkdownContainer"] p { color: #8b949e !important; }

    /* ── Success/warning/error ── */
    .stSuccess { background: rgba(29,185,84,0.1) !important; border: 1px solid rgba(29,185,84,0.3) !important; border-radius: 8px !important; }
    .stWarning { background: rgba(245,158,11,0.1) !important; border: 1px solid rgba(245,158,11,0.3) !important; border-radius: 8px !important; }

    /* ── Info box ── */
    .stInfo { background: rgba(0,212,255,0.08) !important; border: 1px solid rgba(0,212,255,0.2) !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
_active = st.session_state.get("active_league")
_badge  = f'<span style="display:inline-block;background:rgba(29,185,84,0.15);border:1px solid rgba(29,185,84,0.4);border-radius:20px;padding:0.25rem 1rem;font-size:0.82rem;color:#1DB954;font-weight:700;letter-spacing:0.5px;margin-bottom:0.6rem;">📊 {_active}</span>' if _active else ''

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0d1117 0%,#0f1923 50%,#0d1117 100%);
            border-bottom:1px solid #1a2332;padding:2.5rem 2rem 1.8rem 2rem;
            text-align:center;margin-bottom:0;">
    {_badge}
    <div style="font-size:2.8rem;font-weight:900;
                background:linear-gradient(135deg,#1DB954 0%,#00d4ff 100%);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                background-clip:text;letter-spacing:-1px;line-height:1.1;margin-bottom:0.4rem;">
        🏏 Waseef Analytical Portal
    </div>
    <div style="color:#8b949e;font-size:0.95rem;font-weight:400;margin-bottom:0.8rem;">
        Transforming ball-by-ball cricket data into deep insights
    </div>
    <a href="https://www.linkedin.com/in/waseef-khalid-khan-366951237"
       target="_blank"
       style="color:#58a6ff;text-decoration:none;font-size:0.85rem;font-weight:600;">
       🔗 Connect on LinkedIn — Waseef Khalid Khan
    </a>
</div>
""", unsafe_allow_html=True)

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
st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">📊 Overview</div>', unsafe_allow_html=True)

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
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏏 Batting Statistics</div>', unsafe_allow_html=True)

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
        st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.8rem;"><span style="font-size:1rem;font-weight:700;color:#ffffff;">Batters</span><span style="font-size:0.78rem;color:#8b949e;background:#1a2332;padding:0.2rem 0.6rem;border-radius:10px;">{len(batting)} players</span></div>', unsafe_allow_html=True)
    with col_dl:
        st.download_button("⬇️ CSV", batting.to_csv(index=False), file_name="batting_stats.csv", mime="text/csv")
    st.dataframe(batting, use_container_width=True, height=500)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BOWLING
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🎳 Bowling Statistics</div>', unsafe_allow_html=True)

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

    # Always start from precomputed cache — fast
    bowling_base = _cache["bowling_all"].copy()

    # Apply over filter — filter by valid bowlers in those overs
    if use_over_filter and selected_overs:
        valid_bowlers_over = set(bowl_del["bowler"].dropna().unique())
        bowling_base = bowling_base[bowling_base["player"].isin(valid_bowlers_over)]

    # Apply bowling team filter
    if valid_bowl_players is not None:
        bowling_base = bowling_base[bowling_base["player"].isin(valid_bowl_players)]

    bowling = bowling_base[bowling_base["overs"] >= min_overs].copy()
    bowling = bowling.sort_values(sort_by_bowl, ascending=sort_by_bowl in ["economy", "average", "bowling_sr"]).reset_index(drop=True)
    bowling.index += 1

    if use_over_filter and selected_overs:
        st.caption(f"🎯 Stats for overs: {', '.join(map(str, sorted(selected_overs)))}")

    col_th, col_dl = st.columns([6,1])
    with col_th:
        st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.8rem;"><span style="font-size:1rem;font-weight:700;color:#ffffff;">Bowlers</span><span style="font-size:0.78rem;color:#8b949e;background:#1a2332;padding:0.2rem 0.6rem;border-radius:10px;">{len(bowling)} players</span></div>', unsafe_allow_html=True)
    with col_dl:
        st.download_button("⬇️ CSV", bowling.to_csv(index=False), file_name="bowling_stats.csv", mime="text/csv")
    st.dataframe(bowling, use_container_width=True, height=500)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — MATCH RESULTS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">📋 Match Results</div>', unsafe_allow_html=True)

    # Slice cached match stats by current filter
    match_stats = _cache["match_stats"]
    match_stats = match_stats[match_stats["match_id"].isin(final_matches["match_id"])]
    st.dataframe(match_stats, use_container_width=True, height=500)

    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🥇 Player of the Match</div>', unsafe_allow_html=True)

    # Build POM from filtered matches (not full cache — respects current filters)
    filtered_match_ids = set(final_matches["match_id"].tolist())

    # Full match detail with team info for For/Against logic
    match_detail = _cache["match_stats"].copy()
    match_detail = match_detail[match_detail["match_id"].isin(filtered_match_ids)]
    match_detail = match_detail[match_detail["player_of_match"].notna() &
                                (match_detail["player_of_match"] != "")]

    # For/Against toggle — only show when team is selected
    if selected_main_team:
        pom_mode = st.radio(
            "Show Player of Match:",
            ["🏆 For (selected team players)", "⚔️ Against (opposition players)", "📋 All"],
            horizontal=True,
            key="pom_mode"
        )

        # Get players who play FOR the selected team
        team_players = valid_team_players or set()

        if "For" in pom_mode:
            # POM winners who are FROM the selected team
            match_detail = match_detail[match_detail["player_of_match"].isin(team_players)]
            pom_title = f"Top MOM Winners — {', '.join(selected_main_team)} Players"
        elif "Against" in pom_mode:
            # POM winners who are opposition (NOT from selected team)
            match_detail = match_detail[~match_detail["player_of_match"].isin(team_players)]
            pom_title = f"Top MOM Winners — Against {', '.join(selected_main_team)}"
        else:
            pom_title = "All Player of Match Winners"
    else:
        pom_title = "Top Player of Match Winners"

    # Compute POM counts from filtered data
    if not match_detail.empty:
        pom = (
            match_detail["player_of_match"]
            .value_counts()
            .reset_index()
        )
        pom.columns = ["player_of_match", "awards"]

        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(pom, use_container_width=True, height=400)
        with col2:
            plot_top_batsmen(pom.head(10), x="player_of_match", y="awards", title=pom_title)
    else:
        st.info("No Player of the Match data for current selection.")

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
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏆 Team Performance</div>', unsafe_allow_html=True)

    # Filter cached team stats to teams in current match filter
    active_teams = set()
    if "team1" in final_matches.columns: active_teams.update(final_matches["team1"].dropna().unique())
    if "team2" in final_matches.columns: active_teams.update(final_matches["team2"].dropna().unique())
    team_stats = _cache["team_stats"]
    if active_teams:
        team_stats = team_stats[team_stats["team"].isin(active_teams)]
    st.dataframe(team_stats, use_container_width=True, height=400)

    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏏 Batting First vs Batting Second</div>', unsafe_allow_html=True)
    bat_order = _cache["bat_order_stats"]
    if active_teams:
        bat_order = bat_order[bat_order["team"].isin(active_teams)]

    st.caption("Win records when batting first vs chasing — filtered to current match selection")
    st.dataframe(bat_order, use_container_width=True, height=400)

    import plotly.express as px
    if not bat_order.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Win % Batting First vs Second**")
            melt = bat_order[["team","win%_bat_first","win%_bat_second"]].melt(
                id_vars="team", var_name="innings", value_name="win_%"
            )
            melt["innings"] = melt["innings"].map({
                "win%_bat_first": "Bat First",
                "win%_bat_second": "Bat Second"
            })
            fig = px.bar(melt, x="team", y="win_%", color="innings", barmode="group",
                         color_discrete_map={"Bat First": "#1DB954", "Bat Second": "#00b4d8"},
                         text_auto=".1f")
            fig.update_layout(xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Matches Batted First vs Second**")
            melt2 = bat_order[["team","bat_first","bat_second"]].melt(
                id_vars="team", var_name="innings", value_name="matches"
            )
            melt2["innings"] = melt2["innings"].map({
                "bat_first": "Bat First",
                "bat_second": "Bat Second"
            })
            fig2 = px.bar(melt2, x="team", y="matches", color="innings", barmode="group",
                          color_discrete_map={"Bat First": "#1DB954", "Bat Second": "#00b4d8"},
                          text_auto=True)
            fig2.update_layout(xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)",
                               paper_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🪙 Toss Analysis</div>', unsafe_allow_html=True)
    toss = _cache["toss_stats"]
    if active_teams:
        toss = toss[toss["toss_winner"].isin(active_teams)]
    st.dataframe(toss, use_container_width=True)

    st.download_button(
        "⬇️ Download Team Stats CSV",
        bat_order.to_csv(index=False),
        file_name="team_stats.csv",
        mime="text/csv",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — CHARTS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">📈 Visual Analytics</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        plot_runs_per_season(final_deliveries, final_matches)
    with col2:
        plot_wickets_per_season(final_deliveries, final_matches)

    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏏 Top 10 Run Scorers</div>', unsafe_allow_html=True)
    bat_chart = _cache["batting_all"].copy()
    if valid_bat_players is not None:
        bat_chart = bat_chart[bat_chart["player"].isin(valid_bat_players)]
    bat_chart = bat_chart.sort_values("runs", ascending=False).head(10)
    plot_top_batsmen(bat_chart, x="player", y="runs", title="Top 10 Run Scorers")

    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🎳 Top 10 Wicket Takers</div>', unsafe_allow_html=True)
    bowl_chart = _cache["bowling_all"].copy()
    if valid_bowl_players is not None:
        bowl_chart = bowl_chart[bowl_chart["player"].isin(valid_bowl_players)]
    bowl_chart = bowl_chart.sort_values("wickets", ascending=False).head(10)
    plot_top_bowlers(bowl_chart)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — PLAYER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">👤 Player Profile</div>', unsafe_allow_html=True)

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
                st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏏 Batting</div>', unsafe_allow_html=True)

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
                st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🎳 Bowling</div>', unsafe_allow_html=True)

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
            st.markdown('<div style="font-size:1.15rem;font-weight:700;color:#ffffff;padding:0.6rem 0 0.6rem 1rem;margin:1.8rem 0 1rem 0;border-left:3px solid #1DB954;background:linear-gradient(90deg,rgba(29,185,84,0.08) 0%,transparent 100%);border-radius:0 8px 8px 0;">🏅 Player of the Match</div>', unsafe_allow_html=True)

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
