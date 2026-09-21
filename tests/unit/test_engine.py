import subprocess

import pytest

from docker_clean.config import CleanError
from docker_clean.engine import Docker


@pytest.mark.parametrize("host", ["tcp://127.0.0.1:2375", "ssh://user@remote", "tcp://remote:2376"])
def test_non_unix_endpoint_refused(monkeypatch, host):
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setenv("DOCKER_HOST", host)
    with pytest.raises(CleanError, match="拒絕"):
        Docker()


def test_context_precedence_and_endpoint_pinned(monkeypatch):
    monkeypatch.setenv("DOCKER_CONTEXT", "selected")
    monkeypatch.setenv("DOCKER_HOST", "ssh://ignored")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs["env"]))
        return subprocess.CompletedProcess(args, 0,
            '[{"Endpoints":{"docker":{"Host":"unix:///tmp/test.sock"}}}]' if "context" in args else "", "")
    monkeypatch.setattr(subprocess, "run", run)
    docker = Docker()
    monkeypatch.setenv("DOCKER_HOST", "ssh://changed")
    docker.remove("tag:1", False)
    assert calls[0][0] == ["docker", "context", "inspect", "selected"]
    assert calls[1][0] == ["docker", "--host", "unix:///tmp/test.sock", "image", "rm", "--no-prune", "tag:1"]
    assert "DOCKER_CONTEXT" not in calls[1][1]


def test_snapshot_batches_inspect_and_tolerates_missing_container_image(monkeypatch):
    import json
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/fake.sock")
    docker = Docker()
    calls = []
    def call(*args):
        calls.append(args)
        if args[:2] == ("image", "ls"):
            return "\n".join(f"sha256:{i}" for i in range(205))
        if args[:2] == ("container", "ls"):
            return "cid"
        if args[0] == "container":
            return json.dumps([{"Image": "sha256:absent", "Id": "cid", "Name": "/old", "State": {"Status": "exited"}}])
        return json.dumps([{"Id": id, "RepoTags": [], "Size": 1, "Created": "now"} for id in args[2:]])
    monkeypatch.setattr(docker, "call", call)
    assert len(docker.snapshot()) == 205
    assert len(calls) == 6
    assert max(len(args) - 2 for args in calls if args[1] == "inspect") == 100
