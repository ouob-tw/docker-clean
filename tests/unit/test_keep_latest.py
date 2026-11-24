import pytest

from docker_clean.config import CleanError, Config, load, save
from docker_clean.engine import Image, Reference
from docker_clean.plan import plan, render


def image(n: int, *tags: str, created: str | None = None, refs=()) -> Image:
    return Image("sha256:" + f"{n:064x}", tags, 1, created or f"2026-11-{n:02d}T00:00:00Z", refs)


def actions(config: Config, *images: Image) -> dict[str, str]:
    preview = plan(config, {i.id: i for i in images})
    return {", ".join(e.image.tags): e.action for e in preview.entries}


RULE = Config(remove_tags=True, keep_latest=(("rollback", 2),))


def test_keeps_newest_n_per_repository_and_releases_older():
    result = actions(RULE, image(1, "app:rollback-a"), image(2, "app:rollback-b"),
                     image(3, "app:rollback-c"), image(4, "web:rollback-a"))
    assert result == {"app:rollback-a": "移除 tag", "app:rollback-b": "保留",
                      "app:rollback-c": "保留", "web:rollback-a": "保留"}


def test_counts_images_not_tags():
    # Two rollback tags on one image count once; the older image falls outside the newest 2.
    result = actions(RULE, image(1, "app:rollback-old"),
                     image(2, "app:rollback-gpu0", "app:rollback-gpu1"), image(3, "app:rollback-new"))
    assert result["app:rollback-old"] == "移除 tag"
    assert result["app:rollback-gpu0, app:rollback-gpu1"] == "保留"


def test_registry_port_is_part_of_repository():
    result = actions(Config(keep_latest=(("rollback", 1),), remove_tags=True),
                     image(1, "registry:5000/app:rollback-a"), image(2, "registry:5000/app:rollback-b"))
    assert result == {"registry:5000/app:rollback-a": "移除 tag",
                      "registry:5000/app:rollback-b": "保留"}


def test_compares_creation_time_across_timezones():
    older = image(1, "app:rollback-a", created="2026-11-02T07:00:00+08:00")  # 2026-11-01T23:00Z
    newer = image(2, "app:rollback-b", created="2026-11-02T00:00:00.123456789Z")
    result = actions(Config(keep_latest=(("rollback", 1),), remove_tags=True), older, newer)
    assert result == {"app:rollback-a": "移除 tag", "app:rollback-b": "保留"}


def test_unknown_creation_time_is_kept():
    result = actions(Config(keep_latest=(("rollback", 1),), remove_tags=True),
                     image(1, "app:rollback-a", created="today"), image(2, "app:rollback-b"))
    assert result["app:rollback-a"] == "保留"


def test_plain_keep_still_wins_and_older_follows_normal_rules():
    referenced = image(1, "app:rollback-a", refs=(Reference("cid", "c", "exited"),))
    config = Config(keep=(":stable$",), remove_tags=True, keep_latest=(("rollback", 1),))
    result = actions(config, referenced, image(2, "app:rollback-b", "app:stable"),
                     image(3, "app:rollback-c"))
    assert result == {"app:rollback-a": "跳過", "app:rollback-b, app:stable": "保留",
                      "app:rollback-c": "保留"}


def test_reason_and_heading_mention_rule():
    preview = plan(RULE, {i.id: i for i in (image(1, "app:rollback-a"),)})
    assert "最新 2 個" in preview.entries[0].reason
    assert "沒有保留規則" not in render(preview)


def test_config_roundtrip(tmp_path):
    path = tmp_path / "images.yaml"
    config = Config(("^db:",), keep_latest=(("rollback", 3),), unused_days=7)
    revision = save(path, config, None)
    assert load(path) == (config, revision)
    path.write_text("keep: []\nkeep_latest:\n- match: rollback\n  count: 3\n")
    assert load(path)[0].keep_latest == (("rollback", 3),)


@pytest.mark.parametrize("text", [
    "keep_latest: {}", "keep_latest: [rollback]", "keep_latest: [{match: rollback}]",
    "keep_latest: [{match: rollback, count: 0}]", "keep_latest: [{match: rollback, count: true}]",
    "keep_latest: [{match: rollback, count: '3'}]", "keep_latest: [{match: '', count: 3}]",
    "keep_latest: [{match: '[', count: 3}]", "keep_latest: [{match: 1, count: 3}]",
    "keep_latest: [{match: rollback, count: 3, extra: 1}]",
])
def test_invalid_keep_latest_fails_closed(tmp_path, text):
    path = tmp_path / "images.yaml"
    path.write_text("keep: []\n" + text)
    with pytest.raises(CleanError):
        load(path)
