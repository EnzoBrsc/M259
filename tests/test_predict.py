import json
import platform
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.predict_candidates import load_model, predict_candidates, predict_csv
from src.schema import InputError
from src.train import candidate_models
from tests.fixtures import config, dataset


def fitted_bundle():
    cfg = config()
    frame = dataset()
    pipeline = next(m for n, _, m in candidate_models(cfg) if n == "reference")
    pipeline.fit(frame[cfg.features], frame.gagnant)
    return {"format_version": 1, "pipeline": pipeline, "config": cfg.to_dict(),
            "model_name": "reference", "trained_editions": list(range(2000, 2008)),
            "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__}}, cfg


def candidates():
    return dataset().query("edition == 2000").drop(columns="gagnant").assign(edition=2099)


class PredictionTests(unittest.TestCase):
    def test_future_ranking_and_independent_editions(self):
        bundle, cfg = fitted_bundle()
        frame = pd.concat([candidates(), candidates().assign(edition=2100)], ignore_index=True)
        result = predict_candidates(frame, bundle, cfg)
        self.assertEqual(result.columns.tolist(), ["edition", "joueur", "score", "rang"])
        self.assertEqual(result.groupby("edition")["rang"].min().tolist(), [1, 1])
        self.assertGreater(result.score.min(), 1)  # Une référence brute n'est pas une probabilité.
        self.assertEqual(result.iloc[0].joueur, "Fictif 3")

    def test_wrong_schema_target_and_in_sample_rejected(self):
        bundle, cfg = fitted_bundle()
        for frame in [candidates().drop(columns="minutes"), candidates().assign(gagnant=0),
                      candidates().assign(points_vote=1), candidates().assign(edition=2007),
                      candidates().assign(edition="2099.5"), candidates().assign(buts="texte"),
                      candidates().assign(buts=np.inf), candidates().assign(joueur=" ")]:
            with self.subTest(columns=frame.columns.tolist()), self.assertRaises(InputError):
                predict_candidates(frame, bundle, cfg)
        with self.assertRaises(InputError):
            predict_candidates(pd.concat([candidates(), candidates().iloc[[0]]]), bundle, cfg)

    def test_missing_values_reuse_training_imputation(self):
        bundle, cfg = fitted_bundle()
        original = bundle["pipeline"].named_steps["preprocess"].named_transformers_["numeric"].statistics_.copy()
        result = predict_candidates(candidates().assign(buts=np.nan, poste="nouveau"), bundle, cfg)
        self.assertTrue(np.isfinite(result.score).all())
        np.testing.assert_array_equal(bundle["pipeline"].named_steps["preprocess"].named_transformers_["numeric"].statistics_, original)

    def test_model_round_trip_and_version_check(self):
        bundle, cfg = fitted_bundle()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.joblib"
            joblib.dump(bundle, path)
            restored, restored_config = load_model(path)
            payload = candidates().to_csv(index=False).encode()
            result = predict_csv(payload, restored, restored_config)
            self.assertEqual(len(result), 4)
            bundle["versions"]["sklearn"] = "0.0.0"
            joblib.dump(bundle, path)
            with self.assertRaisesRegex(InputError, "incompatibles"):
                load_model(path)
            with self.assertRaisesRegex(InputError, "absent"):
                load_model(Path(folder) / "absent.joblib")


if __name__ == "__main__":
    unittest.main()
