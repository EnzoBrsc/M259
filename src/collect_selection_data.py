"""Préparer des sélections expérimentales à partir de snapshots de statistiques réelles.

Les labels sont calculés par le protocole M259, jamais présentés comme des votes.
Les gros snapshots restent dans artifacts/source_cache, hors Git.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.football_selections import IDENTIFIERS, SelectionConfig, validate_selection_frame
from src.schema import InputError

ROOT = Path(__file__).resolve().parents[1]
CODES = {"ENG": "Premier League", "ESP": "La Liga", "GER": "Bundesliga", "ITA": "Serie A", "FRA": "Ligue 1"}
ESPN = {"eng.1": "Premier League", "esp.1": "La Liga", "ger.1": "Bundesliga", "ita.1": "Serie A", "fra.1": "Ligue 1"}
QUOTAS = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}
SEASON_FEATURES = ["goals", "assists", "minutes", "matches", "tackles", "interceptions", "saves", "goals_conceded", "clean_sheets"]
MATCH_FEATURES = ["goals", "assists", "matches", "shots_on_goal", "yellow_cards", "red_cards", "team_wins", "clean_sheets", "goals_conceded"]
SNAPSHOT = "8940299c2c56c2c0932d3caf292336f5e1689893"


def role(value):
    """Premier poste déclaré ; aucun poste déduit d'une récompense future."""
    first = str(value).split(",")[0].strip().split("-")[0]
    mapping = {"GK": "GK", "G": "GK", "DF": "DEF", "D": "DEF", "CB": "DEF", "LB": "DEF", "RB": "DEF", "WB": "DEF",
               "MF": "MID", "M": "MID", "CM": "MID", "DM": "MID", "AM": "MID", "LM": "MID", "RM": "MID",
               "CD": "DEF", "SW": "DEF", "FW": "FWD", "F": "FWD", "CF": "FWD", "LF": "FWD", "RF": "FWD", "RCF": "FWD", "LW": "FWD", "RW": "FWD", "ST": "FWD"}
    if first not in mapping:
        raise InputError(f"Poste source inconnu : {value!r}.")
    return mapping[first]


def aggregate_stints(frame, *, totals):
    """Les comptes par club sont additionnés, les totaux saisonniers répétés pris au max."""
    keys = ["period_end", "competition", "player_id"]
    sums = [n for n in frame.columns if n not in keys + ["player", "position"] + totals]
    return frame.groupby(keys, as_index=False, sort=True).agg(
        {"player": "first", "position": "first", **{n: lambda s: s.sum(min_count=1) for n in sums}, **{n: "max" for n in totals}})


def rule_scores(frame, *, season):
    """Règle figée avant entraînement ; n'entre pas comme variable du modèle."""
    if season:
        # Les manquants de la règle valent zéro contribution, pas une observation de zéro.
        v = frame[SEASON_FEATURES].fillna(0)
        n = v.minutes / 90
        scores = (4 * v.goals + 3 * v.assists) / n
        scores.loc[frame.position.eq("DEF")] = ((4 * v.goals + 3 * v.assists + v.tackles + v.interceptions) / n).loc[frame.position.eq("DEF")]
        scores.loc[frame.position.eq("MID")] = ((4 * v.goals + 3 * v.assists + .5 * v.tackles + .5 * v.interceptions) / n).loc[frame.position.eq("MID")]
        keeper = 4 * v.clean_sheets / v.matches + v.saves / n - v.goals_conceded / n
        scores.loc[frame.position.eq("GK")] = keeper.loc[frame.position.eq("GK")]
        return scores
    v = frame[MATCH_FEATURES].fillna(0)
    scores = 4 * v.goals + 3 * v.assists + .25 * v.shots_on_goal + v.team_wins - .5 * v.yellow_cards - 2 * v.red_cards
    defensive = frame.position.isin(["GK", "DEF"])
    scores.loc[defensive] += (2 * v.clean_sheets - .5 * v.goals_conceded).loc[defensive]
    return scores


