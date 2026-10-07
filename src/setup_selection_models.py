"""Comparer, évaluer puis entraîner les quatre modèles expérimentaux locaux."""

import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.football_selections import train_selection, load_selection_model, predict_selection_csv, select_squad

ROOT = Path(__file__).resolve().parents[1]


def main():
    for award in ("TOTS", "TOTY", "TOTW", "POTM"):
        name = award.lower()
        print(f"Comparaison chronologique {award}…", flush=True)
        history = "season_history.csv" if award in {"TOTS", "TOTY"} else f"{name}_history.csv"
        candidates = "season_candidates.csv" if award in {"TOTS", "TOTY"} else f"{name}_candidates.csv"
        report = train_selection(ROOT / "data/selections/processed" / history, ROOT / "config/selections" / f"{name}.json",
                                 ROOT / "artifacts/selections" / name, ROOT / "data/selections/README.md", refit_all=True)
        # Les rapports légers sont versionnés ; les binaires du modèle restent locaux.
        summary = ROOT / "docs/resultats_selections"
        summary.mkdir(exist_ok=True)
        (summary / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        bundle, cfg = load_selection_model(ROOT / "artifacts/selections" / name / "model.joblib", award)
        result = predict_selection_csv(ROOT / "data/selections/processed" / candidates, bundle, cfg)
        ids = {(r.period_end, r.competition, r.player_id) for _, group in result.groupby(["period_end", "competition"]) for r in select_squad(group, cfg).itertuples()}
        result["predicted_selection"] = [(r.period_end, r.competition, r.player_id) in ids for r in result.itertuples()]
        outputs = ROOT / "outputs"
        outputs.mkdir(exist_ok=True)
        result.to_csv(outputs / f"classement_{name}.csv", index=False, encoding="utf-8-sig")
        print(json.dumps({"award": award, "model": report["selected"]["model"], "validation": report["selected"]["metrics"], "test": report["final_test"]["metrics"], "candidates": len(result)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
