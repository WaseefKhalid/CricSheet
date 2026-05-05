import zipfile
import io
import hashlib
import pandas as pd
import streamlit as st
from typing import Tuple


def parse_info_csv(content: str, match_id: str) -> dict:
    """Parse the key-value style _info.csv into a flat dict."""
    record = {"match_id": match_id}
    players = {}  # team -> list of players

    for line in content.splitlines():
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue

        row_type = parts[0].strip()
        if row_type != "info":
            continue

        key = parts[1].strip() if len(parts) > 1 else ""
        val = parts[2].strip() if len(parts) > 2 else ""

        if key == "team":
            # collect teams as team1 / team2
            if "team1" not in record:
                record["team1"] = val
            else:
                record["team2"] = val

        elif key == "player":
            # parts[2]=team, parts[3]=player_name
            team = parts[2].strip() if len(parts) > 2 else ""
            player = parts[3].strip() if len(parts) > 3 else ""
            if team not in players:
                players[team] = []
            players[team].append(player)

        elif key == "registry":
            # skip registry rows
            pass

        elif key in (
            "season", "date", "venue", "city", "event",
            "match_number", "toss_winner", "toss_decision",
            "player_of_match", "winner", "winner_wickets",
            "winner_runs", "umpire", "tv_umpire", "reserve_umpire",
            "match_referee", "balls_per_over", "gender",
        ):
            if key == "umpire":
                if "umpire1" not in record:
                    record["umpire1"] = val
                else:
                    record["umpire2"] = val
            elif key not in record:
                record[key] = val

    record["players"] = players
    return record


@st.cache_data(show_spinner=False)
def load_data_from_zip(uploaded_file) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Read a ZIP of PSL CSVs.
    Returns (matches_df, deliveries_df).
    """
    matches_list = []
    deliveries_list = []

    with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as z:
        names = z.namelist()

        # Separate info files from ball-by-ball files
        info_files = [n for n in names if n.endswith("_info.csv")]
        ball_files = [n for n in names if n.endswith(".csv") and not n.endswith("_info.csv")]

        # ── Parse info files ──────────────────────────────────────────────────
        for fname in info_files:
            # extract match_id from filename  e.g. "959175_info.csv" → "959175"
            base = fname.split("/")[-1]  # handle sub-folders
            match_id = base.replace("_info.csv", "")

            with z.open(fname) as f:
                content = f.read().decode("utf-8", errors="replace")
            record = parse_info_csv(content, match_id)
            matches_list.append(record)

        # ── Parse ball-by-ball files ──────────────────────────────────────────
        for fname in ball_files:
            base = fname.split("/")[-1]
            match_id = base.replace(".csv", "")

            with z.open(fname) as f:
                try:
                    df = pd.read_csv(f, dtype=str)
                except Exception:
                    continue

            if df.empty:
                continue

            # Normalise column names
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            df["match_id"] = match_id
            deliveries_list.append(df)

    # ── Build matches DataFrame ───────────────────────────────────────────────
    matches_df = pd.DataFrame(matches_list)

    # Cast numeric / date columns
    for col in ["winner_wickets", "winner_runs", "match_number", "balls_per_over"]:
        if col in matches_df.columns:
            matches_df[col] = pd.to_numeric(matches_df[col], errors="coerce")

    if "date" in matches_df.columns:
        matches_df["date"] = pd.to_datetime(matches_df["date"], errors="coerce")

    # ── Build deliveries DataFrame ────────────────────────────────────────────
    deliveries_df = pd.concat(deliveries_list, ignore_index=True) if deliveries_list else pd.DataFrame()

    numeric_cols = [
        "runs_off_bat", "extras", "wides", "noballs",
        "byes", "legbyes", "penalty", "innings",
    ]
    for col in numeric_cols:
        if col in deliveries_df.columns:
            deliveries_df[col] = pd.to_numeric(deliveries_df[col], errors="coerce").fillna(0)

    return matches_df, deliveries_df
