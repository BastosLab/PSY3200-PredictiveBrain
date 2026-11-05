#!/usr/bin/env python3
"""
White Christmas in Noise: how often people report internally generated experiences.

Participants sat in white noise for about 15 minutes and called out every sound, image or
bodily feeling they noticed. The experimenter logged each one as Auditory (code 1),
Visual (code 2) or Bodily (code 3). This script counts those events, turns them into
events per minute, and compares the 2025 and 2026 classes.

    python white_noise/analyze_white_noise.py              # figure + summary table
    python white_noise/analyze_white_noise.py --out my.png

sessions.csv lists every participant. 2025 rows hold Ishan's counts (there are no
raw 2025 files). 2026 rows point to a spreadsheet in spreadsheets/2026/; the counts are
read from it. Session durations are estimates.

Based on Ishan Mahajan's white_christmas_visualization.py (2026-10-13).
"""
import argparse
import csv
import datetime as dt
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SHEETS = HERE / 'spreadsheets'
CATEGORIES = {1: 'Auditory', 2: 'Visual', 3: 'Bodily'}
COLORS = {'Auditory': '#2a78d6', 'Visual': '#eb6834', 'Bodily': '#1baf7a'}


def clock_minutes(value):
    """A logged time as minutes on a 12-hour clock. Students typed 5:14:30, 17:14:30, '5:14:30PM' and '5.14.30'."""
    if isinstance(value, dt.datetime):
        value = value.time()
    if isinstance(value, dt.time):
        return (value.hour % 12) * 60 + value.minute + value.second / 60
    if isinstance(value, str):
        s = value.strip().upper().replace('PM', '').replace('AM', '').replace('.', ':')
        if not s[:1].isdigit():
            return None
        parts = [int(p) for p in s.split(':')]
        return (parts[0] % 12) * 60 + parts[1] + (parts[2] if len(parts) > 2 else 0) / 60
    return None


def read_spreadsheet(path, block=0):
    """Count events per category in one Time / Type / Code block of a student spreadsheet.

    The code column decides the category (the Type column is often left blank).
    Returns ({category: count}, [event times in minutes]).
    """
    import openpyxl
    sheet = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    starts = [i for i, h in enumerate(rows[0]) if isinstance(h, str) and h.strip() == 'Time']
    col = starts[block]
    counts, times = {c: 0 for c in CATEGORIES.values()}, []
    for row in rows[1:]:
        t = clock_minutes(row[col])
        code = row[col + 2] if col + 2 < len(row) else None
        if t is None or not isinstance(code, (int, float)) or int(code) not in CATEGORIES:
            continue
        counts[CATEGORIES[int(code)]] += 1
        times.append(t)
    return counts, times


def load_sessions(sessions_csv=HERE / 'sessions.csv'):
    sessions = []
    for row in csv.DictReader(open(sessions_csv, newline='')):
        if row['file']:
            counts, _ = read_spreadsheet(SHEETS / row['year'] / row['file'], int(row['block'] or 0))
        else:
            counts = {c: int(row[c.lower()]) for c in CATEGORIES.values()}
        duration = float(row['duration_min'])
        sessions.append(dict(year=row['year'], participant=row['participant'], duration=duration, counts=counts,
                             rates={c: n / duration for c, n in counts.items()},
                             white_christmas=row['white_christmas'], note=row['note']))
    return sessions


def summarise(sessions):
    """Mean, SD and SE of events per minute, per year and category."""
    out = {}
    for year in sorted({s['year'] for s in sessions}):
        group = [s for s in sessions if s['year'] == year]
        for c in list(CATEGORIES.values()) + ['Total']:
            r = np.array([sum(s['rates'].values()) if c == 'Total' else s['rates'][c] for s in group])
            sd = float(np.std(r, ddof=1))
            out[year, c] = dict(n=len(r), mean=float(r.mean()), sd=sd, se=sd / np.sqrt(len(r)), values=r)
    return out


