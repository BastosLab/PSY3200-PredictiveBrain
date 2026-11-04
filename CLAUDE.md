# Instructions for Claude: helping a PSY 3200 student

This repository is the Mooney prediction task for PSY 3200 (The Predictive
Brain, Vanderbilt). A student may ask you to **set them up**, to **run a
session** (visual in the first class, audio in the second), or to **upload
their data**. Each is described below.

Talk to the student in plain language. Most have never used a terminal. Before
each step, say in one sentence what you are about to do. Ask before installing
anything, and say what it is.

**Do not change the task's code.** If something fails, report the error
message and use the fixes below and in `TROUBLESHOOTING.md`. Do not work
around a failure by editing files.

Work out the operating system first (macOS or Windows). On Windows, use `py`
wherever these instructions say `python3`.

## 1. One-time setup

The goal is the same as the README's "Before the first class" section:
`setup_student.py` finishes with **All set**.

1. **Get the task folder.** If you are not already inside a copy of this
   repository, download it into the student's Documents folder:
   `git clone https://github.com/BastosLab/PSY3200-PredictiveBrain.git`
   (if `git` is missing, download
   `https://github.com/BastosLab/PSY3200-PredictiveBrain/archive/refs/heads/main.zip`
   and unzip it). Then work inside that folder.

2. **Python 3.9 or newer, with a working tkinter.** Check with
   `python3 -c "import sys, tkinter; print(sys.version); tkinter.Tk().destroy()"`.
   - macOS: if this fails, the student must install Python 3.12 from
     https://www.python.org/downloads/ (the macOS installer). Homebrew's Python
     often lacks tkinter, so do not use it. Installing needs the student's
     password, so ask them to run the installer, then continue.
   - Windows: offer `winget install -e --id Python.Python.3.12`, or ask them to
     use the python.org installer and tick **Add python.exe to PATH**. Afterwards
     a new terminal may be needed before `py` works.

3. **GitHub CLI (`gh`).** Check with `gh --version`.
   - macOS: if Homebrew is installed, offer `brew install gh`. Otherwise ask
     the student to install the `.pkg` from https://cli.github.com.
   - Windows: offer `winget install -e --id GitHub.cli`, or the `.msi` from
     https://cli.github.com.

4. **GitHub sign-in.** Check with `gh auth status`. If they are not signed in,
   this step needs the student. Ask them to open a separate Terminal (macOS) or
   Command Prompt (Windows) window and run
   `gh auth login --hostname github.com --web --git-protocol https`, copy the
   one-time code, paste it on the GitHub page that opens, and authorize. Wait
   until they say they are done, then confirm with `gh auth status`.

5. **Their name.** Ask for their first and last name, as they want it to
   appear on their data files.

6. **Run the setup script:** `python3 setup_student.py --name "First Last"`.
   It installs the packages, checks pictures and sound, accepts their class
   invitation, saves their name and uploads a check-in file. It is safe to run
   again.
   - "You have not been invited yet": the instructor has not added their
     GitHub username. Tell them to send the username (the script prints it)
     to the instructor, and to run setup again once they are added. Stop here.
   - "pip could not install the packages": show the pip error. On macOS, an
     "externally-managed-environment" message means they are not using the
     python.org Python (go back to step 2).
   - tkinter or sound failures: go back to step 2 (macOS: python.org Python).

7. When the output ends with **All set**, tell the student it worked.

## 2. Running a session

The student's name was saved by setup in `~/.psy3200_student.json` (key
`name`). If that file is missing, do the setup first.

1. Ask which session: **visual** (first class, about 18 minutes) or **audio**
   (second class, about 36 minutes; headphones on).
2. Start the full session, skipping the menu:
   `python3 mooney_prediction_task_blocks.py --participant "<saved name>" --modality visual`
   (or `--modality audio`). Use the defaults for everything else: the class
   analysis only counts full 10-block sessions.
   Start it as a background process, because it runs for longer than a normal
   command time limit, and wait for it to exit.
3. Tell the student what to do in the window: each block opens on a break
   screen ("Block 3 of 10"); press **SPACE** to start it. **→ = yes**,
   **← = no**. **ESC** quits (it asks first). The student answers every trial
   themselves; the class results are about their perception.
4. **Data are saved and uploaded automatically.** Every trial is written the
   moment it ends to `my_data/Visual_Mooney_Experiment_<Name>_<date>_<time>.csv`
   (audio: `Audio_SineWaveSpeech_Experiment_...`). At the end the program
   uploads the file to the `class-data` branch of the class repository under
   the student's GitHub login. The last screen says *Uploaded to GitHub*, or
   *Not uploaded* with the reason. Tell the student to wait for that screen
   before closing the window.
5. After the program exits, make sure the upload happened (section 3).

`--autopilot` (random answers, for testing the program) and runs with fewer
blocks are never uploaded as class data; do not use them for a real session.

## 3. Uploading data

Run `python3 upload_data.py`. It uploads every session file in `my_data/` that
is not on GitHub yet, and says "Nothing to upload" if all are already there.
Run it after every session, and whenever an upload failed.

If it prints "NOT uploaded":
- No internet: wait until the student is online and run it again. The file is
  safe in `my_data/`.
- GitHub sign-in problems: check `gh auth status` and, if needed, have the
  student sign in again (section 1, step 4), then rerun.
- No upload access: run `python3 setup_student.py` again; if it says they have
  not been invited, the student sends their GitHub username to the instructor.

Uploaded files are listed in `my_data/.uploaded`.
