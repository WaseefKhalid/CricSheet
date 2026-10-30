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
from components import theme as ui

# ── Auto-discover leagues from data/ folder ──────────────────────────────────
# Just drop any ZIP file into /data — it appears automatically as a league option.
# Cricsheet file codes are turned into proper names: "psl_male_csv2.zip" →
# "Pakistan Super League" (Men). Unknown codes fall back to the filename.
_CRICSHEET_NAMES = {
    "psl": "Pakistan Super League", "ipl": "Indian Premier League",
    "bbl": "Big Bash League", "wbb": "Women's Big Bash League",
    "cpl": "Caribbean Premier League", "sat": "SA20", "ilt": "ILT20",
    "mlc": "Major League Cricket", "lpl": "Lanka Premier League",
    "bpl": "Bangladesh Premier League", "npl": "Nepal Premier League",
    "hnd": "The Hundred", "ntb": "Vitality Blast", "ssm": "Super Smash",
    "msl": "Mzansi Super League", "wpl": "Women's Premier League",
    "wcl": "World Championship of Legends",
    "odis": "One-Day Internationals", "odms": "One-Day Matches",
    "t20s": "T20 Internationals", "it20s": "Other T20 Internationals",
    "tests": "Test Matches", "mdms": "Multi-day Matches",
}


def _league_label(fname):
    """Return (display_name, gender_tag or None) for a data file name."""
    stem = os.path.splitext(fname)[0].lower()
    stem = stem.split(" (")[0]                       # "psl_male_csv2 (6)" → "psl_male_csv2"
    parts = [p for p in stem.replace("-", "_").split("_") if p]
    gender = None
    if "male" in parts:
        gender = "Men"
    if "female" in parts:
        gender = "Women"
    core = [p for p in parts if p not in ("male", "female", "csv", "csv2", "json", "all")]
    if core and core[0] in _CRICSHEET_NAMES:
        name = " ".join([_CRICSHEET_NAMES[core[0]]] + [p.upper() for p in core[1:]])
    else:
        name = " ".join(w.upper() if len(w) <= 4 else w.capitalize() for w in core) or fname
    return name, gender


def _discover_leagues(data_dir="data"):
    """Scan data/ folder and return {display_name: file_path} for all ZIPs found."""
    leagues = {}
    if not os.path.exists(data_dir):
        return leagues
    for fname in sorted(os.listdir(data_dir)):
        if fname.lower().endswith(".zip"):
            path = os.path.join(data_dir, fname)
            name, gender = _league_label(fname)
            display = name
            # Keep names unique if two files map to the same league
            # (e.g. men's and women's ODIs)
            if display in leagues and gender:
                display = f"{name} ({gender})"
            base, n = display, 2
            while display in leagues:
                display, n = f"{base} {n}", n + 1
            leagues[display] = path
            LEAGUE_GENDER[display] = gender
    return leagues


LEAGUE_GENDER = {}
AVAILABLE_LEAGUES = _discover_leagues()

st.set_page_config(
    page_title="Waseef Analytical Portal",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="auto",
)

# Chart keys restart at 0 on every run so each chart keeps the same key
# between reruns (no remounting / flicker when a filter changes).
st.session_state._chart_counter = 0

ui.inject_css()

# ── Header ────────────────────────────────────────────────────────────────────
_active = st.session_state.get("active_league")
if _active:
    ui.top_bar()

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
            f'<div class="progress-label">{msg}<b>{int(pct*100)}%</b></div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress(pct)

    _step("Working out batting figures", 0.20)
    batting_all = get_batting_stats(deliveries_df, min_innings=1)

    _step("Working out bowling figures", 0.38)
    bowling_all = get_bowling_stats(deliveries_df, min_overs=1)

    _step("Tallying match and team results", 0.54)
    match_stats_all     = get_match_stats(matches_df)
    team_stats_all      = get_team_stats(matches_df)
    toss_stats_all      = get_toss_stats(matches_df)
    bat_order_stats_all = get_batting_order_stats(matches_df, deliveries_df)
    pom_stats_all       = get_player_of_match_stats(matches_df)

    _step("Building every player profile", 0.75)
    all_profiles = precompute_all_profiles(deliveries_df, matches_df)

    _step("Indexing deliveries", 0.93)
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
def _loading_header(league_name):
    ui.section(f"Loading {league_name}", "Every stat is worked out once now, so filtering afterwards is instant.")


def _load_league(league_name, zip_path):
    """Load a league zip and compute all stats."""
    _loading_header(league_name)
    pb = st.progress(0)
    st_txt = st.empty()
    st_txt.markdown(
        '<div class="progress-label">Reading match files<b>5%</b></div>',
        unsafe_allow_html=True,
    )
    pb.progress(0.05)
    with open(zip_path, "rb") as f:
        matches_df, deliveries_df = load_data_from_zip(f)
    _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
    st.session_state.active_league = league_name
    st.rerun()


def _admin_password():
    # st.secrets raises when no secrets.toml exists (e.g. running locally)
    try:
        return st.secrets.get("ADMIN_PASSWORD", "waseef123")
    except Exception:
        return "waseef123"


def _count_matches(zip_path):
    import zipfile
    try:
        with zipfile.ZipFile(zip_path) as z:
            return len([f for f in z.namelist() if f.endswith("_info.csv")])
    except Exception:
        return 0


# Show league picker if no league loaded yet OR user clicks switch
show_picker = (
    st.session_state.matches_df is None or
    st.session_state.active_league is None
)


def _switch_league():
    st.session_state.matches_df    = None
    st.session_state.deliveries_df = None
    st.session_state.cached        = None
    st.session_state.active_league = None


# League block at the top of the sidebar (only after data is loaded)
if not show_picker and st.session_state.active_league:
    with st.sidebar:
        st.markdown(
            f'<div class="wz-side-kicker">Exploring</div>'
            f'<div class="wz-side-league">{st.session_state.active_league}</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        st.button("Switch league", icon=":material/swap_horiz:", on_click=_switch_league,
                  width="stretch")

# A league was picked on the previous run: load it on a clean page
_pending = st.session_state.pop("_pending_league", None)
if show_picker and _pending:
    ui.top_bar()
    _load_league(*_pending)

