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
# BATTING FIRST vs BATTING SECOND STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_batting_order_stats(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """
    For each team: matches played, won batting first, won batting second,
    win% batting first, win% batting second.
    """
    if matches.empty or deliveries.empty:
        return pd.DataFrame()

    # Find which team batted first in each match (innings == 1)
    inn1 = (
        deliveries[pd.to_numeric(deliveries["innings"], errors="coerce") == 1]
        [["match_id", "batting_team"]]
        .drop_duplicates("match_id")
        .rename(columns={"batting_team": "bat_first_team"})
    )

    df = matches.merge(inn1, on="match_id", how="left")
    df["bat_second_team"] = np.where(
        df["bat_first_team"] == df["team1"], df["team2"], df["team1"]
    )

    teams = sorted(set(
        list(df["team1"].dropna()) + list(df["team2"].dropna())
    ))

    records = []
    for team in teams:
        # All matches this team played
        played_df = df[(df["team1"] == team) | (df["team2"] == team)]
        total = len(played_df)
        if total == 0:
            continue

        # Batting first matches
        bat_first_df  = played_df[played_df["bat_first_team"] == team]
        bat_second_df = played_df[played_df["bat_second_team"] == team]

        bf_total = len(bat_first_df)
        bs_total = len(bat_second_df)

        bf_won = int((bat_first_df["winner"] == team).sum())
        bs_won = int((bat_second_df["winner"] == team).sum())

        bf_pct = round(bf_won / bf_total * 100, 1) if bf_total > 0 else 0.0
        bs_pct = round(bs_won / bs_total * 100, 1) if bs_total > 0 else 0.0

        total_won = bf_won + bs_won
        total_pct = round(total_won / total * 100, 1) if total > 0 else 0.0

        records.append({
            "team":              team,
            "matches":           total,
            "won":               total_won,
            "win_%":             total_pct,
            "bat_first":         bf_total,
            "won_bat_first":     bf_won,
            "win%_bat_first":    bf_pct,
            "bat_second":        bs_total,
            "won_bat_second":    bs_won,
            "win%_bat_second":   bs_pct,
        })

    return pd.DataFrame(records).sort_values("won", ascending=False).reset_index(drop=True)

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


# ─────────────────────────────────────────────────────────────────────────────
# PRECOMPUTE ALL PLAYER PROFILES AT ONCE (fast bulk version)
# ─────────────────────────────────────────────────────────────────────────────

def _get_partnerships(p_agg: pd.DataFrame, player: str) -> pd.DataFrame:
    """Extract and rank partnerships for a player, sorted by avg descending."""
    if p_agg.empty:
        return pd.DataFrame()
    as_p1 = p_agg[p_agg["p1"] == player].copy().rename(columns={"p2": "partner"})
    as_p2 = p_agg[p_agg["p2"] == player].copy().rename(columns={"p1": "partner"})
    combined = pd.concat([as_p1, as_p2], ignore_index=True)
    if combined.empty:
        return pd.DataFrame()
    result = (
        combined.groupby("partner")
        .agg(
            partnerships=("partnerships","sum"),
            total_runs   =("total_runs","sum"),
            best         =("best","max"),
        )
        .reset_index()
    )
    result["avg"] = (result["total_runs"] / result["partnerships"]).round(1)
    return (
        result[["partner","partnerships","total_runs","avg","best"]]
        .sort_values("avg", ascending=False)
        .reset_index(drop=True)
    )

def precompute_all_profiles(
    deliveries: pd.DataFrame,
    matches: pd.DataFrame,
) -> dict:
    """
    Compute stats for ALL players in one vectorized pass.
    Returns dict: { player_name -> profile_dict }
    Much faster than calling get_player_profile() per player.
    """
    profiles = {}

    # ── shared lookup: venue per match ───────────────────────────────────────
    venue_map = matches.set_index("match_id")["venue"].to_dict() if "venue" in matches.columns else {}

    # ── win/loss per match per batting team ──────────────────────────────────
    # match_id -> winner
    winner_map = matches.set_index("match_id")["winner"].to_dict() if "winner" in matches.columns else {}

    # ── BATTING ──────────────────────────────────────────────────────────────
    bat = deliveries.copy()
    bat["venue"] = bat["match_id"].map(venue_map)
    bat["winner"] = bat["match_id"].map(winner_map)
    bat["bat_won"] = bat["winner"] == bat["batting_team"]

    # ── Top innings: runs + balls + 4s + 6s per match+innings per player ─────
    bat_legal_inn = bat[bat["wides"] == 0]
    top_inn_runs  = bat.groupby(["striker","match_id","innings","batting_team"])["runs_off_bat"].sum()
    top_inn_balls = bat_legal_inn.groupby(["striker","match_id","innings"])["runs_off_bat"].count()
    top_inn_4s    = bat[bat["runs_off_bat"]==4].groupby(["striker","match_id","innings"]).size()
    top_inn_6s    = bat[bat["runs_off_bat"]==6].groupby(["striker","match_id","innings"]).size()

    # Build innings-level DataFrame
    top_innings_df = top_inn_runs.reset_index().rename(columns={"runs_off_bat":"runs"})
    top_innings_df = top_innings_df.merge(
        top_inn_balls.reset_index().rename(columns={"runs_off_bat":"balls"}),
        on=["striker","match_id","innings"], how="left"
    )
    top_innings_df = top_innings_df.merge(
        top_inn_4s.reset_index().rename(columns={0:"fours"}),
        on=["striker","match_id","innings"], how="left"
    )
    top_innings_df = top_innings_df.merge(
        top_inn_6s.reset_index().rename(columns={0:"sixes"}),
        on=["striker","match_id","innings"], how="left"
    )
    top_innings_df[["balls","fours","sixes"]] = top_innings_df[["balls","fours","sixes"]].fillna(0).astype(int)
    top_innings_df["SR"] = (top_innings_df["runs"] / top_innings_df["balls"] * 100).round(1).where(top_innings_df["balls"] > 0, 0)

    # Add opponent team & venue
    opp_map = (
        bat.groupby(["match_id","striker","batting_team"])
        .first()
        .reset_index()[["match_id","striker","batting_team","bowling_team","venue"]]
        .drop_duplicates(["match_id","striker"])
    )
    top_innings_df = top_innings_df.merge(
        opp_map.rename(columns={"bowling_team":"opponent"}),
        on=["match_id","striker"], how="left"
    )
    # Add season
    season_map = matches.set_index("match_id")["season"].to_dict() if "season" in matches.columns else {}
    top_innings_df["season"] = top_innings_df["match_id"].map(season_map)

    # ── Partnership Analysis ─────────────────────────────────────────────────
    # For each match+innings, both striker and non_striker are batting together
    # A "partnership run" is any ball where both players are at the crease
    # We attribute ALL runs scored in an over sequence to the partnership

    # Get all legal deliveries with both players
    p_df = bat[["match_id","innings","striker","non_striker","runs_off_bat","batting_team"]].copy()
    p_df["runs_off_bat"] = p_df["runs_off_bat"].fillna(0)

    # Create canonical partnership key (sorted so A+B == B+A)
    p_df["p1"] = np.where(p_df["striker"] < p_df["non_striker"],
                          p_df["striker"], p_df["non_striker"])
    p_df["p2"] = np.where(p_df["striker"] < p_df["non_striker"],
                          p_df["non_striker"], p_df["striker"])

    # Runs per partnership per match+innings
    p_runs = (
        p_df.groupby(["p1","p2","match_id","innings"])["runs_off_bat"]
        .sum()
        .reset_index()
        .rename(columns={"runs_off_bat":"stand_runs"})
    )

    # Aggregate across all stands
    p_agg = (
        p_runs.groupby(["p1","p2"])
        .agg(
            partnerships=("stand_runs","count"),
            total_runs   =("stand_runs","sum"),
            best         =("stand_runs","max"),
        )
        .reset_index()
    )
    p_agg["avg"] = (p_agg["total_runs"] / p_agg["partnerships"]).round(1)

    # runs per ball-level groupby
    bat_legal = bat[bat["wides"] == 0]

    # total runs & balls per player
    runs_total = bat.groupby("striker")["runs_off_bat"].sum()
    balls_total = bat_legal.groupby("striker").size()

    # innings runs (for avg, HS, 50s, 100s)
    inn_runs = (
        bat.groupby(["striker", "match_id", "innings"])["runs_off_bat"]
        .sum()
        .reset_index()
        .rename(columns={"runs_off_bat": "inns_runs"})
    )
    innings_count = inn_runs.groupby("striker")["match_id"].count()
    highest       = inn_runs.groupby("striker")["inns_runs"].max()
    hundreds      = inn_runs[inn_runs["inns_runs"] >= 100].groupby("striker").size()
    fifties       = inn_runs[(inn_runs["inns_runs"] >= 50) & (inn_runs["inns_runs"] < 100)].groupby("striker").size()

    # dismissals
    dismissed = (
        deliveries[
            deliveries["player_dismissed"].notna() &
            (deliveries["player_dismissed"] != "") &
            deliveries["wicket_type"].notna()
        ]
        .groupby("player_dismissed")
        .size()
    )

    # 4s and 6s
    fours = bat[bat["runs_off_bat"] == 4].groupby("striker").size()
    sixes = bat[bat["runs_off_bat"] == 6].groupby("striker").size()

    # runs in wins/losses
    runs_wins = bat[bat["bat_won"] == True].groupby("striker")["runs_off_bat"].sum()
    runs_loss = bat[bat["bat_won"] == False].groupby("striker")["runs_off_bat"].sum()

    # runs vs each opponent team
    vs_team_bat = (
        bat.groupby(["striker", "bowling_team"])["runs_off_bat"]
        .sum()
        .reset_index()
        .rename(columns={"striker": "player", "bowling_team": "opponent", "runs_off_bat": "runs"})
    )

    # runs at each venue
    vs_venue_bat = (
        bat.groupby(["striker", "venue"])["runs_off_bat"]
        .sum()
        .reset_index()
        .rename(columns={"striker": "player", "runs_off_bat": "runs"})
    )

    # ── BOWLING ──────────────────────────────────────────────────────────────
    bowl = deliveries.copy()
    bowl["venue"]   = bowl["match_id"].map(venue_map)
    bowl["winner"]  = bowl["match_id"].map(winner_map)
    bowl["bowl_won"] = bowl["winner"] == bowl["bowling_team"]

    bowl_legal = bowl[(bowl["wides"] == 0) & (bowl["noballs"] == 0)]
    balls_bowl = bowl_legal.groupby("bowler").size()

    bowl["runs_conceded"] = (
        bowl["runs_off_bat"].fillna(0) +
        bowl["wides"].fillna(0) +
        bowl["noballs"].fillna(0)
    )
    runs_given = bowl.groupby("bowler")["runs_conceded"].sum()

    wkt_mask = (
        bowl["wicket_type"].notna() &
        (bowl["wicket_type"] != "") &
        (~bowl["wicket_type"].str.lower().isin(
            ["run out", "retired hurt", "obstructing the field"]
        ))
    )
    wkts_df = bowl[wkt_mask]
    wickets_total = wkts_df.groupby("bowler").size()

    wkts_wins = wkts_df[wkts_df["bowl_won"] == True].groupby("bowler").size()
    wkts_loss = wkts_df[wkts_df["bowl_won"] == False].groupby("bowler").size()

    # ── Top bowling figures: wickets + runs conceded per match+innings ────────
    bowl["runs_c"] = bowl["runs_off_bat"].fillna(0) + bowl["wides"].fillna(0) + bowl["noballs"].fillna(0)
    top_fig_wkts = wkts_df.groupby(["bowler","match_id","innings"]).size().reset_index(name="wickets")
    top_fig_runs = bowl.groupby(["bowler","match_id","innings"])["runs_c"].sum().reset_index(name="runs_given")
    top_fig_balls = bowl[(bowl["wides"]==0)&(bowl["noballs"]==0)].groupby(["bowler","match_id","innings"]).size().reset_index(name="balls")

    top_figures_df = top_fig_wkts.merge(top_fig_runs, on=["bowler","match_id","innings"], how="left")
    top_figures_df = top_figures_df.merge(top_fig_balls, on=["bowler","match_id","innings"], how="left")
    top_figures_df["balls"] = top_figures_df["balls"].fillna(0).astype(int)
    top_figures_df["overs"] = (top_figures_df["balls"] // 6 + (top_figures_df["balls"] % 6) / 10).round(1)

    # Add batting team (opponent) and venue
    bowl_opp = (
        bowl.groupby(["match_id","bowler","bowling_team"])
        .first()
        .reset_index()[["match_id","bowler","bowling_team","batting_team","venue"]]
        .drop_duplicates(["match_id","bowler"])
    )
    top_figures_df = top_figures_df.merge(
        bowl_opp.rename(columns={"batting_team":"opponent"}),
        on=["match_id","bowler"], how="left"
    )
    top_figures_df["season"] = top_figures_df["match_id"].map(season_map)
    top_figures_df["figure"] = top_figures_df["wickets"].astype(str) + "/" + top_figures_df["runs_given"].astype(int).astype(str)

    vs_team_bowl = (
        wkts_df.groupby(["bowler", "batting_team"])
        .size()
        .reset_index()
        .rename(columns={"bowler": "player", "batting_team": "opponent", 0: "wickets"})
    )
    vs_team_bowl.columns = ["player", "opponent", "wickets"]

    vs_venue_bowl = (
        wkts_df.groupby(["bowler", "venue"])
        .size()
        .reset_index()
        .rename(columns={0: "wickets"})
    )
    vs_venue_bowl.columns = ["player", "venue", "wickets"]

    # ── MOM ───────────────────────────────────────────────────────────────────
    mom_df = pd.DataFrame()
    if "player_of_match" in matches.columns:
        mom_df = matches[matches["player_of_match"].notna()].copy()

    # bat_team per match per player (for MOM opponent calc)
    bat_team_map = (
        deliveries[deliveries["striker"].notna()][["match_id", "striker", "batting_team"]]
        .drop_duplicates(["match_id", "striker"])
    )

    # ── BUILD PROFILE DICT PER PLAYER ────────────────────────────────────────
    all_players = set(
        list(deliveries["striker"].dropna().unique()) +
        list(deliveries["bowler"].dropna().unique())
    )

    for player in all_players:
        profile = {}

        # batting
        r = int(runs_total.get(player, 0))
        if r > 0 or player in balls_total.index:
            b   = int(balls_total.get(player, 0))
            inn = int(innings_count.get(player, 0))
            hs  = int(highest.get(player, 0))
            dis = int(dismissed.get(player, 0))
            no  = inn - dis
            avg = round(r / dis, 2) if dis > 0 else float(r)
            sr  = round(r / b * 100, 2) if b > 0 else 0.0

            profile["batting"] = {
                "innings": inn, "runs": r, "balls_faced": b,
                "highest": hs, "average": avg, "strike_rate": sr,
                "hundreds": int(hundreds.get(player, 0)),
                "fifties":  int(fifties.get(player, 0)),
                "not_outs": no,
                "fours": int(fours.get(player, 0)),
                "sixes": int(sixes.get(player, 0)),
                "runs_in_wins":   int(runs_wins.get(player, 0)),
                "runs_in_losses": int(runs_loss.get(player, 0)),
                "vs_team": vs_team_bat[vs_team_bat["player"] == player][["opponent","runs"]].sort_values("runs", ascending=False),
                "vs_venue": vs_venue_bat[vs_venue_bat["player"] == player][["venue","runs"]].sort_values("runs", ascending=False),
                "top_innings": (
                    top_innings_df[top_innings_df["striker"] == player]
                    [["season","opponent","venue","innings","runs","balls","SR","fours","sixes"]]
                    .sort_values("runs", ascending=False)
                    .head(10)
                    .reset_index(drop=True)
                ),
                "partnerships": _get_partnerships(p_agg, player),
            }
        else:
            profile["batting"] = None

        # bowling
        w = int(wickets_total.get(player, 0))
        bl = int(balls_bowl.get(player, 0))
        if bl > 0:
            rg  = int(runs_given.get(player, 0))
            ovs = round(bl // 6 + (bl % 6) / 10, 1)
            eco = round(rg / bl * 6, 2) if bl > 0 else 0.0
            avg_b = round(rg / w, 2) if w > 0 else None
            sr_b  = round(bl / w, 2) if w > 0 else None

            profile["bowling"] = {
                "overs": ovs, "runs_given": rg, "wickets": w,
                "economy": eco, "average": avg_b, "bowling_sr": sr_b,
                "wickets_in_wins":   int(wkts_wins.get(player, 0)),
                "wickets_in_losses": int(wkts_loss.get(player, 0)),
                "vs_team":  vs_team_bowl[vs_team_bowl["player"] == player][["opponent","wickets"]].sort_values("wickets", ascending=False),
                "vs_venue": vs_venue_bowl[vs_venue_bowl["player"] == player][["venue","wickets"]].sort_values("wickets", ascending=False),
                "top_figures": (
                    top_figures_df[top_figures_df["bowler"] == player]
                    [["season","opponent","venue","innings","figure","wickets","runs_given","overs"]]
                    .sort_values(["wickets","runs_given"], ascending=[False,True])
                    .head(10)
                    .reset_index(drop=True)
                ),
            }
        else:
            profile["bowling"] = None

        # mom
        if not mom_df.empty:
            pm = mom_df[mom_df["player_of_match"] == player]
            total_mom = len(pm)

            # opponent per MOM match
            pbat = bat_team_map[bat_team_map["striker"] == player][["match_id","batting_team"]].drop_duplicates("match_id")
            pm2  = pm.merge(pbat, on="match_id", how="left")
            if "team1" in pm2.columns and "team2" in pm2.columns:
                pm2["opponent"] = np.where(
                    pm2["team1"] == pm2["batting_team"],
                    pm2["team2"], pm2["team1"]
                )
                mom_vs_team = pm2.groupby("opponent").size().reset_index(name="mom_awards").sort_values("mom_awards", ascending=False)
            else:
                mom_vs_team = pd.DataFrame(columns=["opponent","mom_awards"])

            mom_vs_venue = pd.DataFrame(columns=["venue","mom_awards"])
            if "venue" in pm.columns:
                mom_vs_venue = pm.groupby("venue").size().reset_index(name="mom_awards").sort_values("mom_awards", ascending=False)

            safe_cols = [c for c in ["match_id","date","venue","team1","team2","season"] if c in pm.columns]
            profile["mom"] = {
                "total": total_mom,
                "vs_team": mom_vs_team,
                "vs_venue": mom_vs_venue,
                "matches": pm[safe_cols],
            }
        else:
            profile["mom"] = {"total": 0, "vs_team": pd.DataFrame(), "vs_venue": pd.DataFrame(), "matches": pd.DataFrame()}

        profiles[player] = profile

    return profiles
