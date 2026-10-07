"""Les vues doivent respecter les classements et les identités, même sur CSV importé."""

import json
import unittest
from collections import Counter
from html.parser import HTMLParser
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.football_visuals import ASSETS, pitch_html, podium_html, portrait_for


class Markup(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.cards, self.positions, self.images = [], [], []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self.cards.append(attrs["aria-label"])
        if "data-position" in attrs:
            self.positions.append(attrs["data-position"])
        if tag == "img":
            self.images.append(attrs)


class FootballVisualTests(unittest.TestCase):
    def test_pitch_preserves_quota_and_every_selected_player(self):
        frame = pd.DataFrame([{"player": f"FICTIF {i}", "position": position, "score": i / 11, "rank": i + 1}
                              for i, position in enumerate(["GK"] + ["DEF"] * 4 + ["MID"] * 3 + ["FWD"] * 3)])
        markup = pitch_html(frame, "TOTS", "Ligue 1", "2099-01-01")
        parsed = Markup(markup)
        self.assertEqual(len(parsed.cards), 11)
        self.assertEqual(parsed.positions, ["FWD", "MID", "DEF", "GK"])
        self.assertEqual(Counter(c.split(", ")[1] for c in parsed.cards), {"GAR": 1, "DÉF": 4, "MIL": 3, "ATT": 3})
        self.assertIn("4–3–3", markup)
        self.assertEqual(parsed.images, [])
        self.assertEqual(pitch_html(frame.assign(position="inconnu"), "TOTS", "", ""), "")

    def test_podium_uses_rank_not_dataframe_order_and_handles_small_pool(self):
        frame = pd.DataFrame([{"player": f"FICTIF {i}", "score": 1 / i, "rank": i} for i in (4, 3, 1, 2)])
        labels = Markup(podium_html(frame, "POTM", "Ligue 1")).cards
        self.assertEqual([c.split(", ")[0] for c in labels], ["FICTIF 2", "FICTIF 1", "FICTIF 3"])
        self.assertEqual(len(Markup(podium_html(frame.query("rank == 1"), "POTM", "")).cards), 1)
        self.assertEqual(podium_html(frame.iloc[:0], "POTM", ""), "")

    def test_csv_names_and_context_are_escaped(self):
        frame = pd.DataFrame([{"player": '<img src=x onerror="alert(1)">', "score": 0.5, "rank": 1}])
        markup = podium_html(frame, "Ballon d'Or", "<script>alert(1)</script>")
        self.assertEqual(Markup(markup).images, [])
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;img", markup)

    def test_portrait_identity_and_source_allowlist(self):
        entry = {"name": "Harry Kane", "provider": "FOX Sports", "image_url": "https://b.fssta.com/uploads/application/soccer/headshots/453.png", "source_url": "https://www.foxsports.com/soccer/harry-kane-player"}
        with patch("src.football_visuals.portrait_catalog", return_value={"harry-kane": entry}):
            self.assertEqual(portrait_for("Harry Kane"), entry)
            entry["image_url"] = "javascript:alert(1)"
            self.assertIsNone(portrait_for("Harry Kane"))
            entry["image_url"] = "https://b.fssta.com/uploads/application/soccer/headshots/453.png"
            entry["name"] = "Autre joueur"
            self.assertIsNone(portrait_for("Harry Kane"))

    def test_catalog_has_traceable_real_portraits(self):
        catalog = json.loads((ASSETS / "player_portraits.json").read_text(encoding="utf-8"))
        self.assertGreater(len(catalog["portraits"]), 50)
        for entry in catalog["portraits"].values():
            self.assertIsNotNone(portrait_for(entry["name"]))
            self.assertTrue(entry["verified_on"])
            self.assertTrue(entry["provider"])

    def test_real_selection_views_for_each_available_model(self):
        root = ASSETS.parent
        if not all((root / "artifacts/selections" / award.lower() / "model.joblib").is_file() for award in ("TOTW", "TOTS", "TOTY", "POTM")):
            self.skipTest("Modèles locaux absents sur un nouveau clone")
        app = AppTest.from_file(root / "app.py", default_timeout=60).run()
        for award in ("TOTW", "TOTS", "TOTY", "POTM"):
            app.selectbox(key="award_choice").set_value(award).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.dataframe), 2)
            self.assertEqual(len(app.dataframe[0].value), 1 if award == "POTM" else 11)
        app.selectbox(key="award_choice").set_value("Ballon d'Or").run()
        if not (root / "artifacts/ballon_or/model.joblib").is_file():
            return
        app.radio[0].set_value("Dataset historique de Luca (test)").run()
        app.file_uploader[0].set_value(("ballon_or.csv", (root / "data/processed/ballon_or.csv").read_bytes(), "text/csv")).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.dataframe), 1)


if __name__ == "__main__":
    unittest.main()
