from pathlib import Path
import re

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Static, TextArea

from .config import CleanError, Config, load, save
from .engine import Docker, Image
from .plan import Preview, execute, plan, render, render_results


class CleanerApp(App):
    TITLE = "Docker Clean"
    CSS = """
    #rules { height: 6; }
    #images { height: 12; }
    #output { height: auto; padding: 1; }
    Horizontal { height: auto; }
    Button {
        width: auto;
        min-width: 0;
        height: 1;
        border: none;
        padding: 0 1;
        margin-right: 1;
    }
    #status { height: auto; padding: 1; }
    """
    BINDINGS = [("ctrl+q", "quit", "離開")]

    def __init__(self, path: Path, docker: Docker | None = None) -> None:
        super().__init__()
        self.path = path
        self.docker = docker
        self.revision: bytes | None = None
        self.images: dict[str, Image] = {}
        self.selected: set[str] = set()
        self.preview: Preview | None = None
        self.loaded = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("Regex 保留規則：每行一條，可直接新增、修改或刪除；搜尋匹配。")
            yield TextArea(id="rules")
            with Horizontal():
                yield Checkbox("移除 tag", id="remove-tags")
                yield Checkbox("強制刪除 image", id="force")
            with Horizontal():
                yield Button("儲存", id="save")
                yield Button("重新載入", id="reload")
                yield Button("重新盤點", id="refresh")
            yield Static("image 列表：Enter／點擊勾選，再按「產生規則」。可水平捲動查看完整欄位。")
            yield DataTable(id="images", cursor_type="row")
            with Horizontal():
                yield Button("產生規則", id="select")
                yield Button("預覽", id="preview")
                yield Button("確認刪除", id="confirm", variant="error", disabled=True)
                yield Button("取消", id="cancel")
            yield Static("", id="status", markup=False)
            yield Static("", id="output", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(DataTable).add_columns("選取", "完整 ID", "全部 tags", "bytes", "建立", "容器", "動作／原因")
        self.reload()
        self.refresh_images()

    def message(self, value: str) -> None:
        self.query_one("#status", Static).update(value)

    @staticmethod
    def rules_text(rules: tuple[str, ...]) -> str:
        # Preserve a final empty regex separately from an empty rule list.
        return "\n".join(rules) + ("\n" if rules and rules[-1] == "" else "")

    def current(self) -> Config:
        config = Config(tuple(self.query_one("#rules", TextArea).text.splitlines()),
                        self.query_one("#remove-tags", Checkbox).value,
                        self.query_one("#force", Checkbox).value)
        config.validate()
        return config

    def invalidate(self) -> None:
        self.preview = None
        self.query_one("#confirm", Button).disabled = True

    def reload(self) -> None:
        self.invalidate()
        self.loaded = False
        try:
            config, self.revision = load(self.path, allow_missing=True)
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
        table = self.query_one(DataTable)
        table.clear()
        for entry in preview.entries:
            image = entry.image
            table.add_row("✓" if image.id in self.selected else "□", image.id,
                          ", ".join(image.tags) or "無 tag", str(image.size), image.created,
                          ", ".join(f"{r.name} ({r.status})" for r in image.references) or "無",
                          entry.action + ": " + entry.reason, key=image.id)
        self.query_one("#output", Static).update(render(preview))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self.update_table()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.update_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        if key in self.selected:
            self.selected.remove(key)
        else:
            self.selected.add(key)
        self.update_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        try:
            action = event.button.id
            if action == "reload":
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
                self.invalidate()
                self.message("設定已儲存")
            elif action == "preview":
                config, revision = load(self.path)
                if config != self.current() or revision != self.revision:
                    raise CleanError("設定尚未儲存或已被外部修改；請儲存／重新載入後預覽")
                assert revision is not None
                if self.docker is None:
                    self.docker = Docker()
                self.images = self.docker.snapshot()
                self.update_table()
                self.preview = plan(config, self.images, revision)
                self.query_one("#output", Static).update(render(self.preview))
                has_targets = any(entry.targets for entry in self.preview.entries)
                self.query_one("#confirm", Button).disabled = not has_targets
                self.message("請查看下方完整預覽再確認。最後 tag 可能刪除 image；force 不保證成功。"
                             if has_targets else "沒有清理候選")
            elif action == "confirm" and self.preview is not None:
                preview = self.preview
                self.invalidate()
                assert self.docker is not None
                results = execute(preview, self.path, self.docker)
                self.query_one("#output", Static).update(render_results(results))
                self.message("執行完畢；請查看成功、跳過與失敗結果。容量未加總。")
        except CleanError as exc:
            self.invalidate()
            self.message(str(exc))
