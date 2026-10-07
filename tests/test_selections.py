"""Données FICTIVES : vérification logicielle, aucun résultat de football réel."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.football_selections import (AWARDS, SelectionConfig, evaluate_selection, load_selection_model,
                                     predict_selection_csv, select_squad, selection_plan, selection_ranking,
                                     train_selection, validate_selection_frame)
from src.schema import InputError

ROOT = Path(__file__).resolve().parents[1]


def config(award="TOTW"):
    return SelectionConfig(award=award, authority="FICTIF : labels de test uniquement",
                           numeric_features=["goals", "minutes"], categorical_features=["position"],
                           baseline_feature="goals", feature_notes={n: "FICTIF : fixture" for n in ["goals", "minutes", "position"]},
                           top_k=1 if award == "POTM" else 2, min_train_periods=3, validation_periods=2, test_periods=2,
                           data_available_before_selection=True, labels_and_candidate_pool_documented=True)


def history(award="TOTW"):
    return pd.DataFrame([
        {"period_end": f"2000-{month:02d}-01", "competition": league,
         "player_id": f"fictif-{i}", "player": f"Joueur FICTIF {i}",
         "goals": (i + month) % 5, "minutes": 10 + 100 * i, "position": ["GK", "DEF", "MID", "FWD"][i % 4],
         "selected": int(i == month % 8 or (award != "POTM" and i == (month + 1) % 8)),
         "label_available_on": f"2000-{month:02d}-02"}
        for month in range(1, 9) for league in ["Ligue 1", "Premier League"] for i in range(8)
    ])


def run_fixture(root, cfg, frame, output):
    frame.to_csv(root / "fixture.csv", index=False)
    (root / "config.json").write_text(json.dumps(asdict(cfg)), encoding="utf-8")
    (root / "sources.md").write_text("FICTIF : aucune source ni résultat sportif réel.", encoding="utf-8")
    return train_selection(root / "fixture.csv", root / "config.json", output, root / "sources.md")


class SelectionTests(unittest.TestCase):
    def test_multi_selected_and_potm_winner_per_league(self):
        validate_selection_frame(history(), config(), training=True)
        with self.assertRaisesRegex(InputError, "exactement un"):
            validate_selection_frame(history(), config("POTM"), training=True)
        validate_selection_frame(history("POTM"), config("POTM"), training=True)
        with self.assertRaisesRegex(InputError, "Championnats"):
            validate_selection_frame(history().assign(competition="Autre"), config(), training=True)
        with self.assertRaises(InputError):
            validate_selection_frame(pd.concat([history(), history().iloc[[0]]]), config(), training=True)

    def test_chronology_and_label_publication(self):
        cfg = config()
        plan = selection_plan(history().period_end, cfg)
        self.assertEqual(plan["test"], ["2000-07-01", "2000-08-01"])
        for fold in plan["folds"]:
            self.assertLess(max(fold["train"]), min(fold["validation"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = history().assign(label_available_on="2001-01-01")
            with self.assertRaisesRegex(InputError, "publiés"):
                run_fixture(root, cfg, frame, root / "out")
            self.assertFalse((root / "out").exists())

    def test_position_quotas_and_selection_metrics(self):
        cfg = config()
        cfg.top_k = 4
        cfg.squad_positions = {"GK": 1, "DEF": 1, "MID": 1, "FWD": 1}
        frame = history().query("period_end == '2000-01-01' and competition == 'Ligue 1'").copy()
        validated = validate_selection_frame(frame, cfg, training=True)
        ordered = selection_ranking(validated, np.ones(8))
        selected = select_squad(ordered, cfg)
        self.assertEqual(selected.position.value_counts().to_dict(), {"GK": 1, "DEF": 1, "MID": 1, "FWD": 1})
        self.assertEqual(evaluate_selection(validated, np.ones(8), cfg)["metrics"]["precision_at_k"], 0.5)
        with self.assertRaisesRegex(InputError, "Postes"):
            validate_selection_frame(frame.assign(position="inconnu"), cfg, training=True)

    def test_config_requires_documented_source_and_no_final_selection_feature(self):
        cfg = config()
        cfg.data_available_before_selection = False
        with self.assertRaisesRegex(InputError, "non validées"):
            cfg.validate()
        cfg = config()
        cfg.numeric_features.append("current_selection")
        cfg.feature_notes["current_selection"] = "FICTIF"
        with self.assertRaisesRegex(InputError, "interdites"):
            cfg.validate()

    def test_pipeline_round_trip_and_test_does_not_change_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg, frame = config(), history()
            first = run_fixture(root, cfg, frame, root / "first")
            changed = frame.copy()
            changed.loc[changed.period_end.ge("2000-07-01"), "selected"] = 1 - changed.loc[changed.period_end.ge("2000-07-01"), "selected"]
            changed.loc[changed.period_end.ge("2000-07-01"), "goals"] = 99999
            second = run_fixture(root, cfg, changed, root / "second")
            self.assertEqual(first["selected"], second["selected"])
            bundle, restored = load_selection_model(root / "first/model.joblib", "TOTW")
            payload = frame.query("period_end == '2000-08-01'").drop(columns=["selected", "label_available_on"]).assign(period_end="2099-01-01").to_csv(index=False).encode()
            result = predict_selection_csv(payload, bundle, restored)
            self.assertEqual(result.groupby("competition")["rank"].min().tolist(), [1, 1])
            (root / "candidates.csv").write_bytes(payload)
            cli = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src/predict_selection.py"),
                                  "--award", "TOTW", "--model", str(root / "first/model.joblib"),
                                  "--input", str(root / "candidates.csv"), "--output", str(root / "export.csv")],
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            exported = pd.read_csv(root / "export.csv")
            self.assertEqual(exported.groupby("competition").predicted_selection.sum().tolist(), [2, 2])
            # Le CSV ne conserve pas la variante de StringDtype de pandas.
            pd.testing.assert_frame_equal(exported.drop(columns="predicted_selection"), result, check_dtype=False)
            with self.assertRaisesRegex(InputError, "récompense"):
                load_selection_model(root / "first/model.joblib", "TOTY")
            with self.assertRaisesRegex(InputError, "supplémentaires"):
                predict_selection_csv(frame.to_csv(index=False).encode(), bundle, restored)
            with patch.dict(os.environ, {"M259_SELECTION_MODELS_DIR": str(root)}):
                (root / "totw").mkdir()
                (root / "totw/model.joblib").write_bytes((root / "first/model.joblib").read_bytes())
                app = AppTest.from_file(ROOT / "app.py", default_timeout=60).run()
                app.selectbox(key="award_choice").set_value("TOTW").run()
                app.file_uploader[0].set_value(("FICTIF.csv", payload, "text/csv")).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.dataframe), 2)
                self.assertEqual(len(app.dataframe[0].value), 2)
                self.assertEqual(len(app.get("vega_lite_chart")), 1)
                self.assertEqual(len(app.download_button), 1)

    def test_four_modes_with_no_model_never_show_replacement_predictions(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"M259_SELECTION_MODELS_DIR": directory}):
            app = AppTest.from_file(ROOT / "app.py", default_timeout=60).run()
            for award in AWARDS:
                app.selectbox(key="award_choice").set_value(award).run()
                self.assertFalse(app.exception)
                self.assertTrue(app.file_uploader[0].disabled)
                self.assertIn(f"Modèle {award} absent", app.warning[0].value)
                self.assertEqual(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