def label_frame(frame, *, award, season):
    frame = frame.copy().reset_index(drop=True)
    scores = rule_scores(frame, season=season)
    audit = frame[IDENTIFIERS + ["position"]].copy()
    audit["rule_score"] = scores
    frame["selected"] = 0
    rejected = []
    for key, group in frame.groupby(["period_end", "competition"]):
        if award != "POTM" and any(group.position.eq(p).sum() <= q for p, q in QUOTAS.items()):
            rejected.append(key)
            continue
        ordered = group.assign(_score=scores.loc[group.index], _tie=group.player_id.str.casefold()).sort_values(["_score", "_tie"], ascending=[False, True], kind="stable")
        selected = ordered.head(1) if award == "POTM" else pd.concat([ordered.loc[ordered.position.eq(p)].head(q) for p, q in QUOTAS.items()])
        frame.loc[selected.index, "selected"] = 1
    keep = ~frame.set_index(["period_end", "competition"]).index.isin(rejected)
    frame = frame.loc[keep].copy()
    # Date analytique de disponibilité potentielle, pas une date de publication officielle.
    frame["label_available_on"] = frame.period_end
    audit = audit.loc[keep].copy()
    audit["selected"] = frame.selected
    return frame.reset_index(drop=True), audit.reset_index(drop=True), rejected


def historical_seasons(cache):
    import pyreadr
    std = pyreadr.read_r(cache / "season_standard.rds")[None]
    defense = pyreadr.read_r(cache / "season_defense.rds")[None]
    keepers = pyreadr.read_r(cache / "season_keepers.rds")[None]
    std = std.loc[std.Season_End_Year.between(2018, 2025)].copy()
    # Deux lignes sans poste (1 et 5 minutes), inéligibles au seuil de 900 minutes.
    unknown = std.Pos.isna() | std.Pos.eq("")
    if std.loc[unknown, "Min_Playing"].ge(900).any():
        raise InputError("Saison : joueur éligible sans poste documenté.")
    std = std.loc[~unknown].copy()
    keys = ["Season_End_Year", "Comp", "Squad", "Url"]
    for other, cols in [(defense, {"Tkl_Tackles": "tackles", "Int": "interceptions"}),
                        (keepers, {"Saves": "saves", "GA": "goals_conceded", "CS": "clean_sheets"})]:
        subset = other[keys + list(cols)].rename(columns=cols)
        if subset.duplicated(keys).any():
            raise InputError("Clés du snapshot saison dupliquées, vérifier la jointure.")
        std = std.merge(subset, on=keys, how="left", validate="many_to_one")
    frame = std.rename(columns={"Player": "player", "Comp": "competition", "Gls": "goals", "Ast": "assists", "Min_Playing": "minutes", "MP_Playing": "matches"})
    frame["period_end"] = frame.Season_End_Year.map(lambda y: f"{y}-06-30")
    frame["player_id"] = "fbref:" + frame.Url.str.extract(r"/players/([^/]+)")[0]
    frame["position"] = frame.Pos.map(role)
    if frame.player_id.isna().any():
        raise InputError("Identifiant FBref absent.")
    frame = aggregate_stints(frame[IDENTIFIERS + SEASON_FEATURES + ["position"]], totals=[])
    frame.loc[frame.position.ne("GK"), ["saves", "goals_conceded", "clean_sheets"]] = 0
    return frame.loc[frame.minutes.ge(900)].reset_index(drop=True)


