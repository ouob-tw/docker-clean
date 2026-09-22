"""Explicit image selection, independent of legacy retention settings."""
from dataclasses import replace
import re

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.theme import BUILTIN_THEMES
from textual.widgets import DataTable, Footer, Static, TextArea

from .config import CleanError
from .engine import Docker, Image
from .dialogs import HelpScreen, ImageDetails
from .plan import ProgressCallback, Result
from .progress import CleanupProgress
from .scrolling import ContainedTextArea
from .themes import E_INK_THEME
from .tui import CleanerApp, ImageTable, readable_date, readable_size
from .widgets import ActionButton as Button, AppHeader


def matching_ids(text: str, images: dict[str, Image]) -> set[str]:
    patterns = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            patterns.append(re.compile(line))
        except re.error as exc:
            raise CleanError(f"第 {number} 行 Regex 無效：{exc}") from exc
    return {image.id for image in images.values()
            if any(pattern.search(tag) for pattern in patterns
                   for tag in (image.tags or ("None",)))}


def delete_selected(images: tuple[Image, ...], docker: Docker,
                    progress: ProgressCallback | None = None) -> list[Result]:
    results: list[Result] = []
    for image in images:
        start = len(results)
        try:
            if progress:
                progress(image, "重新檢查狀態", None)
            try:
                current = docker.snapshot().get(image.id)
            except CleanError as exc:
                results.append(Result("失敗", image.id, str(exc)))
                break
            if current != image:
                results.append(Result("跳過", image.id, "image／tag／容器引用已變更，請重新預覽"))
                continue
            if progress:
                progress(image, "正在強制刪除", None)
            try:
                output = docker.forceDeleteImage(image.id)
            except CleanError as exc:
                results.append(Result("失敗", image.id, str(exc)))
                continue
            for line in output.splitlines() or ["Docker 已接受請求；未回報釋放容量"]:
                status = "移除 tag" if line.startswith("Untagged:") else (
                    "刪除 image" if line.startswith("Deleted:") else "成功")
                results.append(Result(status, image.id, line))
        finally:
            if progress:
                progress(image, "已處理", tuple(results[start:]))
    return results


