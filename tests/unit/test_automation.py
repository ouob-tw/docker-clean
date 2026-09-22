"""Public CLI behavior with a fake Docker boundary; no real deletion evidence."""
import json
import sys
from dataclasses import replace

import pytest

from docker_clean import automation
from docker_clean.config import CleanError
from docker_clean.engine import Image, Reference


@pytest.fixture
def run(monkeypatch, capsys):
    class FakeDocker:
        images = {
            "a": Image("a", ("app:dev", "app:stable"), 1, "today"),
            "b": Image("b", ("other:dev",), 1, "today"),
            "c": Image("c", (), 1, "today"),
        }
        calls = []
        snapshots = 0
        change = False
        query_error = False
        delete_error = False

        def snapshot(self):
            self.snapshots += 1
            if self.snapshots > 1 and self.query_error:
                raise CleanError("query failed")
            if self.snapshots > 1 and self.change:
                return {key: replace(value, tags=("new:protected",)) for key, value in self.images.items()}
            return self.images

        def remove(self, target, force):
            self.calls.append((target, force))
            if self.delete_error:
                raise CleanError("delete failed")
            return "Deleted: " + target

    docker = FakeDocker()
    monkeypatch.setattr(automation, "Docker", lambda: docker)
    def invoke(*args):
        monkeypatch.setattr(sys, "argv", ["dcl", "image", "clean", "--json", *args])
        code = automation.main()
        output = capsys.readouterr()
        assert not output.err
        return code, json.loads(output.out)
    return docker, invoke


def test_default_preview_and_keep_priority(run):
    docker, invoke = run
    code, payload = invoke("--delete", "dev", "--keep", "stable")
    assert code == 0 and payload["mode"] == "preview"
    assert [e["image"]["id"] for e in payload["entries"] if e["targets"]] == ["b"]
    assert not docker.calls


def test_keep_only_and_repeated_rules(run):
    docker, invoke = run
    code, payload = invoke("--keep", "stable", "--keep", "other", "--yes")
    assert code == 0 and docker.calls == [("c", False)]


def test_delete_multiple_rules_and_none(run):
    docker, invoke = run
    code, payload = invoke("--delete", "^None$", "--delete", "^other:", "--yes")
    assert code == 0 and docker.calls == [("b", False), ("c", False)]


@pytest.mark.parametrize("args", [(), ("--keep", ""), ("--delete", " "),
                                  ("--delete", "["), ("--keep", "[")])
def test_invalid_rules_never_connect(run, args):
    docker, invoke = run
    code, payload = invoke(*args, "--yes")
    assert code == 1 and not payload["ok"]
    assert docker.snapshots == 0 and not docker.calls


@pytest.mark.parametrize("force", [False, True])
def test_container_reference_requires_explicit_force(run, force):
    docker, invoke = run
    docker.images = {"a": replace(docker.images["a"], references=(Reference("c", "used", "exited"),))}
    args = ["--force"] if force else []
    code, payload = invoke("--delete", ".*", "--yes", *args)
    assert code == 0
    assert docker.calls == ([("a", True)] if force else [])


@pytest.mark.parametrize("failure", ["change", "query_error", "delete_error"])
def test_execution_rechecks_and_reports_failures(run, failure):
    docker, invoke = run
    setattr(docker, failure, True)
    code, payload = invoke("--delete", ".*", "--yes")
    assert code == (0 if failure == "change" else 1)
    if failure != "delete_error":
        assert not docker.calls
    else:
        assert len(docker.calls) == 3
    assert payload["results"]


def test_no_match_is_successful_noop(run):
    docker, invoke = run
    code, payload = invoke("--delete", "^absent$", "--yes")
    assert code == 0 and not docker.calls