def current_season(cache):
    raw = pd.read_csv(cache / "master.csv")
    raw = raw.loc[raw.season_label.eq("2025/26")].copy()
    mapping = {"ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga", "GER-Bundesliga": "Bundesliga", "ITA-Serie A": "Serie A", "FRA-Ligue 1": "Ligue 1"}
    raw["competition"] = raw.league.map(mapping)
    if raw.competition.isna().any():
        raise InputError("Ligue non reconnue dans le snapshot 2025/26.")
    raw["period_end"] = "2026-06-30"
    raw["player_id"] = raw.apply(lambda r: f"sofascore:{int(r.ss_player_id)}" if pd.notna(r.ss_player_id) else "name-birth:" + hashlib.sha256(f"{r.player}|{r.born}".encode()).hexdigest()[:16], axis=1)
    raw["position"] = raw.pos.map(role)
    rename = {"fb_gls": "goals", "fb_ast": "assists", "playing_time_min": "minutes", "playing_time_mp": "matches", "ss_tackles": "tackles", "ss_interceptions": "interceptions", "ss_saves": "saves", "ss_goalsConceded": "goals_conceded", "ss_cleanSheet": "clean_sheets"}
    raw = raw.rename(columns=rename)
    # SofaScore fournit des totaux par joueur/saison, FBref fournit des passages par club.
    frame = aggregate_stints(raw[IDENTIFIERS + SEASON_FEATURES + ["position"]], totals=["tackles", "interceptions", "saves", "goals_conceded", "clean_sheets"])
    frame.loc[frame.position.ne("GK"), ["saves", "goals_conceded", "clean_sheets"]] = 0
    return frame.loc[frame.minutes.ge(900)].reset_index(drop=True)


def historical_matches(cache):
    frames = []
    duplicates = {}
    for code, league in CODES.items():
        raw = pd.read_csv(cache / f"{code}_M_1st_summary_player_advanced_match_stats.csv")
        key = ["Game_URL", "Player_Href"]
        duplicated = raw.loc[raw.duplicated(key, keep=False)]
        if any(len(group.drop_duplicates()) > 1 for _, group in duplicated.groupby(key)):
            raise InputError("Apparitions contradictoires dans le snapshot historique.")
        duplicates[league] = int(raw.duplicated(key).sum())
        raw = raw.drop_duplicates(key)
        raw = raw.loc[raw.Match_Date.between("2024-08-01", "2025-01-31") & raw.Min.gt(0)].copy()
        frame = raw.rename(columns={"Player": "player", "Match_Date": "match_date", "Gls": "goals", "Ast": "assists", "SoT": "shots_on_goal", "CrdY": "yellow_cards", "CrdR": "red_cards"})
        frame["competition"] = league
        frame["player_id"] = "fbref:" + raw.Player_Href.str.extract(r"/players/([^/]+)")[0]
        frame["position"] = raw.Pos.map(role)
        frame["matches"] = 1
        home = raw.Home_Away.eq("Home")
        frame["goals_conceded"] = np.where(home, raw.Away_Score, raw.Home_Score)
        frame["team_wins"] = np.where(home, raw.Home_Score.gt(raw.Away_Score), raw.Away_Score.gt(raw.Home_Score)).astype(int)
        frame["clean_sheets"] = frame.goals_conceded.eq(0).astype(int)
        frames.append(frame[["match_date", "competition", "player_id", "player", "position"] + MATCH_FEATURES])
    return pd.concat(frames, ignore_index=True), duplicates


def espn_matches(cache, events):
    rows = []
    for lg, eid, event_date, _ in events:
        obj = json.loads((cache / "espn" / f"{lg}_summary_{eid}.json").read_bytes())
        if obj["header"]["competitions"][0]["status"]["type"]["completed"] is not True or len(obj.get("rosters", [])) != 2:
            raise InputError(f"Match incomplet : {eid}.")
        competitors = obj["header"]["competitions"][0]["competitors"]
        score = {str(c["id"]): int(c["score"]) for c in competitors}
        for squad in obj["rosters"]:
            club = str(squad["team"]["id"])
            conceded = next(v for k, v in score.items() if k != club)
            for entry in squad["roster"]:
                stats = {s["name"]: s.get("value") for s in entry.get("stats", [])}
                if not stats.get("appearances", 0):
                    continue
                source_position = entry.get("position", {}).get("abbreviation")
                row = {"match_date": event_date[:10], "competition": ESPN[lg], "player_id": "espn:" + str(entry["athlete"]["id"]),
                       "player": entry["athlete"]["displayName"], "position": role(source_position) if source_position and source_position != "SUB" else np.nan, "matches": 1,
                       "team_wins": int(score[club] > conceded), "clean_sheets": int(conceded == 0), "goals_conceded": conceded}
                for target, name in {"goals": "totalGoals", "assists": "goalAssists", "shots_on_goal": "shotsOnTarget", "yellow_cards": "yellowCards", "red_cards": "redCards"}.items():
                    # Valeur absente conservée vide, jamais remplacée par une statistique inventée.
                    row[target] = stats.get(name, np.nan)
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.duplicated(["match_date", "competition", "player_id"]).any():
        raise InputError("Apparitions ESPN dupliquées le même jour.")
    return frame