if show_picker:
    if AVAILABLE_LEAGUES:
        _counts = {name: _count_matches(path) for name, path in AVAILABLE_LEAGUES.items()}
        hero_l, hero_r = st.columns([1.05, 1], gap="large", vertical_alignment="center")
        with hero_l:
            ui.hero()
        with hero_r:
            _total = sum(_counts.values())
            st.markdown(
                f'<p class="wz-pick-head">Choose a league. {_total:,} matches on file, '
                f'every ball recorded.</p>', unsafe_allow_html=True)
            with st.container(border=True):
                for i, (league_name, zip_path) in enumerate(AVAILABLE_LEAGUES.items()):
                    if i:
                        st.markdown('<hr style="margin:.2rem 0 !important">', unsafe_allow_html=True)
                    gender = LEAGUE_GENDER.get(league_name)
                    meta = f"{gender}'s competition" if gender else "Cricsheet ball-by-ball data"
                    c_name, c_count = st.columns([3, 1.2], vertical_alignment="center")
                    with c_name:
                        st.markdown(ui.league_row_text(league_name, meta), unsafe_allow_html=True)
                    with c_count:
                        st.markdown(ui.league_count(_counts[league_name]), unsafe_allow_html=True)
                    if st.button(f"Open {league_name}", key=f"load_{i}", width="stretch"):
                        st.session_state._pending_league = (league_name, zip_path)
                        st.rerun()

        # Upload option — only shown to admin (password protected)
        st.write("")
        with st.expander("Upload a new league (admin)", icon=":material/lock:"):
            admin_pass = st.text_input("Admin password", type="password", key="admin_pass")
            if admin_pass and admin_pass == _admin_password():
                uploaded_file = st.file_uploader("Cricsheet CSV zip", type=["zip"])
                custom_name   = st.text_input("League name", placeholder="e.g. SA20, LPL, MLC")
                if uploaded_file and custom_name:
                    if st.button("Load uploaded league", type="primary"):
                        _loading_header(custom_name)
                        pb = st.progress(0)
                        st_txt = st.empty()
                        pb.progress(0.05)
                        matches_df, deliveries_df = load_data_from_zip(uploaded_file)
                        _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
                        st.session_state.active_league = custom_name
                        st.rerun()
            elif admin_pass:
                st.error("That password isn't right. Check it and try again.")
    else:
        # No leagues in data/ folder — show upload
        ui.hero()
        ui.section("Add your first league",
                   "No leagues are on file yet. Upload a Cricsheet CSV zip to start.")
        uploaded_file = st.file_uploader("Cricsheet CSV zip", type=["zip"])
        custom_name   = st.text_input("League name", placeholder="e.g. PSL, IPL, T20I")
        if uploaded_file and custom_name:
            if st.button("Load league", type="primary"):
                _loading_header(custom_name)
                pb = st.progress(0)
                st_txt = st.empty()
                pb.progress(0.05)
                matches_df, deliveries_df = load_data_from_zip(uploaded_file)
                _compute_and_cache(matches_df, deliveries_df, pb, st_txt)
                st.session_state.active_league = custom_name
                st.rerun()
    ui.footer()
    st.stop()

# ── Guard ─────────────────────────────────────────────────────────────────────
if st.session_state.matches_df is None or st.session_state.cached is None:
    st.stop()

matches_df: pd.DataFrame    = st.session_state.matches_df
deliveries_df: pd.DataFrame = st.session_state.deliveries_df
_cache = st.session_state.cached  # precomputed stats dict

# ── Sidebar Filters ───────────────────────────────────────────────────────────
_FILTER_KEYS = ["f_season", "f_event", "f_team", "f_bat_team", "f_bowl_team",
                "f_venue", "f_toss_winner", "f_toss_decision", "f_winner"]


def _reset_filters():
    for k in _FILTER_KEYS:
        st.session_state.pop(k, None)


st.sidebar.divider()
st.sidebar.header("Filters", anchor=False)
st.sidebar.caption("Each filter narrows the options in the ones below it.")

filter_opts = get_filter_options(matches_df)

# Season
selected_seasons = st.sidebar.multiselect(
    "Season", options=filter_opts["seasons"], default=[], key="f_season",
    placeholder="All seasons",
)
filtered_matches_temp = apply_filters(matches_df, {"season": selected_seasons})
opts_after_season = get_filter_options(filtered_matches_temp)

# Event filter — key for T20 data with multiple tournaments
_event_opts = opts_after_season.get("events", [])
if len(_event_opts) > 1:
    selected_events = st.sidebar.multiselect(
        "Event",
        options=_event_opts,
        default=[],
        key="f_event",
        placeholder="All events",
        help="Filter by specific tournament/event e.g. T20 World Cup, PSL, etc."
    )
    if selected_events:
        filtered_matches_temp = apply_filters(filtered_matches_temp, {"event": selected_events})
        opts_after_season = get_filter_options(filtered_matches_temp)
else:
    selected_events = []

# ── MAIN TEAM FILTER — filters everything at once ─────────────────────────
selected_main_team = st.sidebar.multiselect(
    "Team",
    options=opts_after_season["teams"],
    default=[],
    key="f_team",
    placeholder="All teams",
    help="Filters every tab: batting, bowling, matches, team stats and player profiles",
)
if selected_main_team:
    filtered_matches_temp = apply_filters(filtered_matches_temp, {"team": selected_main_team})

opts_after_main_team = get_filter_options(filtered_matches_temp)

# ── ADVANCED: separate batting/bowling team overrides ─────────────────────
with st.sidebar.expander("Batting and bowling teams", icon=":material/tune:", expanded=False):
    st.caption("Overrides the team filter on the batting and bowling tabs")
    selected_batting_teams = st.multiselect(
        "Batting team",
        options=opts_after_main_team["teams"], default=[], key="f_bat_team",
        placeholder="Same as team filter",
        help="Show batting stats only for this team",
    )
    selected_bowling_teams = st.multiselect(
        "Bowling team",
        options=opts_after_main_team["teams"], default=[], key="f_bowl_team",
        placeholder="Same as team filter",
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

# Venue
selected_venues = st.sidebar.multiselect(
    "Venue", options=opts_after_team["venues"], default=[], key="f_venue",
    placeholder="All venues",
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"venue": selected_venues})
opts_after_venue = get_filter_options(filtered_matches_temp)

# Toss Winner
selected_toss_winners = st.sidebar.multiselect(
    "Toss winner", options=opts_after_venue["toss_winners"], default=[], key="f_toss_winner",
    placeholder="Any team",
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"toss_winner": selected_toss_winners})
opts_after_toss = get_filter_options(filtered_matches_temp)

# Toss Decision
selected_toss_decision = st.sidebar.multiselect(
    "Toss decision", options=opts_after_toss["toss_decisions"], default=[], key="f_toss_decision",
    placeholder="Bat or field",
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"toss_decision": selected_toss_decision})

# Winner
selected_winners = st.sidebar.multiselect(
    "Match winner", options=get_filter_options(filtered_matches_temp)["winners"], default=[],
    key="f_winner", placeholder="Any team",
)
filtered_matches_temp = apply_filters(filtered_matches_temp, {"winner": selected_winners})

st.sidebar.divider()
st.sidebar.markdown(
    f'<div class="wz-inview"><b>{len(filtered_matches_temp):,}</b>'
    f'of {len(matches_df):,} matches in view</div>',
    unsafe_allow_html=True,
)
st.sidebar.write("")
st.sidebar.button("Reset all filters", icon=":material/restart_alt:", on_click=_reset_filters,
                  width="stretch")

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
# Always filter players by current match selection (season/event/team filters)
# This ensures season filter affects batting/bowling stats
_filtered_strikers = set(final_deliveries["striker"].dropna().unique())
_filtered_bowlers  = set(final_deliveries["bowler"].dropna().unique())

# Team filter on top of season filter
if eff_batting_teams:
    valid_bat_players = set(bat_deliveries["striker"].dropna().unique())
else:
    valid_bat_players = _filtered_strikers  # season-filtered players

if eff_bowling_teams:
    valid_bowl_players = set(bowl_deliveries["bowler"].dropna().unique())
else:
    valid_bowl_players = _filtered_bowlers  # season-filtered players

# For player profile tab: union of both to get all squad members
valid_team_players = None
if selected_main_team:
    _bat_p  = valid_bat_players  or set()
    _bowl_p = valid_bowl_players or set(final_deliveries["bowler"].dropna().unique())
    valid_team_players = _bat_p | _bowl_p

# ── Title + scoreboard ────────────────────────────────────────────────────────
_title = st.session_state.active_league
_gender = LEAGUE_GENDER.get(_title)
if "gender" in matches_df.columns and matches_df["gender"].dropna().nunique() == 1:
    _gender = {"male": "Men", "female": "Women"}.get(str(matches_df["gender"].dropna().iloc[0]).lower(), _gender)

