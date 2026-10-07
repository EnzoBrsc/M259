"""Pipelines distinctes pour les sélections du football réel ; aucune donnée de remplacement."""

import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.schema import InputError, is_leaking_feature, read_csv
from src.train import candidate_models, model_scores

AWARDS = {
    "TOTW": "Team of the Week · performances de la semaine",
    "TOTY": "Team of the Year · performances de l'année et récompenses annuelles",
    "TOTS": "Team of the Season · performances de la saison, par compétition",
    "POTM": "Player of the Month · performances du mois, par compétition",
}
IDENTIFIERS = ["period_end", "competition", "player_id", "player"]
LEAGUES = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]


@dataclass
class SelectionConfig:
    award: str
    authority: str
    numeric_features: list[str]
    categorical_features: list[str]
    baseline_feature: str
    feature_notes: dict[str, str]
    top_k: int
    min_train_periods: int = 3
    validation_periods: int = 3
    test_periods: int = 2
    random_seed: int = 42
    data_available_before_selection: bool = False
    labels_and_candidate_pool_documented: bool = False
    competitions: list[str] = field(default_factory=lambda: LEAGUES.copy())
    squad_positions: dict[str, int] = field(default_factory=dict)

    @property
    def features(self):
        return self.numeric_features + self.categorical_features

    def validate(self):
        if self.award not in AWARDS:
            raise InputError("Sélection inconnue : TOTW, TOTY, TOTS ou POTM attendue.")
        if not isinstance(self.authority, str) or not self.authority.strip():
            raise InputError("Préciser l'organisme ou le média qui définit la récompense dans authority.")
        if not isinstance(self.competitions, list) or not self.competitions or len(set(self.competitions)) != len(self.competitions) or any(c not in LEAGUES for c in self.competitions):
            raise InputError("Choisir des compétitions distinctes parmi les cinq championnats déclarés.")
        for names in (self.numeric_features, self.categorical_features):
            if not isinstance(names, list) or any(not isinstance(n, str) or not n.strip() for n in names):
                raise InputError("Les variables doivent être des listes de noms de colonnes.")
        if not self.numeric_features or self.baseline_feature not in self.numeric_features:
            raise InputError("Une référence numérique déclarée est nécessaire.")
        names = IDENTIFIERS + ["selected"] + self.features
        if len(names) != len(set(names)) or any(is_leaking_feature(n) or {"selected", "selection"} & set(n.lower().split("_")) for n in self.features):
            raise InputError("Variables dupliquées ou révélant la sélection finale interdites.")
        if not isinstance(self.feature_notes, dict) or any(not isinstance(self.feature_notes.get(n), str) or not self.feature_notes[n].strip() for n in self.features):
            raise InputError("Documenter la source, l'unité et la disponibilité de chaque variable.")
        for name in ("top_k", "min_train_periods", "validation_periods", "test_periods"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise InputError(f"{name} doit être un entier strictement positif.")
        if self.award == "POTM" and self.top_k != 1:
            raise InputError("POTM : top_k doit valoir 1, un gagnant par compétition/mois.")
        if not isinstance(self.squad_positions, dict) or any(k not in {"GK", "DEF", "MID", "FWD"} or type(v) is not int or v < 1 for k, v in self.squad_positions.items()):
            raise InputError("squad_positions : quotas positifs pour GK, DEF, MID et FWD.")
        if self.squad_positions and (self.award == "POTM" or "position" not in self.categorical_features or sum(self.squad_positions.values()) != self.top_k):
            raise InputError("Les quotas nécessitent position dans les catégories, un effectif égal à top_k et une récompense d'équipe.")
        if type(self.random_seed) is not int or self.random_seed < 0:
            raise InputError("random_seed doit être un entier positif ou nul.")
        if self.data_available_before_selection is not True or self.labels_and_candidate_pool_documented is not True:
            raise InputError("Données football non validées : documenter les périodes, sources, candidats et labels avant de confirmer la configuration.")
        return self


def load_selection_config(path):
    try:
        return SelectionConfig(**json.loads(Path(path).read_text(encoding="utf-8-sig"))).validate()
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise InputError(f"Configuration football illisible : {exc}") from exc


def validate_selection_frame(frame, config, *, training):
    config.validate()
    required = IDENTIFIERS + config.features + (["selected", "label_available_on"] if training else [])
    if frame.empty or frame.columns.duplicated().any():
        raise InputError("CSV vide ou colonnes dupliquées.")
    missing = sorted(set(required) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(required))
    if missing or extra:
        raise InputError(f"Schéma {config.award} invalide. Colonnes manquantes : {missing} ; supplémentaires : {extra}.")
    result = frame.copy().reset_index(drop=True)
    for name in IDENTIFIERS:
        result[name] = result[name].astype("string").str.strip()
        if result[name].isna().any() or result[name].eq("").any():
            raise InputError(f"Identifiant vide : {name}.")
    dates = pd.to_datetime(result.period_end, format="%Y-%m-%d", errors="coerce")
    if dates.isna().any() or not dates.dt.strftime("%Y-%m-%d").eq(result.period_end).all():
        raise InputError("period_end doit être une date ISO exacte YYYY-MM-DD, fin de la fenêtre de statistiques avant la sélection.")
    if not result.competition.isin(config.competitions).all():
        raise InputError(f"Championnats autorisés : {', '.join(config.competitions)}.")
    keys = result[["period_end", "competition", "player_id"]].apply(lambda c: c.str.casefold())
    if keys.duplicated().any():
        raise InputError("Joueur en double dans une même période/compétition.")
    for name in config.numeric_features:
        raw = result[name].replace(r"^\s*$", np.nan, regex=True)
        numeric = pd.to_numeric(raw, errors="coerce")
        if (raw.notna() & numeric.isna()).any() or np.isinf(numeric).any():
            raise InputError(f"Valeur numérique invalide : {name}.")
        result[name] = numeric.astype(float)
    for name in config.categorical_features:
        result[name] = result[name].map(lambda v: np.nan if pd.isna(v) or not str(v).strip() else str(v).strip())
    if config.squad_positions:
        if not result.position.isin(config.squad_positions).all():
            raise InputError("Postes attendus selon les quotas : GK, DEF, MID, FWD ; ne pas inventer un poste absent.")
        for _, group in result.groupby(["period_end", "competition"]):
            if any(group.position.eq(position).sum() < count for position, count in config.squad_positions.items()):
                raise InputError("Pas assez de candidats à chaque poste pour composer l'équipe prévue.")
    if training:
        available = pd.to_datetime(result.label_available_on, format="%Y-%m-%d", errors="coerce")
        if available.isna().any() or not available.dt.strftime("%Y-%m-%d").eq(result.label_available_on).all() or (available < dates).any():
            raise InputError("label_available_on doit être une date ISO de publication au moins égale à la fin des statistiques ; aucun résultat futur dans les entrées.")
        if (result.groupby(["period_end", "competition"]).label_available_on.nunique() != 1).any():
            raise InputError("Une date de publication des labels par période et compétition est nécessaire.")
        target = pd.to_numeric(result.selected, errors="coerce")
        if target.isna().any() or not target.isin([0, 1]).all():
            raise InputError("selected doit valoir 0 ou 1 : sélection officielle observée.")
        result["selected"] = target.astype(int)
        counts = result.groupby(["period_end", "competition"]).selected.agg(["sum", "count"])
        if (counts["sum"] < 1).any() or (counts["sum"] >= counts["count"]).any():
            raise InputError("Chaque période/compétition doit contenir des sélectionnés et des non-sélectionnés documentés.")
        if config.award == "POTM" and (counts["sum"] != 1).any():
            raise InputError("POTM : exactement un gagnant par période/compétition.")
    return result


def selection_ranking(frame, scores):
    result = frame[IDENTIFIERS + (["position"] if "position" in frame else [])].copy()
    result["score"] = scores
    result["_tie"] = result.player_id.str.casefold()
    result = result.sort_values(["period_end", "competition", "score", "_tie"], ascending=[True, True, False, True], kind="stable")
    result["rank"] = result.groupby(["period_end", "competition"]).cumcount() + 1
    return result.drop(columns="_tie").reset_index(drop=True)


def select_squad(ordered, config):
    """Effectif fixé avant évaluation ; aucune sélection selon les vrais labels."""
    if not config.squad_positions:
        return ordered.head(config.top_k)
    return pd.concat([ordered.loc[ordered.position.eq(position)].head(count)
                      for position, count in config.squad_positions.items()]).sort_values("rank")


def evaluate_selection(frame, scores, config):
    ordered = selection_ranking(frame, scores)
    details = []
    for (period, competition), group in ordered.groupby(["period_end", "competition"], sort=True):
        source = frame.loc[frame.period_end.eq(period) & frame.competition.eq(competition)]
        actual = set(source.loc[source.selected.eq(1), "player_id"])
        first = select_squad(group, config)
        hits = len(set(first.player_id) & actual)
        details.append({"period_end": period, "competition": competition, "candidates": len(group),
                        "selected_count": len(actual), "reviewed_count": len(first), "hits": hits,
                        "precision_at_k": hits / len(first), "recall_at_k": hits / len(actual),
                        "tie_at_cutoff": bool(group.score.eq(first.iloc[-1].score).sum() > 1)})
    metrics = {"groups": len(details), **{k: float(np.mean([d[k] for d in details])) for k in ("precision_at_k", "recall_at_k")}}
    return {"metrics": metrics, "by_group": details}


def selection_plan(periods, config):
    periods = sorted(set(periods))
    required = config.min_train_periods + config.validation_periods + config.test_periods
    if len(periods) < required:
        raise InputError(f"{required} périodes chronologiques complètes nécessaires, reçues : {len(periods)}.")
    development, test = periods[:-config.test_periods], periods[-config.test_periods:]
    folds = [{"train": development[:i], "validation": [development[i]]}
             for i in range(len(development) - config.validation_periods, len(development))]
    return {"development": development, "test": test, "folds": folds}


def train_selection(data_path, config_path, output_dir, data_readme_path):
    for path in (data_path, config_path, data_readme_path):
        if not Path(path).is_file() or not Path(path).stat().st_size:
            raise InputError(f"Données, configuration ou documentation manquante : {path}.")
    cfg = load_selection_config(config_path)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise InputError("Dossier de résultats non vide : choisir un nouveau dossier.")
    frame = validate_selection_frame(read_csv(data_path), cfg, training=True)
    plan = selection_plan(frame.period_end, cfg)
    development = frame.loc[frame.period_end.isin(plan["development"])]
    validation = []
    for name, parameters, _ in candidate_models(cfg):
        details = []
        for fold in plan["folds"]:
            model = next(m for n, p, m in candidate_models(cfg) if n == name and p == parameters)
            train = development.loc[development.period_end.isin(fold["train"])]
            valid = development.loc[development.period_end.isin(fold["validation"])]
            if train.label_available_on.max() >= valid.period_end.min():
                raise InputError("Des labels d'entraînement n'étaient pas publiés avant la validation. Revoir les fenêtres et le protocole.")
            model.fit(train[cfg.features], train.selected)
            details.extend(evaluate_selection(valid, model_scores(model, valid[cfg.features]), cfg)["by_group"])
        metrics = {k: float(np.mean([d[k] for d in details])) for k in ("precision_at_k", "recall_at_k")}
        validation.append({"model": name, "parameters": parameters, "metrics": metrics, "by_group": details})
    chosen = max(validation, key=lambda r: (r["metrics"]["precision_at_k"], r["metrics"]["recall_at_k"]))
    if development.label_available_on.max() >= min(plan["test"]):
        raise InputError("Les labels de développement doivent être publiés avant le premier test.")
    model = next(m for n, p, m in candidate_models(cfg) if n == chosen["model"] and p == chosen["parameters"])
    model.fit(development[cfg.features], development.selected)
    test = frame.loc[frame.period_end.isin(plan["test"])]
    test_evaluation = evaluate_selection(test, model_scores(model, test[cfg.features]), cfg)
    versions = {"python": platform.python_version(), "sklearn": sklearn.__version__}
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "config": asdict(cfg),
              "chronology": plan, "selected": chosen, "validation": validation, "final_test": test_evaluation,
              "versions": versions, "selection_rule": "validation precision@k, puis recall@k ; ordre fixe en cas d'égalité ; aucun choix sur le test",
              "inputs_sha256": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (data_path, config_path, data_readme_path)}}
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump({"format": "m259-football-selections-v1", "award": cfg.award, "pipeline": model, "config": asdict(cfg),
                 "model_name": chosen["model"], "trained_periods": plan["development"],
                 "trained_labels_available_on": development.label_available_on.max(), "versions": versions}, output / "model.joblib")
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_selection_model(path, award):
    if not Path(path).is_file():
        raise InputError(f"Modèle {award} absent. Les données et sélections historiques {award} doivent être documentées puis entraînées séparément.")
    try:
        bundle = joblib.load(path)
        if bundle.get("format") != "m259-football-selections-v1" or bundle.get("award") != award:
            raise InputError("Ce modèle n'appartient pas à la récompense sélectionnée.")
        cfg = SelectionConfig(**bundle["config"]).validate()
        if cfg.award != award or bundle["versions"]["sklearn"] != sklearn.__version__ or bundle["versions"]["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
            raise InputError("Récompense ou versions incompatibles : réentraîner dans cet environnement.")
        from sklearn.pipeline import Pipeline
        years = bundle["trained_periods"]
        if not isinstance(bundle["pipeline"], Pipeline) or not isinstance(years, list) or not years:
            raise InputError("Pipeline ou historique de périodes invalide.")
        dates = pd.to_datetime(pd.Series(years + [bundle["trained_labels_available_on"]]), format="%Y-%m-%d", errors="coerce")
        if dates.isna().any():
            raise InputError("Historique de périodes invalide.")
        return bundle, cfg
    except InputError:
        raise
    except Exception as exc:
        raise InputError("Modèle football local illisible ; utiliser uniquement vos artefacts de confiance.") from exc


def predict_selection_csv(source, bundle, config):
    frame = validate_selection_frame(read_csv(source), config, training=False)
    if frame.period_end.min() <= max(max(bundle["trained_periods"]), bundle["trained_labels_available_on"]):
        raise InputError("Les périodes à prédire doivent être postérieures aux périodes apprises.")
    return selection_ranking(frame, model_scores(bundle["pipeline"], frame[config.features]))
