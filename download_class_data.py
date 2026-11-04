#!/usr/bin/env python3
"""
Download everyone's latest data from GitHub, for your own analysis.

    python3 download_class_data.py                 # into class_data/
    python3 download_class_data.py some/folder     # somewhere else

The folder is replaced by a fresh copy each time, so do not keep your own work in it.
Inside: visual/ and audio/ (class sessions, one CSV per session), demo/ (shortened
test runs) and checkins/ (setup check-ins).
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import class_repo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', nargs='?', default=str(Path(__file__).resolve().parent / class_repo.CLASS_DATA),
                    help="where to put the data (default: class_data/ in this folder)")
    args = ap.parse_args()
    try:
        dest = class_repo.download_class_data(Path(args.folder))
    except class_repo.UploadError as e:
        sys.exit(f"Download failed: {e}")
    counts = Counter(p.parent.name for p in dest.glob('*/*.csv'))
    print(f"Downloaded the class data into {dest}")
    for modality in ('visual', 'audio'):
        print(f"  {modality}/: {counts.get(modality, 0)} session files")


if __name__ == '__main__':
    main()
