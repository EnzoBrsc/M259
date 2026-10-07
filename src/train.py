"""Entraînement reproductible par éditions entières, sans sélection sur le test."""

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src.schema import InputError, load_config, read_csv, validate_frame
from src.baseline import FeatureReference


def make_preprocessor(config):
    transformers = [("numeric", Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ]), config.numeric_features)]
    if config.categorical_features:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__", keep_empty_features=True)),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), config.categorical_features))
    return ColumnTransformer(transformers, remainder="drop")


def candidate_models(config):
    """Petite grille fixée avant toute lecture des résultats du test final."""
    baseline = Pipeline([
        ("preprocess", ColumnTransformer([
            ("numeric", SimpleImputer(strategy="median", keep_empty_features=True), [config.baseline_feature])
        ], remainder="drop")),
        ("model", FeatureReference()),
    ])
    yield "reference", {}, baseline
    for c in (0.1, 1.0, 10.0):
        params = {"C": c}
        yield "regression_logistique", params, Pipeline([
            ("preprocess", make_preprocessor(config)),
            ("model", LogisticRegression(C=c, max_iter=2000, class_weight="balanced", random_state=config.random_seed)),
        ])
    for depth in (2, 4, None):
        params = {"max_depth": depth, "min_samples_leaf": 2}
        yield "arbre_decision", params, Pipeline([
            ("preprocess", make_preprocessor(config)),
            ("model", DecisionTreeClassifier(**params, class_weight="balanced", random_state=config.random_seed)),
        ])
    for depth in (4, None):
        params = {"n_estimators": 100, "max_depth": depth, "min_samples_leaf": 2}
        yield "foret_aleatoire", params, Pipeline([
            ("preprocess", make_preprocessor(config)),
            ("model", RandomForestClassifier(**params, class_weight="balanced", random_state=config.random_seed, n_jobs=1)),
        ])


def model_scores(model, X):
    if hasattr(model, "predict_proba"):
        positive = list(model.classes_).index(1)
        scores = model.predict_proba(X)[:, positive]
    else:
        scores = model.decision_function(X)
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or len(scores) != len(X) or not np.isfinite(scores).all():
        raise InputError("Le modèle a produit des scores invalides.")
    return scores


def ranking(frame, scores, config):
    result = pd.DataFrame({
        "edition": frame[config.edition_column].to_numpy(),
        "joueur": frame[config.player_column].to_numpy(),
        "score": scores,
    })
    if config.player_id_column:
        result["player_id"] = frame[config.player_id_column].to_numpy()
    result["_tie"] = result["player_id" if config.player_id_column else "joueur"].str.casefold()
    result = result.sort_values(["edition", "score", "_tie"], ascending=[True, False, True], kind="stable")
    result["rang"] = result.groupby("edition").cumcount() + 1
    return result.drop(columns="_tie").reset_index(drop=True)


def evaluate_editions(frame, scores, config):
    ordered = ranking(frame, scores, config)
    details = []
    for edition, candidates in ordered.groupby("edition", sort=True):
        source = frame.loc[frame[config.edition_column].eq(edition)]
        winner_source = source.loc[source[config.target_column].eq(1)].iloc[0]
        winner = winner_source[config.player_column]
        identity_column = "player_id" if config.player_id_column else "joueur"
        identity = winner_source[config.player_id_column or config.player_column]
        winner_row = candidates.loc[candidates[identity_column].eq(identity)].iloc[0]
        counts = candidates.groupby("score").size()
        details.append({
            "edition": int(edition), "gagnant_reel": winner,
            "gagnant_predit": candidates.iloc[0].joueur,
            "top_3_predit": candidates.head(3).joueur.tolist(),
            "rang_gagnant": int(winner_row["rang"]),
            "top_1": int(winner_row["rang"] == 1),
            "top_3": int(winner_row["rang"] <= 3),
            "rang_reciproque": float(1 / winner_row["rang"]),
            "top_1_aleatoire": float(1 / len(candidates)),
            "top_3_aleatoire": float(min(3, len(candidates)) / len(candidates)),
            "nombre_candidats": len(candidates),
            "egalite_score_gagnant": bool(counts.loc[winner_row.score] > 1),
            "egalite_premiere_place": bool(counts.loc[candidates.iloc[0].score] > 1),
        })
    return details


def aggregate(details):
    return {"editions": len(details),
            "top_1": float(np.mean([d["top_1"] for d in details])),
            "top_3": float(np.mean([d["top_3"] for d in details])),
            **{key: float(np.mean([d[key] for d in details])) for key in
               ("rang_reciproque", "top_1_aleatoire", "top_3_aleatoire")}}


