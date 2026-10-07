"""Régressions du contrat réel de Luca, sans retoucher le test sportif."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.predict_candidates import predict_historical_csv
from src.schema import InputError, load_config, validate_frame
from src.train import chronological_plan, evaluate_editions, ranking, validate_split
from tests.fixtures import config, dataset
from tests.test_predict import fitted_bundle

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_real_contract_matches_manifest_and_fixed_split(self):
        import json
        cfg = load_config(ROOT / "config/model_config.json")
        manifest = json.loads((ROOT / "data/processed/features.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.features, manifest["numeric_features"])
        frame = validate_frame(pd.read_csv(ROOT / "data/processed/ballon_or.csv"), cfg, training=True)
        plan = chronological_plan(frame.edition, cfg)
        validate_split(frame, cfg, plan)
        self.assertEqual(plan["test"], [2022, 2023, 2024, 2025])
        self.assertEqual(plan["folds"][0]["train"], list(range(1995, 2016)))
        self.assertEqual([f["validation"][0] for f in plan["folds"]], [2016, 2017, 2018, 2019, 2021])
        frame.loc[frame.edition.eq(2022), "split"] = "validation"
        with self.assertRaisesRegex(InputError, "découpage"):
            validate_split(frame, cfg, plan)

    def test_historical_rank_exception_does_not_allow_current_rank(self):
        cfg = load_config(ROOT / "config/model_config.json")
        for name in ["rank", "current_rank", "previous_vote_points", "previous_winner"]:
            bad = type(cfg)(**cfg.to_dict())
            bad.numeric_features = cfg.numeric_features + [name]
            bad.feature_notes = {**cfg.feature_notes, name: "Pas de preuve d'antériorité"}
            with self.assertRaisesRegex(InputError, "interdites"):
                bad.validate()

    def test_identifiers_resolve_homonyms_and_ties(self):
        cfg = config()
        cfg.player_id_column = "id"
        frame = dataset().query("edition == 2000").assign(id=["z", "a", "b", "c"], joueur="Même nom")
        validated = validate_frame(frame, cfg, training=True)
        ordered = ranking(validated, np.ones(4), cfg)
        self.assertEqual(ordered.player_id.tolist(), ["a", "b", "c", "z"])
        self.assertEqual(evaluate_editions(validated, np.ones(4), cfg)[0]["rang_gagnant"], 4)
        with self.assertRaises(InputError):
            validate_frame(frame.assign(id="doublon"), cfg, training=True)

    def test_future_history_audit_rejected(self):
        cfg = config()
        cfg.history_edition_column = "history_year"
        frame = dataset().assign(history_year=lambda f: f.edition - 1)
        validate_frame(frame, cfg, training=True)
        with self.assertRaisesRegex(InputError, "antérieure"):
            validate_frame(frame.assign(history_year=lambda f: f.edition), cfg, training=True)

    def test_historical_mode_excludes_learned_editions_and_requires_snapshot(self):
        bundle, cfg = fitted_bundle()
        frame = dataset()
        payload = frame.to_csv(index=False).encode("utf-8")
        bundle["trained_editions"] = list(range(2000, 2006))
        bundle["final_test_editions"] = [2006, 2007]
        bundle["training_data_sha256"] = hashlib.sha256(payload).hexdigest()
        result, evaluation = predict_historical_csv(payload, bundle, cfg)
        self.assertEqual(result.edition.unique().tolist(), [2006, 2007])
        self.assertEqual(evaluation["metrics"]["editions"], 2)
        with self.assertRaisesRegex(InputError, "snapshot exact"):
            predict_historical_csv(payload + b"\n", bundle, cfg)
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"M259_MODEL_DIR": directory}):
            joblib.dump(bundle, Path(directory) / "model.joblib")
            app = AppTest.from_file(ROOT / "app.py", default_timeout=60).run()
            app.radio[0].set_value("Dataset historique de Luca (test)").run()
            app.file_uploader[0].set_value(("historique.csv", payload, "text/csv")).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.selectbox[0].options, ["2006", "2007"])
            self.assertEqual(len(app.dataframe[0].value), 4)
            self.assertEqual(len(app.get("vega_lite_chart")), 1)


if __name__ == "__main__":
    unittest.main()
