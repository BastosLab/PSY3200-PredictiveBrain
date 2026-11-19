#!/usr/bin/env python3
"""
Class results app: everyone's Mooney task data in one window.

    python3 class-results-app/class_results_app.py              # open the app
    python3 class-results-app/class_results_app.py --save out/  # save the figures, no window

The app reads the class data in class_data/ (the folder download_class_data.py fills)
and has a button to download the latest copy from GitHub. For the visual or the audio
task it shows, for each condition, the share of "yes" answers (or the median reaction
time) before and after the reveal: one thin line per student and the class mean +/- SEM.
A second panel shows each student's disambiguation effect,
(target post - pre) - (non-target not yet revealed post - pre), with a one-sample t-test.

Which sessions count: each student's latest complete session (all 10 blocks). Shorter
sessions and earlier repeats are listed in the table with the reason they were left out.
"""
import argparse
import csv
import sys
import threading
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import class_repo  # noqa: E402

DATA_DIR = ROOT / class_repo.CLASS_DATA
FULL_BLOCKS = 10
TRIALS_PER_BLOCK = 49                      # 24 pre + 1 reveal + 24 post

CONDITIONS = ('target', 'filler_old', 'filler_new')
LABELS = {'target': 'Target',
          'filler_old': 'Non-target, revealed earlier',
          'filler_new': 'Non-target, not yet revealed'}
COLORS = {'target': '#eb6834', 'filler_new': '#2a78d6', 'filler_old': '#1baf7a'}
INK, INK2, MUTED, GRID = '#0b0b0b', '#52514e', '#8a8984', '#e4e3df'
MEASURES = {'yes': ('Yes answers (%)', 'yes'), 'rt': ('Median reaction time (ms)', 'rt')}


# ---------------------------------------------------------------- data

def read_session(path):
    """One session CSV -> dict with its name, participant, block count and trial rows."""
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    trials = [r for r in rows if r['trial_type'] in ('pre', 'post') and r['recognized'] in ('0', '1')]
    blocks_done = len({r['block'] for r in rows if r['trial_type'] == 'post'})
    complete = (rows and rows[0]['n_blocks'] == str(FULL_BLOCKS)
                and len(rows) == FULL_BLOCKS * TRIALS_PER_BLOCK)
    return {'file': Path(path).name,
            'participant': rows[0]['participant_id'] if rows else '?',
            'modality': rows[0]['modality'] if rows else '?',
            'start': rows[0]['timestamp'] if rows else '',
            'blocks': blocks_done, 'complete': bool(complete), 'trials': trials}


def choose_sessions(sessions):
    """Keep each participant's latest complete session; give a reason for every other one."""
    latest = {}
    for s in sessions:
        if s['complete'] and (s['participant'] not in latest
                              or s['start'] > latest[s['participant']]['start']):
            latest[s['participant']] = s
    for s in sessions:
        if not s['complete']:
            s['status'] = f"left out: {s['blocks']} of {FULL_BLOCKS} blocks"
        elif latest[s['participant']] is not s:
            s['status'] = 'left out: a later complete session exists'
        else:
            s['status'] = 'included'
    return sorted(latest.values(), key=lambda s: s['participant'].lower())


def load_modality(data_dir, modality):
    """All session files for one modality: (included sessions, every session with its status)."""
    files = sorted((Path(data_dir) / modality).glob('*.csv'))
    sessions = [read_session(p) for p in files]
    included = choose_sessions(sessions)
    return included, sorted(sessions, key=lambda s: (s['participant'].lower(), s['start']))


def summarize(session):
    """{(condition, phase): {'yes': % yes, 'rt': median RT in ms, 'n': trials}} for one session."""
    out = {}
    for c in CONDITIONS:
        for phase in ('pre', 'post'):
            rows = [r for r in session['trials'] if r['condition'] == c and r['trial_type'] == phase]
            if not rows:
                out[c, phase] = {'yes': np.nan, 'rt': np.nan, 'n': 0}
                continue
            rts = [float(r['reaction_time_ms']) for r in rows if r['reaction_time_ms'] not in ('', 'NA')]
            out[c, phase] = {'yes': 100 * np.mean([r['recognized'] == '1' for r in rows]),
                             'rt': float(np.median(rts)) if rts else np.nan, 'n': len(rows)}
    return out


def disambiguation(summary, measure):
    """(target post - pre) - (not-yet-revealed non-target post - pre)."""
    def change(c):
        return summary[c, 'post'][measure] - summary[c, 'pre'][measure]
    return change('target') - change('filler_new')


