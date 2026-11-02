"""
Uploading to the class data repository, against a fake GitHub (no network):
    python -m pytest tests/test_upload.py
"""
import base64
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import class_repo  # noqa: E402
from class_repo import UploadError  # noqa: E402


class FakeGitHub:
    """Answers the `gh api` calls class_repo makes, keeping files in a dict."""

    def __init__(self, conflicts=0, access=True):
        self.files, self.puts, self.conflicts, self.access = {}, 0, conflicts, access

    def __call__(self, *args, input_text=None, timeout=60):
        if args[:3] == ('api', '--method', 'PUT'):
            path = args[3].split('/contents/')[1]
            if not self.access:
                raise UploadError('gh: Not Found (HTTP 404)')
            if self.conflicts:                     # someone else committed at the same moment
                self.conflicts -= 1
                raise UploadError('gh: main is at 1a2b but expected 3c4d (HTTP 409)')
            body = json.loads(input_text)
            if path in self.files and body.get('sha') != class_repo.blob_sha(self.files[path]):
                raise UploadError('gh: "sha" wasn\'t supplied. (HTTP 422)')
            self.files[path] = base64.b64decode(body['content'])
            self.puts += 1
            return '{}'
        if args[0] == 'api' and '/contents/' in args[1]:
            path = args[1].split('/contents/')[1]
            if path not in self.files:
                raise UploadError('gh: Not Found (HTTP 404)')
            return class_repo.blob_sha(self.files[path]) + '\n'
        raise AssertionError(f"unexpected gh call {args}")


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(class_repo, 'gh', fake)
    monkeypatch.setattr(class_repo.time, 'sleep', lambda s: None)
    return fake


def session_file(folder, name, modality='visual', n_blocks=10, pre=24, blocks_done=None, partial=None):
    """A session file with just the columns the upload looks at."""
    rows = []
    for b in range(1, (blocks_done or n_blocks) + 1):
        rows += [dict(modality=modality, n_blocks=n_blocks, block=b, trial_type=t)
                 for t in ['pre'] * pre + ['reveal'] + ['post'] * pre]
    rows = rows[:partial] if partial else rows
    path = Path(folder) / name
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['modality', 'n_blocks', 'block', 'trial_type'])
        w.writeheader()
        w.writerows(rows)
    return path


def test_clean_name():
    assert class_repo.clean_name('André  bastos') == 'AndreBastos'
    assert class_repo.clean_name("Jane O'Brien") == 'JaneOBrien'
    assert class_repo.clean_name('  ') == ''


def test_destination(tmp_path):
    full = session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    short = session_file(tmp_path, 'Visual_Mooney_Experiment_B_1.csv', n_blocks=2)
    fewer_reps = session_file(tmp_path, 'Audio_SineWaveSpeech_Experiment_C_1.csv', 'audio', pre=12)
    quit_early = session_file(tmp_path, 'Audio_SineWaveSpeech_Experiment_D_1.csv', 'audio', partial=10)
    assert class_repo.destination(full) == 'visual/Visual_Mooney_Experiment_A_1.csv'
    assert class_repo.destination(short) == 'demo/visual/Visual_Mooney_Experiment_B_1.csv'
    assert class_repo.destination(fewer_reps) == 'demo/audio/Audio_SineWaveSpeech_Experiment_C_1.csv'
    assert class_repo.destination(quit_early) == 'audio/Audio_SineWaveSpeech_Experiment_D_1.csv'


def test_uploads_each_file_once(tmp_path, github):
    session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    session_file(tmp_path, 'Audio_SineWaveSpeech_Experiment_A_2.csv', 'audio')
    done, failed = class_repo.upload_pending(tmp_path)
    assert not failed and sorted(github.files) == ['audio/Audio_SineWaveSpeech_Experiment_A_2.csv',
                                                   'visual/Visual_Mooney_Experiment_A_1.csv']
    assert class_repo.pending(tmp_path) == [] and class_repo.upload_pending(tmp_path) == ([], [])
    (tmp_path / class_repo.UPLOAD_LOG).unlink()          # log lost: same content is not uploaded again
    class_repo.upload_pending(tmp_path)
    assert github.puts == 2


def test_retries_when_many_students_upload_at_once(tmp_path, github):
    github.conflicts = 3
    session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    done, failed = class_repo.upload_pending(tmp_path)
    assert done and not failed and github.puts == 1


def test_no_access_keeps_file_pending(tmp_path, github):
    github.access = False
    path = session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    done, failed = class_repo.upload_pending(tmp_path)
    assert done == [] and 'No access' in failed[0][1]
    assert class_repo.pending(tmp_path) == [path]
