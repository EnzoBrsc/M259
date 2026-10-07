"""Classer des candidats de football réel avec leur modèle spécifique."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.football_selections import AWARDS, load_selection_model, predict_selection_csv, select_squad
from src.schema import InputError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--award", required=True, choices=AWARDS)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model_path = args.model or Path("artifacts/selections") / args.award.lower() / "model.joblib"
    try:
        if args.output.exists() or args.output.resolve() in {args.input.resolve(), model_path.resolve()}:
            raise InputError("Choisir un export inexistant, distinct du CSV d'entrée et du modèle.")
        bundle, config = load_selection_model(model_path, args.award)
        result = predict_selection_csv(args.input, bundle, config)
        ids = {(r.period_end, r.competition, r.player_id) for _, group in result.groupby(["period_end", "competition"]) for r in select_squad(group, config).itertuples()}
        result["predicted_selection"] = [(r.period_end, r.competition, r.player_id) in ids for r in result.itertuples()]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.output, index=False, encoding="utf-8-sig")
    except (InputError, OSError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    print(f"Classement exporté : {args.output}. Scores non calibrés ; sélection expérimentale selon la source documentée.")


if __name__ == "__main__":
    main()
