"""Parcours complet sur fixture FICTIVE et fichiers temporaires uniquement."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from tests.fixtures import config, dataset
from tests.test_predict import candidates

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_cli_training_prediction_and_interface_agree(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "docs").mkdir()
            (root / "data").mkdir()
            (root / "docs" / "cadrage.md").write_text("FICTIF : exercice technique sans résultat réel.", encoding="utf-8")
            (root / "data" / "README.md").write_text("FICTIF : schéma des fixtures tests.fixtures.", encoding="utf-8")
            dataset().to_csv(root / "fixture.csv", index=False)
            (root / "config.json").write_text(json.dumps(config().to_dict()), encoding="utf-8")
            train = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src" / "train.py"),
                                    "--data", "fixture.csv", "--config", "config.json", "--output", "artifacts"],
                                   cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=120)
            self.assertEqual(train.returncode, 0, train.stderr)
            payload = candidates().to_csv(index=False).encode("utf-8")
            (root / "candidates.csv").write_bytes(payload)
            predict = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src" / "predict_candidates.py"),
                                      "--model", "artifacts/model.joblib", "--input", "candidates.csv", "--output", "ranking.csv"],
                                     cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(predict.returncode, 0, predict.stderr)
            self.assertIn("pas des probabilités", predict.stdout)
            expected = pd.read_csv(root / "ranking.csv")[["rang", "joueur", "score"]]
            with patch.dict(os.environ, {"M259_MODEL_DIR": str(root / "artifacts")}):
                app = AppTest.from_file(ROOT / "app.py", default_timeout=60).run()
                app.file_uploader[0].set_value(("FICTIF.csv", payload, "text/csv")).run()
                self.assertEqual(len(app.exception), 0)
                pd.testing.assert_frame_equal(app.dataframe[0].value.reset_index(drop=True), expected.reset_index(drop=True))
                self.assertEqual(len(app.get("vega_lite_chart")), 1)

    def test_cli_missing_luca_files_is_an_error_not_a_result(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "src" / "train.py")], cwd=folder,
                                    capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(result.returncode, 2)
            for name in ["docs/cadrage.md", "data/README.md", "data/processed/ballon_or.csv"]:
                self.assertIn(str(Path(name)), result.stderr)
            self.assertFalse((Path(folder) / "artifacts").exists())


if __name__ == "__main__":
    unittest.main()
