"""Track images that remain unreferenced across successful daily inventories."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
from collections.abc import Iterator

from .config import CleanError
from .plan import Preview


def default_state_path() -> Path:
    return Path.home() / ".local/state/docker-clean/image-unused.json"


@contextmanager
def locked_state(path: Path) -> Iterator[None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield
    except OSError as exc:
        raise CleanError(f"無法鎖定 image 閒置紀錄: {exc}") from exc


def read_state(path: Path, now: datetime) -> dict[str, tuple[datetime, datetime]]:
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise CleanError(f"無法讀取 image 閒置紀錄: {exc}") from exc
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"version", "images"} or data["version"] != 1:
            raise ValueError("版本或格式錯誤")
        images = data["images"]
        if not isinstance(images, dict):
            raise ValueError("images 必須是物件")
        result = {}
        for image_id, item in images.items():
            if (not isinstance(image_id, str) or not image_id
                    or not isinstance(item, dict) or set(item) != {"since", "last_seen"}):
                raise ValueError("image 紀錄格式錯誤")
            since = datetime.fromisoformat(item["since"])
            last_seen = datetime.fromisoformat(item["last_seen"])
            if (since.tzinfo is None or last_seen.tzinfo is None
                    or not since <= last_seen <= now):
                raise ValueError("image 閒置時間無效")
            result[image_id] = (since, last_seen)
        return result
    except (ValueError, TypeError, KeyError) as exc:
        raise CleanError(f"image 閒置紀錄損壞；未執行刪除: {exc}") from exc


def save_state(path: Path, images: dict[str, tuple[datetime, datetime]]) -> None:
    raw = json.dumps({"version": 1, "images": {
        image_id: {"since": since.isoformat(), "last_seen": last_seen.isoformat()}
        for image_id, (since, last_seen) in images.items()}}, ensure_ascii=False)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(raw + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise CleanError(f"無法儲存 image 閒置紀錄: {exc}") from exc
    finally:
        if temporary is not None:
            os.unlink(temporary)


def apply_unused_days(preview: Preview, path: Path, days: int,
                      now: datetime | None = None) -> Preview:
    now = now or datetime.now(timezone.utc)
    previous = read_state(path, now)
    current = {}
    entries = []
    for entry in preview.entries:
        if entry.image.references or entry.action == "保留":
            entries.append(entry)
            continue
        since, last_seen = previous.get(entry.image.id, (now, now))
        if now - last_seen > timedelta(hours=36):
            since = now
        current[entry.image.id] = (since, now)
        if entry.targets and now - since < timedelta(days=days):
            entries.append(replace(entry, action="跳過", targets=(),
                reason=f"無容器引用尚未滿 {days} 天；首次觀察 {since.isoformat()}"))
        else:
            entries.append(entry)
    save_state(path, current)
    return replace(preview, entries=tuple(entries))
