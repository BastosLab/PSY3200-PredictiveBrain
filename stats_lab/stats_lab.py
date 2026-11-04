#!/usr/bin/env python3
"""
Stats lab: simulate studies to see what the mean, SD, standard error, 95% confidence
interval, t and p actually do. Every run draws made-up reaction times (ms) from a
"true" population you choose, so you can compare what a study finds with the truth.

    python3 stats_lab/stats_lab.py sample                # one study: mean, SD, SE, 95% CI
    python3 stats_lab/stats_lab.py repeat                # repeat a study 10,000 times: why SE = SD / sqrt(n)
    python3 stats_lab/stats_lab.py coverage              # how often does a 95% CI contain the true mean?
    python3 stats_lab/stats_lab.py two                   # two groups: difference, its CI, t and p
    python3 stats_lab/stats_lab.py many --diff 0         # 1,000 studies with NO true difference: how often p < .05?

Options (all commands): --n (people per group, default 20), --mean (true mean, 300 ms),
--sd (true SD, 45 ms), --seed (repeat a run exactly; otherwise each run is new).
two and many also take --diff (true difference between the groups, default 40 ms; 0 = none).

Each command prints its numbers and saves a figure in stats_lab/figures/.
Pair it with STATS_PRIMER.pdf in this folder.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import stats

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:                       # numbers still work without matplotlib
    plt = None

FIG_DIR = Path(__file__).resolve().parent / 'figures'
INK, GRAY, NAVY = '#1F1F1F', '#5F6368', '#1F3A68'
GROUP_A, GROUP_B, RED, NULL_GRAY = '#2A78D6', '#EB6834', '#E53A35', '#7F93B2'


# ---------------------------------------------------------------- the formulas
def describe(x):
    """Mean, SD, SE and 95% CI of one sample, written out the way the primer does it."""
    n = len(x)
    mean = sum(x) / n
    sd = (sum((v - mean) ** 2 for v in x) / (n - 1)) ** 0.5      # n - 1: see the primer
    se = sd / n ** 0.5
    t_crit = stats.t.ppf(0.975, n - 1)                           # about 2 (2.09 for n = 20)
    return dict(n=n, mean=mean, sd=sd, se=se, t_crit=t_crit, lo=mean - t_crit * se, hi=mean + t_crit * se)


def compare(a, b):
    """Difference between two independent groups (b minus a), its SE, 95% CI, t, df and p (Welch's t-test)."""
    da, db = describe(a), describe(b)
    diff = db['mean'] - da['mean']
    se_diff = (da['se'] ** 2 + db['se'] ** 2) ** 0.5
    df = se_diff ** 4 / (da['se'] ** 4 / (da['n'] - 1) + db['se'] ** 4 / (db['n'] - 1))
    t = diff / se_diff
    p = 2 * stats.t.sf(abs(t), df)
    t_crit = stats.t.ppf(0.975, df)
    return dict(a=da, b=db, diff=diff, se_diff=se_diff, df=df, t=t, p=p, t_crit=t_crit,
                lo=diff - t_crit * se_diff, hi=diff + t_crit * se_diff)


# ---------------------------------------------------------------- helpers
def rng_for(args):
    seed = args.seed if args.seed is not None else int(np.random.default_rng().integers(1, 100000))
    print(f"(seed {seed}: add --seed {seed} to repeat this exact run)\n")
    return np.random.default_rng(seed)


def draw(rng, n, mean, sd):
    return np.round(rng.normal(mean, sd, n))


def ms(v):
    return f"{v:.1f} ms"


def save(fig, name):
    FIG_DIR.mkdir(exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"\nFigure: {path}")


def axes(figsize, rows=1):
    fig, ax = plt.subplots(rows, 1, figsize=figsize, squeeze=False)
    for a in ax[:, 0]:
        for side in ('top', 'right', 'left'):
            a.spines[side].set_visible(False)
        a.set_yticks([])
    return fig, ax[:, 0]


def dots(ax, x, y, color, seed=0):
    jitter = np.random.default_rng(seed).uniform(-0.15, 0.15, len(x))
    ax.scatter(x, y + jitter, s=45, color=color, alpha=0.75, edgecolor='white', linewidth=1, zorder=3)


# ---------------------------------------------------------------- commands
def cmd_sample(args):
    rng = rng_for(args)
    x = draw(rng, args.n, args.mean, args.sd)
    d = describe(x)
    print(f"One study: {args.n} people, drawn from a population whose true mean is {args.mean:g} ms "
          f"and true SD is {args.sd:g} ms.\n")
    print(f"  Data (sorted): {', '.join(f'{v:.0f}' for v in sorted(x))}\n")
    print(f"  Mean                   {ms(d['mean']):>10}   where the data sit")
    print(f"  Standard deviation     {ms(d['sd']):>10}   how spread out the people are")
    print(f"  Standard error         {ms(d['se']):>10}   SD / sqrt(n) = {d['sd']:.1f} / sqrt({args.n}): "
          "how much the mean would wobble across repeats of the study")
    print(f"  95% CI                 [{d['lo']:.1f}, {d['hi']:.1f}] ms   mean +/- {d['t_crit']:.2f} x SE")
    inside = int(np.sum(np.abs(x - d['mean']) <= d['sd']))
    print(f"\n  {inside} of {args.n} people are within 1 SD of the mean.")
    hit = d['lo'] <= args.mean <= d['hi']
    print(f"  The true mean ({args.mean:g}) is {'inside' if hit else 'OUTSIDE'} this study's 95% CI.")
    if plt is None:
        return
    fig, (ax,) = axes((8, 3.0))
    ax.axvspan(d['mean'] - d['sd'], d['mean'] + d['sd'], color=NAVY, alpha=0.08, lw=0, label='mean ± 1 SD')
    dots(ax, x, np.zeros(args.n), NAVY)
    ax.axvline(d['mean'], color=INK, lw=2, label='study mean')
    ax.plot([d['lo'], d['hi']], [0.55, 0.55], color=INK, lw=5, solid_capstyle='butt', label='95% CI of the mean')
    ax.axvline(args.mean, color=RED, lw=1.5, ls='--', label='true mean')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), frameon=False)
    ax.set(ylim=(-0.5, 1.0), xlabel='Reaction time (ms)',
           title=f"One study (n = {args.n}): mean {d['mean']:.0f}, SD {d['sd']:.0f}, SE {d['se']:.1f} ms")
    save(fig, 'sample.png')


