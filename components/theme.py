"""
Floodlit — the design system for the Waseef Analytical Portal.

Everything visual lives here: colour tokens, fonts, global CSS, the Plotly
chart template, chart/table helpers and the small HTML blocks (top bar,
scoreboard strip, league board). app.py only decides *what* to show.

Palette idea: a day-night match. Night-sky navy, floodlight amber,
cricket-ball red and "whites" ivory text.
"""

from __future__ import annotations

import html
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ── Colour tokens ─────────────────────────────────────────────────────────────
NIGHT   = "#0E1528"   # page
DEEP    = "#0A1022"   # sidebar
PANEL   = "#141C33"   # surfaces: charts, tables, scoreboard
PANEL_2 = "#1A2442"   # raised / hover
LINE    = "#253052"   # hairline borders
GRID    = "#1E2846"   # chart gridlines
INK     = "#EEE9DD"   # primary text ("whites")
INK_2   = "#B9BFD0"   # secondary text
MUTED   = "#8590AD"   # captions, axis ticks
FLOOD   = "#F2A541"   # UI accent (buttons, active tab, scoreboard digits)

# Chart series — validated as a set for colour-blind separation and contrast
# on PANEL. Assign in this order; never cycle a fifth colour in.
# Amber is the floodlight accent itself, so bars match the scoreboard digits
# and the in-table bars.
AMBER  = FLOOD
SKY    = "#3F8FE0"
RED    = "#DD4B57"
VIOLET = "#9B7BEA"
SERIES = [AMBER, SKY, RED, VIOLET]

WIN, LOSS = SKY, RED
PHASE_COLORS = {
    "Powerplay (1-6)": AMBER,
    "Middle (7-15)":   SKY,
    "Death (16-20)":   RED,
}

BODY_FONT    = "Instrument Sans, system-ui, -apple-system, Segoe UI, sans-serif"
DISPLAY_FONT = "Big Shoulders Display, Instrument Sans, sans-serif"

LINKEDIN_URL = "https://www.linkedin.com/in/waseef-khalid-khan-366951237"


# ── Plotly template ───────────────────────────────────────────────────────────
def _register_template() -> None:
    axis_common = dict(
        zeroline=False,
        ticks="",
        tickfont=dict(color=MUTED, size=12),
        title=dict(font=dict(color=MUTED, size=12), standoff=10),
        automargin=True,
    )
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        font=dict(family=BODY_FONT, size=13, color=INK_2),
        title=dict(
            font=dict(family=BODY_FONT, size=15, color=INK, weight=600),
            x=0, xanchor="left", xref="container", y=0.97, yanchor="top", yref="container",
            pad=dict(l=6, t=4),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES,
        margin=dict(l=8, r=20, t=56, b=8),
        xaxis=dict(showgrid=False, showline=True, linecolor=LINE, linewidth=1, **axis_common),
        yaxis=dict(showgrid=True, gridcolor=GRID, gridwidth=1, showline=False, **axis_common),
        hoverlabel=dict(
            bgcolor=PANEL_2, bordercolor=LINE,
            font=dict(family=BODY_FONT, color=INK, size=13), align="left",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
            font=dict(color=INK_2, size=12), bgcolor="rgba(0,0,0,0)", title_text="",
        ),
        bargap=0.34,
        barcornerradius=4,
        hovermode="closest",
        coloraxis=dict(showscale=False),
        separators=".,",
    )
    pio.templates["floodlit"] = tpl
    pio.templates.default = "floodlit"


_register_template()

_PLOT_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d",
        "autoScale2d", "resetScale2d", "hoverClosestCartesian",
        "hoverCompareCartesian", "toggleSpikelines",
    ],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


