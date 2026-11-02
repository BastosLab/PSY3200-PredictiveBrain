#!/usr/bin/env python3
"""
Analyse the whole class: every session file in a folder.

    python analysis/analyze_class.py --download     # fetch everyone's latest data from GitHub first
    python analysis/analyze_class.py class_data/    # or analyse a folder you already have

Skips anything in a demo/ subfolder and incomplete (quit or crashed) sessions,
listing them. Writes to results/class/:
    participants.csv        one row per participant x modality, with exclusion flags
    stats.txt               the tests, in plain English
    fig_class_modality.png  pre -> post recognition by condition, visual vs audio
    fig_effects.png         each participant's disambiguation effect and control gain
    fig_items.png           post - pre gain per item, for spotting bad stimuli
    mixed_model.txt         optional, only if statsmodels is installed
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from common import (COLORS, CONDITIONS, INK, INK2, LABELS, MUTED, ROOT, SURFACE, answered,
                    effects, end_labels, is_complete, load, style)

N_PERM = 10_000


# ---------------------------------------------------------------- loading
def collect(folder: Path):
    """Read every complete session in folder. Returns (sessions, list of (file, reason) skipped)."""
    sessions, skipped = [], []
    for f in sorted(folder.rglob('*.csv')):
        if 'demo' in f.relative_to(folder).parts[:-1]:
            continue
        try:
            df = load(f)
        except Exception as e:                       # not a task file, unreadable, ...
            skipped.append((f.name, str(e)))
            continue
        if not is_complete(df):
            skipped.append((f.name, f"incomplete session ({len(df)} rows)"))
            continue
        sessions.append(df)

    # the same participant x modality more than once: keep the earliest, warn
    by_key = {}
    for df in sorted(sessions, key=lambda d: d.timestamp.iloc[0]):
        key = (df.participant_id.iloc[0], df.modality.iloc[0])
        if key in by_key:
            skipped.append((df.source_file.iloc[0], f"duplicate of {by_key[key].source_file.iloc[0]} "
                                                    f"(same participant and modality); kept the earlier one"))
        else:
            by_key[key] = df
    return list(by_key.values()), skipped


def participant_table(sessions) -> pd.DataFrame:
    rows = []
    for df in sessions:
        a = answered(df)
        pre_yes = a[a.trial_type == 'pre'].recognized.mean()
        median_rt = a.reaction_time_ms.median()
        flags = []
        if pre_yes > 0.90 or pre_yes < 0.05:
            flags.append('response_bias')
        if median_rt < 200:
            flags.append('too_fast')
        rows.append({'participant_id': df.participant_id.iloc[0], 'modality': df.modality.iloc[0],
                     **effects(df), 'pre_yes_rate': pre_yes, 'median_rt_ms': median_rt,
                     'n_rows': len(df), 'flags': ';'.join(flags), 'file': df.source_file.iloc[0]})
    return pd.DataFrame(rows).sort_values(['modality', 'participant_id']).reset_index(drop=True)


# ---------------------------------------------------------------- statistics
def sign_flip_p(x, rng) -> float:
    """Two-sided sign-flip permutation test of mean(x) = 0."""
    x = np.asarray(x)
    flips = rng.choice([-1, 1], size=(N_PERM, len(x)))
    null = np.abs((flips * x).mean(axis=1))
    return (np.sum(null >= abs(x.mean()) - 1e-12) + 1) / (N_PERM + 1)


def one_sample(x, rng) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 2:
        return {'n': n}
    t, p = stats.ttest_1samp(x, 0)
    sd = x.std(ddof=1)
    half = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return {'n': n, 'mean': x.mean(), 'sd': sd, 'ci': (x.mean() - half, x.mean() + half),
            't': t, 'df': n - 1, 'p': p, 'dz': x.mean() / sd if sd > 0 else np.nan,
            'p_perm': sign_flip_p(x, rng)}


def fmt_p(p):
    return "p < .001" if p < 0.001 else f"p = {p:.3f}"


def sentence(question, r, verdicts=("Yes", "No: it is reliably below zero"), unit="percentage points"):
    """verdicts = what to say when the mean is reliably above / below zero."""
    if r['n'] < 2:
        return f"{question}\n  Not enough participants (n = {r['n']}).\n"
    pp = lambda v: f"{100 * v:+.1f}"
    verdict = verdicts[0 if r['mean'] > 0 else 1] if r['p'] < 0.05 else "No clear evidence"
    return (f"{question}\n"
            f"  {verdict}. Mean = {pp(r['mean'])} {unit} (SD {100 * r['sd']:.1f}), "
            f"95% CI [{pp(r['ci'][0])}, {pp(r['ci'][1])}], n = {r['n']}.\n"
            f"  t({r['df']}) = {r['t']:.2f}, {fmt_p(r['p'])}, Cohen's d_z = {r['dz']:.2f}. "
            f"Sign-flip permutation test ({N_PERM:,} permutations): {fmt_p(r['p_perm'])}.\n")


def run_stats(table: pd.DataFrame, rng) -> tuple:
    results, lines = {}, []
    for mod in ('visual', 'audio'):
        t = table[table.modality == mod]
        if t.empty:
            continue
        lines.append(f"=== {mod.upper()} (n = {len(t)} participants) ===\n")
        for c in CONDITIONS:
            pre, post = t[f'{c}_pre'].mean(), t[f'{c}_post'].mean()
            lines.append(f"  {c:<11} pre {100 * pre:5.1f}%   post {100 * post:5.1f}%")
        lines.append("")
        results[(mod, 'effect')] = r = one_sample(t.effect, rng)
        lines.append(sentence("Is the disambiguation effect above zero? "
                              "[(target post - pre) - (filler_new post - pre)]", r))
        results[(mod, 'control_gain')] = r = one_sample(t.control_gain, rng)
        lines.append(sentence("Do the never-revealed fillers improve too (repetition / general learning)? "
                              "[filler_new post - pre]", r))

    wide = table.pivot(index='participant_id', columns='modality', values=['effect', 'control_gain'])
    both = wide.dropna() if wide.columns.get_level_values('modality').nunique() == 2 else wide.iloc[:0]
    lines.append(f"=== VISUAL vs AUDIO (paired; {len(both)} participants did both modalities) ===\n")
    if len(both) >= 2:
        lines.append("Everyone did visual in the first class and audio in the second, so a difference here "
                     "can also come from doing the task a second time.\n")
    for measure, question in (('effect', "Is the disambiguation effect different for audio than for visual? "
                                         "(the modality x condition x phase interaction)"),
                              ('control_gain', "Do the never-revealed fillers improve more for audio than for "
                                               "visual? (a general 'speech mode' vs an item-specific prior)")):
        if len(both) < 2:
            lines.append(f"{question}\n  Not enough participants with both modalities.\n")
            continue
        d = both[(measure, 'audio')] - both[(measure, 'visual')]
        results[('audio-visual', measure)] = r = one_sample(d, rng)
        lines.append(sentence(question + " [audio minus visual]", r,
                              verdicts=("Yes: larger for audio", "Yes: larger for visual")))

    flagged = table[table['flags'] != '']     # not table.flags: that is a pandas attribute
    lines.append("=== EXCLUSION FLAGS (flagged, not removed) ===\n")
    if flagged.empty:
        lines.append("  None.")
    for _, row in flagged.iterrows():
        lines.append(f"  {row.participant_id} {row.modality}: {row['flags']} "
                     f"(pre 'yes' rate {100 * row.pre_yes_rate:.0f}%, median RT {row.median_rt_ms:.0f} ms)")
    lines.append("  response_bias = answered 'yes' on more than 90% or fewer than 5% of pre trials; "
                 "too_fast = median RT under 200 ms.")
    return results, "\n".join(lines) + "\n"


def mixed_model(sessions, out: Path) -> str:
    """Optional logistic mixed model; beyond what we covered in class."""
    try:
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    except ImportError:
        return "statsmodels is not installed, so the optional mixed model was skipped."
    d = pd.concat([answered(s) for s in sessions])
    d = d[d.condition.isin(['target', 'filler_new'])].copy()
    d['item'] = d.modality + '_' + d.stimulus_file
    d['recognized'] = d.recognized.astype(float)
    model = BinomialBayesMixedGLM.from_formula(
        "recognized ~ C(trial_type, Treatment('pre')) * C(condition, Treatment('filler_new')) * modality",
        {'participant': '0 + C(participant_id)', 'item': '0 + C(item)'}, d)
    fit = model.fit_vb()
    text = ("OPTIONAL - beyond what we covered in class.\n"
            "Logistic mixed model: recognized ~ phase * condition * modality + (1 | participant) + (1 | item),\n"
            "fitted by variational Bayes (statsmodels BinomialBayesMixedGLM). Coefficients are log-odds.\n"
            "The three-way term tests whether the disambiguation effect differs between modalities.\n\n"
            + str(fit.summary()))
    (out / 'mixed_model.txt').write_text(text)
    return "Optional mixed model written to mixed_model.txt."


# ---------------------------------------------------------------- figures
def mean_ci(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return (x.mean() if len(x) else np.nan), 0.0
    return x.mean(), stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def fig_class_modality(table, path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True, facecolor=SURFACE)
    for ax, mod in zip(axes, ('visual', 'audio')):
        style(ax)
        t = table[table.modality == mod]
        post_means = []
        for k, c in enumerate(CONDITIONS):
            x = np.array([0, 1]) + (k - 1) * 0.07
            for _, row in t.iterrows():
                ax.plot(x, [row[f'{c}_pre'], row[f'{c}_post']], color=COLORS[c], lw=0.8, alpha=0.18)
            m = [mean_ci(t[f'{c}_{ph}']) for ph in ('pre', 'post')]
            ax.errorbar(x, [v for v, _ in m], yerr=[h for _, h in m], color=COLORS[c], lw=2, marker='o', ms=8,
                        capsize=0, markeredgecolor=SURFACE, markeredgewidth=2, label=LABELS[c], zorder=3)
            post_means.append(m[1][0])
        end_labels(ax, 1.16, post_means, [COLORS[c] for c in CONDITIONS])
        ax.set_xticks([0, 1], ['pre', 'post'], color=INK)
        ax.set_xlim(-0.3, 1.35)
        ax.set_ylim(-0.03, 1.06)
        ax.set_title(f"{mod.capitalize()} (n = {len(t)})", color=INK, loc='left', fontsize=11)
    axes[0].set_ylabel('proportion answered "yes"\n(mean ± 95% CI; faint lines = participants)', color=INK2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, loc='lower center', ncol=3, labelcolor=INK2)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_effects(table, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), facecolor=SURFACE)
    wide = table.pivot(index='participant_id', columns='modality', values=['effect', 'control_gain'])
    for ax, (measure, title) in zip(axes, (('effect', 'Disambiguation effect\n(target gain − filler_new gain)'),
                                          ('control_gain', 'Control gain\n(filler_new post − pre)'))):
        style(ax)
        ax.axhline(0, color=MUTED, lw=1)
        mods = [m for m in ('visual', 'audio') if (measure, m) in wide.columns]
        for _, row in wide[measure].iterrows():
            vals = [row.get(m, np.nan) for m in mods]
            ax.plot(range(len(mods)), vals, color=MUTED, lw=0.8, alpha=0.5, marker='o', ms=4)
        for i, m in enumerate(mods):
            v, h = mean_ci(wide[(measure, m)])
            ax.errorbar(i + 0.12, v, yerr=h, color=INK, lw=2, marker='D', ms=7, capsize=0, zorder=3)
            ax.text(i + 0.2, v, f"{100 * v:+.0f} pp", color=INK, fontsize=9, va='center')
        ax.set_xticks(range(len(mods)), mods, color=INK)
        ax.set_xlim(-0.4, len(mods) - 0.4)
        ax.set_title(title, color=INK, loc='left', fontsize=10.5)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{100 * y:+.0f}"))
    axes[0].set_ylabel('percentage points\n(grey = one participant; black = mean ± 95% CI)', color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_items(sessions, path):
    d = pd.concat([answered(s) for s in sessions])
    d = d[d.condition.isin(['target', 'filler_new'])]
    p = d.groupby(['modality', 'stimulus_file', 'condition', 'trial_type']).recognized.mean().unstack('trial_type')
    gain = (p['post'] - p['pre']).rename('gain').reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True, facecolor=SURFACE)
    for ax, mod in zip(axes, ('visual', 'audio')):
        style(ax)
        ax.axhline(0, color=MUTED, lw=1)
        g = gain[gain.modality == mod]
        items = sorted(g.stimulus_file.unique())
        for k, c in enumerate(('target', 'filler_new')):
            gc = g[g.condition == c].set_index('stimulus_file').reindex(items)
            ax.scatter(np.arange(len(items)) + (k - 0.5) * 0.25, gc.gain, s=36, color=COLORS[c],
                       edgecolor=SURFACE, lw=1.5, label=c, zorder=3)
        ax.set_xticks(range(len(items)), items, rotation=45, color=INK, fontsize=8.5)
        ax.set_title(mod.capitalize(), color=INK, loc='left', fontsize=11)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{100 * y:+.0f}"))
    axes[0].set_ylabel('post − pre, percentage points\n(pooled over participants)', color=INK2)
    axes[0].legend(frameon=False, fontsize=9, labelcolor=INK2)
    fig.suptitle("Per-item gain: a target that does not improve may be a bad stimulus", color=INK2,
                 fontsize=10, x=0.01, ha='left')
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- main
def analyze(folder, out, seed=0, quiet=False):
    folder, out = Path(folder), Path(out)
    sessions, skipped = collect(folder)
    if not sessions:
        raise SystemExit(f"No complete session files found in {folder}")
    out.mkdir(parents=True, exist_ok=True)
    table = participant_table(sessions)
    table.to_csv(out / 'participants.csv', index=False)
    results, text = run_stats(table, np.random.default_rng(seed))
    header = f"Class analysis of {folder}\n{len(sessions)} complete sessions used.\n"
    if skipped:
        header += "Skipped files:\n" + "".join(f"  {f}: {why}\n" for f, why in skipped)
    text = header + "\n" + text
    (out / 'stats.txt').write_text(text)
    fig_class_modality(table, out / 'fig_class_modality.png')
    fig_effects(table, out / 'fig_effects.png')
    fig_items(sessions, out / 'fig_items.png')
    if not quiet:
        print(text)
        print(mixed_model(sessions, out))
        print(f"Results in {out}")
    return table, results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', nargs='?', help="folder of session files (default with --download: class_data/)")
    ap.add_argument('--download', action='store_true',
                    help="first fetch everyone's latest data from GitHub into the folder")
    ap.add_argument('--out', default=str(ROOT / 'results' / 'class'))
    args = ap.parse_args()
    if args.download:
        sys.path.insert(0, str(ROOT))
        import class_repo
        folder = class_repo.download_class_data(Path(args.folder or ROOT / class_repo.CLASS_DATA))
        print(f"Downloaded the latest class data into {folder}\n")
        args.folder = folder
    elif not args.folder:
        ap.error("give a folder, or --download")
    analyze(args.folder, args.out)


if __name__ == '__main__':
    main()
