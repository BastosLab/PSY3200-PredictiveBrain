#!/usr/bin/env python3
"""
Write fake class data, in exactly the task's file format, with KNOWN effects,
so we can check that the analysis finds them before collecting real data.

    python analysis/simulate_class_data.py                 # 20 participants x both modalities
    python analysis/simulate_class_data.py --null          # no disambiguation effect at all
    python analysis/analyze_class.py data/simulated/

P(answer "yes") used here (before participant and item differences):
                                   visual  audio
    pre, target and filler_new      0.20   0.15
    post, filler_new (control)      0.30   0.55
    post, target                    0.85   0.85
    filler_old (revealed earlier)   0.85   0.85
Audio controls rise more on purpose: after hearing clear versions, listeners
switch into "speech mode" and understand even new sine-wave sentences
(Remez et al., 1981), whereas the visual prior is item-specific.
"""
import argparse
import os
import random
from pathlib import Path

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import numpy as np
import pandas as pd
from scipy.special import expit, logit

from common import ROOT
from mooney_prediction_task_blocks import FIELDNAMES, N_ITEMS, MooneyPredictionTask

PROBS = {'visual': dict(pre=0.20, post_control=0.30, post_target=0.85, revealed=0.85),
         'audio': dict(pre=0.15, post_control=0.55, post_target=0.85, revealed=0.85)}
SUBJECT_SD = 0.5    # participant random intercept, log-odds
ITEM_SD = 0.5       # item random intercept, log-odds


def p_yes(modality, phase, condition, null=False):
    p = PROBS[modality]
    if null:
        return p['pre']
    if condition == 'filler_old':
        return p['revealed']
    if phase == 'pre':
        return p['pre']
    return p['post_target'] if condition == 'target' else p['post_control']


class _Rows:
    """Stands in for the task's csv writer, collecting rows in memory."""
    def __init__(self):
        self.rows = []

    def writerow(self, record):
        self.rows.append(dict(record))


def make_task():
    return MooneyPredictionTask(ROOT / 'stimuli', ROOT / 'unused')


def simulate_session(task, participant_id, modality, item_effects, rng, null=False) -> pd.DataFrame:
    """One session, built with the task's own sequence and logging code."""
    task.participant_id, task.modality = participant_id, modality
    task.seed = int(rng.integers(2 ** 32))
    task.rng = random.Random(task.seed)
    task.revealed = set()
    task.current_trial = 0
    task.writer, task._sync = _Rows(), lambda: None
    subject = rng.normal(0, SUBJECT_SD)

    for block, target in enumerate(task.rng.sample(task.item_indices, task.n_blocks), start=1):
        seq = task.generate_block_sequence(target)
        for phase in ('pre', 'reveal', 'post'):
            for idx in ([target] if phase == 'reveal' else seq[phase]):
                task.current_trial += 1
                if phase == 'reveal':
                    task.log_trial(block, phase, idx, target, None, None)
                    continue
                p = expit(logit(p_yes(modality, phase, task.condition_of(idx, target), null))
                          + subject + item_effects[idx])
                response = 'yes' if rng.random() < p else 'no'
                rt = (rng.lognormal(np.log(1.1), 0.35) if modality == 'visual'
                      else 3.3 + rng.lognormal(np.log(0.8), 0.4))
                task.log_trial(block, phase, idx, target, response, rt)
            if phase == 'reveal':
                task.revealed.add(target)
    return pd.DataFrame(task.writer.rows, columns=FIELDNAMES)


def simulate_class(n=20, seed=1, null=False, modalities=('visual', 'audio'), task=None):
    """Yield (participant_id, modality, DataFrame) for a simulated class."""
    task = task or make_task()
    rng = np.random.default_rng(seed)
    item_effects = {m: rng.normal(0, ITEM_SD, N_ITEMS) for m in modalities}
    for k in range(1, n + 1):
        for m in modalities:
            yield f"S{k:02d}", m, simulate_session(task, f"S{k:02d}", m, item_effects[m], rng, null)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, default=20, help="participants (default 20)")
    ap.add_argument('--null', action='store_true', help="no disambiguation effect")
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', default=str(ROOT / 'data' / 'simulated'))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for pid, mod, df in simulate_class(args.n, args.seed, args.null):
        df.to_csv(out / f"mooney_{pid}_{mod}_simulated.csv", index=False)
    print(f"Wrote {2 * args.n} files to {out}" + (" (null: no effect)" if args.null else ""))


if __name__ == '__main__':
    main()
