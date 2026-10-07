"""Données exclusivement synthétiques pour tester le logiciel."""

import pandas as pd
from src.schema import ModelConfig


def config():
    return ModelConfig(edition_column="edition", player_column="joueur", target_column="gagnant",
                       numeric_features=["buts", "minutes"], categorical_features=["poste"],
                       baseline_feature="buts", feature_notes={f: "FICTIF : fixture technique" for f in ["buts", "minutes", "poste"]},
                       test_editions=2, min_train_editions=2, validation_editions=2,
                       data_available_before_vote=True, history_uses_previous_editions_only=True)


def dataset():
    return pd.DataFrame([
        {"edition": year, "joueur": f"Fictif {i}", "gagnant": int(i == year % 4),
         "buts": 10 + i * 4 + year % 3, "minutes": 1000 + i * 100,
         "poste": "attaque" if i % 2 else "milieu"}
        for year in range(2000, 2008) for i in range(4)
    ])