# ── Global CSS ────────────────────────────────────────────────────────────────
_CSS = f"""
<style>
:root {{
  --night:{NIGHT}; --deep:{DEEP}; --panel:{PANEL}; --panel-2:{PANEL_2};
  --line:{LINE}; --ink:{INK}; --ink-2:{INK_2}; --muted:{MUTED}; --flood:{FLOOD};
  --red:{RED}; --sky:{SKY};
  --display:{DISPLAY_FONT}; --body:{BODY_FONT};
}}

/* Chrome */
#MainMenu, footer {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container, [data-testid="stMainBlockContainer"] {{
  padding-top: 2.2rem !important; padding-bottom: 4rem !important; max-width: 1440px;
}}
::selection {{ background: rgba(242,165,65,.35); color: var(--ink); }}
a {{ color: var(--flood); }}
*:focus-visible {{ outline: 2px solid var(--flood) !important; outline-offset: 2px; }}

/* Type */
h1, h2, h3 {{ letter-spacing: .005em; color: var(--ink); }}
h3 {{ font-size: 1.85rem !important; line-height: 1.1 !important; padding-top: .4rem !important; }}
h4 {{
  font-family: var(--body) !important; font-weight: 600 !important;
  font-size: 1.02rem !important; color: var(--ink) !important; letter-spacing: 0;
  padding: .6rem 0 .3rem !important;
}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: #98A2BE !important; font-size: .9rem !important; }}
.wz-lede {{ color: var(--ink-2) !important; font-size: 1.02rem !important; margin: .9rem 0 1.1rem !important; max-width: 46rem; }}
hr {{ border-color: var(--line) !important; margin: 1.6rem 0 !important; }}

/* Tabs: underline style, floodlight active bar */
[data-testid="stTabs"] [role="tablist"] {{ gap: 1.6rem; }}
[data-testid="stTabs"] button[role="tab"] {{
  padding: .55rem 0 .7rem; background: transparent;
}}
[data-testid="stTabs"] button[role="tab"] p {{
  font-size: .98rem; font-weight: 600; color: var(--muted);
}}
[data-testid="stTabs"] button[role="tab"]:hover p {{ color: var(--ink-2); }}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {{ color: var(--ink); }}
[data-baseweb="tab-highlight"] {{ background-color: var(--flood) !important; height: 3px !important; border-radius: 3px; }}
[data-baseweb="tab-border"] {{ background-color: var(--line) !important; }}
[data-testid="stTabs"] [data-testid="stTabs"] [role="tablist"] {{ gap: 1.2rem; }}
[data-testid="stTabs"] [data-testid="stTabs"] button[role="tab"] p {{ font-size: .92rem; }}

/* st.metric rows render as one scoreboard strip */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  gap: 0 !important; padding: .2rem 0; margin: .4rem 0 1rem;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {{
  padding: .85rem 1.1rem .8rem;
}}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] + [data-testid="stColumn"] {{
  border-left: 1px solid var(--line);
}}
[data-testid="stMetricLabel"] p {{ color: var(--muted) !important; font-size: .84rem !important; font-weight: 500; }}
[data-testid="stMetricValue"] {{
  font-family: var(--display) !important; color: var(--ink) !important;
  line-height: 1.05; letter-spacing: .01em;
}}
[data-testid="stMetricValue"] > div {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}

/* Buttons */
.stButton > button, .stDownloadButton > button {{
  font-weight: 600; border: 1px solid var(--line); background: transparent; color: var(--ink);
  transition: border-color .15s ease, color .15s ease, background-color .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--flood); color: var(--flood); background: rgba(242,165,65,.06);
}}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {{
  background: var(--flood); color: #1A1206; border-color: var(--flood);
}}
.stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover {{
  background: #F7B65C; color: #1A1206; border-color: #F7B65C;
}}

/* Inputs */
[data-baseweb="tag"] {{ background: rgba(242,165,65,.14) !important; }}
[data-baseweb="tag"] span {{ color: var(--flood) !important; }}
[data-testid="stWidgetLabel"] p {{ color: var(--ink-2); font-weight: 500; }}

/* Expanders */
[data-testid="stExpander"] details {{ border-color: var(--line) !important; border-radius: 10px; background: transparent; }}
[data-testid="stExpander"] summary p {{ font-weight: 600; color: var(--ink-2); }}

/* Charts sit on a panel */
[data-testid="stPlotlyChart"] {{
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: .6rem .7rem .2rem;
}}

/* Alerts */
[data-testid="stAlert"] {{ border-radius: 10px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] h2 {{ font-size: 1.7rem !important; padding: .2rem 0 .1rem !important; }}
[data-testid="stSidebar"] hr {{ margin: 1.1rem 0 !important; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 1.2rem; }}

/* Progress */
[data-testid="stProgress"] > div > div > div > div {{ background-color: var(--flood) !important; }}
.progress-label {{ color: var(--ink-2); font-size: .95rem; padding: .3rem 0; }}
.progress-label b {{ color: var(--flood); font-family: var(--display); font-size: 1.15rem; margin-left: .4rem; }}

/* ── Custom blocks ─────────────────────────────────────────────────────── */
.wz-top {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; }}
.wz-brand {{ display:flex; align-items:center; gap:.6rem; text-decoration:none; }}
.wz-brand-word {{
  font-family: var(--display); font-weight: 800; font-size: 1.55rem; letter-spacing: .06em;
  color: var(--ink); line-height: 1;
}}
.wz-brand-sub {{ color: var(--muted); font-size: .9rem; padding-left: .7rem; margin-left: .1rem; border-left: 1px solid var(--line); line-height: 1.1; }}
.wz-link {{
  color: var(--ink-2) !important; text-decoration: none; font-size: .92rem; font-weight: 500;
  border: 1px solid var(--line); border-radius: 999px; padding: .38rem .9rem .4rem;
  display: inline-flex; align-items: center; gap: .45rem; transition: border-color .15s, color .15s;
}}
.wz-link:hover {{ color: var(--flood) !important; border-color: var(--flood); }}
.wz-link svg {{ width: 14px; height: 14px; fill: currentColor; }}

.wz-title {{ margin: 2.2rem 0 .2rem; display:flex; align-items:baseline; gap:.9rem; flex-wrap:wrap; }}
.wz-title h1 {{
  font-family: var(--display) !important; font-weight: 800 !important; font-size: clamp(2.6rem, 5vw, 4rem) !important;
  line-height: .95 !important; margin: 0 !important; padding: 0 !important; color: var(--ink) !important; letter-spacing: .01em;
}}
.wz-chip {{
  font-size: .82rem; font-weight: 600; color: var(--ink-2); border: 1px solid var(--line);
  border-radius: 999px; padding: .2rem .65rem; position: relative; top: -.35rem;
}}
.wz-title + .wz-dek, .wz-dek {{ color: #98A2BE !important; font-size: 1rem !important; margin: .55rem 0 1.4rem !important; }}

/* Scoreboard strip */
.wz-board {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  background: var(--panel); border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
}}
.wz-cell {{ padding: 1.05rem 1.3rem 1rem; border-left: 1px solid var(--line); margin-left: -1px; }}
.wz-num {{
  font-family: var(--display); font-weight: 700; font-size: clamp(2.2rem, 3.4vw, 3.1rem);
  line-height: 1; color: var(--flood); letter-spacing: .015em; font-variant-numeric: tabular-nums;
}}
.wz-lbl {{ color: var(--ink-2); font-size: .9rem; margin-top: .45rem; font-weight: 500; }}
.wz-board-foot {{ color: var(--muted); font-size: .9rem; margin: .7rem .2rem 1.8rem; }}
.wz-board-foot b {{ color: var(--ink-2); font-weight: 600; }}

/* Landing hero */
.wz-hero {{ padding: 1.6rem 0 1rem; }}
.wz-wordmark {{
  font-family: var(--display) !important; font-weight: 800 !important;
  font-size: clamp(5rem, 13vw, 11rem) !important; line-height: .8 !important;
  letter-spacing: .02em; color: var(--ink) !important; margin: 0 !important; padding: 0 !important;
}}
.wz-hero .wz-hero-name {{ font-size: 1.2rem !important; font-weight: 600; color: var(--flood) !important; margin: 1.5rem 0 .7rem !important; }}
.wz-hero .wz-hero-lede {{ color: var(--ink-2) !important; font-size: 1.1rem !important; line-height: 1.6 !important; max-width: 30rem; margin: 0 0 1.6rem !important; }}
.wz-pick-head {{ color: var(--ink-2); font-size: .95rem; margin: 0 0 .7rem; }}

/* League board rows */
.wz-league-name {{ font-family: var(--display); font-weight: 700; font-size: 1.75rem; color: var(--ink); line-height: 1.05; }}
.wz-league-meta {{ color: var(--muted); font-size: .92rem; margin-top: .25rem; }}
.wz-league-count {{ font-family: var(--display); font-weight: 700; font-size: 2.1rem; color: var(--flood); line-height: 1; text-align: right; }}
.wz-league-count span {{ display:block; font-family: var(--body); font-weight: 500; font-size: .82rem; color: var(--muted); margin-top: .3rem; }}

/* Sidebar blocks */
.wz-side-league {{ font-family: var(--display); font-weight: 700; font-size: 1.35rem; color: var(--ink); line-height: 1.1; }}
.wz-side-kicker {{ color: var(--muted); font-size: .82rem; margin-bottom: .2rem; }}
.wz-inview {{ display:flex; align-items:baseline; gap:.45rem; color: var(--ink-2); font-size: .9rem; }}
.wz-inview b {{ font-family: var(--display); font-size: 1.9rem; color: var(--flood); font-weight: 700; line-height: 1; }}

/* Callouts */
.wz-callout {{
  display:flex; align-items:center; gap:.8rem; background: var(--panel); border: 1px solid var(--line);
  border-left: 3px solid var(--flood); border-radius: 10px; padding: .8rem 1rem; margin: .4rem 0 1rem; color: var(--ink-2);
}}
.wz-callout b {{ font-family: var(--display); font-size: 1.6rem; color: var(--flood); line-height: 1; }}
.wz-player {{
  font-family: var(--display) !important; font-weight: 800 !important; font-size: clamp(2.2rem, 4vw, 3.2rem) !important;
  color: var(--ink) !important; line-height: 1 !important; margin: 1.4rem 0 .4rem !important; padding: 0 !important;
}}

.wz-foot {{ color: var(--muted); font-size: .85rem; border-top: 1px solid var(--line); margin-top: 3rem; padding-top: 1.1rem; }}
.wz-foot a {{ color: var(--ink-2) !important; text-decoration: underline; text-underline-offset: 3px; }}

@media (max-width: 640px) {{
  .wz-cell {{ padding: .9rem 1rem; }}
  .wz-brand-sub {{ display:none; }}
  .wz-league-count {{ text-align: left; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; }}
}}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Small icons ───────────────────────────────────────────────────────────────
def ball_svg(size: int = 26) -> str:
    """A red cricket ball with its stitched seam — the site's mark."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 32 32" aria-hidden="true">'
        f'<circle cx="16" cy="16" r="15" fill="{RED}"/>'
        '<circle cx="16" cy="16" r="15" fill="none" stroke="rgba(0,0,0,.18)" stroke-width="1"/>'
        '<path d="M12.2 1.6 C8.4 10 8.4 22 12.2 30.4" fill="none" stroke="#F4E9D8" '
        'stroke-width="1.15" stroke-dasharray="1.4 1.7" stroke-linecap="round"/>'
        '<path d="M15.6 1.1 C11.8 10 11.8 22 15.6 30.9" fill="none" stroke="#F4E9D8" '
        'stroke-width="1.15" stroke-dasharray="1.4 1.7" stroke-linecap="round"/>'
        '<ellipse cx="22" cy="9.5" rx="3.6" ry="2.2" fill="rgba(255,255,255,.16)" transform="rotate(-35 22 9.5)"/>'
        "</svg>"
    )


