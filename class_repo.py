"""
The class data repository on GitHub, used through the GitHub CLI (`gh`) with each
student's own login, so every upload is credited to the student's GitHub account.

Session files go to <modality>/ (full sessions) or demo/<modality>/ (shortened test
runs, which the class analysis skips). A file counts as uploaded once the repository
has it with the same content, so uploading again never duplicates anything.
"""
import base64
import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import List, Optional, Tuple

DATA_REPO = 'BastosLab/PSY3200-PredictiveBrain-data'
DATA_DIR = Path(__file__).resolve().parent / 'my_data'
STUDENT_FILE = Path.home() / '.psy3200_student.json'   # name and GitHub login, saved by setup_student.py
UPLOAD_LOG = '.uploaded'                                # in the data folder: one uploaded file name per line
FULL_BLOCKS, FULL_PRE_TRIALS = 10, 24                   # the class design; anything else is a test run
FILE_PREFIX = {'visual': 'Visual_Mooney_Experiment', 'audio': 'Audio_SineWaveSpeech_Experiment'}


class UploadError(Exception):
    pass


def clean_name(text: str) -> str:
    """'André  bastos' -> 'AndreBastos': safe in a file name, the same on every computer."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9_-]', '', ''.join(w[:1].upper() + w[1:] for w in text.split()))


def load_student() -> dict:
    try:
        return json.loads(STUDENT_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_student(**fields) -> None:
    STUDENT_FILE.write_text(json.dumps({**load_student(), **fields}, indent=2))


# ---------------------------------------------------------------- GitHub CLI
def gh(*args: str, input_text: Optional[str] = None, timeout: float = 60) -> str:
    exe = shutil.which('gh')
    if exe is None:
        raise UploadError("The GitHub CLI (gh) is not installed. See 'Before the first class' in the README.")
    try:
        r = subprocess.run([exe, *args], input=input_text, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise UploadError("GitHub did not answer in time (no internet?).")
    if r.returncode != 0:
        raise UploadError((r.stderr or r.stdout).strip() or f"gh {args[0]} failed")
    return r.stdout


def github_login() -> str:
    try:
        return gh('api', 'user', '--jq', '.login').strip()
    except UploadError as e:
        raise UploadError(f"Not signed in to GitHub ({e}). Run setup_student.py.")


def accept_invitation() -> bool:
    """Accept a pending invitation to the data repository. True if there was one."""
    invitations = json.loads(gh('api', 'user/repository_invitations') or '[]')
    for inv in invitations:
        if inv['repository']['full_name'].lower() == DATA_REPO.lower():
            gh('api', '--method', 'PATCH', f"user/repository_invitations/{inv['id']}")
            return True
    return False


def can_push() -> bool:
    try:
        return gh('api', f'repos/{DATA_REPO}', '--jq', '.permissions.push').strip() == 'true'
    except UploadError:
        return False


# ---------------------------------------------------------------- uploading
def blob_sha(data: bytes) -> str:
    """The SHA GitHub reports for a file with this content."""
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def remote_sha(dest: str) -> Optional[str]:
    try:
        return gh('api', f'repos/{DATA_REPO}/contents/{dest}', '--jq', '.sha').strip()
    except UploadError as e:
        if 'HTTP 404' in str(e):
            return None
        raise


def put_file(dest: str, data: bytes, message: str, attempts: int = 6) -> None:
    """Create or update dest in the data repository. Retries when many students upload at once."""
    for attempt in range(attempts):
        sha = remote_sha(dest)
        if sha == blob_sha(data):
            return
        body = {'message': message, 'content': base64.b64encode(data).decode()}
        if sha:
            body['sha'] = sha
        try:
            gh('api', '--method', 'PUT', f'repos/{DATA_REPO}/contents/{dest}', '--input', '-',
               input_text=json.dumps(body))
            return
        except UploadError as e:
            if 'HTTP 404' in str(e):
                raise UploadError(f"No access to {DATA_REPO}. Run setup_student.py (it accepts your "
                                  "invitation), or ask your instructor to invite your GitHub username.")
            if attempt == attempts - 1 or not re.search(r'HTTP (409|422|5\d\d)', str(e)):
                raise
        time.sleep((1 + random.random()) * (attempt + 1))


def destination(path: Path) -> str:
    """visual/<file> for a class session; demo/visual/<file> for a shortened test run."""
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise UploadError(f"{path.name} has no trials yet.")
    block1 = [r['trial_type'] for r in rows if r['block'] == '1']
    full = (rows[0]['n_blocks'] == str(FULL_BLOCKS)
            and ('reveal' not in block1 or block1.count('pre') == FULL_PRE_TRIALS))
    return f"{'' if full else 'demo/'}{rows[0]['modality']}/{path.name}"


def upload(path: Path) -> str:
    """Upload one session file; returns where it went in the repository. Safe to repeat."""
    path = Path(path)
    dest = destination(path)
    put_file(dest, path.read_bytes(), f"Add {path.name}")
    log = path.parent / UPLOAD_LOG
    if path.name not in uploaded_names(path.parent):
        with open(log, 'a') as f:
            f.write(path.name + '\n')
    return dest


def uploaded_names(data_dir: Path) -> set:
    try:
        return set((Path(data_dir) / UPLOAD_LOG).read_text().split())
    except OSError:
        return set()


def pending(data_dir: Path = DATA_DIR) -> List[Path]:
    done = uploaded_names(data_dir)
    return [p for p in sorted(Path(data_dir).glob('*_Experiment_*.csv')) if p.name not in done]


def upload_pending(data_dir: Path = DATA_DIR) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Upload every session file not uploaded yet. Returns (destinations, [(file, error)])."""
    done, failed = [], []
    for path in pending(data_dir):
        try:
            done.append(upload(path))
        except UploadError as e:
            failed.append((path.name, str(e)))
    return done, failed
