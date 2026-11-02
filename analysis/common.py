"""Shared helpers for analysing data files from mooney_prediction_task_blocks.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mooney_prediction_task_blocks import FIELDNAMES  # noqa: E402

CONDITIONS = ['target', 'filler_new', 'filler_old']
LABELS = {'target': 'target (revealed this block)',
          'filler_new': 'filler_new (never revealed: control)',
          'filler_old': 'filler_old (revealed in an earlier block)'}
# reference palette, light mode: categorical slots 2 / 1 / 3 and neutral inks
COLORS = {'target': '#eb6834', 'filler_new': '#2a78d6', 'filler_old': '#1baf7a'}
INK, INK2, MUTED, SURFACE, GRID = '#0b0b0b', '#52514e', '#8a8984', '#fcfcfb', '#e4e3df'


def load(path) -> pd.DataFrame:
    """Read one session file; 'NA' cells become missing values."""
    df = pd.read_csv(path, na_values=['NA'], keep_default_na=False, dtype={'participant_id': str})
    missing = set(FIELDNAMES) - set(df.columns)
    if missing:
        raise ValueError(f"not a task data file (missing columns {sorted(missing)})")
    df['source_file'] = Path(path).name
    return df


def is_complete(df: pd.DataFrame) -> bool:
    """True if the session reached the end of its last block's post phase."""
    last = df[df.block == int(df.n_blocks.iloc[0])]
    n_pre, n_post = (last.trial_type == 'pre').sum(), (last.trial_type == 'post').sum()
    return n_pre > 0 and n_pre == n_post


def answered(df: pd.DataFrame) -> pd.DataFrame:
    """The pre and post trials (the reveal has no answer)."""
    return df[df.trial_type.isin(['pre', 'post'])]


def cell_means(df: pd.DataFrame) -> pd.DataFrame:
    """Proportion 'yes', trial count and mean RT for each phase x condition."""
    out = (answered(df).groupby(['trial_type', 'condition'])
           .agg(p_yes=('recognized', 'mean'), n_trials=('recognized', 'size'),
                mean_rt_ms=('reaction_time_ms', 'mean'))
           .reset_index().rename(columns={'trial_type': 'phase'}))
    out['phase'] = pd.Categorical(out.phase, ['pre', 'post'])
    out['condition'] = pd.Categorical(out.condition, CONDITIONS)
    return out.sort_values(['condition', 'phase']).reset_index(drop=True)


def effects(df: pd.DataFrame) -> dict:
    """Pre/post proportions per condition, the gains, and the disambiguation effect."""
    p = answered(df).groupby(['condition', 'trial_type']).recognized.mean()
    out = {}
    for c in CONDITIONS:
        out[f'{c}_pre'] = p.get((c, 'pre'), np.nan)
        out[f'{c}_post'] = p.get((c, 'post'), np.nan)
    out['target_gain'] = out['target_post'] - out['target_pre']
    out['control_gain'] = out['filler_new_post'] - out['filler_new_pre']
    out['effect'] = out['target_gain'] - out['control_gain']
    return out


def end_labels(ax, x, values, colors, min_gap=0.055):
    """Percentage labels at x, each with a dot in its series colour, nudged apart so they never overlap."""
    vals = sorted((v, k) for k, v in enumerate(values) if not np.isnan(v))
    placed = []
    for v, k in vals:
        y = max(v, placed[-1] + min_gap) if placed else v
        placed.append(y)
        ax.plot(x, y, 'o', ms=6, color=colors[k], clip_on=False)
        ax.text(x + 0.05, y, f"{v:.0%}", color=INK, fontsize=9, va='center')


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