_LINKEDIN_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04'
    '-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 '
    '5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 '
    '0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 '
    '22.22 0z"/></svg>'
)


def linkedin_link() -> str:
    return (
        f'<a class="wz-link" href="{LINKEDIN_URL}" target="_blank" rel="noopener">'
        f"{_LINKEDIN_SVG}Waseef Khalid Khan</a>"
    )


# ── Page blocks ───────────────────────────────────────────────────────────────
def _e(x) -> str:
    return html.escape(str(x))


def top_bar() -> None:
    st.markdown(
        f'<div class="wz-top">'
        f'<div class="wz-brand">{ball_svg(26)}<span class="wz-brand-word">WASEEF</span>'
        f'<span class="wz-brand-sub">Analytical Portal</span></div>'
        f"{linkedin_link()}</div>",
        unsafe_allow_html=True,
    )


def page_title(title: str, chip: str | None = None, dek: str | None = None) -> None:
    chip_html = f'<span class="wz-chip">{_e(chip)}</span>' if chip else ""
    dek_html = f'<p class="wz-dek">{dek}</p>' if dek else '<div style="height:1.2rem"></div>'
    st.markdown(
        f'<div class="wz-title"><h1>{_e(title)}</h1>{chip_html}</div>{dek_html}',
        unsafe_allow_html=True,
    )


