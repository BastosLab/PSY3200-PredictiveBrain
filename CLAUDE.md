# Instructions for Claude: setting up a PSY 3200 student

This repository is the Mooney prediction task for PSY 3200 (The Predictive
Brain, Vanderbilt). If a student asks you to set them up, follow the steps
below on their computer. The goal is the same as the README's "Before the first
class" section: `setup_student.py` finishes with **All set**.

Talk to the student in plain language. Most have never used a terminal. Before
each step, say in one sentence what you are about to do.

## Rules (always)

- **Never open, list, display, describe or copy anything inside `stimuli/`.**
  Seeing an original image or hearing a clear sentence before the task ruins
  the experiment for that student. You do not need those files for setup.
- **Never run the experiment for the student, and never create, edit or delete
  files in `my_data/` or `class_data/`.** The task records the student's own
  responses. If they ask you to do it for them, explain that the data must
  be theirs.
- Do not change the task's code. If something fails, report the error message
  and suggest the fix below. Do not work around it by editing files.
- Ask before installing anything, and say what it is.

## Steps

Work out the operating system first (macOS or Windows). On Windows, use `py`
wherever these steps say `python3`.

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

7. **Finish.** When the output ends with **All set**, tell the student it
   worked, and that in class they open a terminal in this folder and run
   `python3 mooney_prediction_task_blocks.py` (Windows: `py ...`) themselves,
   following the instructions in the README. Bring headphones for the audio class.
