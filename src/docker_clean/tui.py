from pathlib import Path
import re
from datetime import datetime
from dataclasses import replace
from collections.abc import Sequence

from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.filter import LineFilter, NoColor
from textual.theme import BUILTIN_THEMES, Theme
from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, DataTable, Footer, Static, TextArea

from .config import CleanError, Config, load, save
from .engine import Docker, Image
from .dialogs import HelpScreen
from .plan import Preview, ProgressCallback, Result, execute, plan, render
from .progress import CleanupProgress
from .scrolling import ContainedTextArea, ContainedVerticalScroll, ScrollContainment
from .themes import E_INK_CSS, E_INK_THEME
from .widgets import ActionButton as Button, AppHeader


class ImageTable(ScrollContainment, DataTable):
    BINDINGS = [Binding("space", "select_cursor", "選取", show=False)]
    sort_column = "tags"
    sort_reverse = False

    def toggle_sort(self, column: str) -> None:
        self.sort_reverse = not self.sort_reverse if column == self.sort_column else False
        self.sort_column = column

    def column_label(self, label: str, key: str) -> str:
        if key != self.sort_column:
            return label
        return label + ("" if key == "selected" else " ") + ("▼" if self.sort_reverse else "▲")

    def image_sort_key(self, image: Image, selected: set[str], reason: str = "") -> tuple:
        values = {
            "tags": tuple(tag.casefold() for tag in sorted(image.tags)) or ("\uffff",),
            "size": image.size,
            "created": datetime.fromisoformat(image.created.replace("Z", "+00:00")).timestamp(),
            "selected": image.id in selected,
            "reason": reason,
        }
        return values[self.sort_column], image.id


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def readable_date(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")


class CleanerApp(App):
    TITLE = "Docker Image Clean — Keep（保留規則）"
    CSS = """
    Screen { overflow: hidden; }
    #rules { height: 6; }
    #images { height: 1fr; }
    #preview-details { height: 1fr; display: none; }
    .previewing #images { display: none; }
    .previewing #preview-details { display: block; }
    #bottom-bar { dock: bottom; height: auto; }
    Footer { dock: none; width: 1fr; height: 1; align-horizontal: right; }
    #output { height: auto; padding: 1; }
    Horizontal { height: auto; }
    Checkbox { height: 1; margin-right: 2; }
    Button {
        width: auto;
        min-width: 0;
        height: 1;
        border: none;
        padding: 0 1;
        margin-right: 1;
    }
    AppHeader #help { margin-right: 0; }
    #status { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
    """ + E_INK_CSS
    BINDINGS = [Binding("ctrl+q", "quit", "離開"),
                Binding("ctrl+p", "command_palette", "命令選單"),
                Binding("ctrl+t", "change_theme", "主題", show=False)]

    def __init__(self, path: Path, docker: Docker | None = None) -> None:
        # Choose the native-color NO_COLOR filter before registering our theme.
        super().__init__(ansi_color=True)
        self.register_theme(replace(BUILTIN_THEMES["ansi-dark"], name="terminal"))
        self.register_theme(E_INK_THEME)
        self.theme = "terminal"
        self.ansi_color = None
        self.path = path
        self.docker = docker
        self.revision: bytes | None = None
        self.images: dict[str, Image] = {}
        self.selected: set[str] = set()
        self.preview: Preview | None = None
        self.loaded = False
        self.saved_config = Config()
        self.cleanup = CleanupProgress()

    def get_line_filters(self) -> Sequence[LineFilter]:
        filters = super().get_line_filters()
        if self.theme == "e-ink":
            # E-Ink is already monochrome; preserve its explicit black/white contrast.
            return [filter for filter in filters if not isinstance(filter, NoColor)]
        return filters

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield ContainedTextArea(id="rules")
        with Horizontal():
            yield Checkbox("逐一移除標籤", id="remove-tags", compact=True,
                           tooltip="逐一移除待清理 image 的所有 tag；最後一個標籤移除時，可能一併刪除 image。")
            yield Checkbox("強制刪除 image", id="force", compact=True)
        with Horizontal():
            yield Button("儲存", id="save")
            yield Button("重新載入", id="reload")
            yield Button("刷新", id="refresh")
        yield ImageTable(id="images", cursor_type="row")
        with ContainedVerticalScroll(id="preview-details"):
            yield Static("", id="output", markup=False)
        with Vertical(id="bottom-bar"):
            yield Static("", id="status", markup=False)
            with Horizontal():
                yield Button("產生規則", id="select")
                yield Button("預覽", id="preview")
                yield Button("確認刪除", id="confirm", variant="error", disabled=True)
                yield Button("取消", id="cancel")
                yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.reload()
        self.refresh_images()
        self.theme_changed_signal.subscribe(self, self.persist_theme)

    def on_resize(self) -> None:
        if self.query("#images") and not self.cleanup.running:
            self.call_after_refresh(self.redraw_table)

    async def action_quit(self) -> None:
        if self.cleanup.running:
            self.message("刪除正在執行；請等待結果後離開。")
        else:
            self.exit()

    def action_change_theme(self) -> None:
        if self.cleanup.running:
            self.message("刪除正在執行；請等待結果後切換主題。")
        else:
            super().action_change_theme()

    def persist_theme(self, theme: Theme) -> None:
        if self.cleanup.running:
            return
        if not self.loaded or theme.name != self.theme or theme.name == self.saved_config.theme:
            return
        self.invalidate()
        try:
            # Theme changes must not save unrelated, unfinished rule edits.
            config = replace(self.saved_config, theme=theme.name)
            self.revision = save(self.path, config, self.revision)
            self.saved_config = config
            self.message(f"主題 {theme.name} 已儲存；terminal 使用終端原生配色。")
        except CleanError as exc:
            self.message(f"主題尚未儲存：{exc}")

    def message(self, value: str) -> None:
        self.query_one("#status", Static).update(value)

    @staticmethod
    def rules_text(rules: tuple[str, ...]) -> str:
        # Preserve a final empty regex separately from an empty rule list.
        return "\n".join(rules) + ("\n" if rules and rules[-1] == "" else "")

    def current(self) -> Config:
        config = Config(tuple(self.query_one("#rules", TextArea).text.splitlines()),
                        self.query_one("#remove-tags", Checkbox).value,
                        self.query_one("#force", Checkbox).value, self.theme,
                        self.saved_config.unused_days)
        config.validate()
        return config

    def invalidate(self) -> None:
        self.preview = None
        self.remove_class("previewing")
        self.query_one("#confirm", Button).disabled = True

    def reload(self) -> None:
        self.invalidate()
        self.loaded = False
        try:
            config, self.revision = load(self.path, allow_missing=True)
            self.saved_config = config
            self.theme = config.theme
            self.query_one("#rules", TextArea).load_text(self.rules_text(config.keep))
            self.query_one("#remove-tags", Checkbox).value = config.remove_tags
            self.query_one("#force", Checkbox).value = config.force
            self.loaded = True
            self.message(f"設定: {self.path}" + ("（尚未建立，請儲存）" if self.revision is None else ""))
            self.update_table()
        except CleanError as exc:
            self.message(str(exc))

    def refresh_images(self) -> None:
        self.invalidate()
        try:
            if self.docker is None:
                self.docker = Docker()
            self.images = self.docker.snapshot()
            self.update_table()
        except CleanError as exc:
            self.images = {}
            self.selected.clear()
            self.query_one(DataTable).clear()
            self.message(str(exc))

    def update_table(self) -> None:
        self.invalidate()
        self.selected.intersection_update(self.images)
        try:
            preview = plan(self.current(), self.images)
        except CleanError as exc:
            self.message(str(exc))
            return
        table = self.query_one(ImageTable)
        cursor_row = table.cursor_row
        cursor_key = (table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
                      if table.row_count else None)
        offset = table.scroll_offset
        available = max(36, self.size.width - 43)
        tag_width = available // 2
        table.clear(columns=True)
        for label, key, width in (("選", "selected", 3), ("tag", "tags", tag_width),
                                  ("大小", "size", 9), ("建立日期", "created", 19),
                                  ("動作原因", "reason", available - tag_width)):
            table.add_column(table.column_label(label, key), key=key, width=width)
        entries = sorted(preview.entries, key=lambda entry: table.image_sort_key(
            entry.image, self.selected, entry.action + ": " + entry.reason), reverse=table.sort_reverse)
        for entry in entries:
            image = entry.image
            table.add_row("✓" if image.id in self.selected else "□",
                          Text("\n".join(image.tags) or "無 tag", overflow="fold"),
                          readable_size(image.size), readable_date(image.created),
                          Text(entry.action + ": " + entry.reason, overflow="fold"),
                          key=image.id, height=None)
        if table.row_count:
            keys = [entry.image.id for entry in entries]
            row = keys.index(cursor_key) if cursor_key in keys else min(cursor_row, table.row_count - 1)
            table.move_cursor(row=row, scroll=False)
            self.call_after_refresh(table.scroll_to, x=offset.x, y=offset.y, animate=False)
        self.query_one("#output", Static).update(render(preview))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if self.cleanup.running:
            return
        try:
            self.current().validate()
        except CleanError as exc:
            self.message(str(exc))
            return
        table = self.query_one(ImageTable)
        table.toggle_sort(str(event.column_key.value))
        self.redraw_table()

    def redraw_table(self) -> None:
        preview = self.preview
        previewing = self.has_class("previewing")
        output = self.query_one("#output", Static).render()
        self.update_table()
        self.preview = preview
        self.set_class(previewing, "previewing")
        self.query_one("#output", Static).update(output)
        self.query_one("#confirm", Button).disabled = not (
            preview and any(entry.targets for entry in preview.entries))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self.cleanup.running:
            return
        self.query_one("#output", Static).display = True
        self.update_table()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if self.cleanup.running:
            return
        self.query_one("#output", Static).display = True
        self.update_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.cleanup.running:
            return
        key = str(event.row_key.value)
        if key in self.selected:
            self.selected.remove(key)
        else:
            self.selected.add(key)
        self.invalidate()
        self.query_one(DataTable).update_cell(key, "selected", "✓" if key in self.selected else "□")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.cleanup.running or self.screen.is_modal:
            return
        try:
            action = event.button.id
            if action == "help":
                self.push_screen(HelpScreen(whitelist=False))
            elif action == "reload":
                self.reload()
            elif action == "refresh":
                self.refresh_images()
            elif action == "cancel":
                self.invalidate()
                self.message("已取消；未修改 Docker")
            elif action == "select":
                rules = list(self.current().keep)
                for image_id in sorted(self.selected):
                    for tag in self.images[image_id].tags:
                        pattern = "^" + re.escape(tag) + "$"
                        if pattern not in rules:
                            rules.append(pattern)
                self.query_one("#rules", TextArea).load_text(self.rules_text(tuple(rules)))
                self.message("已產生精確 tag 規則；無 tag 的 image 不產生規則。請儲存。")
            elif action == "save":
                if not self.loaded:
                    raise CleanError("設定載入失敗，請修正檔案並重新載入")
                self.revision = save(self.path, self.current(), self.revision)
                self.saved_config = self.current()
                self.invalidate()
                self.message("設定已儲存")
            elif action == "preview":
                self.query_one("#output", Static).display = True
                config, revision = load(self.path)
                if config != self.current() or revision != self.revision:
                    raise CleanError("設定尚未儲存或已被外部修改；請儲存／重新載入後預覽")
                assert revision is not None
                if self.docker is None:
                    self.docker = Docker()
                self.images = self.docker.snapshot()
                self.update_table()
                self.preview = plan(config, self.images, revision)
                self.add_class("previewing")
                self.query_one("#output", Static).update(render(self.preview))
                has_targets = any(entry.targets for entry in self.preview.entries)
                self.query_one("#confirm", Button).disabled = not has_targets
                self.message("請查看下方完整預覽再確認。最後 tag 可能刪除 image；force 不保證成功。"
                             if has_targets else "沒有清理候選")
            elif action == "confirm" and self.preview is not None:
                preview = self.preview
                self.invalidate()
                self.cleanup = CleanupProgress()
                assert self.docker is not None
                docker = self.docker

                def operation(progress: ProgressCallback) -> list[Result]:
                    results = execute(preview, self.path, docker, progress)
                    self.call_from_thread(self.cleanup.show_status, "正在刷新")
                    images = docker.snapshot()
                    self.call_from_thread(setattr, self, "images", images)
                    return results

                def finished(error: str | None) -> None:
                    self.selected.clear()
                    if error:
                        self.images = {}
                    self.update_table()
                    self.message(f"執行或盤點失敗：{error}；清單已清空，請刷新。" if error
                                 else "執行已結束；詳細紀錄由舊到新排列。")

                self.query_one("#output", Static).display = False
                self.cleanup.start(len(preview.entries), operation, finished)
        except CleanError as exc:
            self.invalidate()
            self.message(str(exc))
