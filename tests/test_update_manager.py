import sys
import os
import json
import tempfile
import subprocess

import pytest

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.update_manager import UpdateManager


class DummyResponse:
    def __init__(self, data_bytes: bytes):
        self._data = data_bytes

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_check_for_updates_new_version(monkeypatch):
    um = UpdateManager("1.0.0")

    payload = {"version": "1.0.1", "download_url": "http://example.com/foo.exe", "release_notes": "notes"}
    resp = DummyResponse(json.dumps(payload).encode('utf-8'))

    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: resp)

    assert um.check_for_updates(timeout=1) is True
    assert um.update_available is True
    assert um.new_version == "1.0.1"


def test_check_for_updates_no_update(monkeypatch):
    um = UpdateManager("1.2.0")
    payload = {"version": "1.1.9"}
    resp = DummyResponse(json.dumps(payload).encode('utf-8'))
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: resp)

    assert um.check_for_updates(timeout=1) is False


def test_download_update_and_apply(monkeypatch, tmp_path):
    um = UpdateManager("1.0.0")
    um.download_url = "http://example.com/fake.exe"
    um.new_version = "2.0.0"

    # Stub urlretrieve to actually create the file
    def fake_urlretrieve(url, filename, reporthook=None):
        with open(filename, 'wb') as f:
            f.write(b'FAKE')
        return (str(filename), None)

    monkeypatch.setattr('urllib.request.urlretrieve', fake_urlretrieve)

    path = um.download_update()
    assert path is not None
    assert os.path.exists(path)

    # Test apply_update: simulate Windows startfile and ensure sys.exit is called
    exe_path = path

    # Windows branch
    monkeypatch.setattr(sys, 'platform', 'win32', raising=False)
    started = {}

    def fake_startfile(p):
        started['p'] = p

    monkeypatch.setattr(os, 'startfile', fake_startfile, raising=False)

    # Simulate frozen executable environment so apply_update proceeds
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    # Replace sys.exit to raise SystemExit so we can assert it
    monkeypatch.setattr(sys, 'exit', lambda code=0: (_ for _ in ()).throw(SystemExit(code)), raising=False)

    with pytest.raises(SystemExit):
        um.apply_update(exe_path)
    assert started.get('p') == exe_path

    # POSIX branch: ensure subprocess.Popen called
    monkeypatch.setattr(sys, 'platform', 'linux', raising=False)
    called = {}

    class FakePopen:
        def __init__(self, args):
            called['args'] = args

    monkeypatch.setattr(subprocess, 'Popen', FakePopen)
    # Ensure frozen for POSIX branch as well
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'exit', lambda code=0: (_ for _ in ()).throw(SystemExit(code)), raising=False)

    with pytest.raises(SystemExit):
        um.apply_update(exe_path)

    assert called.get('args') is not None
