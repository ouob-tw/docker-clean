from dataclasses import replace

import pytest

from docker_clean.config import CleanError, Config, save
from docker_clean.engine import Image, Reference
from docker_clean.plan import execute, plan, render_results


IMAGE = Image("sha256:" + "a" * 64, ("a:1", "b:2"), 5, "today")


class FakeDocker:
    def __init__(self, image=IMAGE):
        self.image = image
        self.calls = []
        self.error = False

    def snapshot(self):
        if self.error:
            raise CleanError("permission denied")
        return {self.image.id: self.image}

    def remove(self, target, force):
        self.calls.append((target, force))
        self.image = replace(self.image, tags=tuple(t for t in self.image.tags if t != target))
        return f"Untagged: {target}\n" + ("Deleted: sha256:abc\n" if not self.image.tags else "")


def setup(tmp_path, config):
    path = tmp_path / "config.yaml"
    revision = save(path, config, None)
    return path, plan(config, {IMAGE.id: IMAGE}, revision)


def test_tag_mode_rechecks_with_expected_successful_untags(tmp_path):
    path, preview = setup(tmp_path, Config((), True, True))
    docker = FakeDocker()
    results = execute(preview, path, docker)
    assert docker.calls == [("a:1", True), ("b:2", True)]
    assert [r.status for r in results] == ["移除 tag", "移除 tag", "刪除 image"]


@pytest.mark.parametrize("change", ["tag", "reference", "id", "config", "query"])
def test_changes_fail_closed(tmp_path, change):
    path, preview = setup(tmp_path, Config((), True, True))
    docker = FakeDocker()
    if change == "tag":
        docker.image = replace(IMAGE, tags=("protect:1",))
    elif change == "reference":
        docker.image = replace(IMAGE, references=(Reference("c", "running", "running"),))
    elif change == "id":
        docker.image = replace(IMAGE, id="sha256:new")
    elif change == "config":
        path.write_text("keep: ['a']")
    else:
        docker.error = True
    results = execute(preview, path, docker)
    assert not docker.calls
    assert results[0].status in {"跳過", "失敗"}


def test_individual_failure_never_upgrades_force(tmp_path):
    path, preview = setup(tmp_path, Config((), True, False))
    docker = FakeDocker()
    def remove(target, force):
        docker.calls.append((target, force))
        raise CleanError("conflict")
    docker.remove = remove
    results = execute(preview, path, docker)
    assert docker.calls == [("a:1", False), ("b:2", False)]
    assert "失敗" in render_results(results)
