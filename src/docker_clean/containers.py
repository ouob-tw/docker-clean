"""Config-driven cleanup of stopped, non-Swarm containers."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path

import yaml

from .config import CleanError, read_bytes
from .engine import Docker


@dataclass(frozen=True)
class Policy:
    stopped_days: int
    compose: tuple[tuple[str, tuple[str, ...] | None], ...]
    names: tuple[str, ...]


def names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise CleanError("保留清單必須是非空字串陣列")
    return tuple(value)


def load_policy(path: Path) -> tuple[Policy, bytes]:
    raw = read_bytes(path)
    if raw is None:
        raise CleanError(f"容器設定不存在: {path}")
    try:
        data = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeError) as exc:
        raise CleanError(f"YAML 錯誤: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"version", "stopped_days", "keep"}:
        raise CleanError("容器設定必須包含且僅含 version、stopped_days、keep")
    if type(data["version"]) is not int or data["version"] != 1:
        raise CleanError("version 必須為 1")
    days = data["stopped_days"]
    if type(days) is not int or days < 1:
        raise CleanError("stopped_days 必須為大於零的整數")
    keep = data["keep"]
    if not isinstance(keep, dict) or set(keep) - {"compose", "container_names"}:
        raise CleanError("keep 僅支援 compose、container_names")
    rules = keep.get("compose", [])
    if not isinstance(rules, list):
        raise CleanError("keep.compose 必須是陣列")
    compose = []
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) - {"project", "services"}
                or not isinstance(rule.get("project"), str) or not rule["project"].strip()):
            raise CleanError("Compose 規則必須指定 project，可選 services")
        services = names(rule["services"]) if "services" in rule else None
        if services == ():
            raise CleanError("services 不可為空；保留整個 project 請省略 services")
        compose.append((rule["project"], services))
    return Policy(days, tuple(compose), names(keep.get("container_names", []))), raw


@dataclass(frozen=True)
class Container:
    id: str
    name: str
    status: str
    started: str
    finished: str
    labels: dict[str, str]
    mounts: tuple[str, ...]


def inspect(docker: Docker, ids: list[str]) -> list[Container]:
    result = []
    try:
        for offset in range(0, len(ids), 100):
            batch = ids[offset:offset + 100]
            items = json.loads(docker.call("container", "inspect", *batch))
            if not isinstance(items, list) or len(items) != len(batch):
                raise ValueError("inspect 回傳數量不符")
            for item in items:
                state = item["State"]
                labels = item["Config"].get("Labels") or {}
                fields = [item["Id"], item["Name"], state["Status"], state["StartedAt"], state["FinishedAt"]]
                if (not all(isinstance(v, str) and v for v in fields)
                        or not isinstance(labels, dict)
                        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items())):
                    raise ValueError("欄位型別錯誤")
                result.append(Container(fields[0], fields[1].lstrip("/"), fields[2], fields[3], fields[4], labels,
                    tuple(f"{m['Type']}:{m['Source']} → {m['Destination']}" for m in item["Mounts"])))
        if {c.id for c in result} != set(ids):
            raise ValueError("inspect 回傳 ID 不符")
        return result
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise CleanError(f"容器盤點資料不完整: {exc}") from exc


def reason(c: Container, policy: Policy, now: datetime) -> tuple[bool, str, str]:
    if c.name in policy.names:
        return False, "保留：容器名稱", "keep"
    project = c.labels.get("com.docker.compose.project")
    service = c.labels.get("com.docker.compose.service")
    for p, services in policy.compose:
        if project == p and (services is None or service in services):
            return False, f'保留：Compose {p}' + (f'/{service}' if services else ""), "keep"
    if any(k in c.labels for k in ("com.docker.swarm.task.id", "com.docker.swarm.service.id")):
        return False, "跳過：由 Swarm 管理", "swarm"
    if c.status != "exited":
        return False, f'跳過：狀態 {c.status}', "state"
    try:
        finished = datetime.fromisoformat(c.finished.replace("Z", "+00:00"))
        if finished.year == 1 or finished.tzinfo is None or finished > now:
            raise ValueError("停止時間缺失或異常")
    except ValueError as exc:
        raise CleanError(f'{c.name} 停止時間無效: {c.finished}') from exc
    age = now - finished
    eligible = age.total_seconds() >= policy.stopped_days * 86400
    return eligible, f"停止 {age.total_seconds() / 86400:.1f} 天", "candidate" if eligible else "too_recent"


def render_preview(entries: list[dict], days: int | None, path: Path,
                   show_all: bool, complete: bool, empty_keep: bool, yes: bool) -> None:
    if empty_keep:
        print("沒有保留規則；所有符合停止期限的非 Swarm 容器均可能刪除。")
    title = "容器清理" if yes else "容器清理預覽"
    print(f"{title} | 停止滿 {days} 天 | 設定 {path}" if days is not None else title)
    if not complete and not entries:
        print("盤點未完成。")
        return
    groups = [("candidate", "刪除候選"), ("too_recent", "未滿期限"),
              ("keep", "保留"), ("swarm", "Swarm"), ("state", "其他狀態")]
    counts = {key: sum(e["category"] == key for e in entries) for key, _ in groups}
    for key, label in groups:
        if key != "candidate" and not show_all:
            continue
        selected = [e for e in entries if e["category"] == key]
        if not selected:
            continue
        print(f"{label} {len(selected)} 個：")
        for entry in selected:
            c = entry["container"]
            print(f"  {c['name']} | {entry['reason']} | {c['id'][:12]}")
            if entry["delete"]:
                for mount in c["mounts"]:
                    print(f"    掛載：{mount}")
    if complete and not counts["candidate"]:
        print("沒有刪除候選。")
    prefix = "合計" if complete else "盤點未完成，已判斷"
    print(f"{prefix} {len(entries)} | " + " | ".join(
        f"{label} {counts[key]}" for key, label in groups))
    if complete and not show_all:
        print("使用 --all 查看全部容器與保留原因。")
    if complete and counts["candidate"]:
        print("刪除容器後，只存在容器裡的檔案也會刪除；另外儲存在主機資料夾或 Docker volume 的資料會保留。")
    if complete and counts["candidate"] and not yes:
        print("僅預覽，未修改 Docker；加上 --yes 才執行。")


def run(path: Path, yes: bool, json_output: bool, show_all: bool = False) -> int:
    entries: list[dict] = []
    results: list[dict] = []
    error = None
    empty_keep = False
    days = None
    complete = False
    rendered = False
    try:
        policy, revision = load_policy(path)
        days = policy.stopped_days
        empty_keep = not policy.compose and not policy.names
        docker = Docker()
        ids = docker.call("container", "ls", "--all", "--quiet", "--no-trunc").split()
        now = datetime.now(timezone.utc)
        candidates = []
        for c in inspect(docker, ids):
            delete, why, category = reason(c, policy, now)
            entries.append({"container": asdict(c), "delete": delete, "reason": why, "category": category})
            if delete:
                candidates.append(c)
        complete = True
        if not json_output:
            render_preview(entries, days, path, show_all, complete, empty_keep, yes)
            rendered = True
        if yes:
            for c in candidates:
                if read_bytes(path) != revision:
                    raise CleanError("設定已變更；停止清理")
                current = inspect(docker, [c.id])[0]
                if read_bytes(path) != revision:
                    raise CleanError("設定已變更；停止清理")
                if current != c or not reason(current, policy, datetime.now(timezone.utc))[0]:
                    results.append({"id": c.id, "name": c.name, "status": "跳過", "detail": "容器狀態已變更"})
                    continue
                try:
                    receipt = docker.call("container", "rm", c.id)
                    results.append({"id": c.id, "name": c.name, "status": "刪除", "detail": receipt.strip()})
                except CleanError as exc:
                    results.append({"id": c.id, "name": c.name, "status": "失敗", "detail": str(exc)})
    except (CleanError, KeyboardInterrupt) as exc:
        error = str(exc) or "已中斷"
    ok = error is None and not any(r["status"] == "失敗" for r in results)
    payload = {"mode": "execute" if yes else "preview", "ok": ok, "empty_keep": empty_keep,
               "entries": entries, "results": results, "error": error,
               "stopped_days": days, "plan_complete": complete,
               "summary": {"total": len(entries), **{
                   key: sum(e["category"] == key for e in entries)
                   for key in ("candidate", "keep", "too_recent", "swarm", "state")}}}
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if not rendered:
            render_preview(entries, days, path, show_all, complete, empty_keep, yes)
        for result in results:
            detail = "" if result["status"] == "刪除" else f" | {result['detail']}"
            print(f"{result['name']} | {result['status']} | {result['id'][:12]}{detail}")
        if error:
            print(f"停止：{error}")
        if yes:
            deleted = sum(r["status"] == "刪除" for r in results)
            skipped = sum(r["status"] == "跳過" for r in results)
            failed = sum(r["status"] == "失敗" for r in results)
            remaining = str(sum(e["delete"] for e in entries) - len(results)) if complete else "未知（盤點未完成）"
            print(f"結果 | 刪除 {deleted} | 跳過 {skipped} | 失敗 {failed} | 未處理 {remaining}")
    return 0 if ok else 1
