"""
Analysis pipeline checks: does it find effects we planted, and only those?
    python -m pytest tests/test_analysis.py
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

os.environ['SDL_AUDIODRIVER'] = 'dummy'
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'analysis'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_class import analyze  # noqa: E402
from class_repo import FILE_PREFIX  # noqa: E402
from check_csv import check_complete, read  # noqa: E402
from common import effects  # noqa: E402
from simulate_class_data import PROBS, make_task, simulate_class  # noqa: E402


@pytest.fixture(scope='module')
def task():
    return make_task()


@pytest.fixture(scope='module')
def simulated(tmp_path_factory, task):
    folder = tmp_path_factory.mktemp('sim')
    for pid, mod, df in simulate_class(n=20, seed=1, task=task):
        df.to_csv(folder / f"{FILE_PREFIX[mod]}_{pid}_simulated.csv", index=False)
    return folder


def test_simulated_files_match_task_format(simulated):
    for f in sorted(simulated.glob('*.csv'))[:4]:
        check_complete(read(f))


def test_recovers_planted_effects(simulated, tmp_path):
    table, results = analyze(simulated, tmp_path, quiet=True)
    for mod, p in PROBS.items():
        t = table[table.modality == mod]
        assert len(t) == 20
        for col, expected in [('target_pre', p['pre']), ('filler_new_pre', p['pre']),
                              ('target_post', p['post_target']), ('filler_new_post', p['post_control'])]:
            assert abs(t[col].mean() - expected) <= 0.08, (mod, col, t[col].mean(), expected)
        assert results[(mod, 'effect')]['p'] < 0.05 and results[(mod, 'effect')]['mean'] > 0
    # audio controls were simulated to rise more than visual controls
    assert results[('audio-visual', 'control_gain')]['mean'] > 0
    for name in ('participants.csv', 'stats.txt', 'fig_class_modality.png', 'fig_effects.png', 'fig_items.png'):
        assert (tmp_path / name).exists()


def test_null_false_positive_rate(task):
    """200 simulated classes with no effect: the effect test should fire about 5% of the time."""
    hits = 0
    for sim in range(200):
        eff = [effects(df)['effect'] for _, _, df in
               simulate_class(n=20, seed=1000 + sim, null=True, modalities=('visual',), task=task)]
        hits += stats.ttest_1samp(eff, 0).pvalue < 0.05
    assert hits / 200 <= 0.07, f"false-positive rate {hits / 200:.3f}"


def test_skips_demo_incomplete_and_duplicates(simulated, tmp_path):
    folder = tmp_path / 'class'
    (folder / 'demo').mkdir(parents=True)
    files = sorted(simulated.glob('Visual_*.csv'))[:3]
    for f in files:
        (folder / f.name).write_text(f.read_text())
    lines = files[0].read_text().splitlines()
    (folder / 'Visual_Mooney_Experiment_S99_partial.csv').write_text('\n'.join(lines[:100]) + '\n')     # quit early
    (folder / 'demo' / files[1].name).write_text(files[1].read_text())
    (folder / 'Visual_Mooney_Experiment_S01_again.csv').write_text(files[0].read_text())               # duplicate
    table, _ = analyze(folder, tmp_path / 'out', quiet=True)
    assert len(table) == 3
    text = (tmp_path / 'out' / 'stats.txt').read_text()
    assert 'incomplete session' in text and 'duplicate' in text


def test_after_first_class(simulated, tmp_path):
    """First class: everyone did visual; nobody has audio yet."""
    folder = tmp_path / 'class1'
    folder.mkdir()
    for f in simulated.glob('Visual_*.csv'):
        (folder / f.name).write_text(f.read_text())
    table, results = analyze(folder, tmp_path / 'out', quiet=True)
    assert (table.modality == 'visual').sum() == 20 and len(table) == 20
    assert results[('visual', 'effect')]['p'] < 0.05
    assert ('audio', 'effect') not in results and ('audio-visual', 'effect') not in results
    assert 'Not enough participants with both modalities' in (tmp_path / 'out' / 'stats.txt').read_text()
    for name in ('fig_class_modality.png', 'fig_effects.png', 'fig_items.png'):
        assert (tmp_path / 'out' / name).exists()


def test_scripts_run_from_command_line(tmp_path):
    run = lambda *a: subprocess.run([sys.executable, *a], check=True, capture_output=True, text=True,
                                    env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'}, timeout=300)
    run(str(ROOT / 'analysis' / 'simulate_class_data.py'), '--n', '4', '--out', str(tmp_path / 'data'))
    out = run(str(ROOT / 'analysis' / 'analyze_class.py'), str(tmp_path / 'data'), '--out', str(tmp_path / 'res'))
    assert 'disambiguation effect' in out.stdout
    f = next((tmp_path / 'data').glob('Visual_*.csv'))
    out = run(str(ROOT / 'analysis' / 'analyze_session.py'), str(f), '--out', str(tmp_path / 'res'))
    assert 'Targets went from' in out.stdout
    assert (tmp_path / 'res' / f.stem / 'fig_session.png').exists()