def class_stats(summaries, measure):
    """Paired t-test pre vs post for each condition, and a one-sample t-test on the effect."""
    tests = {}
    for c in CONDITIONS:
        pre = np.array([s[c, 'pre'][measure] for s in summaries])
        post = np.array([s[c, 'post'][measure] for s in summaries])
        ok = ~(np.isnan(pre) | np.isnan(post))
        if ok.sum() >= 2 and np.any(post[ok] != pre[ok]):
            t, p = stats.ttest_rel(post[ok], pre[ok])
        else:
            t, p = np.nan, np.nan
        tests[c] = {'n': int(ok.sum()), 't': t, 'p': p,
                    'pre': np.nanmean(pre), 'post': np.nanmean(post)}
    eff = np.array([disambiguation(s, measure) for s in summaries])
    eff = eff[~np.isnan(eff)]
    if len(eff) >= 2 and np.std(eff) > 0:
        t, p = stats.ttest_1samp(eff, 0)
    else:
        t, p = np.nan, np.nan
    tests['effect'] = {'n': len(eff), 't': t, 'p': p, 'mean': eff.mean() if len(eff) else np.nan,
                       'sem': stats.sem(eff) if len(eff) >= 2 else np.nan, 'values': eff}
    return tests


def sem(values):
    values = np.asarray(values, float)
    values = values[~np.isnan(values)]
    return stats.sem(values) if len(values) >= 2 else np.nan


def p_text(p):
    if np.isnan(p):
        return 'p = n/a'
    return 'p < .001' if p < .001 else f'p = {p:.3f}'.lstrip('0').replace('= 0.', '= .')


# ---------------------------------------------------------------- figure

def draw(fig, included, modality, measure):
    """Draw both panels for one modality and measure into a matplotlib figure."""
    fig.clear()
    ylabel = MEASURES[measure][0]
    ax1, ax2 = fig.subplots(1, 2, gridspec_kw={'width_ratios': [3, 1.3]})
    summaries = [summarize(s) for s in included]
    n = len(summaries)
    title = f"{modality.capitalize()} task, {n} student{'s' if n != 1 else ''}"
    if n == 0:
        fig.text(.5, .5, f"No complete {modality} sessions in the class data yet.\n"
                         "Click 'Download latest data' to get them.",
                 ha='center', va='center', color=INK2, fontsize=12)
        ax1.set_visible(False), ax2.set_visible(False)
        return None
    tests = class_stats(summaries, measure)

    # Panel 1: pre vs post, each condition side by side
    offsets = {'target': -0.25, 'filler_old': 0.0, 'filler_new': 0.25}
    for c in CONDITIONS:
        x = np.array([0, 1]) + offsets[c] * 0.4
        for s in summaries:
            ax1.plot(x, [s[c, 'pre'][measure], s[c, 'post'][measure]],
                     color=COLORS[c], alpha=.25, lw=1, zorder=1)
        means = [np.nanmean([s[c, ph][measure] for s in summaries]) for ph in ('pre', 'post')]
        errs = [sem([s[c, ph][measure] for s in summaries]) for ph in ('pre', 'post')]
        t = tests[c]
        ax1.errorbar(x, means, yerr=errs, color=COLORS[c], lw=2.5, marker='o', ms=8,
                     mec='white', mew=1.5, capsize=4, zorder=3,
                     label=f"{LABELS[c]} (n={t['n']}, paired t {p_text(t['p'])})")
    ax1.set_xticks([0, 1], ['Before reveal', 'After reveal'])
    ax1.set_xlim(-.35, 1.35)
    ax1.set_ylabel(ylabel)
    if measure == 'yes':
        ax1.set_ylim(-3, 103)
    ax1.set_title(f"{title}: before vs after the reveal", loc='left', color=INK, fontsize=11)
    ax1.legend(loc='upper center', bbox_to_anchor=(.5, -.09), frameon=False, fontsize=8.5)

    # Panel 2: disambiguation effect per student
    e = tests['effect']
    rng = np.random.default_rng(0)
    ax2.axhline(0, color=MUTED, lw=1, ls='--', zorder=0)
    ax2.scatter(rng.uniform(-.12, .12, len(e['values'])), e['values'], s=36,
                color=COLORS['target'], alpha=.55, edgecolor='white', lw=1, zorder=2)
    ax2.errorbar([0], [e['mean']], yerr=[e['sem']], color=INK, marker='D', ms=8,
                 capsize=5, lw=2, zorder=3)
    ax2.set_xticks([0], ['Each student'])
    ax2.set_xlim(-.5, .5)
    unit = 'percentage points' if measure == 'yes' else 'ms'
    ax2.set_ylabel(f"Disambiguation effect ({unit})")
    ax2.set_title("Disambiguation effect", loc='left', color=INK, fontsize=11)
    ax2.text(.5, -.09, f"mean {e['mean']:.1f} ± {e['sem']:.1f} SEM\n"
                       f"one-sample t({e['n'] - 1}) = {e['t']:.2f}, {p_text(e['p'])}",
             transform=ax2.transAxes, ha='center', va='top', fontsize=8.5, color=INK2)

    for ax in (ax1, ax2):
        ax.spines[['top', 'right']].set_visible(False)
        ax.spines[['left', 'bottom']].set_color(MUTED)
        ax.tick_params(colors=INK2)
        ax.yaxis.grid(True, color=GRID, lw=.8)
        ax.set_axisbelow(True)
    fig.text(.01, .01, "Thin lines and dots: one student each (latest complete session). "
                       "Thick lines and diamond: class mean ± SEM across students. "
                       "Effect = (target after − before) − (non-target not yet revealed after − before).",
             fontsize=7.5, color=MUTED, wrap=True)
    fig.subplots_adjust(left=.07, right=.98, top=.92, bottom=.24, wspace=.3)
    return tests