def cmd_repeat(args):
    rng = rng_for(args)
    reps = args.reps
    data = rng.normal(args.mean, args.sd, (reps, args.n))
    means = data.mean(axis=1)
    print(f"The same study ({args.n} people) repeated {reps:,} times, with a true SD of {args.sd:g} ms.\n")
    print(f"  Spread of individual people (SD):        {ms(data[:, 0].std(ddof=1)):>9}")
    print(f"  Spread of the {reps:,} study means:       {ms(means.std(ddof=1)):>9}   <- the standard error")
    print(f"  Formula: SD / sqrt(n) = {args.sd:g} / sqrt({args.n}) = {ms(args.sd / args.n ** 0.5):>9}")
    print("\n  Try a bigger study (--n 80): the means bunch up twice as tightly, because sqrt(80/20) = 2.")
    if plt is None:
        return
    fig, (a1, a2) = axes((8, 4.6), rows=2)
    lo, hi = args.mean - 3.5 * args.sd, args.mean + 3.5 * args.sd
    bins = np.linspace(lo, hi, 70)
    a1.hist(data[:, 0], bins=bins, color=NULL_GRAY, edgecolor='white', linewidth=0.5)
    a1.set_title(f"Individual people: spread = SD (about {args.sd:g} ms)", loc='left')
    a2.hist(means, bins=bins, color=NAVY, edgecolor='white', linewidth=0.5)
    a2.set_title(f"Means of {reps:,} repeats of the study (n = {args.n}): spread = SE "
                 f"(about {args.sd / args.n ** 0.5:.0f} ms)", loc='left')
    for a in (a1, a2):
        a.set_xlim(lo, hi)
    a2.set_xlabel('Reaction time (ms)')
    fig.subplots_adjust(hspace=0.5)
    save(fig, 'repeat.png')


