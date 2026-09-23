from textual.widgets import Button, Checkbox, DataTable, Static, TextArea, Tooltip

from docker_clean.config import Config, load, save
from docker_clean.engine import Image
from docker_clean.tui import CleanerApp


class DockerFixture:
    def __init__(self):
        self.calls = []

    def snapshot(self):
        image = Image("sha256:" + "a" * 64, ("registry:5000/a:1.2", "other:1"), 12, "2026-01-01")
        return {image.id: image}

    def remove(self, target, force):
        self.calls.append((target, force))
        return "Deleted: " + target


async def test_keep_buttons_show_help_after_hover_without_actions(tmp_path):
    path = tmp_path / "config.yaml"
    docker = DockerFixture()
    app = CleanerApp(path, docker)
    async with app.run_test(size=(100, 30), tooltips=True) as pilot:
        tooltip = app.screen.query_one(Tooltip)
        for button_id in ("help", "save", "reload", "refresh", "select", "preview", "confirm", "cancel"):
            await pilot.hover("#rules")
            await pilot.pause(app.TOOLTIP_DELAY + 0.1)
            await pilot.hover(f"#{button_id}")
            assert not tooltip.display, button_id
            await pilot.pause(app.TOOLTIP_DELAY + 0.1)
            assert tooltip.display, button_id
            assert str(app.query_one(f"#{button_id}", Button).tooltip) in str(tooltip.render())
        await pilot.hover("#rules")
        await pilot.pause(app.TOOLTIP_DELAY + 0.1)
        assert not tooltip.display
        assert not path.exists()
        assert not docker.calls


async def test_edit_save_reopen_preview_invalidation_and_cancel(tmp_path):
    path = tmp_path / "config.yaml"
    save(path, Config(unused_days=14), None)
    docker = DockerFixture()
    app = CleanerApp(path, docker)
    async with app.run_test(size=(140, 60)) as pilot:
        await pilot.pause(0.3)
        rules = app.query_one("#rules", TextArea)
        rules.load_text("^other:1$")
        await pilot.pause(0.3)
        assert "保留" in str(app.query_one("#output", Static).render())
        await pilot.click("#save")
        assert load(path)[0] == Config(("^other:1$",), unused_days=14)
        rules.load_text("")
        await pilot.pause(0.3)
        await pilot.click("#save")
        await pilot.click("#preview")
        assert not app.query_one("#confirm", Button).disabled, str(app.query_one("#status", Static).render())
        app.query_one("#force", Checkbox).value = True
        await pilot.pause(0.3)
        assert app.query_one("#confirm", Button).disabled
        await pilot.click("#save")
        await pilot.click("#preview")
        await pilot.click("#cancel")
        assert app.query_one("#confirm", Button).disabled
        assert not docker.calls
    reopened = CleanerApp(path, docker)
    async with reopened.run_test(size=(140, 60)) as pilot:
        await pilot.pause(0.3)
        assert reopened.query_one("#force", Checkbox).value
        assert reopened.query_one("#rules", TextArea).text == ""


async def test_select_image_generates_escaped_anchored_rules(tmp_path):
    app = CleanerApp(tmp_path / "config.yaml", DockerFixture())
    async with app.run_test(size=(140, 60)) as pilot:
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        await pilot.click("#select")
        text = app.query_one("#rules", TextArea).text
        assert r"^registry:5000/a:1\.2$" in text
        assert "^other:1$" in text


async def test_preview_reconciles_selection_after_external_image_removal(tmp_path):
    docker = DockerFixture()
    app = CleanerApp(tmp_path / "config.yaml", docker)
    async with app.run_test(size=(140, 60)) as pilot:
        await pilot.click("#save")
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        assert app.selected
        docker.snapshot = lambda: {}
        await pilot.click("#preview")
        await pilot.click("#select")
        assert app.selected == set()
        assert app.query_one(DataTable).row_count == 0
        assert app.query_one("#rules", TextArea).text == ""
        assert app.query_one("#confirm", Button).disabled
        assert docker.calls == []


async def test_selection_keeps_cursor_and_scroll_and_accepts_space(tmp_path):
    docker = DockerFixture()
    images = {f"sha256:{i:064x}": Image(f"sha256:{i:064x}", (f"app:{i}",),
              1234, "2026-09-21T12:34:56.123456+08:00") for i in range(30)}
    docker.snapshot = lambda: images
    app = CleanerApp(tmp_path / "config.yaml", docker)
    async with app.run_test(size=(120, 40)) as pilot:
        table = app.query_one(DataTable)
        table.focus()
        await pilot.press(*(["down"] * 15))
        await pilot.pause()
        before = table.scroll_offset
        selected_id = table.ordered_rows[15].key.value
        await pilot.press("enter")
        assert table.cursor_row == 15
        assert table.scroll_offset == before
        assert selected_id in app.selected
        await pilot.press("space")
        assert table.cursor_row == 15
        assert table.scroll_offset == before
        assert selected_id not in app.selected
        assert not docker.calls


async def test_compact_columns_wrap_tags_and_keep_full_id_in_preview(tmp_path):
    docker = DockerFixture()
    image = Image("sha256:" + "b" * 64, ("registry.example:5000/" + "long-name-" * 8 + ":1.2",),
                  1536, "2026-09-21T12:34:56.123456+08:00")
    docker.snapshot = lambda: {image.id: image}
    app = CleanerApp(tmp_path / "config.yaml", docker)
    async with app.run_test(size=(80, 40)) as pilot:
        await pilot.pause()
        table = app.query_one(DataTable)
        assert [str(column.label) for column in table.ordered_columns] == [
            "選", "tag ▲", "大小", "建立日期", "動作原因"]
        image = next(iter(docker.snapshot().values()))
        assert table.rows[table.ordered_rows[0].key].height > 1
        assert str(table.get_cell(image.id, "size")) == "1.5 KiB"
        assert str(table.get_cell(image.id, "created")) == "2026-09-21 12:34:56"
        assert image.id in str(app.query_one("#output", Static).render())
        for checkbox in app.query(Checkbox):
            checkbox.focus()
            await pilot.pause()
            assert checkbox.region.height == 1


async def test_theme_follows_terminal_and_persists_without_saving_draft_rules(tmp_path):
    path = tmp_path / "config.yaml"
    save(path, Config(("^saved:",), unused_days=14), None)
    app = CleanerApp(path, DockerFixture())
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.theme == "terminal"
        assert app.native_ansi_color
        app.query_one("#rules", TextArea).load_text("unfinished[")
        app.theme = "nord"
        await pilot.pause()
        assert load(path)[0] == Config(("^saved:",), theme="nord", unused_days=14)
        assert app.query_one("#rules", TextArea).text == "unfinished["
    reopened = CleanerApp(path, DockerFixture())
    async with reopened.run_test(size=(120, 40)) as pilot:
        assert reopened.theme == "nord"
        external = b"keep: ['^external:']\n"
        path.write_bytes(external)
        reopened.theme = "terminal"
        await pilot.pause()
        assert path.read_bytes() == external
        assert "尚未儲存" in str(reopened.query_one("#status", Static).render())