def plot(sessions, summary, out_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#9AA0A6', 'axes.labelcolor': '#3C4043',
                         'xtick.color': '#3C4043', 'ytick.color': '#3C4043'})
    years = sorted({s['year'] for s in sessions})
    cats = list(CATEGORIES.values())
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw=dict(width_ratios=[1, 1.35], wspace=0.25))

    # left: each category, each year; dots are people, black bar is the mean +- 1 SE
    rng = np.random.default_rng(0)
    ticks, labels = [], []
    for k, c in enumerate(cats):
        for j, year in enumerate(years):
            x = k * 3 + j
            st = summary[year, c]
            filled = j == len(years) - 1
            ax1.scatter(x + rng.uniform(-0.18, 0.18, st['n']), st['values'], s=46, zorder=3,
                        color=COLORS[c] if filled else 'white', edgecolor=COLORS[c], linewidth=1.8)
            ax1.errorbar(x, st['mean'], yerr=st['se'], color='#1F1F1F', lw=2, capsize=6, zorder=4)
            ax1.plot([x - 0.3, x + 0.3], [st['mean']] * 2, color='#1F1F1F', lw=2.5, zorder=4)
            ticks.append(x)
            labels.append(f"{year}\nn = {st['n']}")
        ax1.text(k * 3 + 0.5, -0.16, c, ha='center', va='top', fontweight='bold', color='#1F1F1F',
                 transform=ax1.get_xaxis_transform())
    ax1.set_xticks(ticks, labels, fontsize=9.5)
    ax1.set_xlim(-0.7, len(cats) * 3 - 1.3)
    ax1.set_ylabel('Events per minute')
    ax1.set_title('Each category, by class\n(dots = people, black = mean ± 1 SE)', loc='left', fontsize=12)
    ax1.grid(axis='y', color='#E8EAED', lw=0.8)
    ax1.set_axisbelow(True)

    # right: every person's total, split by category, sorted within year
    x0, xt, xl = 0, [], []
    for year in years:
        group = sorted([s for s in sessions if s['year'] == year], key=lambda s: sum(s['rates'].values()))
        for s in group:
            bottom = 0
            for c in cats:
                v = s['rates'][c]
                ax2.bar(x0, v, bottom=bottom, width=0.78, color=COLORS[c], edgecolor='white', linewidth=1.5)
                bottom += v
            if s['white_christmas'].lower().startswith('yes'):
                ax2.annotate('heard\n"White Christmas"', (x0, bottom), xytext=(0, 18), textcoords='offset points',
                             ha='center', fontsize=9, color='#1F1F1F',
                             arrowprops=dict(arrowstyle='->', color='#5F6368'))
            xt.append(x0)
            xl.append(s['participant'])
            x0 += 1
        mean_total = summary[year, 'Total']['mean']
        ax2.text((x0 - len(group) + x0 - 1) / 2, -0.09, f'{year} class', ha='center', va='top', fontweight='bold',
                 transform=ax2.get_xaxis_transform())
        ax2.plot([x0 - len(group) - 0.4, x0 - 0.6], [mean_total] * 2, color='#1F1F1F', ls='--', lw=1.4)
        ax2.text(x0 - len(group) - 0.4, mean_total, f'mean {mean_total:.2f}', va='bottom', fontsize=9,
                 color='#3C4043')
        x0 += 1
    ax2.set_xticks(xt, xl, fontsize=9.5)
    ax2.set_ylabel('Events per minute (all categories)')
    ax2.set_title('Each person, sorted within class\n(some people report far more of everything)', loc='left', fontsize=12)
    ax2.legend(handles=[Patch(color=COLORS[c], label=c) for c in reversed(cats)], frameon=False, loc='upper left')
    ax2.grid(axis='y', color='#E8EAED', lw=0.8)
    ax2.set_axisbelow(True)
    ax2.set_ylim(0, ax2.get_ylim()[1] * 1.12)

    fig.suptitle('White Christmas in Noise: internally generated experiences', x=0.06, ha='left',
                 fontsize=14, fontweight='bold', y=1.0)
    fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(HERE / 'white_noise_results.png'))
    args = ap.parse_args()
    sessions = load_sessions()
    summary = summarise(sessions)
    print('Events per minute, mean ± SE (SD)')
    for (year, c), st in summary.items():
        print(f"  {year}  {c:9s} n={st['n']}  {st['mean']:.3f} ± {st['se']:.3f}  (SD {st['sd']:.3f})")
    heard = [f"{s['year']} {s['participant']}" for s in sessions if s['white_christmas'].lower().startswith('yes')]
    print('Reported hearing "White Christmas":', ', '.join(heard) or 'nobody')
    plot(sessions, summary, args.out)
    print('Figure saved to', args.out)


if __name__ == '__main__':
    main()
