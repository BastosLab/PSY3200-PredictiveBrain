# Troubleshooting: PSY 3200 Mooney prediction task

Problems a student may run into, and what to do about each one. Find the
message or symptom you are seeing, then follow the steps.

**Your data are safe.** Every trial is saved to `my_data/` the moment it ends.
A failed upload never deletes anything.

**Using Claude Code?** Ask it to "check TROUBLESHOOTING.md". Claude should
follow these steps, tell the student what it finds, and not edit the task's
code to get around a failure.

On Windows, type `py` wherever this page says `python3`.

Last updated from a simulated new-student run on 2026-11-04.
[What that run did not cover](#not-tested-yet) is at the end.

## Quick lookup

| What you see | Go to |
|---|---|
| The task freezes on the first "Block 1" screen | [Task freezes](#the-task-freezes-on-the-first-block-screen) |
| `command not found: python` | [Command not found](#command-not-found-python) |
| A long error ending in `Not signed in to GitHub` | [Sign-in error](#a-long-error-ending-in-not-signed-in-to-github) |
| `STOPPED: You have not been invited yet` | [Not invited](#stopped-you-have-not-been-invited-yet) |
| `STOPPED: Install the GitHub CLI` | [GitHub CLI missing](#stopped-install-the-github-cli) |
| `pip could not install the packages` | [pip failed](#pip-could-not-install-the-packages) |
| `The task window (tkinter) does not work`, or `Sound (pygame) does not work` | [Window or sound](#the-task-window-or-sound-does-not-work) |
| `Not uploaded` or `NOT uploaded` | [Upload failed](#your-data-did-not-upload) |
| You ran a test with `--autopilot` | [Test runs](#test-runs-can-end-up-in-the-class-data) |

## Setup problems

### The task freezes on the first block screen

**Who this affects:** Macs using Apple's built-in Python 3.9. Setup can still
finish with **All set** on this Python, so setup passing does not rule it out.

**Check:**

```bash
python3 -c "import sys, tkinter; print(sys.version.split()[0], tkinter.TkVersion)"
```

If the first number is `3.9` or the second is `8.5`, you are probably on
Apple's Python.

**Fix:**

1. Install Python 3.12 from [python.org](https://www.python.org/downloads/)
   (use the macOS installer, not Homebrew).
2. Open a **new** terminal in the task folder and run the check again.
3. Run `python3 setup_student.py` again so the packages install for the new
   Python.

This was seen on an automated test run, not with a person pressing keys. If
you have this Python, install 3.12 anyway.

### `command not found: python`

**Cause:** Some messages say `python upload_data.py`, but the python.org
installer on a Mac only provides `python3`.

**Fix:** Type `python3` instead:

```bash
python3 upload_data.py
```

### A long error ending in `Not signed in to GitHub`

**Cause:** GitHub sign-in was not finished, for example the browser page was
closed. The long error looks alarming, but nothing is broken.

**Fix:** Sign in, then run setup again:

```bash
gh auth login --hostname github.com --web --git-protocol https
```

```bash
python3 setup_student.py
```

Copy the one-time code from the terminal, paste it on the GitHub page, and
authorize. Claude Code users: run the sign-in in a separate Terminal or Command
Prompt window, not through Claude.

### `STOPPED: You have not been invited yet`

**Cause:** Your instructor has not added your GitHub username yet.

**Fix:** Send your instructor the username shown in the message. Run
`python3 setup_student.py` again once they say you were added.

### `STOPPED: Install the GitHub CLI`

**Cause:** `gh` is not installed. GitHub Desktop and a GitHub account do not
include it.

**Fix:** Install it from [cli.github.com](https://cli.github.com) (Mac: the
`.pkg` download; Windows: the `.msi` download). Open a **new** terminal, then
run setup again.

### `pip could not install the packages`

**If you see `externally-managed-environment`:** you are on a Mac and not using
the python.org Python. Install Python 3.12 from
[python.org](https://www.python.org/downloads/), open a new terminal, and run
setup again.

**Otherwise:** check your internet connection and run setup again. If it still
fails, send the error to your instructor.

### The task window or sound does not work

**Fix:** On a Mac, install Python 3.12 from
[python.org](https://www.python.org/downloads/), open a new terminal, and run
setup again. Homebrew's Python often cannot open the task window. If you are
already on the python.org Python, or on Windows, send the error to your
instructor.

## Session and upload problems

### Your data did not upload

**Fix:** Your file is safe in `my_data/`. When you are online, run:

```bash
python3 upload_data.py
```

It uploads anything not on GitHub yet, and says `Nothing to upload` if
everything is already there. If it still fails:

- **No internet:** wait until you are online and run it again.
- **A sign-in problem:** run `gh auth status`. If you are not signed in, follow
  [the sign-in steps](#a-long-error-ending-in-not-signed-in-to-github).
- **No permission to upload:** run `python3 setup_student.py`. If it says you
  have not been invited, send your username to your instructor.

Uploaded files are listed in `my_data/.uploaded`.

### Test runs can end up in the class data

**Cause:** `--autopilot` answers randomly and is for testing only. It skips the
automatic upload at the end of its own run, but the file stays in `my_data/`.
`upload_data.py` uploaded a full 10-block autopilot file as a real class
session in testing. A later real session's upload may pick it up too.

**How to avoid it:** Do not run `--autopilot` in your task folder unless you
send its data somewhere else:

```bash
python3 mooney_prediction_task_blocks.py --autopilot --speed 50 --modality visual --data-dir ~/Desktop/autopilot_test
```

**If you already ran it:**

- **Not uploaded yet:** move the test file out of `my_data/`. Do not run
  `upload_data.py` or a real session until you have.
- **Already uploaded:** tell your instructor which file it is, so it can be
  left out of the class results.

## Not tested yet

The simulated run used a stand-in for GitHub on one Mac, so these have not been
checked and may hold other problems:

- Real GitHub sign-in, invitations and uploads
- Windows
- A completely new Mac, including the Apple developer tools prompt that can
  appear the first time `git` or `python3` is used
- Claude Code's own permission prompts
- A person answering trials, and the audio session
- The *Uploaded to GitHub* screen at the end of a session

If something here goes wrong, or you hit a problem not listed, tell your
instructor what you did and the exact message you saw.
