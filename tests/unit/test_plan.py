from dataclasses import replace
from itertools import product

import pytest

from docker_clean.config import Config
from docker_clean.engine import Image, Reference
from docker_clean.plan import plan, render


BASE = Image("sha256:" + "a" * 64, ("registry:5000/org/app:1.2", "other:latest"), 123, "today")


@pytest.mark.parametrize("remove_tags,force", list(product((False, True), repeat=2)))
def test_one_matching_alias_protects_whole_image(remove_tags, force):
    config = Config((r"^registry:5000/org/app:1\.2$",), remove_tags, force)
    result = plan(config, {BASE.id: BASE})
    assert result.entries[0].action == "保留"
    assert not result.entries[0].targets
    assert "other:latest" in render(result)


@pytest.mark.parametrize("pattern,protected", [
    (r"^registry:5000/org/app:", True), (r"app:1\.2", True),
    (r"^registry:5000/org/app:1\.3$", False), (r"^app:", False),
])
def test_search_matches_actual_full_tag(pattern, protected):
    entry = plan(Config((pattern,)), {BASE.id: BASE}).entries[0]
    assert (entry.action == "保留") == protected


@pytest.mark.parametrize("remove_tags,force,referenced", list(product((False, True), repeat=3)))
def test_modes_and_container_protection(remove_tags, force, referenced):
    image = replace(BASE, references=(Reference("cid", "stopped", "exited"),) if referenced else ())
    entry = plan(Config((), remove_tags, force), {image.id: image}).entries[0]
    if referenced and not force:
        assert not entry.targets and entry.action == "跳過"
    else:
        assert entry.targets == (image.tags if remove_tags else (image.id,))
        assert entry.action == ("移除 tag" if remove_tags else "刪除 image")


def test_untagged_not_matched_by_fake_name_and_empty_rules_visible():
    image = replace(BASE, tags=())
    assert plan(Config(("<none>",)), {image.id: image}).entries[0].targets == (image.id,)
    text = render(plan(Config(), {image.id: image}))
    assert "無 tag" in text and "沒有保留規則" in text
