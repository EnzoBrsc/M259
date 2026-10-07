"""Classer des candidats avec la pipeline sauvegardée, sans la réentraîner."""

import argparse
import hashlib
import platform
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import sklearn
from sklearn.pipeline import Pipeline

from src.schema import MAX_CSV_BYTES, InputError, ModelConfig, read_csv, validate_frame
from src.train import aggregate, evaluate_editions, model_scores, ranking

SCORE_NOTICE = (
    "Les scores servent à classer les candidats d'une même édition. "
    "Ils ne sont pas des probabilités fiables de gagner : ils ne sont ni "
    "calibrés ni normalisés entre candidats. Les égalités sont départagées "
    "par identifiant déclaré (sinon par nom), sans preuve de supériorité sportive."
)


def load_model(path):
    """Charger seulement un modèle local entraîné par ce projet et de confiance."""
    path = Path(path)
    if not path.is_file():
        raise InputError(f"Modèle absent : {path}. Entraîner d'abord avec les données documentées de Luca.")
    try:
        bundle = joblib.load(path)
    except Exception as exc:
        raise InputError(f"Modèle illisible : {type(exc).__name__}. Réentraîner avec cet environnement.") from exc
    if not isinstance(bundle, dict) or bundle.get("format_version") != 1:
        raise InputError("Format de modèle non reconnu.")
    try:
        config = ModelConfig(**bundle["config"]).validate()
        versions = bundle["versions"]
        if versions["sklearn"] != sklearn.__version__ or versions["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
            raise InputError("Versions Python/scikit-learn incompatibles avec le modèle. Installer requirements.txt ou réentraîner.")
        if not isinstance(bundle["pipeline"], Pipeline):
            raise InputError("Le modèle ne contient pas de pipeline scikit-learn.")
        years = bundle["trained_editions"]
        if not isinstance(years, list) or not years or any(type(y) is not int for y in years):
            raise InputError("Historique d'entraînement absent ou invalide.")
    except (KeyError, TypeError, AttributeError) as exc:
        raise InputError("Métadonnées du modèle incomplètes.") from exc
    return bundle, config


def predict_candidates(frame, bundle, config):
    validated = validate_frame(frame, config, training=False)
    if validated[config.edition_column].min() <= max(bundle["trained_editions"]):
        raise InputError("Les candidats doivent appartenir à des éditions postérieures à l'entraînement ; ne pas présenter une prédiction sur les données apprises comme un test.")
    scores = model_scores(bundle["pipeline"], validated[config.features])
    return ranking(validated, scores, config)


def predict_csv(source, bundle, config):
    return predict_candidates(read_csv(source), bundle, config)


def predict_historical_csv(source, bundle, config):
    """Rejouer exclusivement le test réservé du snapshot qui a servi à l'étude."""
    if not isinstance(source, bytes) and Path(source).stat().st_size > MAX_CSV_BYTES:
        raise InputError("CSV trop volumineux : maximum 10 Mio.")
    payload = source if isinstance(source, bytes) else Path(source).read_bytes()
    if len(payload) > MAX_CSV_BYTES:
        raise InputError("CSV trop volumineux : maximum 10 Mio.")
    if hashlib.sha256(payload).hexdigest() != bundle.get("training_data_sha256"):
        raise InputError("Le CSV historique doit être le snapshot exact utilisé pour entraîner ce modèle. Pour de nouveaux candidats, choisissez le mode candidats et retirez la cible/métadonnées.")
    frame = validate_frame(read_csv(payload), config, training=True)
    years = bundle.get("final_test_editions", [])
    if not years or min(years) <= max(bundle["trained_editions"]):
        raise InputError("Le modèle ne déclare pas de test historique indépendant.")
    test = frame.loc[frame[config.edition_column].isin(years)].copy()
    if sorted(test[config.edition_column].unique().tolist()) != sorted(years):
        raise InputError("Des éditions du test final sont absentes du CSV.")
    scores = model_scores(bundle["pipeline"], test[config.features])
    details = evaluate_editions(test, scores, config)
    return ranking(test, scores, config), {"metrics": aggregate(details), "by_edition": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="artifacts/ballon_or/model.joblib")
    parser.add_argument("--input", required=True, help="CSV UTF-8 conforme au contrat du modèle")
    parser.add_argument("--output", default="outputs/classement.csv")
    parser.add_argument("--historical-test", action="store_true", help="Rejouer le test réservé du snapshot historique, sans prédiction sur les éditions apprises")
    args = parser.parse_args()
    try:
        destination = Path(args.output)
        if destination.resolve() in {Path(args.input).resolve(), Path(args.model).resolve()}:
            raise InputError("L'export ne doit pas écraser le CSV d'entrée ou le modèle.")
        if destination.exists():
            raise InputError("Le fichier d'export existe déjà. Choisir un autre chemin.")
        bundle, config = load_model(args.model)
        if args.historical_test:
            result, evaluation = predict_historical_csv(args.input, bundle, config)
        else:
            result = predict_csv(args.input, bundle, config)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(destination, index=False, encoding="utf-8-sig")
    except (InputError, OSError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    print(f"Classement exporté : {destination}\n{SCORE_NOTICE}")
    if args.historical_test:
        print(f"Évaluation rétrospective du test réservé uniquement : {evaluation['metrics']}")


if __name__ == "__main__":
    main()