def cmd_coverage(args):
    rng = rng_for(args)
    rows = [describe(draw(rng, args.n, args.mean, args.sd)) for _ in range(args.studies)]
    hits = sum(r['lo'] <= args.mean <= r['hi'] for r in rows)
    print(f"{args.studies} separate studies, each with {args.n} people. Each computes its own 95% CI.\n")
    print(f"  {hits} of {args.studies} CIs contain the true mean ({100 * hits / args.studies:.0f}%).")
    print("  Over many studies this settles near 95%: that is what '95% confidence' means.")
    print("  Any single CI either contains the truth or it does not; you just do not know which.")
    if plt is None:
        return
    show = rows[:min(50, len(rows))]
    fig, (ax,) = axes((7, max(3.5, 0.16 * len(show) + 1)))
    for k, r in enumerate(show):
        c = NAVY if r['lo'] <= args.mean <= r['hi'] else RED
        ax.plot([r['lo'], r['hi']], [k, k], color=c, lw=2.2, solid_capstyle='round')
        ax.scatter([r['mean']], [k], color=c, s=14, zorder=3)
    ax.axvline(args.mean, color=INK, lw=1.5, ls='--')
    ax.text(args.mean, len(show) - 0.2, 'true mean', ha='center', va='bottom', color=INK)
    shown_hits = sum(r['lo'] <= args.mean <= r['hi'] for r in show)
    ax.set(xlabel='Reaction time (ms)', ylim=(-1, len(show) + 1.5),
           title=f"{len(show)} studies' 95% CIs: {len(show) - shown_hits} miss the true mean (red)")
    save(fig, 'coverage.png')


def cmd_two(args):
    rng = rng_for(args)
    a = draw(rng, args.n, args.mean, args.sd)
    b = draw(rng, args.n, args.mean + args.diff, args.sd)
    r = compare(a, b)
    print(f"Two groups of {args.n} people. True means: group A {args.mean:g} ms, group B "
          f"{args.mean + args.diff:g} ms (true difference {args.diff:g} ms), true SD {args.sd:g} ms.\n")
    for name, d in (('Group A', r['a']), ('Group B', r['b'])):
        print(f"  {name}: mean {d['mean']:.1f}, SD {d['sd']:.1f}, SE {d['se']:.1f}, "
              f"95% CI [{d['lo']:.1f}, {d['hi']:.1f}] ms")
    print(f"\n  Difference (B - A):     {ms(r['diff'])}")
    print(f"  SE of the difference:   sqrt(SE_A^2 + SE_B^2) = {ms(r['se_diff'])}")
    print(f"  95% CI of difference:   [{r['lo']:.1f}, {r['hi']:.1f}] ms")
    print(f"\n  Null hypothesis H0: the true difference is 0.")
    print(f"  t = difference / SE = {r['diff']:.1f} / {r['se_diff']:.1f} = {r['t']:.2f}   (df = {r['df']:.1f})")
    print(f"  p = {r['p']:.4f}: if H0 were true, a difference at least this big (either direction) would "
          f"turn up in {100 * r['p']:.1f}% of studies.")
    verdict = 'below' if r['p'] < 0.05 else 'not below'
    zero = 'excludes' if not (r['lo'] <= 0 <= r['hi']) else 'includes'
    print(f"  p is {verdict} .05, and the 95% CI of the difference {zero} 0. These always agree.")
    overlap = r['a']['hi'] > r['b']['lo'] and r['b']['hi'] > r['a']['lo']
    if overlap and r['p'] < 0.05:
        print("  Note: the two groups' own CIs overlap, yet the difference is significant. "
              "Judge a difference by the CI of the difference, not by whether the group CIs overlap.")
    if plt is None:
        return
    fig, (a1, a2) = axes((8, 5.2), rows=2)
    for y, x, d, c in ((1, a, r['a'], GROUP_A), (0, b, r['b'], GROUP_B)):
        dots(a1, x, np.full(args.n, y), c, seed=y + 1)
        a1.plot([d['lo'], d['hi']], [y + 0.35, y + 0.35], color=INK, lw=3, solid_capstyle='butt')
        a1.scatter([d['mean']], [y + 0.35], color=INK, s=40, zorder=4)
    a1.set_yticks([0, 1], ['Group B', 'Group A'])
    a1.tick_params(axis='y', length=0)
    a1.set(ylim=(-0.5, 1.7), xlabel='Reaction time (ms)', title='Each group with its mean and 95% CI')
    a2.axvline(0, color=RED, lw=1.8, ls='--')
    a2.text(0, 0.55, '  0 = no difference', color=RED, va='center')
    a2.plot([r['lo'], r['hi']], [0, 0], color=INK, lw=4, solid_capstyle='butt')
    a2.scatter([r['diff']], [0], color=INK, s=50, zorder=3)
    span = max(abs(r['lo']), abs(r['hi'])) * 1.3 + 5
    a2.set(xlim=(min(-10, r['lo'] - 10), span), ylim=(-1, 1), xlabel='Difference, B minus A (ms)',
           title=f"Difference {r['diff']:.0f} ms, 95% CI [{r['lo']:.0f}, {r['hi']:.0f}]; "
                 f"t = {r['t']:.2f}, p = {r['p']:.3f}")
    fig.subplots_adjust(hspace=0.75)
    save(fig, 'two.png')