_seasons_all = matches_df["season"].dropna().nunique() if "season" in matches_df.columns else 0
_dek = f"{len(matches_df):,} matches across {_seasons_all} seasons" if _seasons_all else None
ui.page_title(_title, chip=_gender, dek=_dek)

_fmt = lambda d: f"{pd.Timestamp(d).day} {pd.Timestamp(d).strftime('%b %Y')}" if pd.notna(d) else "—"
_foot = None
if "date" in final_matches.columns:
    _dates = final_matches["date"].dropna().sort_values()
    if not _dates.empty:
        _earliest = _dates.iloc[0]
        _latest   = _dates.iloc[-1]
        _years    = int((_latest - _earliest).days / 365.25)
        _span     = f", a {_years}-year span" if _years >= 1 else ""
        _foot = f"Matches played from <b>{_fmt(_earliest)}</b> to <b>{_fmt(_latest)}</b>{_span}."
if len(final_matches) != len(matches_df):
    _foot = (_foot or "") + f" Filters are on: showing {len(final_matches):,} of {len(matches_df):,} matches."

ui.scoreboard([
    (f"{len(final_matches):,}", "Matches"),
    (f"{len(final_deliveries):,}", "Deliveries"),
    (f"{int(final_deliveries['runs_off_bat'].sum() + final_deliveries['extras'].sum()):,}", "Runs"),
    (f"{int(final_deliveries['wicket_type'].notna().sum()):,}", "Wickets"),
    (f"{final_matches['venue'].nunique()}", "Venues"),
], foot=_foot)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Batting",
    "Bowling",
    "Player of the match",
    "Teams",
    "League trends",
    "Player profiles",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BATTING
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    ui.lede("Career figures for every batter in the matches you've selected.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        min_innings = st.number_input("Minimum innings", min_value=1, value=3, step=1, key="min_inn")
    with col2:
        sort_by_bat = st.selectbox("Sort by", ["runs", "average", "strike_rate", "hundreds", "fifties", "innings"],
                                   key="sort_bat", format_func=ui.nice_label)
    with col3:
        ui.spacer()
        use_pos_filter = st.toggle("Only innings at certain batting positions", value=False)
        if use_pos_filter:
            selected_positions = st.multiselect(
                "Batting positions",
                options=list(range(1, 12)),
                default=[1, 2],
                format_func=lambda x: f"No. {x}",
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
        batting_base = get_batting_stats(bat_del.reset_index(drop=True), min_innings=1)
    else:
        # Filter cache by current season/team selection
        batting_base = get_batting_stats(bat_deliveries.reset_index(drop=True), min_innings=1)

    # Apply player filter (already season+team filtered via bat_deliveries)
    batting_base = batting_base[batting_base["player"].isin(valid_bat_players)]

    batting = batting_base[batting_base["innings"] >= min_innings].copy()
    batting = batting.sort_values(sort_by_bat, ascending=False).reset_index(drop=True)
    batting.index += 1

    col_th, col_dl = st.columns([5, 1], vertical_alignment="bottom")
    with col_th:
        _pos_note = (f", batting at No. {', '.join(map(str, sorted(selected_positions)))}"
                     if use_pos_filter and selected_positions else "")
        ui.subsection(f"{len(batting):,} batters{_pos_note}")
    with col_dl:
        st.download_button("Download CSV", batting.to_csv(index=False), key="dl_1", file_name="batting_stats.csv",
                           mime="text/csv", icon=":material/download:", width="stretch")
    ui.table(batting, height=520, bar=sort_by_bat if sort_by_bat in ("runs", "hundreds", "fifties", "innings") else "runs")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — BOWLING
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    ui.lede("Wickets, economy and strike rates. For economy, average and strike rate, lower is better.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        min_overs = st.number_input("Minimum overs", min_value=1, value=5, step=1, key="min_ovs")
    with col2:
        sort_by_bowl = st.selectbox("Sort by", ["wickets", "economy", "average", "bowling_sr", "overs"],
                                    key="sort_bowl", format_func=ui.nice_label)
    with col3:
        ui.spacer()
        use_over_filter = st.toggle("Only certain overs", value=False)
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
                "Phase",
                ["Custom", "Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"],
                horizontal=True,
            )
            if phase == "Powerplay (1-6)":
                selected_overs = list(range(1, 7))
            elif phase == "Middle (7-15)":
                selected_overs = list(range(7, 16))
            elif phase == "Death (16-20)":
                selected_overs = list(range(16, 21))
            else:
                selected_overs = st.multiselect(
                    "Overs",
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
        # Recompute from over-filtered deliveries
        bowling_base = get_bowling_stats(bowl_del.reset_index(drop=True), min_overs=1)
    else:
        # Recompute from season+team filtered deliveries
        bowling_base = get_bowling_stats(bowl_deliveries.reset_index(drop=True), min_overs=1)

    # Apply player filter (already season+team filtered)
    bowling_base = bowling_base[bowling_base["player"].isin(valid_bowl_players)]

    bowling = bowling_base[bowling_base["overs"] >= min_overs].copy()
    bowling = bowling.sort_values(sort_by_bowl, ascending=sort_by_bowl in ["economy", "average", "bowling_sr"]).reset_index(drop=True)
    bowling.index += 1

    col_th, col_dl = st.columns([5, 1], vertical_alignment="bottom")
    with col_th:
        _ov_note = (f", overs {', '.join(map(str, sorted(selected_overs)))}"
                    if use_over_filter and selected_overs else "")
        ui.subsection(f"{len(bowling):,} bowlers{_ov_note}")
    with col_dl:
        st.download_button("Download CSV", bowling.to_csv(index=False), key="dl_2", file_name="bowling_stats.csv",
                           mime="text/csv", icon=":material/download:", width="stretch")
    ui.table(bowling, height=520, bar="wickets")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — PLAYER OF MATCH ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    ui.lede("Who wins the awards, against whom, and where.")

    filtered_match_ids = set(final_matches["match_id"].tolist())
    match_detail = _cache["match_stats"].copy()
    match_detail = match_detail[match_detail["match_id"].isin(filtered_match_ids)]
    match_detail = match_detail[
        match_detail["player_of_match"].notna() &
        (match_detail["player_of_match"].astype(str).str.strip() != "")
    ]

    # For/Against toggle when team selected
    if selected_main_team:
        pom_mode = st.segmented_control(
            "Show awards won",
            ["For the team", "Against the team", "All"],
            default="For the team", key="pom_mode",
        ) or "All"
        team_players = valid_team_players or set()
        if "For" in pom_mode:
            match_detail = match_detail[match_detail["player_of_match"].isin(team_players)]
        elif "Against" in pom_mode:
            match_detail = match_detail[~match_detail["player_of_match"].isin(team_players)]

    if match_detail.empty:
        st.info("No player of the match awards in the matches you've selected. Widen the filters to see some.")
        st.stop()

    # ── 1. Overall leaderboard ────────────────────────────────────────────────
    ui.subsection("Leaderboard")
    pom_counts = (
        match_detail["player_of_match"]
        .value_counts()
        .reset_index()
    )
    pom_counts.columns = ["player", "awards"]
    pom_counts.index   = range(1, len(pom_counts) + 1)

    # Enrich pom_counts with matches played and award rate
    total_matches_per_player = (
        final_deliveries.groupby("striker")["match_id"].nunique()
        .reset_index().rename(columns={"striker":"player","match_id":"matches_played"})
    )
    pom_table = pom_counts.merge(total_matches_per_player, on="player", how="left")
    pom_table["matches_played"] = pom_table["matches_played"].fillna(0).astype(int)
    pom_table["award_per_match"] = (pom_table["matches_played"] / pom_table["awards"].replace(0,1)).round(1)
    pom_table = pom_table.rename(columns={
        "player":"Player","awards":"Awards",
        "matches_played":"Matches","award_per_match":"Matches per award"
    })
    pom_table.index = range(1, len(pom_table)+1)

    lb_l, lb_r = st.columns([3, 2])
    with lb_l:
        ui.table(pom_table, height=460, bar="Awards")
    with lb_r:
        ui.show(ui.bar(pom_counts.head(10), "player", "awards", title="Most awards",
                       horizontal=True, height=460))

    # ── 2. Player drill-down ──────────────────────────────────────────────────
    st.divider()
    ui.section("One player's awards")
    player_list = pom_counts["player"].tolist()
    selected_pom_player = st.selectbox(
        "Player",
        options=[None] + player_list,
        format_func=lambda x: "Choose a player" if x is None else x,
        key="pom_player_select"
    )

    if selected_pom_player:
        player_awards = match_detail[match_detail["player_of_match"] == selected_pom_player].copy()

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

        # KPI row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Awards", total)
        if "opponent" in player_awards.columns:
            best_opp = player_awards["opponent"].value_counts().idxmax() if not player_awards["opponent"].empty else "—"
            k2.metric("Most against", best_opp)
        if "venue" in player_awards.columns:
            best_venue = player_awards["venue"].value_counts().idxmax() if not player_awards["venue"].empty else "—"
            k3.metric("Best venue", best_venue[:20] + "..." if len(str(best_venue)) > 20 else best_venue,
                      help=str(best_venue))
        if "season" in player_awards.columns:
            best_season = player_awards["season"].value_counts().idxmax() if not player_awards["season"].empty else "—"
            k4.metric("Best season", best_season)

        col_a, col_b, col_c = st.columns(3)
        vs_opp = vs_venue = vs_season = None

        # vs each opponent
        with col_a:
            if "opponent" in player_awards.columns:
                vs_opp = player_awards["opponent"].value_counts().reset_index()
                vs_opp.columns = ["opponent","awards"]
                vs_opp.index += 1
                ui.show(ui.bar(vs_opp, "opponent", "awards", title="Against each team",
                               horizontal=True, height=340))

        # at each venue
        with col_b:
            if "venue" in player_awards.columns:
                vs_venue = player_awards["venue"].value_counts().reset_index()
                vs_venue.columns = ["venue","awards"]
                vs_venue.index += 1
                ui.show(ui.bar(vs_venue, "venue", "awards", title="At each venue",
                               horizontal=True, color=ui.SKY, height=340))

        # per season
        with col_c:
            if "season" in player_awards.columns:
                vs_season = player_awards["season"].value_counts().reset_index()
                vs_season.columns = ["season","awards"]
                vs_season = vs_season.sort_values("season").reset_index(drop=True)
                vs_season.index += 1
                ui.show(ui.bar(vs_season, "season", "awards", title="By season",
                               color=ui.VIOLET, height=340))

        with st.expander("See these as tables", icon=":material/table:"):
            t_a, t_b, t_c = st.columns(3)
            with t_a:
                if vs_opp is not None:
                    ui.table(vs_opp, height=300)
            with t_b:
                if vs_venue is not None:
                    ui.table(vs_venue, height=300)
            with t_c:
                if vs_season is not None:
                    ui.table(vs_season, height=300)

        # ── Full match log ────────────────────────────────────────────────────
        ui.subsection(f"Every match {selected_pom_player} was player of the match")
        safe_cols = [c for c in ["date","season","event","venue","team1","team2",
                                  "opponent","winner","toss_winner","toss_decision"] if c in player_awards.columns]
        ui.table(
            player_awards[safe_cols].sort_values("date", ascending=False).reset_index(drop=True),
            height=400, hide_index=True,
        )

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
    ui.section("Top five, split three ways",
               "The five players with the most awards for each team, against each team, and at each venue.")
    mom_for_tab, mom_against_tab, mom_venue_tab = st.tabs(["For each team", "Against each team", "At each venue"])

    # ── 3. Most MOM FOR each team (top 5 players per team) ───────────────────
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
            with mom_for_tab:
                ui.table(pivot_for_df, height=340)

    # ── 4. Most MOM AGAINST each team (top 5 players) ────────────────────────
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
            with mom_against_tab:
                ui.table(pivot_ag_df, height=340)

    # ── 5. Most MOM at each venue (top 5 players) ────────────────────────────
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
            with mom_venue_tab:
                ui.table(pivot_v_df, height=340)

    st.download_button(
        "Download award counts (CSV)",
        pom_counts.to_csv(index=False),
        file_name="player_of_match.csv",
        key="dl_3",
        mime="text/csv",
        icon=":material/download:",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — TEAM STATS
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    # Active teams for filtering
    active_teams = set()
    if "team1" in final_matches.columns: active_teams.update(final_matches["team1"].dropna().unique())
    if "team2" in final_matches.columns: active_teams.update(final_matches["team2"].dropna().unique())

    # ── Team selector for dashboard ───────────────────────────────────────────
    all_team_list = sorted(active_teams) if active_teams else sorted(
        list(deliveries_df["batting_team"].dropna().unique())
    )
    ui.lede("Results for every side. Pick one team to open its full breakdown.")
    dashboard_team = st.selectbox(
        "Team breakdown",
        options=[None] + all_team_list,
        format_func=lambda x: "All teams" if x is None else x,
        key="dashboard_team"
    )

    # ── OVERVIEW — shown always ───────────────────────────────────────────────
    # Recompute from filtered matches (respects season/event/team filters)
    team_stats = get_team_stats(final_matches)
    if not team_stats.empty:
        ov_l, ov_r = st.columns([3, 2])
        with ov_l:
            ui.subsection("Results")
            ui.table(team_stats, height=400, hide_index=True, bar="win_%")
        with ov_r:
            _ts = team_stats.sort_values("win_%", ascending=False)
            _fig = ui.bar(_ts, "team", "win_%", title="Win %", horizontal=True,
                          colors=ui.win_colors(_ts["win_%"]), height=400)
            _fig.add_vline(x=50, line_dash="dot", line_color=ui.MUTED, line_width=1)
            ui.show(_fig)
        st.caption("Blue bars win half their matches or more; red bars win fewer than half.")
        st.download_button(
            "Download team results (CSV)",
            team_stats.to_csv(index=False),
            file_name="team_stats.csv",
            key="dl_7",
            mime="text/csv",
            icon=":material/download:",
        )

    # ── TEAM DASHBOARD — shown when team selected ─────────────────────────────
    if dashboard_team:
        st.divider()
        ui.section(dashboard_team, "Everything below is for this team only, within your filters.")

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
        k4.metric("Runs scored", f"{tm_runs:,}")
        k5.metric("Wickets taken", f"{tm_wkts:,}")

        # ── SUB TABS ──────────────────────────────────────────────────────────
        t1, t2, t3, t4, t5 = st.tabs([
            "Batters",
            "Bowlers",
            "Venues",
            "Head to head",
            "Toss and batting order",
        ])

        # ── TOP BATTERS ───────────────────────────────────────────────────────
        with t1:
            tm_bat_stats = get_batting_stats(tm_bat_del.reset_index(drop=True), min_innings=1)
            tm_bat_stats = tm_bat_stats.sort_values("runs", ascending=False).reset_index(drop=True)
            tm_bat_stats.index += 1

            col1, col2 = st.columns([3, 2])
            with col1:
                ui.subsection(f"Run scorers for {dashboard_team}")
                ui.table(tm_bat_stats, height=460, bar="runs")
            with col2:
                ui.subsection("Top 10")
                ui.show(ui.bar(tm_bat_stats.head(10), "player", "runs", horizontal=True, height=460))

            st.download_button("Download batting CSV", tm_bat_stats.to_csv(index=False),
                               file_name=f"{dashboard_team}_batting.csv", icon=":material/download:")

        # ── TOP BOWLERS ───────────────────────────────────────────────────────
        with t2:
            tm_bowl_stats = get_bowling_stats(tm_bowl_del.reset_index(drop=True), min_overs=1)
            tm_bowl_stats = tm_bowl_stats.sort_values("wickets", ascending=False).reset_index(drop=True)
            tm_bowl_stats.index += 1

            col1, col2 = st.columns([3, 2])
            with col1:
                ui.subsection(f"Wicket takers for {dashboard_team}")
                ui.table(tm_bowl_stats, height=460, bar="wickets")
            with col2:
                ui.subsection("Top 10")
                ui.show(ui.bar(tm_bowl_stats.head(10), "player", "wickets", horizontal=True,
                               color=ui.VIOLET, height=460))

            st.download_button("Download bowling CSV", tm_bowl_stats.to_csv(index=False),
                               file_name=f"{dashboard_team}_bowling.csv", icon=":material/download:")

        # ── VENUE STATS ───────────────────────────────────────────────────────
        with t3:
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
                    ui.subsection("Record at each ground")
                    ui.table(venue_stats, height=420, bar="win_%")
                with col2:
                    ui.subsection("Won and lost")
                    ui.show(ui.stacked_bar(venue_stats, "venue", {"won": ui.WIN, "lost": ui.LOSS},
                                           horizontal=True, height=420))

                # Runs at each venue
                if "venue" in tm_bat_del.columns:
                    v_runs = (
                        tm_bat_del.groupby("venue")
                        .agg(runs=("runs_off_bat","sum"), balls=("wides","count"))
                        .reset_index()
                    )
                    ui.subsection("Runs scored at each ground")
                    ui.table(v_runs.sort_values("runs", ascending=False).reset_index(drop=True),
                             height=280, hide_index=True, bar="runs")
            else:
                st.info("This data has no venue column, so there's no ground-by-ground record.")

        # ── VS EACH TEAM ──────────────────────────────────────────────────────
        with t4:
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
                ui.subsection(f"{dashboard_team} against each side")
                ui.table(vs_stats, height=420)
            with col2:
                ui.subsection("Win %")
                _vs = vs_stats.sort_values("win_%", ascending=False)
                _fig4 = ui.bar(_vs, "opponent", "win_%", horizontal=True,
                               colors=ui.win_colors(_vs["win_%"]), height=420)
                _fig4.add_vline(x=50, line_dash="dot", line_color=ui.MUTED, line_width=1)
                ui.show(_fig4)

            st.download_button("Download head-to-head CSV", vs_stats.to_csv(index=False),
                               file_name=f"{dashboard_team}_vs_teams.csv", icon=":material/download:")

        # ── TOSS & BAT ORDER ─────────────────────────────────────────────────
        with t5:
            col1, col2 = st.columns(2)
            with col1:
                ui.subsection("After winning the toss")
                toss_tm = get_toss_stats(final_matches)
                toss_tm = toss_tm[toss_tm["toss_winner"] == dashboard_team]
                if not toss_tm.empty:
                    ui.table(toss_tm, hide_index=True)
                    _tw = int(toss_tm["toss_wins"].iloc[0])
                    _mw = int(toss_tm["match_wins"].iloc[0])
                    _toss_split = pd.DataFrame({
                        "result": ["Won the match", "Lost or no result"],
                        "matches": [_mw, max(_tw - _mw, 0)],
                    })
                    ui.show(ui.donut(_toss_split, "result", "matches",
                                     title=f"{_tw} tosses won", colors=[ui.WIN, ui.LOSS]))

            with col2:
                ui.subsection("Batting first or chasing")
                bat_ord_tm = get_batting_order_stats(final_matches.reset_index(drop=True), final_deliveries.reset_index(drop=True))
                bat_ord_tm = bat_ord_tm[bat_ord_tm["team"] == dashboard_team]
                if not bat_ord_tm.empty:
                    ui.table(bat_ord_tm, hide_index=True)
                    melt_tm = bat_ord_tm[["team","win%_bat_first","win%_bat_second"]].melt(
                        id_vars="team", var_name="method", value_name="win_%"
                    )
                    melt_tm["method"] = melt_tm["method"].map({
                        "win%_bat_first":"Batting first","win%_bat_second":"Chasing"
                    })
                    ui.show(ui.bar(melt_tm, "method", "win_%", title="Win %",
                                   colors=[ui.AMBER, ui.SKY], height=340))

    else:
        # ── OVERVIEW CHARTS (no team selected) ───────────────────────────────
        st.divider()
        bo_l, bo_r = st.columns(2)
        with bo_l:
            ui.subsection("Batting first or chasing")
            st.caption("Each team's record when setting a target and when chasing one")
            bat_order = get_batting_order_stats(final_matches.reset_index(drop=True), final_deliveries.reset_index(drop=True))
            ui.table(bat_order, height=380, hide_index=True)
        with bo_r:
            ui.subsection("Does winning the toss help?")
            st.caption("How often each team went on to win after calling correctly")
            toss = get_toss_stats(final_matches)
            ui.table(toss, height=380, hide_index=True, bar="win_after_toss_%")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — LEAGUE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
with tab5:
    ui.lede("How games are played across every match in your selection.")

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
    ui.subsection("Innings scores")
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Avg 1st inns",     f"{inn1['runs'].mean():.1f}"  if not inn1.empty else "—",
              help="Average first-innings total")
    c2.metric("Avg 1st inns, won", f"{inn1[inn1['won']]['runs'].mean():.1f}" if not inn1[inn1["won"]].empty else "—",
              help="Average first-innings total when the side batting first won")
    c3.metric("Avg 2nd inns",     f"{inn2['runs'].mean():.1f}"  if not inn2.empty else "—",
              help="Average second-innings total")
    c4.metric("Avg 2nd inns, won", f"{inn2[inn2['won']]['runs'].mean():.1f}" if not inn2[inn2["won"]].empty else "—",
              help="Average second-innings total when the chasing side won")
    c5.metric("Highest 1st inns", f"{int(inn1['runs'].max())}"  if not inn1.empty else "—")
    c6.metric("Lowest 1st inns",  f"{int(inn1['runs'].min())}"  if not inn1.empty else "—")

    st.divider()
    ui.section("Phase by phase", "Powerplay, middle and death overs. Every value is per innings.")

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
    # Count innings per phase (not matches) for accurate per-innings avg
    phase_inn_count = (
        del_df[del_df["phase"].notna() & (del_df["phase"] != "Super (20+)")]
        .groupby(["phase","match_id","innings"], observed=True)
        .size().reset_index(name="_b")
        .groupby("phase", observed=True).size().reset_index(name="inn_count")
    )
    phase_agg = phase_agg[phase_agg["phase"] != "Super (20+)"].copy()
    phase_agg = phase_agg.merge(phase_inn_count, on="phase", how="left")
    phase_agg["inn_count"]         = phase_agg["inn_count"].fillna(1)
    phase_agg["avg_runs_per_inn"]  = (phase_agg["total_runs"]  / phase_agg["inn_count"]).round(1)
    phase_agg["avg_wkts_per_inn"]  = (phase_agg["total_wkts"]  / phase_agg["inn_count"]).round(2)
    phase_agg["run_rate"]          = (phase_agg["total_runs"]  / phase_agg["total_balls"] * 6).round(2).where(phase_agg["total_balls"]>0, 0)
    phase_agg["balls_per_wicket"]  = (phase_agg["total_balls"] / phase_agg["total_wkts"]).round(1).where(phase_agg["total_wkts"]>0, 0)

    _phase_cols = [ui.PHASE_COLORS.get(str(p), ui.MUTED) for p in phase_agg["phase"]]
    col1, col2, col3 = st.columns(3)
    with col1:
        ui.show(ui.bar(phase_agg, "phase", "avg_runs_per_inn", title="Runs per innings",
                       colors=_phase_cols, height=340))
    with col2:
        ui.show(ui.bar(phase_agg, "phase", "avg_wkts_per_inn", title="Wickets per innings",
                       colors=_phase_cols, height=340))
    with col3:
        ui.show(ui.bar(phase_agg, "phase", "run_rate", title="Run rate",
                       colors=_phase_cols, height=340))

    # Phase table
    ui.table(
        phase_agg[["phase","avg_runs_per_inn","run_rate","avg_wkts_per_inn","balls_per_wicket"]]
        .rename(columns={
            "phase":"Phase",
            "avg_runs_per_inn":"Runs per innings",
            "run_rate":"Run rate",
            "avg_wkts_per_inn":"Wickets per innings",
            "balls_per_wicket":"Balls per wicket",
        }),
        hide_index=True
    )

    # ── Over-by-over run rate ─────────────────────────────────────────────────
    st.divider()
    ui.section("Over by over", "Dotted lines mark the end of the powerplay and the middle overs.")
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
        fig_or = ui.line(over_agg, "over_num", "run_rate", title="Run rate in each over",
                         labels={"over_num": "Over", "run_rate": "Run rate"},
                         vlines=[(6.5, "Powerplay ends"), (15.5, "Death overs")], height=360)
        fig_or.update_xaxes(dtick=1)
        ui.show(fig_or)
    with col2:
        fig_ow = ui.bar(over_agg, "over_num", "avg_wkts", title="Wickets in each over, per match",
                        color=ui.RED, show_values=False, height=360,
                        labels={"over_num": "Over", "avg_wkts": "Wickets per match"})
        fig_ow.add_vline(x=5.5,  line_dash="dot", line_color=ui.MUTED, line_width=1)
        fig_ow.add_vline(x=14.5, line_dash="dot", line_color=ui.MUTED, line_width=1)
        ui.show(fig_ow)

    # ── Toss & Venue ──────────────────────────────────────────────────────────
    st.divider()
    ui.section("Grounds", "Average first-innings score at each venue that has hosted at least three matches.")

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
        ui.show(ui.bar(venue_avg, "venue", "avg", horizontal=True,
                       labels={"avg": "Average 1st innings score"}))

    # ── Season trends ─────────────────────────────────────────────────────────
    st.divider()
    ui.section("Season by season")
    if "season" in final_matches.columns:
        _sm = final_matches.set_index("match_id")["season"].to_dict()
        del_df["_s"] = del_df["match_id"].map(_sm)
        sd2 = del_df[del_df["_s"].notna()].copy()
        season_agg = (
            sd2.groupby("_s")
            .agg(runs=("total_runs","sum"), wickets=("is_wicket","sum"),
                 matches=("match_id","nunique"), balls=("is_legal","sum"))
            .reset_index().rename(columns={"_s":"season"}).sort_values("season")
        )
        _sinn = (
            sd2.groupby(["_s","match_id","innings"])
            .size().reset_index(name="_b")
            .groupby("_s").size().reset_index(name="inn_count")
            .rename(columns={"_s":"season"})
        )
        season_agg = season_agg.merge(_sinn, on="season", how="left")
        season_agg["inn_count"] = season_agg["inn_count"].fillna(season_agg["matches"]*2)
        season_agg["avg_score"] = (season_agg["runs"] / season_agg["inn_count"]).round(1)
        season_agg["run_rate"]  = (season_agg["runs"] / season_agg["balls"] * 6).round(2)
        season_agg["avg_wkts"]  = (season_agg["wickets"] / season_agg["inn_count"]).round(2)

        col1, col2, col3 = st.columns(3)
        _slabels = {"season": "Season", "avg_score": "Average score", "run_rate": "Run rate",
                    "avg_wkts": "Wickets per innings"}
        with col1:
            ui.show(ui.line(season_agg, "season", "avg_score", title="Average innings score",
                            color=ui.AMBER, labels=_slabels, categorical_x=True))
        with col2:
            ui.show(ui.line(season_agg, "season", "run_rate", title="Run rate",
                            color=ui.SKY, labels=_slabels, categorical_x=True))
        with col3:
            ui.show(ui.line(season_agg, "season", "avg_wkts", title="Wickets per innings",
                            color=ui.RED, labels=_slabels, categorical_x=True))

    st.download_button(
        "Download phase analysis (CSV)",
        phase_agg.to_csv(index=False),
        file_name="league_phase_analysis.csv",
        key="dl_8",
        mime="text/csv",
        icon=":material/download:",
    )


    # ── Pre-compute shared base data ─────────────────────────────────────────
    try:
        _sm3  = final_matches.set_index("match_id")
        _smap = final_matches.set_index("match_id")["season"].to_dict() if "season" in final_matches.columns else {}

        def _get_vs(mid, team):
            try:
                r = _sm3.loc[mid]
                return r["team2"] if r["team1"]==team else r["team1"]
            except: return "—"

        # Team innings base
        t_inn = (
            del_df.groupby(["match_id","innings","batting_team"])["total_runs"]
            .sum().reset_index().rename(columns={"total_runs":"runs","batting_team":"team"})
        )
        t_balls = del_df[del_df["is_legal"]].groupby(["match_id","innings"]).size().reset_index(name="balls")
        t_inn = t_inn.merge(t_balls, on=["match_id","innings"], how="left")
        t_inn["SR"]     = (t_inn["runs"]/t_inn["balls"]*100).round(1).where(t_inn["balls"]>0,0)
        t_inn["vs"]     = t_inn.apply(lambda r: _get_vs(r["match_id"], r["team"]), axis=1)
        _venue_map = final_matches.set_index("match_id")["venue"].to_dict() if "venue" in final_matches.columns else {}
        _date_map  = final_matches.set_index("match_id")["date"].to_dict()  if "date"  in final_matches.columns else {}
        t_inn["venue"] = t_inn["match_id"].map(_venue_map)
        t_inn["date"]  = pd.to_datetime(t_inn["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")
        t_inn["season"] = t_inn["match_id"].map(_smap)
        _venue_map = final_matches.set_index("match_id")["venue"].to_dict() if "venue" in final_matches.columns else {}
        _date_map  = final_matches.set_index("match_id")["date"].to_dict()  if "date"  in final_matches.columns else {}
        t_inn["venue"] = t_inn["match_id"].map(_venue_map)
        t_inn["date"]  = pd.to_datetime(t_inn["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")

        # Individual batting innings base
        p_inn = (
            del_df.groupby(["match_id","innings","striker","batting_team"])["runs_off_bat"]
            .sum().reset_index().rename(columns={"runs_off_bat":"runs","striker":"player","batting_team":"team"})
        )
        p_balls = del_df[del_df["wides"]==0].groupby(["match_id","innings","striker"]).size().reset_index(name="balls").rename(columns={"striker":"player"})
        p_inn = p_inn.merge(p_balls, on=["match_id","innings","player"], how="left")
        p_inn["SR"]     = (p_inn["runs"]/p_inn["balls"]*100).round(1).where(p_inn["balls"]>0,0)
        p_inn["vs"]     = p_inn.apply(lambda r: _get_vs(r["match_id"], r["team"]), axis=1)
        p_inn["season"] = p_inn["match_id"].map(_smap)
        p_inn["venue"]  = p_inn["match_id"].map(_venue_map)
        p_inn["date"]   = pd.to_datetime(p_inn["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")
        p_inn["venue"]  = p_inn["match_id"].map(_venue_map)
        p_inn["date"]   = pd.to_datetime(p_inn["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")
        p_inn["4s"]     = del_df[del_df["runs_off_bat"]==4].groupby(["match_id","innings","striker"]).size().reindex(
            p_inn.set_index(["match_id","innings","player"]).index).fillna(0).astype(int).values
        p_inn["6s"]     = del_df[del_df["runs_off_bat"]==6].groupby(["match_id","innings","striker"]).size().reindex(
            p_inn.set_index(["match_id","innings","player"]).index).fillna(0).astype(int).values

        # Bowling figures base
        wk = (del_df["wicket_type"].notna() & (del_df["wicket_type"]!="") &
              (~del_df["wicket_type"].str.lower().isin(["run out","retired hurt","obstructing the field"])))
        bf_w = del_df[wk].groupby(["match_id","innings","bowler"]).size().reset_index(name="wickets")
        del_df["_rc"] = del_df["runs_off_bat"].fillna(0)+del_df["wides"].fillna(0)+del_df["noballs"].fillna(0)
        bf_r = del_df.groupby(["match_id","innings","bowler"])["_rc"].sum().reset_index(name="runs_given")
        bf_b = del_df[del_df["is_legal"]].groupby(["match_id","innings","bowler"]).size().reset_index(name="balls")
        bf   = bf_w.merge(bf_r, on=["match_id","innings","bowler"], how="left")
        bf   = bf.merge(bf_b, on=["match_id","innings","bowler"], how="left")
        bf["overs"]     = (bf["balls"]//6+(bf["balls"]%6)/10).round(1)
        bf["figure"]    = bf["wickets"].astype(str)+"/"+bf["runs_given"].astype(int).astype(str)
        _btmap = del_df.drop_duplicates(["match_id","bowler"]).set_index(["match_id","bowler"])["bowling_team"].to_dict()
        bf["team"]      = bf.apply(lambda r: _btmap.get((r["match_id"],r["bowler"]),"—"), axis=1)
        bf["vs"]        = bf.apply(lambda r: _get_vs(r["match_id"], r["team"]), axis=1)
        bf["season"]    = bf["match_id"].map(_smap)
        bf["venue"]     = bf["match_id"].map(_venue_map)
        bf["date"]      = pd.to_datetime(bf["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")
        bf["venue"]     = bf["match_id"].map(_venue_map)
        bf["date"]      = pd.to_datetime(bf["match_id"].map(_date_map), errors="coerce").dt.strftime("%d %b %Y")

    except Exception as e:
        st.warning(f"Data preparation error: {e}")
        t_inn = p_inn = bf = pd.DataFrame()

    st.divider()
    ui.section("Records", "The best and worst days in your selection.")
    col_l, col_r, col_l2, col_r2 = st.tabs(["Highest team totals", "Lowest team totals",
                                             "Highest individual innings", "Best bowling figures"])

    # ── Highest Team Scores ───────────────────────────────────────────────────
    with col_l:
        if not t_inn.empty:
            top_high = t_inn.sort_values("runs", ascending=False).head(10).reset_index(drop=True)
            top_high.index += 1
            ui.table(
                top_high[["team","vs","season","date","venue","runs","balls","SR"]]
                .rename(columns={"team":"Team","vs":"Vs","season":"Season","date":"Date","venue":"Venue","runs":"Score","balls":"Balls","SR":"SR"}),
                height=400
            )

    # ── Lowest Team Scores ────────────────────────────────────────────────────
    with col_r:
        st.caption("Innings of 10 overs or more")
        if not t_inn.empty:
            top_low = t_inn[t_inn["balls"] >= 60].sort_values("runs", ascending=True).head(10).reset_index(drop=True)
            top_low.index += 1
            ui.table(
                top_low[["team","vs","season","date","venue","runs","balls","SR"]]
                .rename(columns={"team":"Team","vs":"Vs","season":"Season","date":"Date","venue":"Venue","runs":"Score","balls":"Balls","SR":"SR"}),
                height=400
            )


    # ── Top 10 Individual Innings ─────────────────────────────────────────────
    with col_l2:
        if not p_inn.empty:
            top_ind = p_inn.sort_values("runs", ascending=False).head(10).reset_index(drop=True)
            top_ind.index += 1
            ui.table(
                top_ind[["player","team","vs","season","date","venue","runs","balls","SR"]]
                .rename(columns={"player":"Player","team":"Team","vs":"Vs","season":"Season","date":"Date","venue":"Venue","runs":"Runs","balls":"Balls","SR":"SR"}),
                height=400
            )

    # ── Top 10 Bowling Figures ────────────────────────────────────────────────
    with col_r2:
        if not bf.empty:
            top_bf = bf.sort_values(["wickets","runs_given"], ascending=[False,True]).head(10).reset_index(drop=True)
            top_bf.index += 1
            ui.table(
                top_bf[["bowler","team","vs","season","date","venue","figure","wickets","runs_given","overs"]]
                .rename(columns={"bowler":"Bowler","team":"Team","vs":"Vs","season":"Season",
                                  "date":"Date","venue":"Venue","figure":"Figure","wickets":"Wkts","runs_given":"Runs","overs":"Overs"}),
                height=400
            )

# TAB 6 — PLAYER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    ui.lede("Any player's full record within your filters.")

    # Precompute ALL player profiles once — cached by data size so recomputes
    # only when filters change. Individual lookups are then instant (dict key).
    # Recompute profiles from filtered deliveries (respects season/team filters)
    # Use cache only when no filters are active (all matches selected)
    _no_filters = (
        not selected_seasons and not selected_events and
        not selected_main_team and not selected_events
    )
    if _no_filters:
        all_profiles = _cache["all_profiles"]
    else:
        @st.cache_data(show_spinner=False)
        def _filtered_profiles(match_ids_hash, del_hash):
            return precompute_all_profiles(
                final_deliveries.reset_index(drop=True),
                final_matches.reset_index(drop=True)
            )
        all_profiles = _filtered_profiles(
            hash(frozenset(valid_match_ids)),
            len(final_deliveries)
        )

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
                "Player",
                options=[None] + all_players,
                format_func=lambda x: "Type a name or pick from the list" if x is None else x,
                index=0,
            )
        with col_role:
            show_role = st.segmented_control(
                "Show", ["Both", "Batting Only", "Bowling Only"], default="Both", key="profile_role",
                format_func=lambda x: {"Both": "Both", "Batting Only": "Batting", "Bowling Only": "Bowling"}[x],
            ) or "Both"

        if selected_player is None:
            st.info(f"Choose one of {len(all_players):,} players above to open their profile.")
        else:
            # Instant lookup — no computation needed
            profile = all_profiles.get(selected_player, {})

            ui.player_name(selected_player)

            bat  = profile.get("batting")
            bowl = profile.get("bowling")
            mom  = profile.get("mom", {})

            # ── MOM Banner ────────────────────────────────────────────────────
            mom_total = mom.get("total", 0)
            if mom_total > 0:
                ui.callout(mom_total, f"player of the match award{'s' if mom_total != 1 else ''}")

            # ── BATTING SECTION ───────────────────────────────────────────────
            if show_role in ("Both", "Batting Only"):
                ui.section("Batting")

                if bat:
                    # KPIs
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("Innings",      bat["innings"])
                    c2.metric("Runs",         bat["runs"])
                    c3.metric("Highest",      bat["highest"])
                    c4.metric("Average",      bat["average"])
                    c5.metric("Strike rate",  bat["strike_rate"])
                    c6.metric("Not outs",     bat["not_outs"])

                    c7, c8, c9, c10 = st.columns(4)
                    c7.metric("100s",         bat["hundreds"])
                    c8.metric("50s",          bat["fifties"])
                    c9.metric("4s",           bat["fours"])
                    c10.metric("6s",          bat["sixes"])

                    # ── Batting Position Breakdown ────────────────────────
                    if show_role in ("Batting Only",):
                        ui.subsection("By batting position")
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
                                st.caption("Only innings batted at each position count")
                                ui.table(pos_display, height=350)
                            with col_pos2:
                                _pos_sorted = pos_stats.sort_values("position")
                                ui.show(ui.bar(_pos_sorted, "position", "runs", title="Runs at each position",
                                               height=300, labels={"position": "Position"}))
                                ui.show(ui.bar(_pos_sorted, "position", "strike_rate",
                                               title="Strike rate at each position", color=ui.SKY,
                                               height=300, labels={"position": "Position"}))
                        else:
                            st.info("There's no batting-position data for this player in your selection.")

                    # Win / Loss split
                    wl_df = pd.DataFrame({
                        "Result": ["Wins", "Losses"],
                        "Runs":   [bat["runs_in_wins"], bat["runs_in_losses"]],
                    })

                    # Runs vs each team + venue
                    # ── Top 10 Innings ────────────────────────────────────
                    inn_l, inn_r = st.columns([3, 1])
                    with inn_l:
                        ui.subsection("Ten best innings")
                        top_inn = bat.get("top_innings", pd.DataFrame())
                        if not top_inn.empty:
                            top_inn = top_inn.copy()
                            top_inn.index = range(1, len(top_inn) + 1)
                            ui.table(top_inn, height=400)
                        else:
                            st.info("No innings to list for this player in your selection.")
                    with inn_r:
                        ui.subsection("Runs in wins and losses")
                        ui.show(ui.bar(wl_df, "Result", "Runs", colors=[ui.WIN, ui.LOSS], height=400))

                    # ── Partnership Analysis ──────────────────────────────
                    ui.subsection("Partnerships")
                    partnerships = bat.get("partnerships", pd.DataFrame())
                    if not partnerships.empty:
                        # Min runs filter
                        p_col1, p_col2 = st.columns([1, 3])
                        with p_col1:
                            min_p_runs = st.number_input(
                                "Minimum runs together",
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
                            st.caption(f"{len(p_filtered)} partners with {min_p_runs}+ runs together, highest average first")
                            ui.table(
                                p_filtered.rename(columns={
                                    "partner":      "Partner",
                                    "partnerships": "Innings",
                                    "total_runs":   "Total Runs",
                                    "avg":          "Average",
                                    "best":         "Best stand",
                                    "sr":           "SR",
                                }),
                                height=420,
                                bar="Average",
                            )
                        with col_p2:
                            top_p = p_filtered.head(10).copy()
                            ui.show(ui.bar(top_p, "partner", "avg", title="Best average stands",
                                           horizontal=True, height=420, labels={"avg": "Average"}))
                    else:
                        st.info("No partnerships to show for this player in your selection.")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        vs = bat["vs_team"]
                        if not vs.empty:
                            ui.show(ui.bar(vs, "opponent", "runs", title="Runs against each team", horizontal=True))
                        else:
                            st.info("No runs against any team in your selection.")

                    with col_b:
                        vv = bat["vs_venue"]
                        if not vv.empty:
                            ui.show(ui.bar(vv, "venue", "runs", title="Runs at each venue", horizontal=True,
                                           color=ui.SKY))
                        else:
                            st.info("No runs at any venue in your selection.")
                else:
                    st.info(f"{selected_player} hasn't batted in the matches you've selected.")

            # ── BOWLING SECTION ───────────────────────────────────────────────
            if show_role in ("Both", "Bowling Only"):
                st.divider()
                ui.section("Bowling")

                if bowl:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("Overs",      bowl["overs"])
                    c2.metric("Wickets",    bowl["wickets"])
                    c3.metric("Runs conceded", bowl["runs_given"])
                    c4.metric("Economy",    bowl["economy"])
                    c5.metric("Average",    bowl["average"] if bowl["average"] else "—")

                    # Win / Loss wicket split
                    wl_bowl = pd.DataFrame({
                        "Result":  ["Wins", "Losses"],
                        "Wickets": [bowl["wickets_in_wins"], bowl["wickets_in_losses"]],
                    })

                    # ── Top 10 Bowling Figures ────────────────────────────
                    bf_l, bf_r = st.columns([3, 1])
                    with bf_l:
                        ui.subsection("Ten best bowling figures")
                        top_fig = bowl.get("top_figures", pd.DataFrame())
                        if not top_fig.empty:
                            top_fig = top_fig.copy()
                            top_fig.index = range(1, len(top_fig) + 1)
                            ui.table(top_fig, height=400)
                        else:
                            st.info("No bowling figures for this player in your selection.")
                    with bf_r:
                        ui.subsection("Wickets in wins and losses")
                        ui.show(ui.bar(wl_bowl, "Result", "Wickets", colors=[ui.WIN, ui.LOSS], height=400))

                    col_a, col_b = st.columns(2)
                    with col_a:
                        vt_b = bowl["vs_team"]
                        if not vt_b.empty:
                            ui.show(ui.bar(vt_b, "opponent", "wickets", title="Wickets against each team",
                                           horizontal=True, color=ui.VIOLET))
                        else:
                            st.info("No wickets against any team in your selection.")

                    with col_b:
                        vv_b = bowl["vs_venue"]
                        if not vv_b.empty:
                            ui.show(ui.bar(vv_b, "venue", "wickets", title="Wickets at each venue",
                                           horizontal=True, color=ui.SKY))
                        else:
                            st.info("No wickets at any venue in your selection.")
                else:
                    st.info(f"{selected_player} hasn't bowled in the matches you've selected.")

            # ── MAN OF MATCH SECTION ──────────────────────────────────────────
            st.divider()
            ui.section("Player of the match")

            if mom_total == 0:
                st.info(f"{selected_player} hasn't won player of the match in the matches you've selected.")
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    mom_team = mom.get("vs_team", pd.DataFrame())
                    if not mom_team.empty:
                        ui.show(ui.bar(mom_team, "opponent", "mom_awards", title="Awards against each team",
                                       horizontal=True))

                with col_b:
                    mom_venue = mom.get("vs_venue", pd.DataFrame())
                    if not mom_venue.empty:
                        ui.show(ui.bar(mom_venue, "venue", "mom_awards", title="Awards at each venue",
                                       horizontal=True, color=ui.SKY))

                ui.subsection("Every award")
                mom_matches_df = mom.get("matches", pd.DataFrame())
                if not mom_matches_df.empty:
                    ui.table(mom_matches_df.reset_index(drop=True), hide_index=True)

ui.footer()
