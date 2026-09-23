"""Consecutive inventory evidence for scheduled image cleanup."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from docker_clean.config import CleanError, Config
from docker_clean.engine import Image, Reference
from docker_clean.image_age import apply_unused_days
from docker_clean.plan import plan


def preview(image: Image, keep: tuple[str, ...] = ()):
    return plan(Config(keep=keep), {image.id: image})


def test_daily_unreferenced_observations_become_eligible_on_day_21(tmp_path):
    path = tmp_path / "state.json"
    image = Image("sha256:a", ("app:old",), 1, "2020-01-01")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for day in range(21):
        result = apply_unused_days(preview(image), path, 21, start + timedelta(days=day))
        assert not result.entries[0].targets
    result = apply_unused_days(preview(image), path, 21, start + timedelta(days=21))
    assert result.entries[0].targets == (image.id,)
    assert json.loads(path.read_text())["images"][image.id]["since"] == start.isoformat()


def test_reference_and_missed_inventory_reset_clock(tmp_path):
    path = tmp_path / "state.json"
    image = Image("sha256:a", ("app:old",), 1, "2020-01-01")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    apply_unused_days(preview(image), path, 21, start)
    used = Image(image.id, image.tags, image.size, image.created,
                 (Reference("container", "used", "exited"),))
    apply_unused_days(preview(used), path, 21, start + timedelta(days=1))
    assert json.loads(path.read_text())["images"] == {}
    apply_unused_days(preview(image), path, 21, start + timedelta(days=2))
    result = apply_unused_days(preview(image), path, 21, start + timedelta(days=4))
    assert not result.entries[0].targets
    assert json.loads(path.read_text())["images"][image.id]["since"] == (start + timedelta(days=4)).isoformat()


def test_keep_rule_excludes_image_and_clears_clock(tmp_path):
    path = tmp_path / "state.json"
    image = Image("sha256:a", ("app:backup",), 1, "2020-01-01")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    apply_unused_days(preview(image), path, 21, now)
    apply_unused_days(preview(image, ("backup",)), path, 21, now + timedelta(days=1))
    assert json.loads(path.read_text())["images"] == {}


def test_corrupt_state_stops_without_replacing_it(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json")
    image = Image("sha256:a", ("app:old",), 1, "2020-01-01")
    with pytest.raises(CleanError, match="閒置紀錄損壞"):
        apply_unused_days(preview(image), path, 21)
    assert path.read_text() == "not json"
