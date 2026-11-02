#!/usr/bin/env python3
"""
One-time setup before the first class (about 5 minutes):

    python3 setup_student.py        (Windows: py setup_student.py)

1. Installs the Python packages the task needs.
2. Checks that pictures and sound work.
3. Signs you in to GitHub in your browser (once; it is remembered).
4. Accepts your invitation to the class data repository.
5. Saves your name, so both sessions use the same one.
6. Uploads a small check-in file, so you and your instructor know it all works.

Run it again any time; it only redoes what is missing.
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import class_repo

ROOT = Path(__file__).resolve().parent
GH_INSTALL = ("Install the GitHub CLI from https://cli.github.com (Mac: the .pkg download; Windows: the .msi "
              "download), then open a NEW terminal window and run this again.")


def step(text):
    print(f"\n== {text}")


def fail(text):
    print(f"\nSTOPPED: {text}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', help="your first and last name (otherwise you are asked)")
    ap.add_argument('--no-install', action='store_true', help="skip installing Python packages")
    args = ap.parse_args()

    if sys.version_info < (3, 9):
        fail(f"Python {platform.python_version()} is too old; install Python 3.12 from https://www.python.org.")

    if not args.no_install:
        step("Installing Python packages (requirements.txt)")
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')])
        if r.returncode != 0:
            fail("pip could not install the packages (see the messages above).")

    step("Checking pictures and sound")
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception as e:
        fail(f"The task window (tkinter) does not work: {e}. On a Mac, install Python from python.org.")
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.quit()
    except Exception as e:
        fail(f"Sound (pygame) does not work: {e}")
    print("OK")

    step("Signing in to GitHub")
    if shutil.which('gh') is None:
        fail(GH_INSTALL)
    try:
        login = class_repo.github_login()
    except class_repo.UploadError:
        print("Your browser will open. Copy the one-time code shown here, paste it on the GitHub page, "
              "and authorize the GitHub CLI.")
        subprocess.run(['gh', 'auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https'])
        login = class_repo.github_login()
    print(f"Signed in as {login}")

    step(f"Getting access to {class_repo.DATA_REPO}")
    if not class_repo.can_push():
        if class_repo.accept_invitation():
            print("Accepted your invitation.")
        if not class_repo.can_push():
            fail(f"You have not been invited yet. Send your GitHub username, {login}, to your instructor, "
                 "and run this again once they say you were added.")
    print("OK: you can upload to the class data repository")

    step("Your name")
    saved = class_repo.load_student().get('name', '')
    name = args.name or input(f"Your first and last name{f' [{saved}]' if saved else ''}: ").strip() or saved
    if not class_repo.clean_name(name):
        fail("Please give your name.")
    class_repo.save_student(name=name, github=login)
    print(f"Your data files will be named ..._Experiment_{class_repo.clean_name(name)}_<date>_<time>.csv")

    step("Uploading a check-in file")
    note = {'name': name, 'github': login, 'python': platform.python_version(),
            'system': f"{platform.system()} {platform.release()}", 'checked_in': datetime.now().isoformat()}
    class_repo.put_file(f"checkins/{login}.json", json.dumps(note, indent=2).encode(), f"Check in {login}")
    print(f"OK: {class_repo.DATA_REPO}/checkins/{login}.json")

    print("\nAll set. In class, open a terminal in this folder and run:\n"
          f"    {'py' if platform.system() == 'Windows' else 'python3'} mooney_prediction_task_blocks.py")


if __name__ == '__main__':
    main()
