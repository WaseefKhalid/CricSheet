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




# ─────────────────────────────────────────────────────────────────────────────
# PLAYER PROFILE STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_player_profile(
    player_name: str,
    deliveries: pd.DataFrame,
    matches: pd.DataFrame,
) -> dict:
    """Comprehensive player profile: batting, bowling, win/loss splits, MOM."""
    result = {}

    # ── helper: safe groupby that won't KeyError ──────────────────────────────
    def _safe_groupby_sum(df, group_col, val_col):
        if group_col not in df.columns or val_col not in df.columns:
            return pd.DataFrame(columns=[group_col, val_col])
        return (
            df.groupby(group_col)[val_col]
            .sum()
            .reset_index()
            .sort_values(val_col, ascending=False)
        )

    def _safe_groupby_count(df, group_col):
        if group_col not in df.columns:
            return pd.DataFrame(columns=[group_col, "count"])
        return (
            df.groupby(group_col)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

    def _merge_venue(df):
        """Merge venue from matches, safely handle duplicate columns."""
        if "venue" in df.columns:
            return df  # already has venue
        m = matches[["match_id", "venue"]].drop_duplicates("match_id")
        merged = df.merge(m, on="match_id", how="left")
        return merged

    # ── win/loss match IDs for this player ───────────────────────────────────
    player_match_ids = set(
        deliveries[
            (deliveries["striker"] == player_name) |
            (deliveries["non_striker"] == player_name) |
            (deliveries["bowler"] == player_name)
        ]["match_id"].unique()
    )

    # batting team per match for this player
    bat_team_map = (
        deliveries[deliveries["striker"] == player_name][["match_id", "batting_team"]]
        .drop_duplicates("match_id")
    )

    player_matches = matches[matches["match_id"].isin(player_match_ids)].copy()
    player_matches = player_matches.merge(bat_team_map, on="match_id", how="left")

    win_ids = set(
        player_matches[
            player_matches["winner"].notna() &
            (player_matches["winner"] == player_matches["batting_team"])
        ]["match_id"].tolist()
    )
    loss_ids = set(
        player_matches[
            player_matches["winner"].notna() &
            (player_matches["winner"] != "") &
            (player_matches["winner"] != player_matches["batting_team"])
        ]["match_id"].tolist()
    )

    # ── BATTING ──────────────────────────────────────────────────────────────
    bat_df = deliveries[deliveries["striker"] == player_name].copy()

    if not bat_df.empty:
        total_runs  = int(bat_df["runs_off_bat"].sum())
        balls_faced = int((bat_df["wides"] == 0).sum())

        innings_runs = (
            bat_df.groupby(["match_id", "innings"])["runs_off_bat"]
            .sum()
        )
        innings_n = len(innings_runs)
        highest   = int(innings_runs.max()) if innings_n > 0 else 0

        dismissed = int(deliveries[
            (deliveries["player_dismissed"] == player_name) &
            deliveries["wicket_type"].notna() &
            (deliveries["wicket_type"] != "")
        ].shape[0])

        not_outs  = innings_n - dismissed
        average   = round(total_runs / dismissed, 2) if dismissed > 0 else float(total_runs)
        strike_rt = round(total_runs / balls_faced * 100, 2) if balls_faced > 0 else 0.0
        hundreds  = int((innings_runs >= 100).sum())
        fifties   = int(((innings_runs >= 50) & (innings_runs < 100)).sum())
        fours     = int((bat_df["runs_off_bat"] == 4).sum())
        sixes     = int((bat_df["runs_off_bat"] == 6).sum())

        runs_wins = int(bat_df[bat_df["match_id"].isin(win_ids)]["runs_off_bat"].sum())
        runs_loss = int(bat_df[bat_df["match_id"].isin(loss_ids)]["runs_off_bat"].sum())

        # vs team
        vs_team = _safe_groupby_sum(bat_df, "bowling_team", "runs_off_bat")
        vs_team = vs_team.rename(columns={"bowling_team": "opponent", "runs_off_bat": "runs"})

        # vs venue — merge carefully
        bat_venue = _merge_venue(bat_df)
        vs_venue_bat = _safe_groupby_sum(bat_venue, "venue", "runs_off_bat")
        vs_venue_bat = vs_venue_bat.rename(columns={"runs_off_bat": "runs"})

        result["batting"] = {
            "innings": innings_n, "runs": total_runs, "balls_faced": balls_faced,
            "highest": highest, "average": average, "strike_rate": strike_rt,
            "hundreds": hundreds, "fifties": fifties, "not_outs": not_outs,
            "fours": fours, "sixes": sixes,
            "runs_in_wins": runs_wins, "runs_in_losses": runs_loss,
            "vs_team": vs_team, "vs_venue": vs_venue_bat,
        }
    else:
        result["batting"] = None

    # ── BOWLING ──────────────────────────────────────────────────────────────
    bowl_df = deliveries[deliveries["bowler"] == player_name].copy()

    if not bowl_df.empty:
        legal     = bowl_df[(bowl_df["wides"] == 0) & (bowl_df["noballs"] == 0)]
        balls     = int(len(legal))
        overs     = round(balls // 6 + (balls % 6) / 10, 1)
        bowl_df["runs_conceded"] = (
            bowl_df["runs_off_bat"].fillna(0) +
            bowl_df["wides"].fillna(0) +
            bowl_df["noballs"].fillna(0)
        )
        runs_given = int(bowl_df["runs_conceded"].sum())

        wkt_mask = (
            bowl_df["wicket_type"].notna() &
            (bowl_df["wicket_type"] != "") &
            (~bowl_df["wicket_type"].str.lower().isin(
                ["run out", "retired hurt", "obstructing the field"]
            ))
        )
        wickets_df = bowl_df[wkt_mask]
        wickets    = int(len(wickets_df))
        economy    = round(runs_given / balls * 6, 2) if balls > 0 else 0.0
        bowl_avg   = round(runs_given / wickets, 2) if wickets > 0 else None
        bowl_sr    = round(balls / wickets, 2) if wickets > 0 else None

        wkts_wins = int(wickets_df[wickets_df["match_id"].isin(win_ids)].shape[0])
        wkts_loss = int(wickets_df[wickets_df["match_id"].isin(loss_ids)].shape[0])

        # vs team
        vs_team_bowl = _safe_groupby_count(wickets_df, "batting_team")
        vs_team_bowl = vs_team_bowl.rename(columns={"batting_team": "opponent", "count": "wickets"})

        # vs venue
        wkt_venue = _merge_venue(wickets_df)
        vs_venue_bowl = _safe_groupby_count(wkt_venue, "venue")
        vs_venue_bowl = vs_venue_bowl.rename(columns={"count": "wickets"})

        result["bowling"] = {
            "overs": overs, "runs_given": runs_given, "wickets": wickets,
            "economy": economy, "average": bowl_avg, "bowling_sr": bowl_sr,
            "wickets_in_wins": wkts_wins, "wickets_in_losses": wkts_loss,
            "vs_team": vs_team_bowl, "vs_venue": vs_venue_bowl,
        }
    else:
        result["bowling"] = None

    # ── MAN OF MATCH ─────────────────────────────────────────────────────────
    if "player_of_match" in matches.columns:
        mom_matches = matches[matches["player_of_match"] == player_name].copy()
        total_mom   = len(mom_matches)

        mom_merged = mom_matches.merge(bat_team_map, on="match_id", how="left")
        if "team1" in mom_merged.columns and "team2" in mom_merged.columns:
            mom_merged["opponent"] = np.where(
                mom_merged["team1"] == mom_merged["batting_team"],
                mom_merged["team2"],
                mom_merged["team1"],
            )
            mom_vs_team = _safe_groupby_count(mom_merged, "opponent")
            mom_vs_team = mom_vs_team.rename(columns={"count": "mom_awards"})
        else:
            mom_vs_team = pd.DataFrame(columns=["opponent", "mom_awards"])

        mom_vs_venue = pd.DataFrame(columns=["venue", "mom_awards"])
        if "venue" in mom_matches.columns:
            mom_vs_venue = _safe_groupby_count(mom_matches, "venue")
            mom_vs_venue = mom_vs_venue.rename(columns={"count": "mom_awards"})

        safe_cols = [c for c in ["match_id", "date", "venue", "team1", "team2", "season"] if c in mom_matches.columns]
        result["mom"] = {
            "total": total_mom,
            "vs_team": mom_vs_team,
            "vs_venue": mom_vs_venue,
            "matches": mom_matches[safe_cols],
        }
    else:
        result["mom"] = {
            "total": 0,
            "vs_team": pd.DataFrame(),
            "vs_venue": pd.DataFrame(),
            "matches": pd.DataFrame(),
        }

    return result
