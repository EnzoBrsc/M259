"""Préparer les données sans dépendance externe ni information future.

Exécution depuis n'importe quel dossier : python chemin/vers/src/prepare_data.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_COLUMNS = ['year', 'rank', 'player', 'club', 'nationality', 'points', 'percent', 'position']
NUMERIC_FEATURES = [
    'previous_appearances', 'previous_top3', 'previous_wins',
    'previous_best_rank', 'previous_last_rank', 'years_since_previous',
    'appeared_previous_edition', 'has_history',
]
OUTPUT_COLUMNS = [
    'edition', 'player_id', 'player', 'club', 'nationality', 'position',
    *NUMERIC_FEATURES, 'history_last_edition', 'winner', 'split',
]
POSITIONS = {'Forward', 'Midfielder', 'Defender', 'Goalkeeper', 'Unknown'}
NAME_VARIANTS = {'vinicius-junior': {'Vinicius Junior', 'Vinícius Júnior'}}


def clean_text(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', value).split())


def positive_int(value: str, field: str) -> int:
    try:
        number = float(value)
        if not math.isfinite(number) or not number.is_integer() or number <= 0:
            raise ValueError
        return int(number)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{field}: entier positif attendu, reçu {value!r}') from exc


def player_id(name: str, year: int) -> str:
    # Do not merge the Spanish Ballon d'Or winner with the Uruguayan striker.
    if name == 'Luis Suárez':
        if 1958 <= year <= 1965:
            return 'luis-suarez-es'
        if 2011 <= year <= 2021:
            return 'luis-suarez-uy'
        raise ValueError(f'Luis Suárez: occurrence à désambiguïser en {year}')
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    identity = re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')
    if not identity:
        raise ValueError(f'Identifiant vide pour {name!r}')
    return identity


def validate_rows(raw: list[dict[str, str]]) -> list[dict]:
    if not raw:
        raise ValueError('Dataset vide')
    normalized = []
    seen = set()
    names_by_id = {}
    for line, record in enumerate(raw, start=2):
        if set(record) != set(RAW_COLUMNS) or any(v is None for v in record.values()):
            raise ValueError(f'Ligne {line}: colonnes invalides')
        year = positive_int(record['year'], 'year')
        rank = positive_int(record['rank'], 'rank')
        if not 1956 <= year <= 2025 or year == 2020:
            raise ValueError(f'Année non supportée : {year}')
        name = clean_text(record['player'])
        if not name:
            raise ValueError(f'Ligne {line}: joueur absent')
        identity = player_id(name, year)
        if (identity in names_by_id and names_by_id[identity] != name
                and not {name, names_by_id[identity]} <= NAME_VARIANTS.get(identity, set())):
            raise ValueError(f'Collision de noms : {names_by_id[identity]!r} et {name!r}')
        names_by_id[identity] = name
        key = (year, identity)
        if key in seen:
            raise ValueError(f'Doublon joueur/édition : {key}')
        seen.add(key)
        for field in ['points', 'percent']:
            if record[field].strip():
                try:
                    value = float(record[field])
                except ValueError as exc:
                    raise ValueError(f'{field}: valeur non numérique') from exc
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f'{field}: valeur négative ou non finie')
        position = clean_text(record['position']) or 'Unknown'
        if position not in POSITIONS:
            raise ValueError(f'Poste non supporté : {position}')
        normalized.append({
            'edition': year, 'rank': rank, 'player_id': identity, 'player': name,
            'club': clean_text(record['club'].replace('~~~', ' | ')) or 'Unknown',
            'nationality': clean_text(record['nationality']) or 'Unknown',
            'position': position,
        })
    by_year = defaultdict(list)
    for row in normalized:
        by_year[row['edition']].append(row)
    for year, group in by_year.items():
        if sum(row['rank'] == 1 for row in group) != 1:
            raise ValueError(f'{year}: exactement un gagnant attendu')
    return sorted(normalized, key=lambda r: (r['edition'], r['player_id']))


def split_for(year: int) -> str:
    return 'train' if year <= 2015 else 'validation' if year <= 2021 else 'test'


def build_dataset(raw: list[dict[str, str]], start_year: int = 1995) -> list[dict]:
    """Past-only features: emit an entire year before updating its histories."""
    if not 1956 <= start_year <= 2025:
        raise ValueError('start_year doit être entre 1956 et 2025')
    records = validate_rows(raw)
    grouped = defaultdict(list)
    for record in records:
        grouped[record['edition']].append(record)
    history = defaultdict(list)
    output = []
    previous_edition = None
    for year, group in sorted(grouped.items()):
        if year >= start_year:
            for record in group:
                past = history[record['player_id']]
                ranks = [r['rank'] for r in past]
                last_year = past[-1]['edition'] if past else None
                assert last_year is None or last_year < year
                output.append({
                    **{k: record[k] for k in ['edition', 'player_id', 'player', 'club', 'nationality', 'position']},
                    'previous_appearances': len(past),
                    'previous_top3': sum(rank <= 3 for rank in ranks),
                    'previous_wins': sum(rank == 1 for rank in ranks),
                    'previous_best_rank': min(ranks) if ranks else None,
                    'previous_last_rank': ranks[-1] if ranks else None,
                    'years_since_previous': year - last_year if past else None,
                    'appeared_previous_edition': int(bool(past) and last_year == previous_edition),
                    'has_history': int(bool(past)),
                    'history_last_edition': last_year,
                    'winner': int(record['rank'] == 1), 'split': split_for(year),
                })
        for record in group:
            history[record['player_id']].append(record)
        previous_edition = year
    return output


def prepare(raw_path: Path, output_dir: Path, start_year: int = 1995) -> dict:
    provenance_path = raw_path.with_name('provenance.json')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if digest != provenance['sha256']:
        raise ValueError('SHA-256 du brut différent du manifeste : revoir la provenance')
    with raw_path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != RAW_COLUMNS:
            raise ValueError('En-tête brut inattendu')
        raw = list(reader)
    if len(raw) != provenance['rows'] or sorted({int(r['year']) for r in raw}) != provenance['years']:
        raise ValueError('Couverture différente du manifeste')
    output = build_dataset(raw, start_year)
    if not output:
        raise ValueError('Aucune ligne dans la période demandée')
    # Compare labels independently, not by reading the same ranks twice.
    checks_path = raw_path.with_name('winner_checks.csv')
    with checks_path.open(encoding='utf-8', newline='') as stream:
        checks = list(csv.DictReader(stream))
    checked = {int(r['edition']): r['source_player'] for r in checks}
    if len(checked) != 30:
        raise ValueError('30 contrôles indépendants attendus')
    winners = {r['edition']: r['player'] for r in output if r['winner']}
    for year, winner in winners.items():
        if year >= 1995 and checked.get(year) != winner:
            raise ValueError(f'Étiquette différente du contrôle UEFA en {year}')
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / 'ballon_or.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(output)
    features = {
        'schema_version': 1, 'target': 'winner', 'group': 'edition',
        'numeric_features': NUMERIC_FEATURES, 'categorical_features': [],
        'excluded_columns': [c for c in OUTPUT_COLUMNS if c not in NUMERIC_FEATURES],
        'nullable_features': ['previous_best_rank', 'previous_last_rank', 'years_since_previous'],
        'position_policy': 'Excluded: available only in test years, never backfilled.',
        'split_policy': {'train': [1995, 2015], 'validation': [2016, 2021], 'test': [2022, 2025]},
    }
    report = {
        'source_sha256': digest, 'upstream_commit': provenance['upstream_commit'],
        'raw_rows': len(raw), 'raw_editions': len(provenance['years']),
        'output_rows': len(output), 'output_editions': len(winners),
        'start_year': start_year, 'end_year': max(winners),
        'raw_missing_by_column': {k: sum(not r[k].strip() for r in raw) for k in RAW_COLUMNS},
        'output_missing_by_column': {k: sum(r[k] is None for r in output) for k in OUTPUT_COLUMNS},
        'unknown_metadata': {k: sum(r[k] == 'Unknown' for r in output) for k in ['club', 'nationality', 'position']},
        'rows_per_edition': dict(sorted(Counter(r['edition'] for r in output).items())),
        'rows_per_split': dict(Counter(r['split'] for r in output)),
        'winners_per_split': dict(Counter(r['split'] for r in output if r['winner'])),
        'duplicate_player_edition_count': 0,
        'history_leakage_count': sum(r['history_last_edition'] is not None and r['history_last_edition'] >= r['edition'] for r in output),
        'winner_reference_checks': sum(y >= 1995 for y in winners),
        'limitations': ['Retrospective candidate pool, not exhaustive official nominations.',
                       'No goals, assists, minutes or team trophies.',
                       'Position missing before 2022; excluded from features.',
                       'Name-based identities, explicit Luis Suarez disambiguation.',
                       'Unobserved prior appearances cannot be counted.'],
    }
    for filename, content in [('features.json', features), ('quality_report.json', report)]:
        (output_dir / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=ROOT / 'data/raw/ballon_dor_all_years.csv')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/processed')
    args = parser.parse_args()
    report = prepare(args.raw, args.output_dir)
    print(f"Préparation OK : {report['output_rows']} lignes, {report['output_editions']} éditions, "
          f"{report['winner_reference_checks']} gagnants contrôlés.")


if __name__ == '__main__':
    main()
