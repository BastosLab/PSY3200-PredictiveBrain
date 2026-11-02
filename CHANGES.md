# Changes to the original task (branch `fixes`)

The design is still Ishan's: 10 blocks, one new target per block, the target
shown 8 times and 4 fillers 4 times each before and after the reveal. Line
numbers refer to the original `mooney_prediction_task_blocks.py` (commit `cadeabe`).

## Bugs that stopped the task working

1. **The file did not run.** Two identical copies of the script were joined by a
   pasted shell line (`ENDFILEcat > ...`, line 509), a SyntaxError. One copy was
   removed. *Habit: run the file after every paste.*
2. **Audio sessions revealed the wrong sound.** Pre/post trials played the
   block's target *image* index as a sound (lines 288, 315), but the reveal played
   sound `block_num % 16` (line 276), so the sentence that was revealed was
   usually not the one being tested. Both now use the same target item.
3. **Every session revealed both modalities.** The disambiguation phase showed an
   image *and* played a sound (lines 298, 304) in both visual and audio sessions.
   Now it reveals only the session's modality.
4. **The post phase was cut short and unbalanced.** `post_sequence[:17]`
   (line 142) dropped 7 trials, so one filler appeared 3 times and the others
   2 times; the README promised 25. Post now has the same 24 trials as pre
   (8 target + 4 fillers x 4), reshuffled.
5. **Data were saved only on the last screen** (line 461). Closing the window or
   a crash lost the whole session, and there was no way to quit. Now the file is
   created at the start, every trial is written and flushed to disk as it ends,
   and ESC (or the close button) asks before quitting.
6. **The window froze during sounds.** `play_sound` waited in a loop until the
   sound ended (line 113) without updating the window, so key presses queued up
   and the reaction time included the sound's length. Sounds now play in the
   background and the answer is timed from sound onset.

## Changes so the task measures what it is meant to

7. **The degraded image changed on every trial.** `_apply_mooney_threshold`
   (line 98) added fresh random noise and thresholded far below the mean, giving
   ~90% white speckle that was different each time, so pre and post were not the
   same stimulus. The task now shows fixed two-tone images from
   `stimuli/twotone/` (blur, then threshold at the median: 50% black / 50% white),
   made by `make_stimuli.py` and checked by eye for difficulty.
8. **The original was never shown.** The "disambiguation" trial showed another
   degraded copy of the target. It now shows the original photo (3 s) and then
   its two-tone (3 s); for audio, the clear sentence, a 0.5 s gap, then its
   sine-wave version. It is now called the **reveal (load prior)**, as in class,
   and that is the heading on its screens.
9. **The audio items could not be disambiguated.** Sounds 1-12 were clear speech
   and 13-16 buzz tones, with a "HIGHER or LOWER?" question (line 419) that had
   no reference. The audio session now uses sine-wave speech (Remez et al., 1981)
   made from sentences 1-12, and asks "Could you understand the words?"
10. **Yes/No in both modalities**: "Could you tell what is in the picture?" /
    "Could you understand the words?" (← no, → yes).

## Data file

- `trial_type` is `pre / reveal / post` (the reveal row was `disambig`).
- `stimulus_index` is now 1-12 (it was 0-based; the README said 1-16), plus
  `stimulus_file` (img01 ... / sent01 ...).
- New columns: `modality, seed, n_blocks, target_index, condition`
  (target / filler_new / filler_old), `recognized` (1/0).
  `filler_old` marks fillers that were the target of an earlier block. Without
  this column, revealed items would silently mix into the control condition.
- The session's random seed is stored, so its exact trial order can be rebuilt.

## Added

- Data files are named `Visual_Mooney_Experiment_<Name>_<date>_<time>.csv` /
  `Audio_SineWaveSpeech_Experiment_...` and saved in `my_data/` (was
  `~/mooney_data/mooney_<ID>_<modality>_...`). The start screen asks for the
  student's name instead of a participant ID.
- Automatic upload: at the end of each session the file goes to `class_data/`
  on the `class-data` branch of this repository, with the student's own GitHub
  CLI login (`class_repo.py`); failed uploads are retried by the next session or
  by `upload_data.py`. `analysis/analyze_class.py --download` fetches everyone's
  latest data before analysing. `setup_student.py` does the one-time setup;
  `tools/invite_students.py` adds students and shows who has checked in.

- Command-line options: `--participant/--modality` (skip the menu), `--blocks`,
  `--target-reps`, `--filler-reps`, `--data-dir`, `--seed`, and `--autopilot
  --speed N` for testing.
- `tests/`: sequence checks over 200 seeds, full autopilot sessions in both
  modalities (490 rows each), a kill test (every completed trial survives
  SIGKILL), quitting mid-session, and analysis tests.
- `analysis/`: per-session and class analyses, plus a simulator that writes
  fake data in the task's own format with known effects. The class analysis
  recovers them, and on no-effect data its false-positive rate is 3% (target ≤ 7%).
- `docs/task_design.png`: one-page design summary.

## Habits that would have caught these

- Run the file after every paste or edit.
- Look at your stimuli (save a contact sheet) before writing the task around them.
- Write the analysis against a simulated data file before collecting data:
  missing columns (like `condition`) show up immediately.
- Write the README from the code, not from the plan: trial counts and file
  paths should be read off what the code actually does.
