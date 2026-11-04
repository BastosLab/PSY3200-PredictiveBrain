"""Stats lab: its hand-written formulas match scipy, and every command runs."""
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'stats_lab'))
import stats_lab  # noqa: E402


def test_describe_matches_numpy_and_scipy():
    x = np.random.default_rng(0).normal(300, 45, 20)
    d = stats_lab.describe(x)
    assert abs(d['mean'] - x.mean()) < 1e-9
    assert abs(d['sd'] - x.std(ddof=1)) < 1e-9
    assert abs(d['se'] - stats.sem(x)) < 1e-9
    lo, hi = stats.t.interval(0.95, len(x) - 1, loc=x.mean(), scale=stats.sem(x))
    assert abs(d['lo'] - lo) < 1e-9 and abs(d['hi'] - hi) < 1e-9


def test_compare_matches_welch_t_test():
    rng = np.random.default_rng(1)
    a, b = rng.normal(300, 45, 20), rng.normal(340, 60, 25)
    r = stats_lab.compare(a, b)
    w = stats.ttest_ind(b, a, equal_var=False)
    assert abs(r['t'] - w.statistic) < 1e-9 and abs(r['p'] - w.pvalue) < 1e-9
    assert (r['lo'] > 0) == (r['p'] < 0.05)          # CI excludes 0 exactly when p < .05


def test_every_command_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stats_lab, 'FIG_DIR', tmp_path)
    for argv in (['sample'], ['repeat', '--reps', '500'], ['coverage', '--studies', '30'], ['two'],
                 ['many', '--studies', '100'], ['many', '--diff', '40', '--studies', '100']):
        stats_lab.main(argv + ['--seed', '1'])
    out = capsys.readouterr().out
    assert 'Standard error' in out and 'p < .05 in' in out
    assert len(list(tmp_path.glob('*.png'))) == 6
