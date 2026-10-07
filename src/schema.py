"""Contrat explicite à adapter au schéma documenté par Luca."""

import csv
import io
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

MAX_CSV_BYTES = 10 * 1024 * 1024


class InputError(ValueError):
    """Entrée absente, incohérente ou non conforme au contrat."""


def normalized_name(name):
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def is_leaking_feature(name):
    name = normalized_name(name)
    tokens = set(name.split("_"))
    return bool(tokens & {"vote", "votes", "voting", "voted", "rank", "ranking",
                          "classement", "rang", "gagnant", "winner", "winning",
                          "target", "cible"}) or (
        bool(tokens & {"final", "finale", "ballon", "dor", "award"})
        and bool(tokens & {"points", "score", "position", "place"})
    )


@dataclass
class ModelConfig:
    edition_column: str
    player_column: str
    target_column: str
    numeric_features: list[str]
    categorical_features: list[str]
    baseline_feature: str
    feature_notes: dict[str, str] = field(default_factory=dict)
    test_editions: int = 2
    min_train_editions: int = 3
    validation_editions: int = 3
    random_seed: int = 42
    data_available_before_vote: bool = False
    history_uses_previous_editions_only: bool = False

    @property
    def features(self):
        return self.numeric_features + self.categorical_features

    def validate(self):
        for attr in ("edition_column", "player_column", "target_column", "baseline_feature"):
            if not isinstance(getattr(self, attr), str) or not getattr(self, attr).strip():
                raise InputError(f"Configuration : {attr} doit être un nom de colonne.")
        for attr in ("numeric_features", "categorical_features"):
            values = getattr(self, attr)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise InputError(f"Configuration : {attr} doit être une liste de noms.")
        names = [self.edition_column, self.player_column, self.target_column] + self.features
        if len(names) != len(set(names)) or len(names) != len({normalized_name(n) for n in names}):
            raise InputError("Les rôles et variables doivent avoir des noms distincts.")
        if not self.numeric_features or self.baseline_feature not in self.numeric_features:
            raise InputError("La référence simple nécessite une variable numérique déclarée.")
        forbidden = [f for f in self.features if is_leaking_feature(f)]
        if forbidden:
            raise InputError(f"Variables pouvant révéler le résultat du vote interdites : {forbidden}")
        if not isinstance(self.feature_notes, dict) or any(
            not isinstance(self.feature_notes.get(f), str) or not self.feature_notes[f].strip()
            for f in self.features
        ):
            raise InputError("Documenter la source et la date de disponibilité de chaque variable dans feature_notes.")
        for attr in ("test_editions", "min_train_editions", "validation_editions"):
            if type(getattr(self, attr)) is not int or getattr(self, attr) < 1:
                raise InputError(f"{attr} doit être un entier strictement positif.")
        if type(self.random_seed) is not int or self.random_seed < 0:
            raise InputError("random_seed doit être un entier positif ou nul.")
        if self.data_available_before_vote is not True or self.history_uses_previous_editions_only is not True:
            raise InputError("Confirmer avec Luca les données avant vote et les historiques strictement antérieurs dans la configuration.")
        return self

    def to_dict(self):
        return asdict(self)


def load_config(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return ModelConfig(**payload).validate()
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise InputError(f"Configuration illisible ou invalide ({path}) : {exc}") from exc


def read_csv(source):
    """CSV UTF-8, virgule ou point-virgule ; pas de conversion silencieuse."""
    try:
        payload = source if isinstance(source, bytes) else Path(source).read_bytes()
        if len(payload) > MAX_CSV_BYTES:
            raise InputError("CSV trop volumineux : maximum 10 Mio.")
        text = payload.decode("utf-8-sig")
        first = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if first.count(";") > first.count(",") else ","
        header = next(csv.reader(io.StringIO(text), delimiter=delimiter), [])
        if not header or any(not c.strip() for c in header) or len(header) != len(set(header)):
            raise InputError("En-tête CSV absent, vide ou contenant des colonnes en double.")
        return pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError(f"Impossible de lire le CSV UTF-8 : {exc}") from exc


def validate_frame(frame, config, *, training):
    config.validate()
    if frame.empty:
        raise InputError("Le CSV ne contient aucun candidat.")
    if frame.columns.duplicated().any():
        raise InputError("Colonnes en double.")
    required = [config.edition_column, config.player_column] + config.features
    if training:
        required += [config.target_column]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise InputError(f"Colonnes manquantes : {', '.join(missing)}")
    if not training:
        extra = sorted(set(frame.columns) - set(required))
        if extra:
            raise InputError(f"Colonnes non prévues pour la prédiction : {', '.join(extra)}. Retirer notamment les résultats du vote.")
    result = frame.copy()
    players = result[config.player_column].astype("string").str.strip()
    if players.isna().any() or players.eq("").any():
        raise InputError("Chaque candidat doit avoir un nom non vide.")
    result[config.player_column] = players.astype(str)
    editions = pd.to_numeric(result[config.edition_column], errors="coerce")
    if editions.isna().any() or not np.isfinite(editions).all() or (editions % 1 != 0).any() or (editions <= 0).any():
        raise InputError("L'édition doit être un entier positif, ordonnable chronologiquement.")
    result[config.edition_column] = editions.astype(int)
    duplicate_keys = pd.DataFrame({"edition": editions, "joueur": players.str.casefold()})
    if duplicate_keys.duplicated().any():
        raise InputError("Un joueur apparaît plusieurs fois dans une même édition.")
    for name in config.numeric_features:
        raw = result[name].replace(r"^\s*$", np.nan, regex=True)
        numeric = pd.to_numeric(raw, errors="coerce")
        if (raw.notna() & numeric.isna()).any() or np.isinf(numeric.to_numpy(dtype=float)).any():
            raise InputError(f"La variable {name} contient une valeur non numérique ou infinie.")
        result[name] = numeric.astype(float)
    for name in config.categorical_features:
        result[name] = result[name].map(lambda x: np.nan if pd.isna(x) or not str(x).strip() else str(x).strip())
    if training:
        target = pd.to_numeric(result[config.target_column], errors="coerce")
        if target.isna().any() or not target.isin([0, 1]).all():
            raise InputError("La cible doit être binaire : 0 = non-gagnant, 1 = gagnant.")
        result[config.target_column] = target.astype(int)
        groups = result.groupby(config.edition_column)[config.target_column].agg(["sum", "count"])
        if (groups["sum"] != 1).any() or (groups["count"] < 2).any():
            raise InputError("Chaque édition doit contenir exactement un gagnant et au moins un non-gagnant. Exclure les éditions sans prix.")
    return result.reset_index(drop=True)