class WhitelistApp(App):
    TITLE = "Docker Clean — 白名單刪除"
    CSS = CleanerApp.CSS + """
    #rules { height: 4; }
    """
    BINDINGS = CleanerApp.BINDINGS

    def __init__(self, docker: Docker | None = None) -> None:
        super().__init__()
        self.register_theme(replace(BUILTIN_THEMES["ansi-dark"], name="terminal"))
        self.register_theme(E_INK_THEME)
        self.theme = "e-ink"
        self.docker = docker
        self.images: dict[str, Image] = {}
        self.selected: set[str] = set()
        self.preview: tuple[Image, ...] | None = None
        self.cleanup = CleanupProgress()
        self.filter_text: str | None = None

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield ContainedTextArea(id="rules")
        with Horizontal():
            yield Button("Regex 篩選", id="filter")
            yield Button("顯示全部", id="show-all", disabled=True)
            yield Button("Regex 勾選", id="select")
            yield Button("清除勾選", id="clear")
            yield Button("刷新", id="refresh")
            yield Button("詳細資料", id="details")
        yield ImageTable(id="images", cursor_type="row")
        with Vertical(id="bottom-bar"):
            yield Static("", id="status", markup=False)
            with Horizontal():
                yield Button("預覽", id="preview")
                yield Button("確認強制刪除", id="confirm", variant="error", disabled=True)
                yield Button("取消／返回", id="cancel")
                yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.refresh_images()

    def on_resize(self) -> None:
        if self.query("#images") and not self.cleanup.running:
            self.call_after_refresh(self.update_table)
            self.call_after_refresh(self.fit_rules)

    def fit_rules(self) -> None:
        rules = self.query_one(TextArea)
        rules.styles.height = min(4, max(2, rules.wrapped_document.height)) + 2

    async def action_quit(self) -> None:
        if self.cleanup.running:
            self.message("刪除正在執行；請等待結果後離開。")
        else:
            self.exit()

    def message(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def invalidate(self) -> None:
        self.preview = None
        self.query_one("#confirm", Button).disabled = True

    def refresh_images(self) -> bool:
        self.invalidate()
        try:
            if self.docker is None:
                self.docker = Docker()
            self.images = self.docker.snapshot()
            self.selected.intersection_update(self.images)
            self.message(f"共 {len(self.images)} 個 image；已勾選 {len(self.selected)} 個。")
        except CleanError as exc:
            self.images = {}
            self.selected.clear()
            self.message(str(exc))
            self.update_table()
            return False
        self.update_table()
        return True

    def update_table(self) -> None:
        self.query_one("#show-all", Button).disabled = self.filter_text is None
        table = self.query_one(ImageTable)
        cursor = (table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
                  if table.row_count else None)
        row, offset = table.cursor_row, table.scroll_offset
        visible = self.images.values()
        if self.filter_text is not None:
            matches = matching_ids(self.filter_text, self.images)
            visible = {key: image for key, image in self.images.items() if key in matches}.values()
        images = sorted(self.preview if self.preview is not None else visible,
                        key=lambda image: table.image_sort_key(image, self.selected, self.reason(image.id)),
                        reverse=table.sort_reverse)
        available = max(36, self.size.width - 43)
        table.clear(columns=True)
        for label, key, width in (("選", "selected", 3), ("tag", "tags", available // 2),
                                  ("大小", "size", 9), ("建立日期", "created", 19),
                                  ("動作原因", "reason", available - available // 2)):
            table.add_column(table.column_label(label, key), key=key, width=width)
        for image in images:
            selected = image.id in self.selected
            table.add_row("✓" if selected else "□",
                          Text("\n".join(image.tags) or "None", overflow="fold"),
                          readable_size(image.size), readable_date(image.created),
                          Text(self.reason(image.id), overflow="fold"),
                          key=image.id, height=None)
        if images:
            keys = [image.id for image in images]
            table.move_cursor(row=keys.index(cursor) if cursor in keys else min(row, len(keys) - 1),
                              scroll=False)
            self.call_after_refresh(table.scroll_to, x=offset.x, y=offset.y, animate=False)

    def reason(self, image_id: str) -> str:
        reason = "強制刪除整個 image" if image_id in self.selected else "未勾選，不刪除"
        if self.preview is not None:
            refs = "、".join(f"{ref.name} ({ref.status})" for ref in self.images[image_id].references) or "無"
            # Separate the fixed-height action line so toggling cannot change wrapping of refs.
            reason += f"\n容器：{refs}"
        return reason

    def update_selection(self, keys: set[str], was_preview: bool) -> None:
        if was_preview:
            self.update_table()
            return
        table = self.query_one(DataTable)
        visible = {row.key.value for row in table.ordered_rows}
        for key in keys:
            if key not in visible:
                continue
            table.update_cell(key, "selected", "✓" if key in self.selected else "□")
            table.update_cell(key, "reason", Text(self.reason(key), overflow="fold"))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if self.cleanup.running:
            return
        self.query_one(ImageTable).toggle_sort(str(event.column_key.value))
        self.update_table()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self.cleanup.running:
            return
        was_preview = self.preview is not None
        self.invalidate()
        self.fit_rules()
        if was_preview:
            self.update_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.cleanup.running:
            return
        key = str(event.row_key.value)
        self.selected.symmetric_difference_update({key})
        if self.preview is not None:
            self.update_selection({key}, False)
            self.update_preview_status()
        else:
            self.invalidate()
            self.update_selection({key}, False)
            self.message(f"已勾選 {len(self.selected)} 個 image；請預覽後確認。")

    def update_preview_status(self) -> None:
        count = sum(image.id in self.selected for image in self.preview or ())
        self.query_one("#confirm", Button).disabled = not count
        self.message(f"預覽：{count} 個待刪 image；可取消勾選。force 不停止或刪除容器，也不保證成功。"
                     if count else "沒有勾選項目；不會刪除。")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.cleanup.running or self.screen.is_modal:
            return
        action = event.button.id
        try:
            if action == "help":
                self.push_screen(HelpScreen(whitelist=True))
            elif action == "details":
                table = self.query_one(DataTable)
                if table.row_count:
                    key = str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value)
                    self.push_screen(ImageDetails(self.images[key]))
                else:
                    self.message("沒有可查看的項目。")
            elif action == "filter":
                text = self.query_one(TextArea).text
                matches = matching_ids(text, self.images)
                self.filter_text = text if text.strip() else None
                self.invalidate()
                self.update_table()
                count = len(matches) if self.filter_text is not None else len(self.images)
                self.message(f"顯示 {count}／{len(self.images)} 個 image；共勾選 {len(self.selected)} 個（不受篩選影響）。")
            elif action == "show-all":
                self.filter_text = None
                self.invalidate()
                self.update_table()
                self.message(f"顯示全部 {len(self.images)} 個 image；保留 {len(self.selected)} 個勾選。")
            elif action == "confirm" and self.preview is not None:
                preview = tuple(image for image in self.preview if image.id in self.selected)
                if not preview:
                    return
                self.invalidate()
                self.cleanup = CleanupProgress()
                assert self.docker is not None
                docker = self.docker

                def operation(progress: ProgressCallback) -> list[Result]:
                    results = delete_selected(preview, docker, progress)
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

                self.cleanup.start(len(preview), operation, finished)
            elif action == "preview":
                if not self.refresh_images():
                    return
                self.preview = tuple(self.images[key] for key in sorted(self.selected))
                self.update_table()
                self.update_preview_status()
                self.query_one(DataTable).focus()
            elif action == "select":
                matches = matching_ids(self.query_one("#rules", TextArea).text, self.images)
                was_preview = self.preview is not None
                changed = matches - self.selected
                self.invalidate()
                self.selected.update(matches)
                self.update_selection(changed, was_preview)
                self.message(f"Regex 命中 {len(matches)} 個；共勾選 {len(self.selected)} 個 image。")
            elif action == "clear":
                was_preview = self.preview is not None
                changed = set(self.selected)
                self.invalidate()
                self.selected.clear()
                self.update_selection(changed, was_preview)
                self.message("已清除勾選。")
            elif action == "refresh":
                self.refresh_images()
            elif action == "cancel":
                self.invalidate()
                self.update_table()
                self.message("已取消預覽；未修改 Docker，可繼續調整勾選。")
        except CleanError as exc:
            self.invalidate()
            self.update_table()
            self.message(str(exc))
