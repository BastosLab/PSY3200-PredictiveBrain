"""
Uploading session files to the class repository on GitHub, through the GitHub CLI (`gh`)
with each student's own login, so every upload is credited to the student's GitHub account.

The task code is on `main`, where changes need a code owner's approval. The data are on the
`class-data` branch of the same repository, which students push to directly (it cannot be
deleted or force-pushed): class_data/<modality>/ for full sessions, class_data/demo/<modality>/
for shortened test runs (the class analysis skips them). A file counts as uploaded once the
branch has it with the same content, so uploading again never duplicates anything.
"""
import base64
import csv
import hashlib
import io
import json
import random
import re
import shutil
import subprocess
import tarfile
import time
import unicodedata
from pathlib import Path
from typing import List, Optional, Tuple

REPO = 'BastosLab/PSY3200-PredictiveBrain'
DATA_BRANCH = 'class-data'                              # branch that holds the data
CLASS_DATA = 'class_data'                               # folder on that branch
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


def api(method: str, path: str, body: Optional[dict] = None):
    """One GitHub REST call; returns the parsed JSON answer."""
    args = ['api', '--method', method, path]
    out = gh(*args, '--input', '-', input_text=json.dumps(body)) if body is not None else gh(*args)
    return json.loads(out) if out.strip() else {}


def github_login() -> str:
    try:
        return gh('api', 'user', '--jq', '.login').strip()
    except UploadError as e:
        raise UploadError(f"Not signed in to GitHub ({e}). Run setup_student.py.")


def accept_invitation() -> bool:
    """Accept a pending invitation to the class repository. True if there was one."""
    for inv in api('GET', 'user/repository_invitations'):
        if inv['repository']['full_name'].lower() == REPO.lower():
            api('PATCH', f"user/repository_invitations/{inv['id']}")
            return True
    return False


def can_push() -> bool:
    try:
        return gh('api', f'repos/{REPO}', '--jq', '.permissions.push').strip() == 'true'
    except UploadError:
        return False


# ---------------------------------------------------------------- uploading
def blob_sha(data: bytes) -> str:
    """The SHA GitHub reports for a file with this content."""
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def remote_sha(dest: str, ref: str = DATA_BRANCH) -> Optional[str]:
    try:
        return gh('api', f'repos/{REPO}/contents/{dest}?ref={ref}', '--jq', '.sha').strip()
    except UploadError as e:
        if 'HTTP 404' in str(e):
            return None
        raise


def put_file(dest: str, data: bytes, message: str, attempts: int = 6) -> None:
    """Create or update dest on the class-data branch. Retries when many students upload at once."""
    for attempt in range(attempts):
        sha = remote_sha(dest)
        if sha == blob_sha(data):
            return
        body = {'message': message, 'content': base64.b64encode(data).decode(), 'branch': DATA_BRANCH}
        if sha:
            body['sha'] = sha
        try:
            api('PUT', f'repos/{REPO}/contents/{dest}', body)
            return
        except UploadError as e:
            if re.search(r'HTTP 40[34]', str(e)):
                raise UploadError(f"No permission to upload to {REPO}. Run setup_student.py (it accepts your "
                                  "invitation), or ask your instructor to invite your GitHub username.")
            if attempt == attempts - 1 or not re.search(r'HTTP (409|422|5\d\d)', str(e)):
                raise
        time.sleep((1 + random.random()) * (attempt + 1))


def download_class_data(dest: Path) -> Path:
    """Copy everyone's latest files from the class-data branch into dest (replacing what was there)."""
    exe = shutil.which('gh')
    if exe is None:
        raise UploadError("The GitHub CLI (gh) is not installed. See 'Before the first class' in the README.")
    r = subprocess.run([exe, 'api', f'repos/{REPO}/tarball/{DATA_BRANCH}'], capture_output=True, timeout=300)
    if r.returncode != 0:
        raise UploadError(r.stderr.decode(errors='replace').strip() or "download failed")
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts      # <repo>-<commit>/class_data/visual/<file>
            if member.isfile() and len(parts) > 2 and parts[1] == CLASS_DATA and '..' not in parts:
                target = dest.joinpath(*parts[2:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    return dest


def destination(path: Path) -> str:
    """class_data/visual/<file> for a class session; class_data/demo/visual/<file> for a test run."""
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise UploadError(f"{path.name} has no trials yet.")
    block1 = [r['trial_type'] for r in rows if r['block'] == '1']
    full = (rows[0]['n_blocks'] == str(FULL_BLOCKS)
            and ('reveal' not in block1 or block1.count('pre') == FULL_PRE_TRIALS))
    return f"{CLASS_DATA}/{'' if full else 'demo/'}{rows[0]['modality']}/{path.name}"


def upload(path: Path) -> str:
    """Upload one session file; returns where it went in the repository. Safe to repeat."""
    path = Path(path)
    dest = destination(path)
    put_file(dest, path.read_bytes(), f"Add {path.name}")
    if path.name not in uploaded_names(path.parent):
        with open(path.parent / UPLOAD_LOG, 'a') as f:
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