def scoreboard(items: list[tuple[str, str]], foot: str | None = None, extra_class: str = "") -> None:
    """items: [(value, label), ...] → one strip of floodlit scoreboard digits."""
    cells = "".join(
        f'<div class="wz-cell"><div class="wz-num">{_e(v)}</div><div class="wz-lbl">{_e(l)}</div></div>'
        for v, l in items
    )
    foot_html = f'<div class="wz-board-foot">{foot}</div>' if foot else ""
    st.markdown(f'<div class="wz-board {extra_class}">{cells}</div>{foot_html}', unsafe_allow_html=True)


def hero() -> None:
    st.markdown(
        f"""
<section class="wz-hero">
  <h1 class="wz-wordmark">WASEEF</h1>
  <p class="wz-hero-name">Analytical Portal</p>
  <p class="wz-hero-lede">Ball-by-ball cricket data, turned into batting, bowling and match analysis
  you can narrow down to a single season, venue or toss call.</p>
  {linkedin_link()}
</section>
""",
        unsafe_allow_html=True,
    )


def league_row_text(name: str, meta: str) -> str:
    return f'<div class="wz-league-name">{_e(name)}</div><div class="wz-league-meta">{_e(meta)}</div>'


def league_count(n: int) -> str:
    return f'<div class="wz-league-count">{n:,}<span>matches</span></div>'


