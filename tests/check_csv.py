#!/usr/bin/env python3
"""Check that a session CSV from mooney_prediction_task_blocks.py is complete and consistent.

    python tests/check_csv.py ~/mooney_data/mooney_P01_visual_*.csv
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mooney_prediction_task_blocks import FIELDNAMES  # noqa: E402


def check_rows(df: pd.DataFrame) -> None:
    """Checks that hold for complete and for partial (quit / crashed) sessions."""
    assert list(df.columns) == FIELDNAMES, list(df.columns)
    assert df.trial_number.tolist() == list(range(1, len(df) + 1)), "gaps in trial_number"
    assert df.participant_id.nunique() == 1 and df.seed.nunique() == 1
    prefix = 'img' if df.modality.iloc[0] == 'visual' else 'sent'
    assert df.stimulus_file.str.startswith(prefix).all()
    assert (df.stimulus_file.str[-2:].astype(int) == df.stimulus_index).all()

    answered = df[df.trial_type != 'reveal']
    assert answered.response.isin(['yes', 'no']).all()
    assert (answered.recognized.astype(int) == (answered.response == 'yes')).all()
    assert (answered.reaction_time_ms.astype(float) > 0).all()
    rev = df[df.trial_type == 'reveal']
    assert (rev.response == 'NA').all() and (rev.reaction_time_ms == 'NA').all()
    assert (rev.stimulus_index == rev.target_index).all()

    # condition: target = this block's target; filler_old = target of an earlier block
    earlier_targets = set()
    for block, b in df.groupby('block', sort=True):
        assert b.target_index.nunique() == 1
        target = b.target_index.iloc[0]
        assert target not in earlier_targets, "target reused"
        expected = [('target' if s == target else 'filler_old' if s in earlier_targets else 'filler_new')
                    for s in b.stimulus_index]
        assert b.condition.tolist() == expected, f"block {block}: wrong condition labels"
        earlier_targets.add(target)


def check_complete(df: pd.DataFrame, target_reps=8, n_fillers=4, filler_reps=4) -> None:
    check_rows(df)
    n_blocks = int(df.n_blocks.iloc[0])
    per_phase = target_reps + n_fillers * filler_reps
    assert len(df) == n_blocks * (2 * per_phase + 1), f"{len(df)} rows"
    for block, b in df.groupby('block'):
        target = b.target_index.iloc[0]
        assert b.trial_type.tolist() == ['pre'] * per_phase + ['reveal'] + ['post'] * per_phase
        fillers = None
        for phase in ('pre', 'post'):
            counts = b[b.trial_type == phase].stimulus_index.value_counts().to_dict()
            assert counts.pop(target) == target_reps
            assert len(counts) == n_fillers and set(counts.values()) == {filler_reps}
            assert fillers is None or fillers == set(counts), "fillers differ between pre and post"
            fillers = set(counts)


def read(path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False,
                       dtype={'response': str, 'recognized': str, 'reaction_time_ms': str})


if __name__ == '__main__':
    for p in sys.argv[1:]:
        check_complete(read(p))
        print(f"OK  {p}")
