#!/usr/bin/env python3
"""
Analyse one session (your own data).

    python analysis/analyze_session.py my_data/Visual_Mooney_Experiment_JaneDoe_2026-11-10_10-15-00.csv

Writes results/<file name>/summary.csv and fig_session.png, and prints a summary.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from common import (COLORS, CONDITIONS, INK, INK2, LABELS, ROOT, SURFACE, answered,
                    cell_means, effects, end_labels, is_complete, load, style)


def session_figure(df, path):
    fig, ax = plt.subplots(figsize=(6.5, 5.2), facecolor=SURFACE)
    style(ax)
    a = answered(df)
    rng = np.random.default_rng(0)
    post_means, post_colors = [], []
    for k, c in enumerate(CONDITIONS):
        sub = a[a.condition == c]
        if sub.empty:
            continue
        means = [sub[sub.trial_type == ph].recognized.mean() for ph in ('pre', 'post')]
        x = np.array([0, 1]) + (k - 1) * 0.06
        # one faint dot per item: that item's proportion "yes" in the phase
        items = sub.groupby(['trial_type', 'stimulus_file']).recognized.mean()
        for i, ph in enumerate(('pre', 'post')):
            vals = items.get(ph)
            if vals is not None:
                ax.scatter(x[i] + rng.uniform(-0.025, 0.025, len(vals)), vals, s=14, color=COLORS[c],
                           alpha=0.35, lw=0, zorder=2)
        ax.plot(x, means, color=COLORS[c], lw=2, marker='o', ms=8, zorder=3,
                markeredgecolor=SURFACE, markeredgewidth=2, label=LABELS[c])
        post_means.append(means[1])
        post_colors.append(COLORS[c])
    end_labels(ax, 1.16, post_means, post_colors)
    ax.set_xticks([0, 1], ['before reveal (pre)', 'after reveal (post)'], color=INK)
    ax.set_xlim(-0.3, 1.35)
    ax.set_ylim(-0.03, 1.06)
    ax.set_ylabel('proportion answered "yes"\n(dots = individual items)', color=INK2)
    pid, mod = df.participant_id.iloc[0], df.modality.iloc[0]
    ax.set_title(f"{pid}, {mod}: recognition before and after the reveal", color=INK, fontsize=11, loc='left')
    fig.legend(frameon=False, fontsize=8.5, loc='lower center', ncol=1, labelcolor=INK2)
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chance_margin(df) -> float:
    """Approximate 95% margin of the effect from trial-to-trial (binomial) chance alone."""
    a = answered(df)
    var = 0.0
    for c in ('target', 'filler_new'):
        for ph in ('pre', 'post'):
            x = a[(a.condition == c) & (a.trial_type == ph)].recognized
            var += x.mean() * (1 - x.mean()) / max(len(x), 1)
    return 1.96 * np.sqrt(var)


def describe(e, margin) -> str:
    pct = lambda v: f"{100 * v:.0f}%"
    return (f"Targets went from {pct(e['target_pre'])} to {pct(e['target_post'])}; "
            f"controls (filler_new) from {pct(e['filler_new_pre'])} to {pct(e['filler_new_post'])}; "
            f"disambiguation effect = ({pct(e['target_post'])} - {pct(e['target_pre'])}) - "
            f"({pct(e['filler_new_post'])} - {pct(e['filler_new_pre'])}) = "
            f"{100 * e['effect']:+.0f} percentage points "
            f"(± about {100 * margin:.0f} from chance alone, for one person's session).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv')
    ap.add_argument('--out', default=str(ROOT / 'results'), help="results folder (default results/)")
    args = ap.parse_args()

    df = load(args.csv)
    out = Path(args.out) / Path(args.csv).stem
    out.mkdir(parents=True, exist_ok=True)
    if not is_complete(df):
        print(f"Note: this session is incomplete ({len(df)} rows); analysing what is there.")

    cell_means(df).to_csv(out / 'summary.csv', index=False)
    session_figure(df, out / 'fig_session.png')
    e = effects(df)
    print(describe(e, chance_margin(df)))
    if np.isnan(e['effect']):
        print("(Some cells are empty, e.g. a very short session, so the effect cannot be computed.)")
    if str(df.participant_id.iloc[0]).lower().startswith('auto'):
        print("(This is an autopilot run: the answers are random, so the effect should be near zero.)")
    print(f"Saved {out / 'summary.csv'} and {out / 'fig_session.png'}")


if __name__ == '__main__':
    main()
