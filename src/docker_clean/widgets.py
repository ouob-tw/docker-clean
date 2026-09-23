"""Shared keyboard-friendly buttons and a non-expanding title bar."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Static


class ActionButton(Button):
    BINDINGS = [Binding("space", "press", "按下", show=False)]

    def on_mount(self) -> None:
        self.active_effect_duration = 0


class AppHeader(Horizontal):
    DEFAULT_CSS = """
    AppHeader { dock: top; height: 1; }
    #app-title { width: 1fr; text-align: center; }
    AppHeader #help { margin: 0; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title, id="app-title", markup=False)
        yield ActionButton("使用說明", id="help", tooltip="查看操作步驟與清理選項說明。")
