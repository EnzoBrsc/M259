"""Audit des transformations et CSV réels ; fixtures techniques explicitement fictives."""

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.collect_selection_data import (MATCH_FEATURES, SEASON_FEATURES, aggregate_stints,
                                        label_frame, periods_from_matches, role, rule_scores)
from src.football_selections import (load_selection_config, validate_selection_frame,
                                     train_selection, load_selection_model)
from src.schema import InputError, read_csv
from tests.test_selections import config, history

ROOT = Path(__file__).resolve().parents[1]


class SelectionDataTests(unittest.TestCase):
    def test_club_stints_do_not_duplicate_season_totals(self):
        # FICTIF : deux passages par club, même total SofaScore répété.
        frame = pd.DataFrame([{"period_end": "2000-06-30", "competition": "Ligue 1", "player_id": "fictif", "player": "FICTIF", "position": "FWD", "minutes": n, "goals": g, "tackles": 15} for n, g in [(900, 3), (450, 2)]])
        result = aggregate_stints(frame, totals=["tackles"]).iloc[0]
        self.assertEqual((result.minutes, result.goals, result.tackles), (1350, 5, 15))

    def test_last_match_and_calendar_month_are_distinct(self):
        frame = pd.DataFrame([{"match_date": d, "competition": "Ligue 1", "player_id": "fictif", "player": "FICTIF", "position": p, **{n: (g if n == "goals" else 1) for n in MATCH_FEATURES}} for d, g, p in [("2000-01-29", 2, "MID"), ("2000-01-30", 1, np.nan), ("2000-02-01", 3, "FWD")]])
        weekly = periods_from_matches(frame, monthly=False)
        self.assertEqual(weekly.period_end.tolist(), ["2000-01-30", "2000-02-06"])
        self.assertEqual(weekly.goals.tolist(), [1, 3])
        self.assertEqual(weekly.position.tolist(), ["MID", "FWD"])
        monthly = periods_from_matches(frame, monthly=True)
        self.assertEqual(monthly.goals.tolist(), [3, 3])
        self.assertEqual(monthly.period_end.tolist(), ["2000-01-31", "2000-02-29"])
        # Un poste futur ne complète pas une semaine antérieure.
        frame.loc[:1, "position"] = np.nan
        self.assertTrue(pd.isna(periods_from_matches(frame, monthly=False).iloc[0].position))

    def test_roles_and_rule_targets_are_explicit(self):
        self.assertEqual(role("MF,FW"), "MID")
        self.assertEqual(role("CD-L"), "DEF")
        self.assertEqual(role("CF-R"), "FWD")
        with self.assertRaises(InputError):
            role("SUB")
        frame = pd.DataFrame([{"period_end": "2000-01-31", "competition": "Ligue 1", "player_id": f"fictif-{i}", "player": "FICTIF", "position": "FWD", **{n: (i if n == "goals" else 0) for n in MATCH_FEATURES}} for i in range(3)])
        labeled, audit, _ = label_frame(frame, award="POTM", season=False)
        self.assertEqual(labeled.selected.tolist(), [0, 0, 1])
        self.assertNotIn("rule_score", labeled)
        self.assertEqual(audit.rule_score.tolist(), [0, 4, 8])
        missing = frame.copy()
        missing.loc[0, "goals"] = np.nan
        rule_scores(missing, season=False)
        self.assertTrue(pd.isna(missing.iloc[0].goals))

    def test_production_refit_preserves_test_evaluation_boundary(self):
        cfg = config()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history().to_csv(root / "data.csv", index=False)
            (root / "config.json").write_text(json.dumps(asdict(cfg)), encoding="utf-8")
            (root / "sources.md").write_text("FICTIF : données de test.", encoding="utf-8")
            report = train_selection(root / "data.csv", root / "config.json", root / "model", root / "sources.md", refit_all=True)
            bundle, _ = load_selection_model(root / "model/model.joblib", "TOTW")
            self.assertEqual(report["production_refit"]["evaluation_trained_through"], "2000-06-01")
            self.assertEqual(report["production_refit"]["saved_model_trained_through"], "2000-08-01")
            self.assertEqual(max(bundle["trained_periods"]), "2000-08-01")
            self.assertEqual(report["chronology"]["test"], ["2000-07-01", "2000-08-01"])

    def test_real_csv_contract_and_label_provenance(self):
        for award in ("TOTW", "TOTY", "TOTS", "POTM"):
            cfg = load_selection_config(ROOT / "config/selections" / f"{award.lower()}.json")
            prefix = "season" if award in {"TOTY", "TOTS"} else award.lower()
            data = ROOT / "data/selections/processed"
            frame = validate_selection_frame(read_csv(data / f"{prefix}_history.csv"), cfg, training=True)
            future = validate_selection_frame(read_csv(data / f"{prefix}_candidates.csv"), cfg, training=False)
            self.assertEqual(cfg.label_kind, "derived_statistical")
            self.assertEqual(cfg.availability_kind, "retrospective_reconstruction")
            self.assertLess(frame.period_end.max(), future.period_end.min())
            self.assertEqual(set(future.competition), set(cfg.competitions))
            self.assertTrue(frame.groupby(["period_end", "competition"]).selected.sum().eq(cfg.top_k).all())
            self.assertNotIn("rule_score", cfg.features)
            if prefix == "season":
                self.assertTrue(frame.minutes.ge(900).all())
                self.assertTrue(future.player.str.contains("Haaland").any())
                self.assertTrue(future.player.str.contains("Kylian Mbappé").any())
                self.assertTrue(future.loc[future.position.ne("GK"), ["saves", "goals_conceded", "clean_sheets"]].eq(0).all().all())


if __name__ == "__main__":
    unittest.main()