def cmd_many(args):
    rng = rng_for(args)
    ps, ts = [], []
    for _ in range(args.studies):
        r = compare(draw(rng, args.n, args.mean, args.sd), draw(rng, args.n, args.mean + args.diff, args.sd))
        ps.append(r['p'])
        ts.append(r['t'])
    ps, ts = np.array(ps), np.array(ts)
    sig = int(np.sum(ps < 0.05))
    print(f"{args.studies:,} two-group studies, {args.n} people per group, true difference {args.diff:g} ms "
          f"(true SD {args.sd:g}).\n")
    print(f"  p < .05 in {sig} of {args.studies:,} studies ({100 * sig / args.studies:.1f}%).")
    if args.diff == 0:
        print("  There is no real difference here, so every one of those is a false positive.")
        print("  With alpha = .05 you expect about 5%: that is the risk you accept when you test.")
    else:
        print(f"  There IS a real difference, so this is the test's power: its chance of detecting {args.diff:g} ms "
              f"with {args.n} per group.")
        print("  Try a larger --n, or a smaller --diff, and see how power changes.")
    if plt is None:
        return
    fig, (a1, a2) = axes((8, 5.2), rows=2)
    a1.hist(ts, bins=60, density=True, color=NULL_GRAY, edgecolor='white', linewidth=0.5)
    if args.diff == 0:
        xs = np.linspace(-5, 5, 400)
        a1.plot(xs, stats.t.pdf(xs, 2 * args.n - 2), color=INK, lw=1.5)
    a1.set(xlim=(-6, max(6, ts.max() + 0.5)), xlabel='t',
           title=f"t from {args.studies:,} studies" + (" (black curve: the t distribution)" if args.diff == 0 else ""))
    bins = np.linspace(0, 1, 21)
    a2.hist(ps, bins=bins, color=NAVY, edgecolor='white', linewidth=0.5)
    a2.hist(ps[ps < 0.05], bins=bins, color=RED, edgecolor='white', linewidth=0.5)
    a2.set(xlim=(0, 1), xlabel='p', title=f"p from {args.studies:,} studies: {sig} below .05 (red)")
    fig.subplots_adjust(hspace=0.6)
    save(fig, f"many_diff{args.diff:g}.png")


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--n', type=int, default=20, help="people per group (default 20)")
    common.add_argument('--mean', type=float, default=300, help="true mean in ms (default 300)")
    common.add_argument('--sd', type=float, default=45, help="true SD in ms (default 45)")
    common.add_argument('--seed', type=int, help="repeat a run exactly")
    sub.add_parser('sample', parents=[common], help="one study: mean, SD, SE, 95%% CI")
    p = sub.add_parser('repeat', parents=[common], help="repeat a study many times: where SE comes from")
    p.add_argument('--reps', type=int, default=10000)
    p = sub.add_parser('coverage', parents=[common], help="how often 95%% CIs contain the true mean")
    p.add_argument('--studies', type=int, default=100)
    p = sub.add_parser('two', parents=[common], help="two groups: difference, CI, t, p")
    p.add_argument('--diff', type=float, default=40, help="true difference in ms (default 40)")
    p = sub.add_parser('many', parents=[common], help="many two-group studies: false positives or power")
    p.add_argument('--diff', type=float, default=0, help="true difference in ms (default 0: none)")
    p.add_argument('--studies', type=int, default=1000)
    args = ap.parse_args(argv)
    if args.n < 2:
        ap.error("--n must be at least 2")
    {'sample': cmd_sample, 'repeat': cmd_repeat, 'coverage': cmd_coverage, 'two': cmd_two,
     'many': cmd_many}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