def save_all(data_dir, out_dir):
    """Save the four figures (visual/audio x yes/RT) without opening a window."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for modality in ('visual', 'audio'):
        included, everyone = load_modality(data_dir, modality)
        print(f"{modality}: {len(included)} students included")
        for s in everyone:
            print(f"   {s['status']:<45} {s['file']}")
        for measure in MEASURES:
            fig = plt.figure(figsize=(11, 6.2))
            draw(fig, included, modality, measure)
            path = out_dir / f"class_{modality}_{measure}.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            print(f"   saved {path}")


# ---------------------------------------------------------------- window

class ClassResultsApp:
    """The window: controls on top, the figure in the middle, the session table below."""

    def __init__(self, data_dir):
        import tkinter as tk
        from tkinter import ttk
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.tk, self.data_dir = tk, Path(data_dir)
        self.root = tk.Tk()
        self.root.title('PSY 3200 class results')
        self.root.geometry('1150x860')

        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill='x')
        self.modality = tk.StringVar(value='visual')
        self.measure = tk.StringVar(value='yes')
        ttk.Label(bar, text='Task:').pack(side='left')
        for m in ('visual', 'audio'):
            ttk.Radiobutton(bar, text=m.capitalize(), value=m, variable=self.modality,
                            command=self.refresh).pack(side='left', padx=4)
        ttk.Label(bar, text='   Show:').pack(side='left')
        for key, (label, _) in MEASURES.items():
            ttk.Radiobutton(bar, text=label, value=key, variable=self.measure,
                            command=self.refresh).pack(side='left', padx=4)
        ttk.Button(bar, text='Save figure…', command=self.save).pack(side='right', padx=4)
        self.download_button = ttk.Button(bar, text='Download latest data', command=self.download)
        self.download_button.pack(side='right', padx=4)
        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, padding=(10, 0), foreground=INK2).pack(fill='x')

        self.fig = Figure(figsize=(11, 6), dpi=100, facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        cols = ('participant', 'status', 'blocks', 'file')
        self.table = ttk.Treeview(self.root, columns=cols, show='headings', height=8)
        for c, w in zip(cols, (150, 300, 60, 560)):
            self.table.heading(c, text=c.capitalize())
            self.table.column(c, width=w, anchor='w')
        self.table.pack(fill='x', padx=8, pady=8)
        self.refresh()

    def refresh(self):
        modality, measure = self.modality.get(), self.measure.get()
        included, everyone = load_modality(self.data_dir, modality)
        draw(self.fig, included, modality, measure)
        self.canvas.draw()
        self.table.delete(*self.table.get_children())
        for s in everyone:
            self.table.insert('', 'end', values=(s['participant'], s['status'], s['blocks'], s['file']))
        if not (self.data_dir / modality).exists():
            self.status.set(f"No class data in {self.data_dir} yet. Click 'Download latest data'.")
        else:
            self.status.set(f"{len(included)} students included, {len(everyone) - len(included)} "
                            f"sessions left out ({modality}). Data folder: {self.data_dir}")

    def download(self):
        self.download_button.state(['disabled'])
        self.status.set('Downloading the class data from GitHub…')

        def work():
            try:
                class_repo.download_class_data(self.data_dir)
                msg = None
            except class_repo.UploadError as e:
                msg = f"Download failed: {e}"
            self.root.after(0, lambda: self.downloaded(msg))
        threading.Thread(target=work, daemon=True).start()

    def downloaded(self, error):
        self.download_button.state(['!disabled'])
        self.refresh()
        if error:
            self.status.set(error)

    def save(self):
        from tkinter import filedialog
        name = f"class_{self.modality.get()}_{self.measure.get()}.png"
        path = filedialog.asksaveasfilename(initialfile=name, defaultextension='.png',
                                            filetypes=[('PNG image', '*.png')])
        if path:
            self.fig.savefig(path, dpi=150)
            self.status.set(f"Saved {path}")

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DATA_DIR), help='class data folder (default: class_data/)')
    ap.add_argument('--save', metavar='FOLDER', help='save the figures to FOLDER instead of opening the app')
    args = ap.parse_args()
    if args.save:
        save_all(args.data, args.save)
    else:
        ClassResultsApp(args.data).run()


if __name__ == '__main__':
    main()
