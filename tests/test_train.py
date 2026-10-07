import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.schema import InputError, read_csv, validate_frame
from src.train import candidate_models, chronological_plan, evaluate_editions, run_training, select_model
from tests.fixtures import config, dataset


class TrainingTests(unittest.TestCase):
    def test_whole_editions_and_chronology(self):
        cfg = config()
        plan = chronological_plan(dataset().edition, cfg)
        self.assertEqual(plan["test"], [2006, 2007])
        for fold in plan["folds"]:
            self.assertLess(max(fold["train"]), min(fold["validation"]))
            self.assertTrue(set(fold["train"]).isdisjoint(plan["test"]))
            self.assertTrue(set(fold["validation"]).isdisjoint(plan["test"]))
        with self.assertRaises(InputError):
            chronological_plan([2000, 2001], cfg)

    def test_preprocessing_fitted_only_on_train(self):
        cfg = config()
        train = dataset().query("edition < 2003").copy()
        valid = dataset().query("edition == 2003").copy()
        train.loc[0, "buts"] = np.nan
        valid["buts"] = 999999
        valid["poste"] = "categorie_inconnue"
        model = next(m for n, _, m in candidate_models(cfg) if n == "regression_logistique")
        model.fit(train[cfg.features], train.gagnant)
        numeric = model.named_steps["preprocess"].named_transformers_["numeric"]
        self.assertEqual(numeric.named_steps["imputer"].statistics_[0], train.buts.median())
        before = numeric.named_steps["scaler"].mean_.copy()
        model.predict_proba(valid[cfg.features])
        np.testing.assert_array_equal(before, numeric.named_steps["scaler"].mean_)

    def test_bad_targets_duplicates_and_leakage(self):
        cfg = config()
        frame = dataset()
        with self.assertRaises(InputError):
            validate_frame(pd.concat([frame, frame.iloc[[0]]]), cfg, training=True)
        frame.loc[0, "gagnant"] = 0
        with self.assertRaises(InputError):
            validate_frame(frame, cfg, training=True)
        for forbidden in ["points_vote", "classement_final", "winner", "vote_points", "rang_final"]:
            bad = config()
            bad.numeric_features.append(forbidden)
            bad.feature_notes[forbidden] = "Fictif"
            with self.assertRaises(InputError):
                bad.validate()

    def test_top_one_top_three_and_ties(self):
        cfg = config()
        frame = dataset().query("edition == 2000").reset_index(drop=True)
        details = evaluate_editions(frame, np.array([2, 3, 4, 1]), cfg)[0]
        self.assertEqual(details["top_1"], 0)
        self.assertEqual(details["top_3"], 1)
        self.assertEqual(details["rang_gagnant"], 3)
        tied = evaluate_editions(frame, np.ones(4), cfg)[0]
        self.assertTrue(tied["egalite_score_gagnant"])
        self.assertTrue(tied["egalite_premiere_place"])

    def test_final_test_cannot_change_selection(self):
        cfg = config()
        frame = dataset()
        plan = chronological_plan(frame.edition, cfg)
        development = frame[frame.edition.isin(plan["development"])]
        _, chosen, _ = select_model(development, cfg, plan)
        changed = frame.copy()
        changed.loc[changed.edition.isin(plan["test"]), "buts"] = 1e9
        changed.loc[changed.edition.isin(plan["test"]), "gagnant"] = 0
        _, chosen_again, _ = select_model(changed[changed.edition.isin(plan["development"])], cfg, plan)
        self.assertEqual(chosen, chosen_again)

    def test_missing_inputs_do_not_create_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(InputError, "manquants"):
                run_training(root / "absent.csv", root / "absent.json", root / "output",
                             framing_path=root / "absent.md", data_readme_path=root / "data.md")
            self.assertFalse((root / "output").exists())

    def test_full_training_on_fictional_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dataset().to_csv(root / "data.csv", index=False)
            (root / "config.json").write_text(json.dumps(config().to_dict()), encoding="utf-8")
            for filename in ["cadrage.md", "data.md"]:
                (root / filename).write_text("FICTIF : test technique, aucune source réelle.", encoding="utf-8")
            report = run_training(root / "data.csv", root / "config.json", root / "output",
                                  framing_path=root / "cadrage.md", data_readme_path=root / "data.md")
            self.assertEqual(len(report["validation"]), 9)
            self.assertEqual(report["final_test"]["metrics"]["editions"], 2)
            self.assertEqual(report["trained_editions"], list(range(2000, 2006)))
            for file in ["model.joblib", "results.json", "validation.csv", "final_test.csv"]:
                self.assertTrue((root / "output" / file).is_file())
            with self.assertRaisesRegex(InputError, "pas vide"):
                run_training(root / "data.csv", root / "config.json", root / "output",
                             framing_path=root / "cadrage.md", data_readme_path=root / "data.md")

    def test_csv_headers_and_semicolon(self):
        with self.assertRaises(InputError):
            read_csv(b"edition,edition\n2000,2000\n")
        self.assertEqual(read_csv(b"edition;joueur\n2000;Fictif\n").iloc[0].joueur, "Fictif")


if __name__ == "__main__":
    unittest.main()