def footer() -> None:
    st.markdown(
        '<div class="wz-foot">Ball-by-ball data from '
        '<a href="https://cricsheet.org" target="_blank" rel="noopener">Cricsheet</a>. '
        f'Built by Waseef Khalid Khan.</div>',
        unsafe_allow_html=True,
    )


def section(title: str, note: str | None = None) -> None:
    st.subheader(title, anchor=False)
    if note:
        st.caption(note)


def lede(text: str) -> None:
    """One line under a tab that says what the tab answers."""
    st.markdown(f'<p class="wz-lede">{text}</p>', unsafe_allow_html=True)


def spacer(rem: float = 1.9) -> None:
    """Pushes a toggle down so it lines up with labelled inputs beside it."""
    st.markdown(f'<div style="height:{rem}rem"></div>', unsafe_allow_html=True)


def subsection(title: str) -> None:
    st.markdown(f"#### {title}")


def callout(value, text: str) -> None:
    st.markdown(f'<div class="wz-callout"><b>{_e(value)}</b><span>{text}</span></div>', unsafe_allow_html=True)


def player_name(name: str) -> None:
    st.markdown(f'<h2 class="wz-player">{_e(name)}</h2>', unsafe_allow_html=True)


# ── Tables ────────────────────────────────────────────────────────────────────
_LABELS = {
    "player": "Player", "team": "Team", "innings": "Inns", "runs": "Runs",
    "highest_score": "Highest", "highest": "Highest", "average": "Average",
    "strike_rate": "Strike rate", "hundreds": "100s", "fifties": "50s",
    "not_outs": "Not outs", "balls_faced": "Balls faced", "balls": "Balls",
    "overs": "Overs", "maidens": "Maidens", "runs_given": "Runs conceded",
    "wickets": "Wickets", "economy": "Economy", "bowling_sr": "Bowling SR",
    "played": "Played", "won": "Won", "lost": "Lost", "no_result": "No result",
    "win_%": "Win %", "matches": "Matches", "toss_winner": "Toss winner",
    "toss_wins": "Tosses won", "match_wins": "Matches won",
    "win_after_toss_%": "Win % after winning toss", "bat_first": "Batted first",
    "won_bat_first": "Won batting first", "win%_bat_first": "Win % batting first",
    "bat_second": "Chased", "won_bat_second": "Won chasing",
    "win%_bat_second": "Win % chasing", "opponent": "Opponent", "venue": "Venue",
    "season": "Season", "date": "Date", "event": "Event", "team1": "Team 1",
    "team2": "Team 2", "winner": "Winner", "toss_decision": "Toss decision",
    "awards": "Awards", "mom_awards": "Awards", "position": "Position",
    "fours": "4s", "sixes": "6s", "figure": "Figures", "partner": "Partner",
    "partnerships": "Innings", "total_runs": "Total runs", "avg": "Average",
    "sr": "SR", "best": "Best stand", "match_id": "Match ID", "city": "City",
    "player_of_match": "Player of the match", "winner_runs": "Won by runs",
    "winner_wickets": "Won by wickets",
}


