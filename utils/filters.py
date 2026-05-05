import pandas as pd
from typing import Dict, List


def get_filter_options(matches_df: pd.DataFrame) -> Dict[str, List]:
    """Extract unique sorted values for each filterable column."""
    def _sorted(series):
        return sorted(series.dropna().unique().tolist())

    teams = set()
    if "team1" in matches_df.columns:
        teams.update(matches_df["team1"].dropna().unique().tolist())
    if "team2" in matches_df.columns:
        teams.update(matches_df["team2"].dropna().unique().tolist())

    return {
        "seasons":        _sorted(matches_df["season"])         if "season"        in matches_df.columns else [],
        "venues":         _sorted(matches_df["venue"])          if "venue"         in matches_df.columns else [],
        "teams":          sorted(teams),
        "toss_winners":   _sorted(matches_df["toss_winner"])    if "toss_winner"   in matches_df.columns else [],
        "toss_decisions": _sorted(matches_df["toss_decision"])  if "toss_decision" in matches_df.columns else [],
        "winners":        _sorted(matches_df["winner"])         if "winner"        in matches_df.columns else [],
        "cities":         _sorted(matches_df["city"])           if "city"          in matches_df.columns else [],
        "events":         _sorted(matches_df["event"])          if "event"         in matches_df.columns else [],
    }


def apply_filters(matches_df: pd.DataFrame, filters: Dict[str, List]) -> pd.DataFrame:
    """
    Apply a dict of filters to matches_df.
    Each key maps to a list of selected values (empty = no filter on that key).
    """
    df = matches_df.copy()

    season = filters.get("season", [])
    if season:
        df = df[df["season"].isin(season)]

    venue = filters.get("venue", [])
    if venue:
        df = df[df["venue"].isin(venue)]

    team = filters.get("team", [])
    if team:
        df = df[df["team1"].isin(team) | df["team2"].isin(team)]

    toss_winner = filters.get("toss_winner", [])
    if toss_winner:
        df = df[df["toss_winner"].isin(toss_winner)]

    toss_decision = filters.get("toss_decision", [])
    if toss_decision:
        df = df[df["toss_decision"].isin(toss_decision)]

    winner = filters.get("winner", [])
    if winner:
        df = df[df["winner"].isin(winner)]

    city = filters.get("city", [])
    if city:
        df = df[df["city"].isin(city)]

    return df
