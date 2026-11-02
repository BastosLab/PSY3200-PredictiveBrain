# Mooney Prediction Task (PSY 3200, The Predictive Brain)

## What the experiment tests

Some images and sounds are so degraded that you cannot tell what they are: a
black-and-white "two-tone" photo, or "sine-wave speech" made of three whistles.
Once you have seen the original photo or heard the clear sentence, the same
degraded version suddenly makes sense.

Predictive-processing theories say this happens because the brain uses what it
already knows (a *prior*) to interpret ambiguous input. In each block of this
experiment you rate the degraded items, then see or hear the clear original of
**one** of them (the *target*), the **reveal (load prior)**, then rate them all
again. If the prior explains
recognition, the target should improve much more than the other items, whose
originals you have not seen.

![Task design](docs/task_design.png)

**Do not open the `stimuli/` folders before you run the task.** Seeing the
originals in advance ruins the effect for you.

## Install (once)

You need Python 3.9 or newer.

```bash
git clone https://github.com/BastosLab/PSY3200-PredictiveBrain.git
cd PSY3200-PredictiveBrain
pip install -r requirements.txt
```

No git? Use the green **Code → Download ZIP** button on GitHub, unzip it, and
open a terminal in that folder.

`requirements.txt` installs `pygame-ce`, which provides `import pygame` and
installs on every recent Python (the original `pygame` package does not install
on Python 3.13+). If both are installed, uninstall `pygame`.

**Mac users:** the task window uses tkinter. The python.org installer includes
it. If you use Homebrew's Python and `python -c "import tkinter"` fails, run
`brew install python-tk` (matching your Python version).

Check everything works with a 1-minute test run that answers by itself:

```bash
python mooney_prediction_task_blocks.py --autopilot --speed 20 --modality visual --blocks 1 --data-dir test_run
```

## Run the experiment

You run **two sessions, in separate class meetings**, and look at the data
after each one. Everyone does **VISUAL in the first class** and **AUDIO in the
second**, with the same participant ID both times. Use headphones for the audio
session.

```bash
python mooney_prediction_task_blocks.py
```

Pick the modality, type your participant ID, and follow the screen. Each block
starts on a break screen showing its number ("Block 3 of 10"); take a break if
you need one, then press SPACE to start the block.
Keys: **→ = yes**, **← = no**, **SPACE** to start each block, **ESC** to quit (it asks first).

| Session (10 blocks of 49 trials) | Approx. time |
|---|---|
| Visual | 18 min (14-22) |
| Audio | 36 min (32-42) |

Trials are self-paced: the next one starts as soon as you answer. A visual trial
takes about 2 s. An audio trial lasts the whole sentence (2-4.5 s, 3.5 s on
average) plus your answer, which is why the audio session is twice as long.

## Your data

Each trial is saved the moment it ends, to
`~/mooney_data/mooney_<ID>_<modality>_<date>_<time>.csv` (the final screen shows
the full path). Nothing is lost if the window closes or the computer crashes.

### Submit it (after each class)

Class data go to the **private** repository
[BastosLab/PSY3200-PredictiveBrain-data](https://github.com/BastosLab/PSY3200-PredictiveBrain-data).
Accept GitHub's e-mail invitation to it first. Then:

1. On GitHub, open the data repository's `visual/` folder (first class) or
   `audio/` folder (second class).
2. Click **Add file → Upload files**, drag in your CSV, and click **Commit changes**.

Upload only your own, complete session file, without renaming or editing it.

Columns: `participant_id, modality, seed, n_blocks, block, trial_number,
trial_type` (pre / reveal / post), `target_index, stimulus_index` (1-12),
`stimulus_file, condition` (target / filler_new / filler_old), `response`
(yes / no), `recognized` (1 / 0), `reaction_time_ms, timestamp`. The
reveal (load prior) row has `NA` for the response columns.

## Analyse (after each session)

Your own session:

```bash
python analysis/analyze_session.py ~/mooney_data/mooney_P01_visual_20261110_101500.csv
```

The whole class: download the data repository (its **Code → Download ZIP**, or
`git clone https://github.com/BastosLab/PSY3200-PredictiveBrain-data.git`
next to this folder), then:

```bash
python analysis/analyze_class.py ../PSY3200-PredictiveBrain-data/
```

After the first class this tests the visual effect. After the second class, with
everyone's files from both classes in the folder, it tests the audio effect and
compares audio with visual within each student. Because everyone did visual
first, that comparison also includes any effect of doing the task a second time
(for example, already knowing that a reveal is coming).

Results go to `results/`. To see what the class analysis produces before any
real data exist:

```bash
python analysis/simulate_class_data.py
python analysis/analyze_class.py data/simulated/
```

## Found a bug? Propose a fix

Anyone can propose a change; André or Ishan reviews it before it goes in.
Click **Fork** on GitHub, make the change in your fork, check that
`python -m pytest tests/` still passes, and open a pull request saying what was
wrong and how you checked the fix.

## For instructors

- `make_stimuli.py` rebuilds the two-tone images and sine-wave speech from
  `stimuli/images/*.jpg` and `stimuli/sounds/*.mp3` (needs `praat-parselmouth`
  and `soundfile`). Per-image difficulty settings are at its top.
- `docs/make_design_figure.py` redraws the design figure and prints run-time estimates.
- `--blocks`, `--target-reps` and `--filler-reps` shorten a session (for demos;
  the class uses the full design).
- `python -m pytest tests/` runs the tests: autopilot sessions in both
  modalities, crash safety, sequence checks, and the analysis on simulated data.
- `CHANGES.md` lists what was fixed and why.
- Students need write access to the data repository, added by GitHub username.
  This code repository is public: students pull it and propose fixes as pull
  requests; only maintainers (André, Ishan) merge them.

PSY 3200 Predictive Brain | Vanderbilt University | Prof. André Bastos
