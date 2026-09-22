from dataclasses import dataclass
import json
import os
import subprocess

from .config import CleanError


@dataclass(frozen=True, order=True)
class Reference:
    id: str
    name: str
    status: str


@dataclass(frozen=True)
class Image:
    id: str
    tags: tuple[str, ...]
    size: int
    created: str
    references: tuple[Reference, ...] = ()


class Docker:
    """Pin a local socket once; never inherit a changing context for deletion."""

    def __init__(self) -> None:
        env = dict(os.environ)
        context = env.get("DOCKER_CONTEXT")
        host = env.get("DOCKER_HOST") if not context else None
        if not host:
            args = ["docker", "context", "inspect"]
            if context:
                args.append(context)
            try:
                host = json.loads(self._call(args, env))[0]["Endpoints"]["docker"]["Host"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise CleanError("無法判定 Docker 連線") from exc
        if not isinstance(host, str) or not host.startswith("unix:///"):
            raise CleanError(f"僅支援本機 Unix socket；拒絕遠端或不明連線: {host}")
        self.host = host
        self.env = {k: v for k, v in env.items() if k not in {
            "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_TLS"}}

    @staticmethod
    def _call(args: list[str], env: dict[str, str]) -> str:
        try:
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CleanError(f"Docker 查詢／操作失敗: {exc}") from exc
        if result.returncode:
            raise CleanError(result.stderr.strip() or result.stdout.strip() or "Docker 操作失敗")
        return result.stdout

    def call(self, *args: str) -> str:
        return self._call(["docker", "--host", self.host, *args], self.env)

    def snapshot(self) -> dict[str, Image]:
        try:
            ids = sorted(set(self.call("image", "ls", "--all", "--quiet", "--no-trunc").split()))
            container_ids = self.call("container", "ls", "--all", "--quiet", "--no-trunc").split()
            refs: dict[str, list[Reference]] = {}
            containers = []
            for offset in range(0, len(container_ids), 100):
                containers.extend(json.loads(self.call("container", "inspect", *container_ids[offset:offset + 100])))
            for container in containers:
                refs.setdefault(container["Image"], []).append(Reference(
                    container["Id"], container["Name"].lstrip("/"), container["State"]["Status"]))
            images = {}
            items = []
            for offset in range(0, len(ids), 100):
                items.extend(json.loads(self.call("image", "inspect", *ids[offset:offset + 100])))
            for item in items:
                images[item["Id"]] = Image(item["Id"], tuple(sorted(item.get("RepoTags") or [])),
                    item["Size"], item["Created"], tuple(sorted(refs.get(item["Id"], []))))
            return images
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise CleanError(f"Docker 盤點資料不完整: {exc}") from exc

    def remove(self, target: str, force: bool) -> str:
        args = ["image", "rm", "--no-prune"]
        if force:
            args.append("--force")
        return self.call(*args, target)

    def forceDeleteImage(self, image_id: str) -> str:
        return self.remove(image_id, force=True)
