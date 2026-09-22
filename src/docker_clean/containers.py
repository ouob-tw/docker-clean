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


def reason(c: Container, policy: Policy, now: datetime) -> tuple[bool, str]:
    if c.name in policy.names:
        return False, "保留：容器名稱"
    project = c.labels.get("com.docker.compose.project")
    service = c.labels.get("com.docker.compose.service")
    for p, services in policy.compose:
        if project == p and (services is None or service in services):
            return False, f'保留：Compose {p}' + (f'/{service}' if services else "")
    if any(k in c.labels for k in ("com.docker.swarm.task.id", "com.docker.swarm.service.id")):
        return False, "跳過：由 Swarm 管理"
    if c.status != "exited":
        return False, f'跳過：狀態 {c.status}'
    try:
        finished = datetime.fromisoformat(c.finished.replace("Z", "+00:00"))
        if finished.year == 1 or finished.tzinfo is None or finished > now:
            raise ValueError("停止時間缺失或異常")
    except ValueError as exc:
        raise CleanError(f'{c.name} 停止時間無效: {c.finished}') from exc
    age = now - finished
    eligible = age.total_seconds() >= policy.stopped_days * 86400
    return eligible, f"{'刪除候選' if eligible else '未滿期限'}：停止 {age.total_seconds() / 86400:.1f} 天"


def run(path: Path, yes: bool, json_output: bool) -> int:
    entries: list[dict] = []
    results: list[dict] = []
    error = None
    empty_keep = False
    try:
        policy, revision = load_policy(path)
        empty_keep = not policy.compose and not policy.names
        docker = Docker()
        ids = docker.call("container", "ls", "--all", "--quiet", "--no-trunc").split()
        now = datetime.now(timezone.utc)
        candidates = []
        for c in inspect(docker, ids):
            delete, why = reason(c, policy, now)
            entries.append({"container": asdict(c), "delete": delete, "reason": why})
            if delete:
                candidates.append(c)
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
               "entries": entries, "results": results, "error": error}
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if empty_keep:
            print("沒有保留規則；所有符合停止期限的非 Swarm 容器均可能刪除。")
        for entry in entries:
            cdata = entry["container"]
            print(f"{cdata['name']}  {entry['reason']}  {cdata['id']}")
            for mount in cdata["mounts"]:
                print(f'  掛載：{mount}')
        print("刪除會失去容器可寫層；掛載資料與 volume 保留，匿名 volume 不自動重新掛回。")
        for result in results:
            print(f"{result['name']}  {result['id']}  {result['status']}  {result['detail']}")
        if error:
            print(f'停止：{error}')
        elif not yes:
            print("僅預覽，未修改 Docker；加上 --yes 才執行。")
    return 0 if ok else 1
