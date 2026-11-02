"""
Tests for mooney_prediction_task_blocks.py:   python -m pytest tests/
The autopilot tests open a real window (Xvfb on headless Linux) with sound off.
"""
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pytest

os.environ['SDL_AUDIODRIVER'] = 'dummy'
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_csv import check_complete, check_rows, read  # noqa: E402
from mooney_prediction_task_blocks import MooneyPredictionTask  # noqa: E402

HEADLESS = sys.platform.startswith('linux') and not os.environ.get('DISPLAY')
needs_display = pytest.mark.skipif(HEADLESS and not shutil.which('xvfb-run'),
                                   reason="no display and no xvfb-run")
ENV = {**os.environ, 'SDL_AUDIODRIVER': 'dummy'}


def task_cmd(*args):
    cmd = [sys.executable, str(ROOT / 'mooney_prediction_task_blocks.py'), *args]
    return ['xvfb-run', '-a'] + cmd if HEADLESS else cmd


def test_stimuli_load():
    task = MooneyPredictionTask(ROOT / 'stimuli', ROOT / 'unused')
    assert len(task.images) == len(task.originals) == len(task.sounds) == len(task.clear_sounds) == 12
    for img in task.images:
        assert set(img.ravel().tolist()) <= {0, 255}          # two-tone: black and white only
        assert 0.45 < (img == 255).mean() < 0.55


def test_block_sequences_over_many_seeds():
    task = MooneyPredictionTask(ROOT / 'stimuli', ROOT / 'unused')
    for seed in range(200):
        task.rng = random.Random(seed)
        targets = task.rng.sample(task.item_indices, task.n_blocks)
        assert len(set(targets)) == 10
        for t in targets:
            seq = task.generate_block_sequence(t)
            for phase in ('pre', 'post'):
                c = Counter(seq[phase])
                assert len(seq[phase]) == 24 and c.pop(t) == 8
                assert set(c) == set(seq['fillers']) and set(c.values()) == {4}
            assert seq['pre'] != seq['post']            # reshuffled


@needs_display
@pytest.mark.parametrize('modality', ['visual', 'audio'])
def test_autopilot_full_session(tmp_path, modality):
    subprocess.run(task_cmd('--autopilot', '--speed', '50', '--participant', 'AUTO',
                            '--modality', modality, '--data-dir', str(tmp_path)),
                   env=ENV, check=True, timeout=600, capture_output=True)
    (f,) = tmp_path.glob(f'mooney_AUTO_{modality}_*.csv')
    df = read(f)
    check_complete(df)
    assert len(df) == 490


@needs_display
def test_short_session_options(tmp_path):
    subprocess.run(task_cmd('--autopilot', '--speed', '50', '--modality', 'visual', '--blocks', '3',
                            '--target-reps', '4', '--filler-reps', '2', '--data-dir', str(tmp_path)),
                   env=ENV, check=True, timeout=300, capture_output=True)
    (f,) = tmp_path.glob('mooney_autopilot_visual_*.csv')
    check_complete(read(f), target_reps=4, filler_reps=2)


@pytest.mark.skipif(HEADLESS, reason="in-process Tk needs a display")
def test_quit_midway_keeps_data(tmp_path):
    """What happens after the participant confirms ESC (the dialog itself is not automated)."""
    from mooney_prediction_task_blocks import MooneyGUI
    task = MooneyPredictionTask(ROOT / 'stimuli', tmp_path)
    gui = MooneyGUI(task, autopilot=True, speed=20)
    gui.root.after(50, lambda: gui.begin_session('QUIT', 'visual'))
    gui.root.after(1500, lambda: setattr(gui, 'quit_requested', True))
    gui.run()
    (f,) = tmp_path.glob('mooney_QUIT_*.csv')
    df = read(f)
    check_rows(df)
    assert 0 < len(df) < 490 and task.data_file.closed


@needs_display
def test_break_screen_before_every_block(tmp_path):
    """Every block starts on a break screen with its number, and SPACE starts it."""
    import tkinter as tk
    from mooney_prediction_task_blocks import MooneyGUI
    task = MooneyPredictionTask(ROOT / 'stimuli', tmp_path, n_blocks=3, target_reps=1, filler_reps=1)
    gui = MooneyGUI(task, autopilot=True, speed=20)
    screens, wait = [], gui.wait_for_response

    def recording_wait(choices):
        if choices == ['continue']:
            labels = [w for f in gui.root.winfo_children() for w in f.winfo_children() if isinstance(w, tk.Label)]
            screens.append((' | '.join(w.cget('text') for w in labels), bool(gui.root.bind('<space>'))))
        return wait(choices)

    gui.wait_for_response = recording_wait
    gui.root.after(50, lambda: gui.begin_session('BREAKS', 'visual'))
    gui.run()
    assert len(screens) == 3
    for k, (text, space_bound) in enumerate(screens, start=1):
        assert f"Block {k} of 3" in text and 'SPACE' in text and space_bound, text
        assert (f"Block {k - 1} of 3 done" in text) == (k > 1), text


@needs_display
def test_sigkill_keeps_completed_trials(tmp_path):
    proc = subprocess.Popen(task_cmd('--autopilot', '--speed', '3', '--participant', 'KILL',
                                     '--modality', 'visual', '--data-dir', str(tmp_path)), env=ENV)
    deadline = time.time() + 120
    f = None
    while time.time() < deadline:
        files = list(tmp_path.glob('mooney_KILL_*.csv'))
        if files and len(read(files[0])) >= 10:
            f = files[0]
            break
        time.sleep(0.2)
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=30)
    assert f is not None, "no rows were written"
    df = read(f)
    check_rows(df)                       # every row that was written is complete
    assert 10 <= len(df) < 490
