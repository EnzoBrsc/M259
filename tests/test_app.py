import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd
from streamlit.testing.v1 import AppTest

from src.predict_candidates import predict_csv
from tests.test_predict import candidates, fitted_bundle

APP = Path(__file__).resolve().parents[1] / "app.py"


class InterfaceTests(unittest.TestCase):
    def test_missing_model_shows_message_without_ranking(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"M259_MODEL_DIR": directory}):
            app = AppTest.from_file(APP, default_timeout=60).run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Modèle absent", app.warning[0].value)
            self.assertEqual(len(app.dataframe), 0)
            self.assertTrue(app.file_uploader[0].disabled)

    def test_upload_ranking_chart_and_invalid_csv(self):
        bundle, cfg = fitted_bundle()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"M259_MODEL_DIR": directory}):
            joblib.dump(bundle, Path(directory) / "model.joblib")
            app = AppTest.from_file(APP, default_timeout=60).run()
            payload = candidates().to_csv(index=False).encode("utf-8")
            app.file_uploader[0].set_value(("FICTIF.csv", payload, "text/csv")).run()
            self.assertEqual(len(app.exception), 0)
            expected = predict_csv(payload, bundle, cfg)[["rang", "joueur", "score"]]
            pd.testing.assert_frame_equal(app.dataframe[0].value.reset_index(drop=True), expected.reset_index(drop=True))
            self.assertEqual(len(app.get("vega_lite_chart")), 1)
            self.assertEqual(len(app.download_button), 1)
            self.assertTrue(any("probabilités" in element.value for element in app.info))
            app.file_uploader[0].set_value(("invalide.csv", b"edition,joueur\n2099,Fictif\n", "text/csv")).run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Colonnes manquantes", app.error[0].value)
            self.assertEqual(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
