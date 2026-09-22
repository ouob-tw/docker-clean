import argparse
import os
import sys
from pathlib import Path

# Multiplexers can report cell coordinates even after advertising pixel support.
# This supported Textual setting must precede imports that load its constants.
os.environ["TEXTUAL_SMOOTH_SCROLL"] = "0"

from .config import CleanError, load
from .engine import Docker
from .plan import execute, plan, render, render_results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本機 Docker image 清理：預覽後確認")
    parser.add_argument("command", choices=["keep", "delete", "clean", "whitelist", "tui"],
                        metavar="{keep,delete,clean}")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/docker-clean/config.yaml")
    args = parser.parse_args(argv)
    # Accept previous entrypoints without advertising the ambiguous names.
    args.command = {"whitelist": "delete", "tui": "keep"}.get(args.command, args.command)
    try:
        if args.command in {"keep", "delete"}:
            from .terminal import use_cell_coordinates
            use_cell_coordinates()
            if sys.stdout.isatty():
                # Clear pixel/resize modes a previous TUI may have left enabled.
                sys.stdout.write("\x1b[?1016l\x1b[?2048l")
                sys.stdout.flush()
            if args.command == "delete":
                from .whitelist import WhitelistApp
                WhitelistApp().run()
            else:
                from .tui import CleanerApp
                CleanerApp(args.config).run()
            return 0
        config, revision = load(args.config)
        assert revision is not None
        docker = Docker()
        preview = plan(config, docker.snapshot(), revision)
        print(render(preview))
        if not any(entry.targets for entry in preview.entries):
            print("沒有清理候選")
            return 0
        print("移除最後一個 tag 可能刪除 image；force 不會停止或刪除容器，且不保證成功。")
        try:
            confirmed = input("輸入 DELETE 確認執行，其他輸入取消: ") == "DELETE"
        except EOFError:
            confirmed = False
        if not confirmed:
            print("已取消；未修改 Docker")
            return 0
        results = execute(preview, args.config, docker)
        print(render_results(results, (entry.image for entry in preview.entries)))
        return 1 if any(result.status == "失敗" for result in results) else 0
    except (CleanError, KeyboardInterrupt) as exc:
        print(f"停止: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
