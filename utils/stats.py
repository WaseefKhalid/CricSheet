import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# BATTING STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_batting_stats(deliveries: pd.DataFrame, min_innings: int = 3) -> pd.DataFrame:
    """Compute per-player batting stats from deliveries."""
    if deliveries.empty or "striker" not in deliveries.columns:
        return pd.DataFrame()

    df = deliveries.copy()

    # Runs per ball
    runs = (
        df.groupby(["match_id", "innings", "striker"])["runs_off_bat"]
        .sum()
        .reset_index()
    )

    # Innings count (times batted)
    innings_count = (
        runs.groupby("striker")["match_id"]
        .count()
        .reset_index()
        .rename(columns={"match_id": "innings"})
    )

    # Total runs
    total_runs = runs.groupby("striker")["runs_off_bat"].sum().reset_index().rename(
        columns={"runs_off_bat": "runs", "striker": "player"}
    )

    # Balls faced (exclude wides)
    balls = df[df["wides"] == 0].groupby("striker").size().reset_index(name="balls_faced")
    balls = balls.rename(columns={"striker": "player"})

    # Dismissals
    dismissed = (
        df[df["player_dismissed"].notna() & (df["player_dismissed"] != "")]
        .groupby("player_dismissed")
        .size()
        .reset_index(name="dismissals")
        .rename(columns={"player_dismissed": "player"})
    )

    # 50s and 100s
    innings_runs = runs.rename(columns={"striker": "player", "runs_off_bat": "inns_runs"})
    fifties = (
        innings_runs[innings_runs["inns_runs"].between(50, 99)]
        .groupby("player")
        .size()
        .reset_index(name="fifties")
    )
    hundreds = (
        innings_runs[innings_runs["inns_runs"] >= 100]
        .groupby("player")
        .size()
        .reset_index(name="hundreds")
    )

    # Highest score
    highest = innings_runs.groupby("player")["inns_runs"].max().reset_index(name="highest_score")

    # Merge all
    stats = total_runs
    stats = stats.merge(innings_count.rename(columns={"striker": "player"}), on="player", how="left")
    stats = stats.merge(balls, on="player", how="left")
    stats = stats.merge(dismissed, on="player", how="left")
    stats = stats.merge(fifties, on="player", how="left")
    stats = stats.merge(hundreds, on="player", how="left")
    stats = stats.merge(highest, on="player", how="left")

    stats = stats.fillna(0)
    stats[["innings", "balls_faced", "dismissals", "fifties", "hundreds"]] = stats[
        ["innings", "balls_faced", "dismissals", "fifties", "hundreds"]
    ].astype(int)

    # Computed columns
    stats["not_outs"] = stats["innings"] - stats["dismissals"]
    stats["average"] = np.where(
        stats["dismissals"] > 0,
        (stats["runs"] / stats["dismissals"]).round(2),
        stats["runs"].astype(float),
    )
    stats["strike_rate"] = np.where(
        stats["balls_faced"] > 0,
        ((stats["runs"] / stats["balls_faced"]) * 100).round(2),
        0.0,
    )

    # Filter by min innings
    stats = stats[stats["innings"] >= min_innings]

    col_order = [
        "player", "innings", "runs", "highest_score", "average",
        "strike_rate", "hundreds", "fifties", "not_outs", "balls_faced",
    ]
    return stats[col_order].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# BOWLING STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_bowling_stats(deliveries: pd.DataFrame, min_overs: int = 5) -> pd.DataFrame:
    """Compute per-player bowling stats."""
    if deliveries.empty or "bowler" not in deliveries.columns:
        return pd.DataFrame()

    df = deliveries.copy()

    # Legal deliveries (not wides or no-balls count as balls bowled)
    legal = df[(df["wides"] == 0) & (df["noballs"] == 0)]
    balls_bowled = legal.groupby("bowler").size().reset_index(name="balls")

    # Runs conceded (runs_off_bat + extras but NOT byes/legbyes)
    df["runs_conceded"] = df["runs_off_bat"] + df["wides"] + df["noballs"]
    runs_given = df.groupby("bowler")["runs_conceded"].sum().reset_index(name="runs_given")

    # Wickets (exclude run outs)
    wickets = (
        df[
            df["wicket_type"].notna()
            & (df["wicket_type"] != "")
            & (~df["wicket_type"].str.lower().isin(["run out", "retired hurt", "obstructing the field"]))
        ]
        .groupby("bowler")
        .size()
        .reset_index(name="wickets")
    )

    # Maidens
    over_runs = (
        legal.groupby(["bowler", "match_id", "innings", "ball"])
        .apply(lambda g: g["runs_off_bat"].sum() + g["wides"].sum() + g["noballs"].sum())
        .reset_index(name="over_runs")
    )
    # approximate over from ball number
    over_runs["over_num"] = over_runs["ball"].apply(
        lambda b: int(float(str(b).split(".")[0])) if pd.notna(b) else 0
    )
    maiden_overs = (
        over_runs.groupby(["bowler", "match_id", "innings", "over_num"])["over_runs"]
        .sum()
        .reset_index()
    )
    maidens = (
        maiden_overs[maiden_overs["over_runs"] == 0]
        .groupby("bowler")
        .size()
        .reset_index(name="maidens")
    )

    # Merge
    stats = balls_bowled.rename(columns={"bowler": "player"})
    stats = stats.merge(runs_given.rename(columns={"bowler": "player"}), on="player", how="left")
    stats = stats.merge(wickets.rename(columns={"bowler": "player"}), on="player", how="left")
    stats = stats.merge(maidens.rename(columns={"bowler": "player"}), on="player", how="left")
    stats = stats.fillna(0)
    stats[["balls", "runs_given", "wickets", "maidens"]] = stats[
        ["balls", "runs_given", "wickets", "maidens"]
    ].astype(int)

    stats["overs"] = (stats["balls"] // 6 + (stats["balls"] % 6) / 10).round(1)
    stats["economy"] = np.where(
        stats["balls"] > 0,
        ((stats["runs_given"] / stats["balls"]) * 6).round(2),
        0.0,
    )
    stats["average"] = np.where(
        stats["wickets"] > 0,
        (stats["runs_given"] / stats["wickets"]).round(2),
        np.nan,
    )
    stats["bowling_sr"] = np.where(
        stats["wickets"] > 0,
        (stats["balls"] / stats["wickets"]).round(2),
        np.nan,
    )

    stats = stats[stats["overs"] >= min_overs]

    col_order = ["player", "overs", "maidens", "runs_given", "wickets", "economy", "average", "bowling_sr"]
    return stats[col_order].reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# MATCH STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_match_stats(matches: pd.DataFrame) -> pd.DataFrame:
    """Return a clean match results table."""
    cols = [c for c in [
        "match_id", "date", "season", "event", "venue", "city",
        "team1", "team2", "toss_winner", "toss_decision",
        "winner", "winner_wickets", "winner_runs", "player_of_match",
    ] if c in matches.columns]
    return matches[cols].sort_values("date", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# PLAYER OF MATCH
# ─────────────────────────────────────────────────────────────────────────────

def get_player_of_match_stats(matches: pd.DataFrame) -> pd.DataFrame:
    if "player_of_match" not in matches.columns:
        return pd.DataFrame()
    pom = (
        matches["player_of_match"]
        .dropna()
        .value_counts()
        .reset_index()
    )
    pom.columns = ["player_of_match", "awards"]
    return pom


# ─────────────────────────────────────────────────────────────────────────────
# TEAM STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_team_stats(matches: pd.DataFrame) -> pd.DataFrame:
    """Win/loss/NR record per team."""
    if matches.empty:
        return pd.DataFrame()

    teams = set()
    if "team1" in matches.columns:
        teams.update(matches["team1"].dropna().unique())
    if "team2" in matches.columns:
        teams.update(matches["team2"].dropna().unique())

    records = []
    for team in sorted(teams):
        played = matches[(matches.get("team1", pd.Series()) == team) | (matches.get("team2", pd.Series()) == team)]
        won = played[played.get("winner", pd.Series()) == team] if "winner" in played.columns else pd.DataFrame()
        lost = played[
            played["winner"].notna() & (played["winner"] != team) & (played["winner"] != "")
        ] if "winner" in played.columns else pd.DataFrame()
        nr = played[played["winner"].isna() | (played["winner"] == "")] if "winner" in played.columns else pd.DataFrame()

        win_pct = round(len(won) / len(played) * 100, 1) if len(played) > 0 else 0.0
        records.append({
            "team": team,
            "played": len(played),
            "won": len(won),
            "lost": len(lost),
            "no_result": len(nr),
            "win_%": win_pct,
        })

    return pd.DataFrame(records).sort_values("won", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# TOSS STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_toss_stats(matches: pd.DataFrame) -> pd.DataFrame:
    """How often toss winner also wins the match."""
    if matches.empty or "toss_winner" not in matches.columns:
        return pd.DataFrame()

    df = matches.copy()
    df["toss_won_match"] = df["toss_winner"] == df["winner"]

    stats = (
        df.groupby("toss_winner")
        .agg(
            toss_wins=("toss_winner", "count"),
            match_wins=("toss_won_match", "sum"),
        )
        .reset_index()
    )
    stats["win_after_toss_%"] = (stats["match_wins"] / stats["toss_wins"] * 100).round(1)
    return stats.sort_values("toss_wins", ascending=False).reset_index(drop=True)
