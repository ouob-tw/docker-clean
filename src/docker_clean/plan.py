from dataclasses import dataclass, replace
from pathlib import Path
from collections.abc import Callable, Iterable
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


ProgressCallback = Callable[[Image, str, tuple[Result, ...] | None], None]


def execute(preview: Preview, path: Path | None, docker: Docker,
            progress: ProgressCallback | None = None) -> list[Result]:
    results: list[Result] = []
    for entry in preview.entries:
        start = len(results)
        try:
            if not entry.targets:
                results.append(Result("跳過", entry.image.id, entry.reason))
                continue
            expected = entry.image
            for target in entry.targets:
                if progress:
                    progress(entry.image, "重新檢查狀態", None)
                try:
                    config, revision = load(path) if path is not None else (preview.config, preview.revision)
                    if revision != preview.revision or config != preview.config:
                        raise CleanError("設定已改變，停止執行；請重新預覽")
                    current = docker.snapshot().get(entry.image.id)
                except CleanError as exc:
                    results.append(Result("失敗", target, str(exc)))
                    return results
                if current != expected:
                    results.append(Result("跳過", target, "image／tag／容器引用已變更，請重新預覽"))
                    break
                if progress:
                    progress(entry.image, f"正在執行：{entry.action} {target}", None)
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
        finally:
            if progress:
                progress(entry.image, "已處理", tuple(results[start:]))
    return results


def render_results(results: list[Result], images: Iterable[Image] = ()) -> str:
    if not results:
        return "沒有清理候選"
    names = {}
    image_ids: dict[str, str] = {}
    for image in images:
        names[image.id] = ", ".join(image.tags) or "無 tag"
        image_ids.update((tag, image.id) for tag in image.tags)
    groups: dict[str, list[Result]] = {}
    for result in results:
        groups.setdefault(image_ids.get(result.target, result.target), []).append(result)
    failed = sum(any(r.status == "失敗" for r in group) for group in groups.values())
    skipped = sum(all(r.status == "跳過" for r in group) for group in groups.values())
    blocks = [f"執行結果：{len(groups)} 個目標｜完成 {len(groups) - failed - skipped}｜跳過 {skipped}｜失敗 {failed}"]
    for index, (target, group) in enumerate(groups.items(), 1):
        label = names.get(target, "無 tag" if target.startswith("sha256:") else target)
        short_id = target[:19] if target.startswith("sha256:") else ""
        statuses = "、".join(dict.fromkeys(r.status for r in group))
        lines = [f"{index}. {label}" + (f" ({short_id})" if short_id else ""),
                 f"   結果：{statuses}"]
        if target.startswith("sha256:") and not any(target in r.detail for r in group):
            lines.append(f"   ID：{target}")
        # Keep daemon receipts intact, once per line, beneath the recognizable name.
        for result in group:
            lines.extend(f"   {line}" for line in result.detail.splitlines())
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
