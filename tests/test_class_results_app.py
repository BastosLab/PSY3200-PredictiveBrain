"""
The class results app's session choice and numbers, on made-up sessions:
    python -m pytest tests/test_class_results_app.py
"""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'class-results-app'))
import class_results_app as app  # noqa: E402

COLS = ['participant_id', 'modality', 'seed', 'n_blocks', 'block', 'trial_number', 'trial_type',
        'target_index', 'stimulus_index', 'stimulus_file', 'condition', 'response', 'recognized',
        'reaction_time_ms', 'timestamp']


def write_session(folder, name, start, blocks=10, target_pre_yes=False):
    """A session where the target is 'yes' only after the reveal; other items are always 'no'."""
    path = folder / 'visual' / f'Visual_Mooney_Experiment_{name}_{start}.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(COLS)
        n = 0
        for b in range(1, blocks + 1):
            for phase in ('pre', 'reveal', 'post'):
                if phase == 'reveal':
                    n += 1
                    w.writerow([name, 'visual', 1, 10, b, n, 'reveal', b, b, f'img{b:02d}', 'reveal',
                                'NA', 'NA', 'NA', f'{start}T00:00'])
                    continue
                for i in range(24):
                    n += 1
                    cond = 'target' if i < 8 else ('filler_old' if b > 1 and i < 12 else 'filler_new')
                    yes = cond == 'target' and (phase == 'post' or target_pre_yes)
                    w.writerow([name, 'visual', 1, 10, b, n, phase, b, b, f'img{b:02d}', cond,
                                'yes' if yes else 'no', int(yes), 1000 if yes else 2000,
                                f'{start}T00:00'])
    return path


def test_latest_complete_session_is_used(tmp_path):
    write_session(tmp_path, 'Ann', '2026-11-01', blocks=2)                 # quit early
    write_session(tmp_path, 'Ann', '2026-11-02', target_pre_yes=True)      # complete, earlier
    write_session(tmp_path, 'Ann', '2026-11-03')                           # complete, latest
    write_session(tmp_path, 'Bob', '2026-11-03')
    included, everyone = app.load_modality(tmp_path, 'visual')
    assert [s['participant'] for s in included] == ['Ann', 'Bob']
    assert included[0]['start'].startswith('2026-11-03')
    status = {s['file'].split('_')[-1]: s['status'] for s in everyone if s['participant'] == 'Ann'}
    assert status['2026-11-01.csv'].startswith('left out: 2 of 10')
    assert status['2026-11-02.csv'] == 'left out: a later complete session exists'
    assert status['2026-11-03.csv'] == 'included'


def test_numbers(tmp_path):
    write_session(tmp_path, 'Ann', '2026-11-03')
    (session,), _ = app.load_modality(tmp_path, 'visual')
    s = app.summarize(session)
    assert s['target', 'pre']['yes'] == 0 and s['target', 'post']['yes'] == 100
    assert s['filler_new', 'post']['yes'] == 0
    assert s['target', 'post']['rt'] == 1000 and s['target', 'pre']['rt'] == 2000
    assert app.disambiguation(s, 'yes') == 100
    assert s['target', 'pre']['n'] == 80              # 8 target trials x 10 blocks


def test_figures_are_saved(tmp_path):
    pytest.importorskip('matplotlib')
    for name in ('Ann', 'Bob', 'Cy'):
        write_session(tmp_path / 'data', name, '2026-11-03')
    app.save_all(tmp_path / 'data', tmp_path / 'out')
    assert {p.name for p in (tmp_path / 'out').glob('*.png')} == {
        'class_visual_yes.png', 'class_visual_rt.png', 'class_audio_yes.png', 'class_audio_rt.png'}
