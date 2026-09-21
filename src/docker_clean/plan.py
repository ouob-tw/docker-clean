from dataclasses import dataclass, replace
from pathlib import Path
import re

from .config import CleanError, Config, load
from .engine import Docker, Image


@dataclass(frozen=True)
class Entry:
    image: Image
    action: str
    reason: str
    targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Preview:
    config: Config
    revision: bytes
    entries: tuple[Entry, ...]


def plan(config: Config, images: dict[str, Image], revision: bytes = b"") -> Preview:
    config.validate()
    patterns = [(value, re.compile(value)) for value in config.keep]
    entries = []
    for image in sorted(images.values(), key=lambda image: image.id):
        matches = [f"{tag} 符合 {value!r}" for tag in image.tags
                   for value, pattern in patterns if pattern.search(tag)]
        if matches:
            entries.append(Entry(image, "保留", "; ".join(matches)))
        elif image.references and not config.force:
            entries.append(Entry(image, "跳過", "容器引用；force 未啟用"))
        elif config.remove_tags and image.tags:
            entries.append(Entry(image, "移除 tag", "最後一個 tag 可能同時刪除 image", image.tags))
        else:
            entries.append(Entry(image, "刪除 image", "按完整 ID 刪除", (image.id,)))
    return Preview(config, revision, tuple(entries))


def describe(entry: Entry, force: bool) -> str:
    image = entry.image
    refs = ", ".join(f"{r.name} ({r.status}, {r.id})" for r in image.references) or "無"
    return (f"{entry.action} | {image.id}\n"
            f"  tags: {', '.join(image.tags) or '無 tag'}\n"
            f"  大小: {image.size} bytes（共用層不可加總） | 建立: {image.created}\n"
            f"  容器: {refs} | force={str(force).lower()}\n"
            f"  原因: {entry.reason}\n"
            f"  目標: {', '.join(entry.targets) or '無'}")


def render(preview: Preview) -> str:
    heading = f"remove_tags={preview.config.remove_tags}, force={preview.config.force}\n"
    if not preview.config.keep:
        heading += "警告：沒有保留規則 (keep: [])\n"
    return heading + "\n\n".join(describe(entry, preview.config.force) for entry in preview.entries)


@dataclass(frozen=True)
class Result:
    status: str
    target: str
    detail: str


def execute(preview: Preview, path: Path, docker: Docker) -> list[Result]:
    results: list[Result] = []
    for entry in preview.entries:
        if not entry.targets:
            results.append(Result("跳過", entry.image.id, entry.reason))
            continue
        expected = entry.image
        for target in entry.targets:
            try:
                config, revision = load(path)
                if revision != preview.revision or config != preview.config:
                    raise CleanError("設定已改變，停止執行；請重新預覽")
                current = docker.snapshot().get(entry.image.id)
            except CleanError as exc:
                results.append(Result("失敗", target, str(exc)))
                return results
            if current != expected:
                results.append(Result("跳過", target, "image／tag／容器引用已變更，請重新預覽"))
                break
            try:
                output = docker.remove(target, config.force)
            except CleanError as exc:
                results.append(Result("失敗", target, str(exc)))
                continue
            # Report the daemon's actual outcomes, including both lines for the last tag.
            count_before = len(results)
            for line in output.splitlines():
                if line.startswith("Untagged:"):
                    results.append(Result("移除 tag", target, line))
                elif line.startswith("Deleted:"):
                    results.append(Result("刪除 image", target, line))
            if len(results) == count_before:
                results.append(Result("成功", target, output.strip() or "Docker 已接受請求；未回報釋放容量"))
            expected = replace(expected, tags=tuple(t for t in expected.tags if t != target))
    return results


def render_results(results: list[Result]) -> str:
    return "\n".join(f"{r.status} | {r.target} | {r.detail}" for r in results) or "沒有清理候選"