def chronological_plan(editions, config):
    editions = sorted(set(int(e) for e in editions))
    required = config.test_editions + config.min_train_editions + config.validation_editions
    if len(editions) < required:
        raise InputError(f"Il faut au moins {required} éditions complètes pour ce protocole (reçues : {len(editions)}).")
    development = editions[:-config.test_editions]
    test = editions[-config.test_editions:]
    folds = []
    for position in range(len(development) - config.validation_editions, len(development)):
        folds.append({"train": development[:position], "validation": [development[position]]})
    return {"development": development, "test": test, "folds": folds}


def validate_split(frame, config, plan):
    """Contrôler le découpage livré plutôt que le remplacer silencieusement."""
    if not config.split_column:
        return
    validation = {year for fold in plan["folds"] for year in fold["validation"]}
    expected = frame[config.edition_column].map(
        lambda year: "test" if year in plan["test"] else "validation" if year in validation else "train")
    if not frame[config.split_column].eq(expected).all():
        raise InputError("Le découpage train/validation/test du CSV ne correspond pas au protocole configuré.")


def select_model(development, config, plan):
    results = []
    for name, params, _ in candidate_models(config):
        details, folds = [], []
        # Réinstancier une pipeline par pli : aucune statistique partagée.
        for fold in plan["folds"]:
            model = next(m for n, p, m in candidate_models(config) if n == name and p == params)
            train = development.loc[development[config.edition_column].isin(fold["train"])]
            valid = development.loc[development[config.edition_column].isin(fold["validation"])]
            model.fit(train[config.features], train[config.target_column])
            evaluated = evaluate_editions(valid, model_scores(model, valid[config.features]), config)
            details.extend(evaluated)
            folds.append({**fold, "metrics": aggregate(evaluated)})
        results.append({"model": name, "parameters": params, "metrics": aggregate(details), "folds": folds, "by_edition": details})
    # Ordre déclaré et grille la plus simple en cas d'égalité exacte.
    chosen = max(results, key=lambda r: (r["metrics"]["top_1"], r["metrics"]["top_3"]))
    model = next(m for n, p, m in candidate_models(config) if n == chosen["model"] and p == chosen["parameters"])
    model.fit(development[config.features], development[config.target_column])
    return model, chosen, results


def run_training(data_path, config_path, output_dir, *, framing_path="docs/cadrage.md", data_readme_path="data/README.md"):
    required = [Path(framing_path), Path(data_readme_path), Path(data_path), Path(config_path)]
    missing = [str(p) for p in required if not p.is_file() or p.stat().st_size == 0]
    if missing:
        raise InputError("Entraînement impossible. Fichiers nécessaires manquants ou vides : " + ", ".join(missing))
    config = load_config(config_path)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise InputError("Le dossier de résultats n'est pas vide. Utiliser un nouveau dossier pour conserver les anciens essais.")
    frame = validate_frame(read_csv(data_path), config, training=True)
    plan = chronological_plan(frame[config.edition_column], config)
    validate_split(frame, config, plan)
    development = frame.loc[frame[config.edition_column].isin(plan["development"])].copy()
    model, chosen, validation = select_model(development, config, plan)
    # Le choix est figé avant de calculer la moindre performance sur le test.
    test = frame.loc[frame[config.edition_column].isin(plan["test"])].copy()
    test_details = evaluate_editions(test, model_scores(model, test[config.features]), config)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config.to_dict(), "chronology": plan,
        "selection_rule": "validation top_1, puis top_3, puis ordre fixe de la grille ; jamais le test final",
        "tie_rule": f"score décroissant puis {config.player_id_column or config.player_column} sans distinction de casse ; égalités signalées",
        "selected": chosen, "validation": validation,
        "final_test": {"metrics": aggregate(test_details), "by_edition": test_details},
        "score_warning": "Scores de classement non calibrés ; pas des probabilités fiables de victoire par édition.",
        "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__, "joblib": joblib.__version__},
        "inputs_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in required},
        "trained_editions": plan["development"],
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump({"format_version": 1, "pipeline": model, "config": config.to_dict(),
                 "model_name": chosen["model"], "parameters": chosen["parameters"],
                 "final_test_editions": plan["test"],
                 "training_data_sha256": hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),
                 "trained_editions": plan["development"], "versions": report["versions"]}, output / "model.joblib")
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"model": r["model"], "parameters": json.dumps(r["parameters"], sort_keys=True), **r["metrics"]} for r in validation]
    pd.DataFrame(rows).to_csv(output / "validation.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(test_details).to_csv(output / "final_test.csv", index=False, encoding="utf-8-sig")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/processed/ballon_or.csv")
    parser.add_argument("--config", default="config/model_config.json")
    parser.add_argument("--output", default="artifacts/ballon_or")
    args = parser.parse_args()
    try:
        report = run_training(args.data, args.config, args.output)
    except (InputError, OSError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    print(json.dumps({"selected_model": report["selected"]["model"], "validation": report["selected"]["metrics"], "final_test": report["final_test"]["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
