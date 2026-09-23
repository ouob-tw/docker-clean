"""Non-interactive image cleanup using config and command-line rules."""
import argparse
from contextlib import nullcontext
from dataclasses import asdict, replace
import json
import re
import sys
from pathlib import Path

from .config import CleanError, Config, default_image_config, load
from .engine import Docker
from .image_age import apply_unused_days, default_state_path, locked_state
from .plan import execute, plan, render, render_results


def main() -> int:
    parser = argparse.ArgumentParser(prog="dcl")
    commands = parser.add_subparsers(dest="resource", required=True)
    image = commands.add_parser("image")
    actions = image.add_subparsers(dest="action", required=True)
    for name, help_text in (("keep", "Image Keep：管理保留規則"),
                            ("delete", "Image Delete：勾選要刪除的 image")):
        tui = actions.add_parser(name, help=help_text)
        if name == "keep":
            tui.add_argument("--config", type=Path,
                             default=default_image_config())
    clean = actions.add_parser("clean", help="依 Regex 預覽或清理本機 image")
    clean.add_argument("--config", type=Path, default=default_image_config(),
                       help="排除清單設定檔；預設 ~/.config/docker-clean/images.yaml")
    clean.add_argument("--delete", action="append", default=[], metavar="REGEX",
                       help="只刪除命中的 image；可重複")
    clean.add_argument("--keep", action="append", default=[], metavar="REGEX",
                       help="保留命中的整個 image，優先於 --delete；可重複")
    clean.add_argument("--yes", action="store_true", help="執行刪除；未指定時只預覽")
    clean.add_argument("--force", action="store_true", help="向 Docker 要求強制刪除")
    clean.add_argument("--unused-days", type=int, metavar="DAYS",
                       help="覆寫 cleanup.unused_days；預覽會開始記錄無引用時間")
    clean.add_argument("--json", action="store_true", help="輸出單一 JSON 物件")
    container = commands.add_parser("container", help="清理停止滿指定天數的容器")
    container_actions = container.add_subparsers(dest="action", required=True)
    container_clean = container_actions.add_parser("clean", help="依設定預覽或清理容器")
    container_clean.add_argument("--config", type=Path,
                                 default=Path.home() / ".config/docker-clean/containers.yaml")
    container_clean.add_argument("--all", action="store_true", help="文字顯示全部容器；不影響清理範圍或 JSON")
    container_clean.add_argument("--ignore-age", action="store_true",
                                 help="手動清理時忽略 stopped_days；仍只處理已停止、未受保護的非 Swarm 容器")
    container_clean.add_argument("--yes", action="store_true")
    container_clean.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.resource == "container":
        from .containers import run
        return run(args.config, args.yes, args.json, args.all, args.ignore_age)
    if args.action in {"keep", "delete"}:
        from .cli import main as tui_main
        return tui_main([args.action, "--config", str(args.config)]
                        if args.action == "keep" else [args.action])
    try:
        saved, revision = load(args.config)
        assert revision is not None
        unused_days = args.unused_days if args.unused_days is not None else saved.unused_days
        if unused_days is not None and (unused_days < 1 or args.force):
            raise CleanError("unused_days 必須大於零，且不可搭配 --force")
        if any(not value.strip() for value in args.keep + args.delete):
            raise CleanError("Regex 不可空白；全部匹配請明確使用 .*")
        config = Config(keep=saved.keep + tuple(args.keep), force=args.force)
        config.validate()
        try:
            patterns = [re.compile(value) for value in args.delete]
        except re.error as exc:
            raise CleanError(f"無效 delete Regex: {exc}") from exc
        state_path = default_state_path() if unused_days is not None else None
        with locked_state(state_path) if state_path is not None else nullcontext():
            docker = Docker()
            preview = plan(config, docker.snapshot(), revision)
            if patterns:
                preview = replace(preview, entries=tuple(
                    replace(entry, action="跳過", reason="未命中 delete 規則", targets=())
                    if entry.targets and not any(pattern.search(tag)
                        for tag in entry.image.tags or ("None",) for pattern in patterns)
                    else entry for entry in preview.entries))
            if state_path is not None and unused_days is not None:
                preview = apply_unused_days(preview, state_path, unused_days)
            results = execute(preview, args.config, docker) if args.yes else []
            failed = any(result.status == "失敗" for result in results)
            if args.json:
                print(json.dumps({"mode": "execute" if args.yes else "preview",
                                  "ok": not failed, "force": args.force, "unused_days": unused_days,
                                  "keep": list(config.keep), "delete": args.delete,
                                  "entries": [asdict(entry) for entry in preview.entries],
                                  "results": [asdict(result) for result in results]}, ensure_ascii=False))
            else:
                print(render(preview))
                if args.yes:
                    print(render_results(results, (entry.image for entry in preview.entries)))
                else:
                    print("僅預覽，未修改 Docker；加上 --yes 才執行。")
            return 1 if failed else 0
    except (CleanError, KeyboardInterrupt) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc) or "已中斷"}, ensure_ascii=False))
        else:
            print(f"停止: {exc}", file=sys.stderr)
        return 1
