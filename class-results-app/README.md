# Class results app

A window that shows the whole class's results for the Mooney prediction task.

```bash
python3 class-results-app/class_results_app.py
```

- **Download latest data** gets everyone's sessions from the `class-data` branch
  into `class_data/` (the same thing `download_class_data.py` does).
- **Task** switches between the visual and the audio session.
- **Show** switches between the share of "yes" answers and the median reaction time.
- **Save figure…** saves what is on screen as a PNG.

## What the figure shows

- **Left panel:** for each condition, the value before vs after the reveal.
  - Thin lines: one student each.
  - Thick lines: the class mean ± SEM across students.
  - The legend gives a paired t-test (after vs before) for each condition.

  The three conditions:
  - **Target:** the picture or sentence revealed in that block.
  - **Non-target, revealed earlier:** an item whose original was shown in an earlier block.
  - **Non-target, not yet revealed:** an item never revealed so far.
- **Right panel:** each student's **disambiguation effect**. This is the change for the
  target, minus the change for non-targets not yet revealed:
  (target after − before) − (non-target not yet revealed after − before).
  The diamond is the class mean ± SEM, with a one-sample t-test against 0.

## Which sessions are used

Each student's **latest complete session** (all 10 blocks). The table under the figure
lists every session file, including those left out and why:
- a session quit early, or a short test run;
- an earlier session from a student who also has a later complete one.

Sessions are grouped by the name typed at the start of the task. So the same person
under two names counts as two students.

## Without a window

```bash
python3 class-results-app/class_results_app.py --save figures/
```

This saves all four figures (visual/audio × yes/reaction time) to `figures/`, and
prints which sessions were used.
