"""Non-interactive image cleanup using explicit command-line rules."""
import argparse
from dataclasses import asdict, replace
import json
import re
import sys
from pathlib import Path

from .config import CleanError, Config
from .engine import Docker
from .plan import execute, plan, render, render_results


def main() -> int:
    parser = argparse.ArgumentParser(prog="dc")
    commands = parser.add_subparsers(required=True)
    image = commands.add_parser("image")
    actions = image.add_subparsers(dest="action", required=True)
    for name, help_text in (("keep", "Image Keep：管理保留規則"),
                            ("delete", "Image Delete：勾選要刪除的 image")):
        tui = actions.add_parser(name, help=help_text)
        if name == "keep":
            tui.add_argument("--config", type=Path,
                             default=Path.home() / ".config/docker-clean/config.yaml")
    clean = actions.add_parser("clean", help="依 Regex 預覽或清理本機 image")
    clean.add_argument("--delete", action="append", default=[], metavar="REGEX",
                       help="只刪除命中的 image；可重複")
    clean.add_argument("--keep", action="append", default=[], metavar="REGEX",
                       help="保留命中的整個 image，優先於 --delete；可重複")
    clean.add_argument("--yes", action="store_true", help="執行刪除；未指定時只預覽")
    clean.add_argument("--force", action="store_true", help="向 Docker 要求強制刪除")
    clean.add_argument("--json", action="store_true", help="輸出單一 JSON 物件")
    args = parser.parse_args()
    if args.action in {"keep", "delete"}:
        from .cli import main as tui_main
        return tui_main([args.action, "--config", str(args.config)]
                        if args.action == "keep" else [args.action])
    try:
        if not args.keep and not args.delete:
            raise CleanError("至少提供一個 --keep 或 --delete Regex")
        if any(not value.strip() for value in args.keep + args.delete):
            raise CleanError("Regex 不可空白；全部匹配請明確使用 .*")
        config = Config(keep=tuple(args.keep), force=args.force)
        config.validate()
        try:
            patterns = [re.compile(value) for value in args.delete]
        except re.error as exc:
            raise CleanError(f"無效 delete Regex: {exc}") from exc
        docker = Docker()
        preview = plan(config, docker.snapshot())
        if patterns:
            preview = replace(preview, entries=tuple(
                replace(entry, action="跳過", reason="未命中 delete 規則", targets=())
                if entry.targets and not any(pattern.search(tag)
                    for tag in entry.image.tags or ("None",) for pattern in patterns)
                else entry for entry in preview.entries))
        results = execute(preview, None, docker) if args.yes else []
        failed = any(result.status == "失敗" for result in results)
        if args.json:
            print(json.dumps({"mode": "execute" if args.yes else "preview",
                              "ok": not failed, "force": args.force,
                              "keep": args.keep, "delete": args.delete,
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
