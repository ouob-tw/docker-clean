"""Threaded cleanup with per-image progress and a chronological receipt log."""
from collections.abc import Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, TextArea

from .dialogs import DialogScreen
from .engine import Image
from .plan import ProgressCallback, Result, render_results
from .scrolling import ContainedVerticalScroll
from .widgets import ActionButton as Button


class CleanupProgress(DialogScreen):
    DEFAULT_CSS = """
    #cleanup-status { height: auto; margin-bottom: 1; }
    #cleanup-log { height: 1fr; border: solid $foreground; }
    .cleanup-entry { height: auto; margin-bottom: 1; }
    """
    BINDINGS = [("escape", "close", "返回"), ("ctrl+q", "quit", "離開")]

    def __init__(self) -> None:
        super().__init__()
        self.running = False
        self.completed = self.total = 0
        self.failed = self.skipped = 0

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-panel"):
            yield Static("刪除進度與詳細紀錄", classes="dialog-title")
            yield Static("", id="cleanup-status", markup=False)
            yield ContainedVerticalScroll(id="cleanup-log")
            yield Button("返回清單", id="close-progress", disabled=True, classes="dialog-close")

    def action_close(self) -> None:
        if not self.running:
            self.dismiss()

    async def action_quit(self) -> None:
        if not self.running:
            self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_close()

    def show_status(self, phase: str) -> None:
        filled = 20 * self.completed // max(1, self.total)
        self.query_one("#cleanup-status", Static).update(
            f"[{'█' * filled}{' ' * (20 - filled)}]  {self.completed}／{self.total}\n"
            f"完成 {self.completed - self.failed - self.skipped}　跳過 {self.skipped}　失敗 {self.failed}\n"
            f"{phase}")

    def append_log(self, text: str) -> None:
        log = self.query_one("#cleanup-log", VerticalScroll)
        follow = log.scroll_y >= log.max_scroll_y

        async def append() -> None:
            await log.mount(Static(text, classes="cleanup-entry", markup=False))
            if follow:
                self.call_after_refresh(log.scroll_end, animate=False, immediate=True)

        self.call_next(append)

    def update_progress(self, image: Image, phase: str,
                        results: tuple[Result, ...] | None) -> None:
        name = ", ".join(image.tags) or f"無 tag ({image.id[:19]})"
        if results:
            self.completed += 1
            self.failed += any(result.status == "失敗" for result in results)
            self.skipped += all(result.status == "跳過" for result in results)
            detail = render_results(list(results), [image]).split("\n\n", 1)[1].removeprefix("1. ")
            self.append_log(f"{datetime.now():%H:%M:%S}  {detail}")
        self.show_status(f"{phase}：{name}")

    def start(self, total: int, operation: Callable[[ProgressCallback], list[Result]],
              finished: Callable[[str | None], None]) -> None:
        if self.running:
            return
        self.running = True
        self.total = total
        self._operation = operation
        self._finished = finished
        self._controls = [(widget, widget.disabled) for widget in self.app.query("Button, Checkbox")]
        for widget, _ in self._controls:
            widget.disabled = True
        self._rules = self.app.query_one(TextArea)
        self._read_only = self._rules.read_only
        self._rules.read_only = True
        self.app.push_screen(self)

    def on_mount(self) -> None:
        self.show_status("開始執行")

        def finish(error: str | None) -> None:
            if error:
                self.append_log(f"{datetime.now():%H:%M:%S}  執行中止：{error}")
            phase = ("處理已結束；請查看錯誤紀錄" if error else "執行結束") if self.completed == self.total else (
                f"執行已停止；尚有 {self.total - self.completed} 個未處理")
            self.show_status(phase)
            self.running = False
            for widget, disabled in self._controls:
                widget.disabled = disabled
            self._rules.read_only = self._read_only
            self.query_one("#close-progress", Button).disabled = False
            self._finished(error)

        def run() -> None:
            def publish(image: Image, phase: str, results: tuple[Result, ...] | None) -> None:
                self.app.call_from_thread(self.update_progress, image, phase, results)

            error = None
            try:
                self._operation(publish)
            except Exception as exc:
                error = str(exc)
            self.app.call_from_thread(finish, error)

        self.run_worker(run, thread=True, name="cleanup")
