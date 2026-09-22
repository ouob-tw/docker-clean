from dataclasses import replace

import pytest

from docker_clean.config import CleanError
from docker_clean.engine import Docker, Image, Reference
from docker_clean.whitelist import delete_selected, matching_ids


def test_matching_is_or_full_tag_search_and_untagged_matches_none():
    images = {str(i): Image(str(i), tags, 1, "2026-01-01") for i, tags in enumerate([
        ("registry:5000/app:1.2", "alias:latest"), ("db:2",), (), ("keep:1",)])}
    assert matching_ids("^alias:\n^db:2$\n\n", images) == {"0", "1"}
    assert matching_ids(" ", images) == set()
    assert matching_ids(".*", images) == {"0", "1", "2", "3"}
    assert matching_ids("^None$", images) == {"2"}
    assert matching_ids("^None$\n^db:2$", images) == {"1", "2"}
    assert images["2"].tags == ()
    with pytest.raises(CleanError, match="第 2 行"):
        matching_ids(".*\n[", images)


def test_force_delete_uses_full_id_force_and_no_prune(monkeypatch):
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/unused.sock")
    docker = Docker()
    calls = []
    monkeypatch.setattr(docker, "call", lambda *args: calls.append(args) or "")
    image_id = "sha256:" + "a" * 64
    docker.forceDeleteImage(image_id)
    assert calls == [("image", "rm", "--no-prune", "--force", image_id)]


@pytest.mark.parametrize("change", ["missing", "tags", "references", "query", "delete"])
def test_changed_or_failed_targets_never_expand_selection(change):
    original = Image("sha256:a", ("app:1",), 1, "2026-01-01")
    calls = []
    class FakeDocker:
        def snapshot(self):
            if change == "query":
                raise CleanError("query failed")
            image = original
            if change == "tags":
                image = replace(image, tags=("new:1",))
            if change == "references":
                image = replace(image, references=(Reference("c", "new", "running"),))
            return {} if change == "missing" else {image.id: image}

        def forceDeleteImage(self, image_id):
            calls.append(image_id)
            raise CleanError("delete failed")

    result = delete_selected((original,), FakeDocker())
    assert result[0].status == ("失敗" if change in {"query", "delete"} else "跳過")
    assert calls == ([original.id] if change == "delete" else [])


def test_individual_delete_failure_continues_only_confirmed_ids():
    images = tuple(Image(f"sha256:{i}", (f"app:{i}",), 1, "2026-01-01") for i in range(3))
    calls = []
    class FakeDocker:
        def snapshot(self):
            return {image.id: image for image in images}

        def forceDeleteImage(self, image_id):
            calls.append(image_id)
            if image_id == images[0].id:
                raise CleanError("conflict")
            return f"Untagged: app:1\nDeleted: {image_id}"

    results = delete_selected(images[:2], FakeDocker())
    assert calls == [images[0].id, images[1].id]
    assert [result.status for result in results] == ["失敗", "移除 tag", "刪除 image"]