def nice_label(col) -> str:
    c = str(col)
    if c in _LABELS:
        return _LABELS[c]
    if c != c.lower():          # already a display label ("Avg ↓", "Team", "SR")
        return c
    s = c.replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def table(df: pd.DataFrame, height=None, hide_index=None, bar: str | None = None, **kw) -> None:
    """st.dataframe with readable column labels; `bar` turns one numeric
    column into an in-cell bar so the leader stands out."""
    cfg = {}
    for col in df.columns:
        label = nice_label(col)
        if bar is not None and col == bar and pd.api.types.is_numeric_dtype(df[col]) and len(df):
            vmax = float(pd.to_numeric(df[col], errors="coerce").max() or 0) or 1.0
            is_int = pd.api.types.is_integer_dtype(df[col])
            cfg[col] = st.column_config.ProgressColumn(
                label, min_value=0, max_value=vmax, format="%d" if is_int else "%.1f",
            )
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            cfg[col] = st.column_config.DateColumn(label, format="D MMM YYYY")
        else:
            cfg[col] = st.column_config.Column(label)
    if hide_index is not True:
        cfg["_index"] = st.column_config.Column(nice_label(df.index.name) if df.index.name else "#")
    args = dict(width="stretch", column_config=cfg, **kw)
    if height is not None:
        # don't leave empty rows under short tables
        args["height"] = int(min(height, 36 + 33.5 * max(len(df), 1) + 4))
    if hide_index is not None:
        args["hide_index"] = hide_index
    st.dataframe(df, **args)


# ── Charts ────────────────────────────────────────────────────────────────────
def _chart_key() -> str:
    st.session_state["_chart_counter"] = st.session_state.get("_chart_counter", 0) + 1
    return f"chart_{st.session_state['_chart_counter']}"


