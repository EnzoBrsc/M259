"""Entraîner un modèle TOTW/TOTY/TOTS/POTM avec des données documentées."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.football_selections import train_selection
from src.schema import InputError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--data-readme", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        report = train_selection(args.data, args.config, args.output, args.data_readme)
    except (InputError, OSError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    print(json.dumps({"selected": report["selected"]["model"], "validation": report["selected"]["metrics"],
                      "test": report["final_test"]["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
