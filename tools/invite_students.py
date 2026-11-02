#!/usr/bin/env python3
"""
For instructors: give students upload (write) access to the class repository,
and see who has finished setup_student.py.

    python tools/invite_students.py usernames.txt        # one GitHub username per line
    python tools/invite_students.py janedoe jsmith42     # or on the command line
    python tools/invite_students.py --status             # who has checked in, who is still invited

Needs the GitHub CLI signed in as an admin of the repository.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from class_repo import CLASS_DATA, REPO, UploadError, gh  # noqa: E402


def status():
    try:
        checkins = json.loads(gh('api', f'repos/{REPO}/contents/{CLASS_DATA}/checkins'))
    except UploadError:
        checkins = []
    names = [c['name'][:-5] for c in checkins if c['name'].endswith('.json')]
    invited = [i['invitee']['login'] for i in json.loads(gh('api', f'repos/{REPO}/invitations'))]
    print(f"Checked in ({len(names)}): {', '.join(sorted(names, key=str.lower)) or '-'}")
    print(f"Invited, not accepted yet ({len(invited)}): {', '.join(sorted(invited, key=str.lower)) or '-'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('users', nargs='*', help="GitHub usernames, or a text file of them")
    ap.add_argument('--status', action='store_true')
    args = ap.parse_args()
    if args.status:
        return status()

    users = []
    for u in args.users:
        users += Path(u).read_text().split() if Path(u).is_file() else [u]
    if not users:
        ap.error("give GitHub usernames or a file of them")
    for u in dict.fromkeys(x.strip().lstrip('@') for x in users if x.strip()):
        try:
            gh('api', '--method', 'PUT', f'repos/{REPO}/collaborators/{u}', '-f', 'permission=push')
            print(f"invited {u}")
        except UploadError as e:
            print(f"FAILED {u}: {e}")


if __name__ == '__main__':
    main()