def periods_from_matches(frame, *, monthly):
    frame = frame.copy()
    frame = frame.sort_values("match_date", kind="stable")
    # Conserver un poste antérieur documenté pour les remplaçants, sans lire un match futur.
    frame["position"] = frame.groupby(["competition", "player_id"]).position.ffill()
    dates = pd.to_datetime(frame.match_date)
    if monthly:
        frame["period_end"] = dates.dt.to_period("M").dt.end_time.dt.strftime("%Y-%m-%d")
        keys = ["period_end", "competition", "player_id"]
        # Le poste est celui de la dernière apparition, les performances sont additionnées.
        ordered = frame.sort_values("match_date", kind="stable")
        return ordered.groupby(keys, as_index=False).agg({"player": "last", "position": "last", **{n: lambda s: s.sum(min_count=1) for n in MATCH_FEATURES}})
    frame["period_end"] = (dates + pd.to_timedelta(6 - dates.dt.dayofweek, unit="D")).dt.strftime("%Y-%m-%d")
    # Dernier match du joueur dans la semaine, pas le cumul de plusieurs rencontres.
    return frame.sort_values("match_date", kind="stable").drop_duplicates(["period_end", "competition", "player_id"], keep="last").drop(columns="match_date").reset_index(drop=True)


def prepare(cache, output, config_dir):
    seasons = historical_seasons(cache)
    season_candidates = current_season(cache)
    matches, duplicates = historical_matches(cache)
    events = json.loads((cache / "espn" / "events.json").read_text(encoding="utf-8"))
    recent = espn_matches(cache, events)
    weekly = periods_from_matches(matches, monthly=False)
    weekly = weekly.loc[weekly.period_end.le("2025-01-31")]
    monthly = periods_from_matches(matches, monthly=True)
    recent_week = periods_from_matches(recent, monthly=False)
    recent_week = recent_week.loc[recent_week.period_end.eq(recent_week.period_end.max())]
    recent_month = periods_from_matches(recent, monthly=True)
    unknown_week = recent_week.loc[recent_week.position.isna(), IDENTIFIERS].to_dict("records")
    unknown_month = recent_month.loc[recent_month.position.isna(), IDENTIFIERS].to_dict("records")
    recent_week = recent_week.loc[recent_week.position.notna()]
    recent_month = recent_month.loc[recent_month.position.notna()]
    prepared = {"TOTS": (seasons, season_candidates, True), "TOTY": (seasons, season_candidates, True), "TOTW": (weekly, recent_week, False), "POTM": (monthly, recent_month, False)}
    report = {"as_of": "2026-10-07", "label_kind": "derived_statistical", "duplicate_appearances_removed": duplicates, "excluded_unknown_positions": {"TOTW": unknown_week, "POTM": unknown_month}, "awards": {}}
    output.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    for award, (history, candidates, season) in prepared.items():
        features = SEASON_FEATURES if season else MATCH_FEATURES
        cfg = SelectionConfig(award=award, authority="M259 : règle statistique expérimentale v1, labels reconstruits ; aucun vote officiel", numeric_features=features, categorical_features=["position"], baseline_feature="goals",
                              feature_notes={n: "Statistiques réelles agrégées ; dictionnaire et fenêtres : data/selections/README.md" for n in features + ["position"]}, top_k=1 if award == "POTM" else 11,
                              squad_positions={} if award == "POTM" else QUOTAS, min_train_periods=2 if award == "POTM" else 3, validation_periods=2 if award == "POTM" else 3, test_periods=2,
                              data_available_before_selection=True, labels_and_candidate_pool_documented=True, label_kind="derived_statistical", availability_kind="retrospective_reconstruction")
        labeled, audit, rejected = label_frame(history, award=award, season=season)
        labeled = validate_selection_frame(labeled, cfg, training=True)
        candidates = validate_selection_frame(candidates[IDENTIFIERS + features + ["position"]], cfg, training=False)
        filename = "season_history.csv" if season else award.lower() + "_history.csv"
        labeled.to_csv(output / filename, index=False, encoding="utf-8")
        candidates.to_csv(output / ("season_candidates.csv" if season else award.lower() + "_candidates.csv"), index=False, encoding="utf-8")
        audit.to_csv(output / ("season_rule_audit.csv" if season else award.lower() + "_rule_audit.csv"), index=False, encoding="utf-8")
        from dataclasses import asdict
        (config_dir / f"{award.lower()}.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
        report["awards"][award] = {"history_rows": len(labeled), "history_periods": sorted(labeled.period_end.unique()), "candidates_rows": len(candidates), "candidate_periods": sorted(candidates.period_end.unique()), "candidates_by_league": candidates.groupby("competition").size().to_dict(), "rejected_groups": rejected, "missing_history": labeled[features].isna().sum().to_dict(), "missing_candidates": candidates[features].isna().sum().to_dict()}
    report["current_matches"] = {"count": len(events), "first_date": recent.match_date.min(), "last_date": recent.match_date.max(), "by_league": recent.groupby("competition").match_date.agg(["min", "max"]).to_dict("index")}
    (output / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def acquire(cache, *, download):
    release = "https://github.com/JaseZiv/worldfootballR_data/releases/download/"
    sources = {f"season_{part}.rds": release + f"fb_big5_advanced_season_stats/big5_player_{name}.rds" for part, name in [("standard", "standard"), ("defense", "defense"), ("keepers", "keepers")]}
    sources["master.csv"] = f"https://raw.githubusercontent.com/m-mahadi/top5-football-dataset/{SNAPSHOT}/data/master/player_seasons.csv"
    for code in CODES:
        name = f"{code}_M_1st_summary_player_advanced_match_stats.csv"
        sources[name] = release + "fb_advanced_match_stats/" + name
    for lg in ESPN:
        for offset in range(37):
            d = date(2026, 9, 1) + timedelta(days=offset)
            sources[f"espn/{lg}_{d:%Y%m%d}.json"] = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={d:%Y%m%d}"
    manifest_path = ROOT / "data/selections/sources_manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))["files"] if manifest_path.exists() else {}

    def fetch(item):
        name, url = item
        path = cache / name
        if not path.exists():
            if not download:
                raise InputError(f"Snapshot manquant : {path} ; relancer avec --download.")
            data = urllib.request.urlopen(url, timeout=40).read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if name in previous and previous[name]["sha256"] != digest:
            raise InputError(f"Le snapshot a changé : {name}. Audit nécessaire avant de remplacer la source.")
        return name, {"url": url, "sha256": digest, "bytes": len(data)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = dict(pool.map(fetch, sources.items()))
    events = []
    for name in sources:
        if not name.startswith("espn/"):
            continue
        lg = name.split("/")[1].split("_")[0]
        for event in json.loads((cache / name).read_bytes()).get("events", []):
            if event["status"]["type"]["completed"]:
                events.append([lg, event["id"], event["date"], event["name"]])
    summary_sources = {f"espn/{lg}_summary_{eid}.json": f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/summary?event={eid}" for lg, eid, _, _ in events}
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest.update(dict(pool.map(fetch, summary_sources.items())))
    (cache / "espn/events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps({"collected_on": "2026-10-07", "files": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Télécharger les snapshots manquants ; les empreintes existantes restent obligatoires.")
    args = parser.parse_args()
    try:
        cache = ROOT / "artifacts/source_cache"
        acquire(cache, download=args.download)
        report = prepare(cache, ROOT / "data/selections/processed", ROOT / "config/selections")
    except (InputError, OSError, ValueError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    print(json.dumps({"as_of": report["as_of"], "current_matches": report["current_matches"],
                      "awards": {a: {n: r[n] for n in ("history_rows", "history_periods", "candidates_rows", "candidate_periods")} for a, r in report["awards"].items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
