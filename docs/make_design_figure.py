#!/usr/bin/env python3
"""
Draw docs/task_design.png (one-page summary of the task) and print run-time estimates.

    python docs/make_design_figure.py

The example stimulus is spare image 16, which is NOT one of the 12 task images,
so showing this figure to students does not spoil any item.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from scipy.signal import spectrogram

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from make_stimuli import square_gray, two_tone  # noqa: E402

# reference palette (light): categorical slots 2 / 1 / 3, plus violet for the reveal
TARGET, FILLER_NEW, FILLER_OLD, REVEAL = "#eb6834", "#2a78d6", "#1baf7a", "#6250d6"
INK, INK2, MUTED, SURFACE, RULE = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e4e3df"

# ---------------------------------------------------------------- run time
# Trials are self-paced: the next trial starts as soon as you answer.
# Assumptions: a visual trial takes ~2 s in all (range 1.5-2.5 s);
# an audio trial lasts the sentence (mean 3.5 s) plus ~0.8 s to answer (range 0.3-1.5 s);
# ~5 s per block-intro screen.
SWS_MEAN_S = np.mean([sf.info(f).duration for f in sorted((ROOT / "stimuli" / "sws").glob("*.wav"))])
CLEAR_MEAN_S = np.mean([sf.info(f).duration for f in sorted((ROOT / "stimuli" / "speech_clear").glob("*.wav"))])


def minutes(modality, blocks=10, target_reps=8, filler_reps=4, n_fillers=4, rt=None):
    answered = blocks * 2 * (target_reps + n_fillers * filler_reps)
    if modality == "visual":
        per_trial = 2.0 if rt is None else rt
        reveal = 2 * 3.0
    else:
        per_trial = SWS_MEAN_S + (0.8 if rt is None else rt)
        reveal = CLEAR_MEAN_S + 0.5 + SWS_MEAN_S
    return (answered * per_trial + blocks * (reveal + 5)) / 60


def runtime_table():
    """(session, minutes, low, high) for the full design: 10 blocks, target x8, fillers 4 x 4."""
    return [("Visual", minutes("visual"), minutes("visual", rt=1.5), minutes("visual", rt=2.5)),
            ("Audio", minutes("audio"), minutes("audio", rt=0.3), minutes("audio", rt=1.5))]


# ---------------------------------------------------------------- drawing helpers
def box(ax, x, y, w, h, fc, ec="none", r=0.02, lw=0, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(ax, x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=14,
                                 color=INK2, lw=1.4, zorder=3))


def section(ax, x, y, text):
    ax.text(x, y, text, fontsize=13.5, fontweight="bold", color=INK, va="bottom")


def main():
    from mooney_prediction_task_blocks import MooneyPredictionTask
    task = MooneyPredictionTask(ROOT / "stimuli", ROOT / "unused", seed=3)
    seq = task.generate_block_sequence(target_idx=0)
    names = {0: "T", **{f: "ABCD"[k] for k, f in enumerate(seq["fillers"])}}

    gray = square_gray(ROOT / "stimuli" / "images" / "16.jpg")
    example_tt = np.asarray(two_tone(gray))
    example_orig = np.asarray(gray)
    x, sr = sf.read(ROOT / "stimuli" / "sws" / "sent07.wav")
    f, t, S = spectrogram(x, sr, nperseg=512, noverlap=448)

    fig = plt.figure(figsize=(16, 11.2), facecolor=SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11.2)
    ax.axis("off")

    def inset(x0, y0, w, h):
        a = fig.add_axes([x0 / 16, y0 / 11.2, w / 16, h / 11.2])
        a.set_xticks([])
        a.set_yticks([])
        for s in a.spines.values():
            s.set_color(RULE)
        return a

    # title
    ax.text(0.5, 10.65, "PSY 3200 disambiguation task: design summary", fontsize=21,
            fontweight="bold", color=INK)
    ax.text(0.5, 10.25, "Each student runs two sessions, in separate class meetings, each followed by a first "
            "look at the data:", fontsize=12, color=INK2)
    ax.text(0.5, 9.93, "everyone does VISUAL (two-tone \"Mooney\" images) in the first class and AUDIO "
            "(sine-wave speech) in the second.", fontsize=12, color=INK2)

    # 1. session = 10 blocks
    section(ax, 0.5, 9.4, "1  One session = 10 blocks, each with a new target item")
    bw, gap = 1.38, 0.12
    for b in range(10):
        x0 = 0.5 + b * (bw + gap)
        box(ax, x0, 8.85, bw * 0.47, 0.5, "#dcdbd6", r=0.04)
        box(ax, x0 + bw * 0.49, 8.85, bw * 0.04, 0.5, REVEAL, r=0.01)
        box(ax, x0 + bw * 0.55, 8.85, bw * 0.45, 0.5, "#dcdbd6", r=0.04)
        ax.text(x0 + bw / 2, 8.6, f"Block {b + 1}", ha="center", fontsize=10, color=INK2)
    ax.text(0.5, 8.18, "pre (24 trials)  |  reveal (load prior)  |  post (24 trials)  in every block.   "
            "12 items per modality; 10 become targets (one per block), in random order.",
            fontsize=11, color=INK2)

    # 2. inside one block
    section(ax, 0.5, 7.55, "2  Inside one block (49 rows in the data file)")
    tw, tg, y = 0.205, 0.02, 6.65

    def ticks(x0, order, label):
        for k, item in enumerate(order):
            c = TARGET if item == 0 else FILLER_NEW
            box(ax, x0 + k * (tw + tg), y, tw, 0.55, c, r=0.03)
            ax.text(x0 + k * (tw + tg) + tw / 2, y + 0.27, names[item], ha="center", va="center",
                    fontsize=8.5, color="white", fontweight="bold")
        ax.text(x0, y - 0.32, label, fontsize=11, color=INK2)
        return x0 + len(order) * (tw + tg)

    end_pre = ticks(0.5, seq["pre"], "PRE: target T x 8 + fillers A-D x 4 each, shuffled. Answer every trial.")
    rx = end_pre + 0.25
    box(ax, rx, 6.25, 2.55, 1.2, "#efedfb", ec=REVEAL, lw=1.5, r=0.06)
    ax.text(rx + 1.275, 7.27, "REVEAL (load prior)", ha="center", fontsize=10.5, color=REVEAL, fontweight="bold")
    a1, a2 = inset(rx + 0.12, 6.33, 0.8, 0.8), inset(rx + 1.6, 6.33, 0.8, 0.8)
    a1.imshow(example_orig, cmap="gray")
    a2.imshow(example_tt, cmap="gray")
    arrow(ax, rx + 0.98, 6.73, rx + 1.55, 6.73)
    ax.text(rx + 1.27, 6.83, "3 s → 3 s", ha="center", fontsize=8.5, color=INK2)
    ticks(rx + 2.8, seq["post"], "POST: the same 24 trials, reshuffled.")
    ax.text(rx, 6.12, "No answer. Visual: original photo 3 s, then its two-tone 3 s.\n"
            "Audio: clear sentence, 0.5 s gap, then its sine-wave version.",
            fontsize=10, color=INK2, va="top")

    # 3. one trial
    section(ax, 0.5, 4.75, "3  One trial")
    box(ax, 0.5, 1.0, 3.7, 3.5, "white", ec=RULE, lw=1.2, r=0.08)
    ax.text(2.35, 4.2, "VISUAL", ha="center", fontsize=11.5, fontweight="bold", color=INK)
    a = inset(1.5, 2.15, 1.7, 1.7)
    a.imshow(example_tt, cmap="gray")
    ax.text(2.35, 1.85, "Could you tell what is in the picture?", ha="center", fontsize=10.5, color=INK)
    ax.text(2.35, 1.45, "←  NO            YES  →", ha="center", fontsize=11, color=INK, fontweight="bold")
    ax.text(2.35, 1.12, "image stays until you answer", ha="center", fontsize=9, color=MUTED)

    box(ax, 4.5, 1.0, 3.7, 3.5, "white", ec=RULE, lw=1.2, r=0.08)
    ax.text(6.35, 4.2, "AUDIO", ha="center", fontsize=11.5, fontweight="bold", color=INK)
    a = inset(4.9, 2.25, 2.9, 1.55)
    a.pcolormesh(t, f, 10 * np.log10(S + 1e-12), shading="auto", cmap="Greys",
                 vmin=10 * np.log10(S.max()) - 60)
    a.set_ylim(0, 4500)
    ax.text(6.35, 2.02, "sine-wave speech plays (2-4.5 s)", ha="center", fontsize=9, color=MUTED)
    ax.text(6.35, 1.72, "Could you understand the words?", ha="center", fontsize=10.5, color=INK)
    ax.text(6.35, 1.32, "←  NO            YES  →", ha="center", fontsize=11, color=INK, fontweight="bold")
    ax.text(6.35, 1.05, "answer any time", ha="center", fontsize=9, color=MUTED)

    # 4. conditions + analysis
    section(ax, 8.6, 4.75, "4  What we compare")
    for k, (c, lab, desc) in enumerate([
            (TARGET, "target", "this block's revealed item"),
            (FILLER_NEW, "filler_new", "filler whose original was never shown yet (the control)"),
            (FILLER_OLD, "filler_old", "filler that was the target of an earlier block (block 2 on)")]):
        yy = 4.15 - k * 0.42
        box(ax, 8.6, yy, 0.32, 0.26, c, r=0.04)
        ax.text(9.05, yy + 0.13, lab, fontsize=10.5, color=INK, va="center", fontweight="bold")
        ax.text(10.3, yy + 0.13, desc, fontsize=10, color=INK2, va="center")
    ax.text(8.6, 2.6, "Disambiguation effect  =  (target post − pre)  −  (filler_new post − pre)",
            fontsize=11.5, color=INK, fontweight="bold")
    ax.text(8.6, 2.28, "Prediction: knowing the original (a high-level prior) makes the degraded version "
            "recognisable,\nso target recognition rises more than filler_new, which only gets repetition.",
            fontsize=10, color=INK2, va="top")

    # 5. run time
    ax.text(8.6, 1.62, "Estimated time per session (full design: 10 blocks of 49 trials)", fontsize=11,
            color=INK, fontweight="bold")
    ax.plot([8.6, 15.6], [1.5, 1.5], color=RULE, lw=1)
    for k, (name, m, lo, hi) in enumerate(runtime_table()):
        yy = 1.18 - k * 0.32
        ax.text(8.6, yy, f"Class {k + 1}: {name.lower()} session", fontsize=10.5, color=INK2)
        ax.text(11.2, yy, f"~{m:.0f} min", fontsize=10.5, color=INK, fontweight="bold")
        ax.text(12.2, yy, f"(range {lo:.0f}-{hi:.0f})", fontsize=10, color=INK2)
    ax.text(0.5, 0.25, "Example stimuli shown here use spare image 16, which is not in the task. "
            "Trials are self-paced. Run times assume ~2 s per visual trial (range 1.5-2.5 s) and an answer "
            "~0.8 s after each sentence ends (0.3-1.5 s), plus the reveals and block screens.",
            fontsize=8.5, color=MUTED)

    out = ROOT / "docs" / "task_design.png"
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    print(f"saved {out}")


if __name__ == "__main__":
    for name, m, lo, hi in runtime_table():
        print(f"{name}: {m:.1f} min ({lo:.1f}-{hi:.1f})")
    main()