def show(fig: go.Figure, height: int | None = None) -> None:
    # Streamlit sets its own Plotly default template once st.plotly_chart has
    # been imported, so pin ours on every figure.
    fig.layout.template = pio.templates["floodlit"]
    # Streamlit also writes its theme's background colours straight into the
    # layout, so set ours explicitly: the chart sits on its CSS panel.
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_family=BODY_FONT)
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, width="stretch", theme=None, key=_chart_key(), config=_PLOT_CONFIG)


def _value_format(values) -> str:
    v = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if v.empty or (v % 1 == 0).all():
        return ",.0f"
    if ((v * 10).round(6) % 1 == 0).all():
        return ",.1f"
    return ",.2f"


def bar(
    df: pd.DataFrame,
    category: str,
    value: str,
    title: str | None = None,
    color: str = AMBER,
    colors: list[str] | None = None,
    horizontal: bool = False,
    show_values: bool = True,
    labels: dict | None = None,
    height: int | None = None,
    category_order: list | None = None,
    hover_extra: dict | None = None,
) -> go.Figure:
    """Single-series bar. Horizontal for named categories (players, venues,
    teams) so long names read flat; vertical for ordered ones (seasons, overs)."""
    d = df.copy()
    fmt = _value_format(d[value])
    vlab = (labels or {}).get(value, nice_label(value))
    clab = (labels or {}).get(category, nice_label(category))
    d[category] = d[category].astype(str)
    marker_colors = colors if colors is not None else [color] * len(d)

    if horizontal:
        fig = go.Figure(go.Bar(
            x=d[value], y=d[category], orientation="h", marker_color=marker_colors,
            text=d[value] if show_values else None, texttemplate=f"%{{x:{fmt}}}" if show_values else None,
            textposition="outside", cliponaxis=False,
            textfont=dict(color=INK_2, size=12),
            hovertemplate=f"<b>%{{y}}</b><br>{vlab}: %{{x:{fmt}}}<extra></extra>",
        ))
        n = len(d)
        vmax = pd.to_numeric(d[value], errors="coerce").max()
        vmax = float(vmax) if pd.notna(vmax) and vmax > 0 else 1.0
        fig.update_layout(
            height=height or max(240, min(640, 64 + 34 * n)),
            bargap=0.28,
            xaxis=dict(visible=False, showgrid=False, range=[0, vmax * 1.14]),
            yaxis=dict(autorange="reversed", showgrid=False, tickfont=dict(color=INK_2, size=12.5), title=None),
        )
    else:
        fig = go.Figure(go.Bar(
            x=d[category], y=d[value], marker_color=marker_colors,
            text=d[value] if show_values else None, texttemplate=f"%{{y:{fmt}}}" if show_values else None,
            textposition="outside", cliponaxis=False,
            textfont=dict(color=INK_2, size=12),
            hovertemplate=f"<b>%{{x}}</b><br>{vlab}: %{{y:{fmt}}}<extra></extra>",
        ))
        fig.update_layout(
            height=height or 380,
            xaxis=dict(type="category", title=None,
                       categoryorder="array" if category_order else "trace",
                       categoryarray=[str(c) for c in category_order] if category_order else None),
            yaxis=dict(title=None, rangemode="tozero"),
        )
        if show_values:
            vmax = pd.to_numeric(d[value], errors="coerce").max()
            if pd.notna(vmax) and vmax > 0:
                fig.update_yaxes(range=[0, float(vmax) * 1.15])
        longest = d[category].str.len().max() if len(d) else 0
        if (longest > 10 and len(d) > 4) or (longest > 4 and len(d) > 6):
            fig.update_xaxes(tickangle=-45)
    if title:
        fig.update_layout(title_text=title)
    else:
        fig.update_layout(margin=dict(t=24))
    return fig


