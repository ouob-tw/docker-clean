from dataclasses import dataclass
from pathlib import Path
import os
import re
import tempfile

import yaml
from textual.theme import BUILTIN_THEMES


class CleanError(Exception):
    """An error that must stop unsafe cleanup."""


@dataclass(frozen=True)
class Config:
    keep: tuple[str, ...] = ()
    remove_tags: bool = False
    force: bool = False
    theme: str = "terminal"

    def validate(self) -> None:
        if not isinstance(self.keep, tuple) or not all(isinstance(x, str) for x in self.keep):
            raise CleanError("keep 必須是字串陣列")
        if type(self.remove_tags) is not bool or type(self.force) is not bool:
            raise CleanError("cleanup 選項必須是布林值")
        if not isinstance(self.theme, str) or self.theme not in {"terminal", "e-ink", *BUILTIN_THEMES}:
            raise CleanError("theme 必須是 terminal、e-ink 或有效的內建主題名稱")
        for pattern in self.keep:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise CleanError(f"無效 Regex {pattern!r}: {exc}") from exc


def read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CleanError(f"無法讀取設定: {exc}") from exc


def load(path: Path, *, allow_missing: bool = False) -> tuple[Config, bytes | None]:
    raw = read_bytes(path)
    if raw is None:
        if allow_missing:
            return Config(), None
        raise CleanError("設定不存在；請先執行 dc image keep 建立設定")
    try:
        data = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeError) as exc:
        raise CleanError(f"YAML 錯誤: {exc}") from exc
    if not isinstance(data, dict) or set(data) - {"keep", "cleanup", "theme"}:
        raise CleanError("設定必須是僅含 keep、cleanup 與 theme 的 mapping")
    keep = data.get("keep")
    cleanup = data.get("cleanup", {})
    if not isinstance(keep, list) or not all(isinstance(x, str) for x in keep):
        raise CleanError("keep 必須是字串陣列；空清單請明確使用 keep: []")
    if not isinstance(cleanup, dict) or set(cleanup) - {"remove_tags", "force"}:
        raise CleanError("cleanup 必須僅含 remove_tags 與 force")
    config = Config(tuple(keep), cleanup.get("remove_tags", False), cleanup.get("force", False),
                    data.get("theme", "terminal"))
    config.validate()
    return config, raw


def save(path: Path, config: Config, expected: bytes | None) -> bytes:
    config.validate()
    raw = yaml.safe_dump({"theme": config.theme, "keep": list(config.keep), "cleanup": {
        "remove_tags": config.remove_tags, "force": config.force}}, allow_unicode=True).encode()
    if read_bytes(path) != expected:
        raise CleanError("設定已被外部修改；請重新載入")
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if read_bytes(path) != expected:
            raise CleanError("設定已被外部修改；請重新載入")
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise CleanError(f"無法儲存設定: {exc}") from exc
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return raw
