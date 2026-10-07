"""Tests métier : fuites temporelles, identités et contrat des données."""
import copy
import csv
import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path

from src.prepare_data import ROOT, NUMERIC_FEATURES, build_dataset, prepare, validate_rows


def row(year, name, rank, **kwargs):
    return dict(year=str(year), player=name, rank=str(rank), club='Club',
                nationality='France', points='', percent='', position='', **kwargs)


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.raw = [row(1995, 'Alice', 1), row(1995, 'Bob', 2),
                    row(1996, 'Alice', 2), row(1996, 'Bob', 1),
                    row(1997, 'Alice', 1), row(1997, 'Bob', 2)]

    def feature_map(self, raw, year):
        return {r['player_id']: [r[k] for k in NUMERIC_FEATURES]
                for r in build_dataset(raw) if r['edition'] == year}

    def test_current_votes_do_not_change_current_features(self):
        changed = copy.deepcopy(self.raw)
        changed[2]['rank'], changed[3]['rank'] = '1', '2'
        changed[2]['points'], changed[2]['percent'] = '999', '99'
        self.assertEqual(self.feature_map(self.raw, 1996), self.feature_map(changed, 1996))
        # Changed results must only affect subsequent historical features.
        self.assertNotEqual(self.feature_map(self.raw, 1997), self.feature_map(changed, 1997))

    def test_future_rows_have_no_effect_on_past(self):
        extended = self.raw + [row(1998, 'Future Star', 1), row(1998, 'Alice', 2)]
        baseline = build_dataset(self.raw)
        self.assertEqual(baseline, [r for r in build_dataset(extended) if r['edition'] <= 1997])

    def test_input_order_does_not_encode_rank(self):
        shuffled = copy.deepcopy(self.raw)
        random.Random(42).shuffle(shuffled)
        self.assertEqual(build_dataset(self.raw), build_dataset(shuffled))

    def test_first_appearance_and_exact_lag(self):
        rows = build_dataset(self.raw)
        first = next(r for r in rows if r['edition'] == 1995 and r['player'] == 'Alice')
        self.assertEqual(first['previous_wins'], 0)
        self.assertIsNone(first['previous_best_rank'])
        later = next(r for r in rows if r['edition'] == 1997 and r['player'] == 'Alice')
        self.assertEqual((later['previous_appearances'], later['previous_top3'], later['previous_wins']), (2, 2, 1))
        self.assertEqual(later['previous_last_rank'], 2)

    def test_no_backfill_of_future_position(self):
        raw = [row(2021, 'Alice', 1), row(2022, 'Alice', 1)]
        raw[1]['position'] = 'Forward'
        self.assertEqual(build_dataset(raw)[0]['position'], 'Unknown')

    def test_cancelled_year_not_treated_as_edition(self):
        rows = build_dataset([row(2019, 'Alice', 1), row(2021, 'Alice', 1)])
        self.assertEqual(rows[-1]['appeared_previous_edition'], 1)
        self.assertEqual(rows[-1]['years_since_previous'], 2)

    def test_homonyms_do_not_share_history(self):
        raw = [row(1960, 'Luis Suárez', 1), row(2011, 'Luis Suárez', 2), row(2011, 'Lionel Messi', 1)]
        uruguayan = next(r for r in build_dataset(raw) if r['player_id'] == 'luis-suarez-uy')
        self.assertEqual(uruguayan['previous_wins'], 0)
        self.assertEqual(uruguayan['previous_appearances'], 0)

    def test_documented_accent_variant_keeps_history(self):
        rows = build_dataset([row(2022, 'Vinicius Junior', 1), row(2023, 'Vinícius Júnior', 1)])
        self.assertEqual(rows[-1]['previous_wins'], 1)

    def test_duplicates_invalid_types_and_missing_targets_fail(self):
        bad_cases = [self.raw + [self.raw[0]], [row(1995, 'Alice', '')],
                     [row(1995, 'Alice', '1.5')], [row(1995, 'Alice', 2)],
                     [row(2020, 'Alice', 1)], [row(1995, '', 1)]]
        for bad in bad_cases:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_rows(bad)


class SnapshotTests(unittest.TestCase):
    def test_full_snapshot_contract_and_reproducibility(self):
        raw_path = ROOT / 'data/raw/ballon_dor_all_years.csv'
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / 'a', Path(folder) / 'b'
            report = prepare(raw_path, first)
            prepare(raw_path, second)
            for path in first.iterdir():
                self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
            self.assertEqual(report['output_editions'], 30)
            self.assertEqual(report['history_leakage_count'], 0)
            self.assertEqual(report['winner_reference_checks'], 30)
            self.assertEqual(report['winners_per_split'], {'train': 21, 'validation': 5, 'test': 4})
            with (first / 'ballon_or.csv').open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            for r in rows:
                self.assertTrue(not r['history_last_edition'] or int(r['history_last_edition']) < int(r['edition']))
            config = json.loads((first / 'features.json').read_text(encoding='utf-8'))
            forbidden = {'rank', 'points', 'percent', 'winner', 'edition', 'split', 'player', 'player_id', 'position', 'history_last_edition'}
            self.assertFalse(forbidden & set(config['numeric_features']))
            self.assertFalse(forbidden & set(config['categorical_features']))
            messi_2010 = next(r for r in rows if r['edition'] == '2010' and r['player_id'] == 'lionel-messi')
            self.assertEqual(messi_2010['previous_wins'], '1')

    def test_tampered_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = Path(folder) / 'input.csv'
            raw.write_text('modified', encoding='utf-8')
            manifest = {'sha256': hashlib.sha256(b'original').hexdigest()}
            raw.with_name('provenance.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                prepare(raw, Path(folder) / 'out')


if __name__ == '__main__':
    unittest.main()
