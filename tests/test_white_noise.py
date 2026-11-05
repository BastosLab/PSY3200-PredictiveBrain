"""The White Noise analysis reads the 2026 spreadsheets and matches Ishan's original tally."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'white_noise'))
import analyze_white_noise as wn  # noqa: E402

ISHAN_2026 = {'P1': (6, 0, 0), 'P2': (0, 2, 8), 'P3': (4, 3, 1), 'P4': (0, 5, 0), 'P5': (12, 14, 16)}


def test_clock_formats():
    assert wn.clock_minutes(dt.time(17, 14, 30)) == wn.clock_minutes(dt.time(5, 14, 30))
    assert wn.clock_minutes('5:14:30PM') == pytest.approx(5 * 60 + 14.5)
    assert wn.clock_minutes('5.14.30') == pytest.approx(5 * 60 + 14.5)
    assert wn.clock_minutes('No') is None


def test_2026_counts_match_original():
    sessions = {s['participant']: s for s in wn.load_sessions() if s['year'] == '2026'}
    for p, expected in ISHAN_2026.items():
        c = sessions[p]['counts']
        assert (c['Auditory'], c['Visual'], c['Bodily']) == expected, p


def test_summary_and_figure(tmp_path):
    summary = wn.summarise(wn.load_sessions())
    assert summary['2025', 'Auditory']['mean'] == pytest.approx(0.549, abs=5e-4)
    assert summary['2026', 'Bodily']['se'] == pytest.approx(0.187, abs=5e-4)
    out = tmp_path / 'fig.png'
    wn.plot(wn.load_sessions(), summary, out)
    assert out.stat().st_size > 10_000
