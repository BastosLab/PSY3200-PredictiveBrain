#!/usr/bin/env python3
"""
Upload any of your session files that are not on GitHub yet (the task does this by
itself at the end of each session; use this if that upload failed, e.g. no internet).

    python upload_data.py
"""
import argparse
import sys
from pathlib import Path

import class_repo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', default=str(class_repo.DATA_DIR), help="default: my_data/")
    args = ap.parse_args()

    todo = class_repo.pending(Path(args.data_dir))
    if not todo:
        print(f"Nothing to upload: every session file in {args.data_dir} is already on GitHub.")
        return
    done, failed = class_repo.upload_pending(Path(args.data_dir))
    for dest in done:
        print(f"Uploaded {class_repo.DATA_REPO}/{dest}")
    for name, error in failed:
        print(f"NOT uploaded {name}: {error}")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