def stacked_bar(
    df: pd.DataFrame, category: str, series: dict[str, str], title: str | None = None,
    names: dict[str, str] | None = None, horizontal: bool = True, height: int | None = None,
) -> go.Figure:
    """series: {column: colour}. 2px panel-coloured gap between segments."""
    d = df.copy()
    d[category] = d[category].astype(str)
    fig = go.Figure()
    for col, colr in series.items():
        name = (names or {}).get(col, nice_label(col))
        if horizontal:
            fig.add_bar(y=d[category], x=d[col], name=name, orientation="h", marker_color=colr,
                        marker_line=dict(color=PANEL, width=2),
                        hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x}}<extra></extra>")
        else:
            fig.add_bar(x=d[category], y=d[col], name=name, marker_color=colr,
                        marker_line=dict(color=PANEL, width=2),
                        hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y}}<extra></extra>")
    fig.update_layout(barmode="stack", barcornerradius=3)
    if horizontal:
        n = len(d)
        fig.update_layout(
            height=height or max(260, min(640, 90 + 34 * n)), bargap=0.3,
            yaxis=dict(autorange="reversed", showgrid=False, tickfont=dict(color=INK_2, size=12.5), title=None),
            xaxis=dict(showgrid=True, gridcolor=GRID, showline=False, title=None),
        )
    else:
        fig.update_layout(height=height or 380, xaxis=dict(type="category", title=None), yaxis=dict(title=None))
    fig.update_layout(title_text=title) if title else fig.update_layout(margin=dict(t=40))
    return fig


def line(
    df: pd.DataFrame, x: str, y: str, title: str | None = None, color: str = AMBER,
    labels: dict | None = None, vlines: list[tuple[float, str]] | None = None,
    height: int = 340, categorical_x: bool = False,
) -> go.Figure:
    fmt = _value_format(df[y])
    xlab = (labels or {}).get(x, nice_label(x))
    ylab = (labels or {}).get(y, nice_label(y))
    fig = go.Figure(go.Scatter(
        x=df[x].astype(str) if categorical_x else df[x], y=df[y], mode="lines+markers",
        line=dict(color=color, width=2.2),
        marker=dict(size=8, color=color, line=dict(color=PANEL, width=2)),
        hovertemplate=f"<b>{xlab} %{{x}}</b><br>{ylab}: %{{y:{fmt}}}<extra></extra>",
    ))
    fig.update_layout(height=height, xaxis=dict(title=None, showgrid=False), yaxis=dict(title=None))
    if not categorical_x and pd.api.types.is_numeric_dtype(df[x]) and len(df):
        fig.update_xaxes(range=[float(df[x].min()) - .5, float(df[x].max()) + .5])
    if categorical_x:
        fig.update_xaxes(type="category")
        if len(df) > 8:
            fig.update_xaxes(tickangle=-40)
    for xpos, label in (vlines or []):
        fig.add_vline(x=xpos, line_dash="dot", line_color=MUTED, line_width=1, opacity=.7)
        if label:
            fig.add_annotation(x=xpos, y=1, yref="paper", text=label, showarrow=False,
                               xanchor="left", yanchor="bottom", xshift=4,
                               font=dict(color=MUTED, size=11))
    fig.update_layout(title_text=title) if title else fig.update_layout(margin=dict(t=28))
    return fig


def donut(df: pd.DataFrame, names: str, values: str, title: str | None = None,
          colors: list[str] | None = None, height: int = 340) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=df[names].astype(str), values=df[values], hole=.62, sort=False,
        marker=dict(colors=colors or SERIES, line=dict(color=PANEL, width=2)),
        textinfo="percent", textfont=dict(color=INK, size=13),
        hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
    ))
    fig.update_layout(height=height, showlegend=True,
                      legend=dict(orientation="v", x=1, xanchor="left", y=.5, yanchor="middle"))
    fig.update_layout(title_text=title) if title else fig.update_layout(margin=dict(t=24))
    return fig


def win_colors(values, threshold: float = 50.0) -> list[str]:
    """Bars at or above the threshold in WIN colour, below it in LOSS."""
    out = []
    for v in values:
        try:
            out.append(WIN if float(v) >= threshold else LOSS)
        except (TypeError, ValueError):
            out.append(MUTED)
    return out
