"""
Uploading to class_data/ in the class repository, against a fake GitHub (no network):
    python -m pytest tests/test_upload.py
"""
import base64
import csv
import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import class_repo  # noqa: E402
from class_repo import UploadError  # noqa: E402


class FakeGitHub:
    """Answers the `gh api` calls class_repo makes: branches, files, pull requests, merges."""

    def __init__(self, access=True, unmergeable=0):
        self.branches = {'main': {}}
        self.pulls = {}
        self.merges = 0
        self.access = access
        self.unmergeable = unmergeable          # merges that fail first, as when many upload at once

    def __call__(self, *args, input_text=None, timeout=60):
        args = list(args)
        jq = args.pop(args.index('--jq') + 1) if '--jq' in args else None
        if '--input' in args:
            del args[args.index('--input'):args.index('--input') + 2]
        if args[1] == '--method':
            method, path = args[2], args[3]
        else:
            method, path = 'GET', args[1]
        path, _, query = path.partition('?')
        result = self.handle(method, path.replace(f'repos/{class_repo.REPO}/', ''), dict(parse_qsl(query)),
                             json.loads(input_text) if input_text else {})
        return {'.sha': lambda r: r['sha'], '.login': lambda r: r['login']}.get(jq, json.dumps)(result) + '\n'

    def handle(self, method, path, query, body):
        def fail(code):
            raise UploadError(f'gh: error (HTTP {code})')

        if path == 'user':
            return {'login': 'student'}
        if path == 'git/ref/heads/main':
            return {'object': {'sha': 'abc123'}}
        if method == 'POST' and path == 'git/refs':
            if not self.access:
                fail(404)
            branch = body['ref'].removeprefix('refs/heads/')
            if branch in self.branches:
                fail(422)
            self.branches[branch] = dict(self.branches['main'])
            return {}
        if method == 'DELETE' and path.startswith('git/refs/heads/'):
            self.branches.pop(path.removeprefix('git/refs/heads/'))
            return {}
        if path.startswith('contents/'):
            dest = path.removeprefix('contents/')
            if method == 'GET':
                files = self.branches[query.get('ref', 'main')]
                if dest not in files:
                    fail(404)
                return {'sha': class_repo.blob_sha(files[dest])}
            files = self.branches[body['branch']]
            if dest in files and body.get('sha') != class_repo.blob_sha(files[dest]):
                fail(422)
            files[dest] = base64.b64decode(body['content'])
            return {}
        if path == 'pulls' and method == 'POST':
            if any(p['head'] == body['head'] and p['state'] == 'open' for p in self.pulls.values()):
                fail(422)
            number = len(self.pulls) + 1
            self.pulls[number] = {'head': body['head'], 'state': 'open', 'number': number}
            return {'number': number}
        if path == 'pulls':
            head = query['head'].split(':', 1)[1]
            return [p for p in self.pulls.values() if p['head'] == head and p['state'] == query['state']]
        if path.endswith('/merge'):
            if self.unmergeable:
                self.unmergeable -= 1
                fail(405)
            pull = self.pulls[int(path.split('/')[1])]
            self.branches['main'].update(self.branches[pull['head']])
            pull['state'] = 'merged'
            self.merges += 1
            return {}
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(class_repo, 'gh', fake)
    monkeypatch.setattr(class_repo.time, 'sleep', lambda s: None)
    return fake


def session_file(folder, name, modality='visual', n_blocks=10, pre=24, partial=None):
    """A session file with just the columns the upload looks at."""
    rows = []
    for b in range(1, n_blocks + 1):
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
    assert class_repo.destination(full) == 'class_data/visual/Visual_Mooney_Experiment_A_1.csv'
    assert class_repo.destination(short) == 'class_data/demo/visual/Visual_Mooney_Experiment_B_1.csv'
    assert class_repo.destination(fewer_reps) == 'class_data/demo/audio/Audio_SineWaveSpeech_Experiment_C_1.csv'
    assert class_repo.destination(quit_early) == 'class_data/audio/Audio_SineWaveSpeech_Experiment_D_1.csv'


def test_uploads_each_file_once_through_a_merged_pull_request(tmp_path, github):
    session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    session_file(tmp_path, 'Audio_SineWaveSpeech_Experiment_A_2.csv', 'audio')
    done, failed = class_repo.upload_pending(tmp_path)
    assert not failed and sorted(github.branches['main']) == [
        'class_data/audio/Audio_SineWaveSpeech_Experiment_A_2.csv',
        'class_data/visual/Visual_Mooney_Experiment_A_1.csv']
    assert list(github.branches) == ['main'] and github.merges == 2      # upload branches deleted
    assert class_repo.pending(tmp_path) == [] and class_repo.upload_pending(tmp_path) == ([], [])
    (tmp_path / class_repo.UPLOAD_LOG).unlink()          # log lost: same content is not uploaded again
    class_repo.upload_pending(tmp_path)
    assert github.merges == 2


def test_retries_merge_when_many_students_upload_at_once(tmp_path, github):
    github.unmergeable = 3
    session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    done, failed = class_repo.upload_pending(tmp_path)
    assert done and not failed and github.merges == 1


def test_finishes_an_upload_interrupted_before_the_merge(tmp_path, github):
    path = session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    github.unmergeable = 99                              # first try: branch and PR made, merge fails
    assert class_repo.upload_pending(tmp_path)[1]
    github.unmergeable = 0                               # next try reuses the branch and the open PR
    assert class_repo.upload_pending(tmp_path) == ([class_repo.destination(path)], [])
    assert len(github.pulls) == 1 and github.merges == 1


def test_no_access_keeps_file_pending(tmp_path, github):
    github.access = False
    path = session_file(tmp_path, 'Visual_Mooney_Experiment_A_1.csv')
    done, failed = class_repo.upload_pending(tmp_path)
    assert done == [] and 'No permission' in failed[0][1]
    assert class_repo.pending(tmp_path) == [path]
