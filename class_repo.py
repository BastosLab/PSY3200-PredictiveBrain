"""
Uploading session files to class_data/ in the class repository on GitHub, through the
GitHub CLI (`gh`) with each student's own login, so every upload is credited to the
student's GitHub account.

The main branch only accepts changes through pull requests, and changes to the task code
need approval from a code owner (.github/CODEOWNERS). class_data/ has no code owner, so an
upload is a pull request that merges at once: branch -> add the file -> pull request ->
merge -> delete the branch.

Files go to class_data/<modality>/ (full sessions) or class_data/demo/<modality>/
(shortened test runs, which the class analysis skips). A file counts as uploaded once
main has it with the same content, so uploading again never duplicates anything.
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

REPO = 'BastosLab/PSY3200-PredictiveBrain'
CLASS_DATA = 'class_data'                               # folder in the repository
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


def remote_sha(dest: str, ref: str = 'main') -> Optional[str]:
    try:
        return gh('api', f'repos/{REPO}/contents/{dest}?ref={ref}', '--jq', '.sha').strip()
    except UploadError as e:
        if 'HTTP 404' in str(e):
            return None
        raise


def retry(call, attempts: int = 6, retry_on: str = r'HTTP (405|409|5\d\d)'):
    """Retry when many students upload at the same moment (or GitHub is still checking a merge)."""
    for attempt in range(attempts):
        try:
            return call()
        except UploadError as e:
            if attempt == attempts - 1 or not re.search(retry_on, str(e)):
                raise
        time.sleep((1 + random.random()) * (attempt + 1))


def put_file(dest: str, data: bytes, message: str) -> None:
    """Add or update dest on main with a pull request that is merged at once."""
    if remote_sha(dest) == blob_sha(data):
        return
    branch = f"upload/{github_login()}/{Path(dest).stem}"

    main = api('GET', f'repos/{REPO}/git/ref/heads/main')['object']['sha']
    try:
        api('POST', f'repos/{REPO}/git/refs', {'ref': f'refs/heads/{branch}', 'sha': main})
    except UploadError as e:
        if re.search(r'HTTP 40[34]', str(e)):
            raise UploadError(f"No permission to upload to {REPO}. Run setup_student.py (it accepts your "
                              "invitation), or ask your instructor to invite your GitHub username.")
        if 'HTTP 422' not in str(e):            # 422: the branch is left over from an earlier try
            raise

    sha = remote_sha(dest, ref=branch)
    if sha != blob_sha(data):
        body = {'message': message, 'content': base64.b64encode(data).decode(), 'branch': branch}
        if sha:
            body['sha'] = sha
        api('PUT', f'repos/{REPO}/contents/{dest}', body)

    try:
        number = api('POST', f'repos/{REPO}/pulls', {'title': message, 'head': branch, 'base': 'main',
                                                       'body': 'Uploaded by the task (class_repo.py).'})['number']
    except UploadError as e:                     # 422: a pull request for this branch is already open
        if 'HTTP 422' not in str(e):
            raise
        open_prs = api('GET', f"repos/{REPO}/pulls?head={REPO.split('/')[0]}:{branch}&state=open")
        if not open_prs:
            raise
        number = open_prs[0]['number']
    retry(lambda: api('PUT', f'repos/{REPO}/pulls/{number}/merge', {'merge_method': 'squash'}))
    try:
        api('DELETE', f'repos/{REPO}/git/refs/heads/{branch}')
    except UploadError:
        pass                                     # only tidying up


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
