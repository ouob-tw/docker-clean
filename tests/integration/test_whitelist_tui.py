"""Real Textual interactions with a fake Docker; no real deletion evidence."""
from dataclasses import replace

from textual.widgets import Button, DataTable, Static, TextArea

from docker_clean.config import CleanError
from docker_clean.engine import Image
from docker_clean.whitelist import WhitelistApp


class DockerFixture:
    def __init__(self):
        self.images = {f"sha256:{i:064x}": Image(f"sha256:{i:064x}", tags, 1536,
                      "2026-09-21T12:34:56Z") for i, tags in enumerate([
                          ("app:1", "alias:latest"), ("db:2",), (), ("keep:1",)])}
        self.calls = []

    def snapshot(self):
        return dict(self.images)

    def forceDeleteImage(self, image_id):
        self.calls.append(image_id)
        self.images.pop(image_id)
        return "Deleted: " + image_id


async def test_regex_manual_preview_cancel_and_force_delete():
    docker = DockerFixture()
    ids = list(docker.images)
    app = WhitelistApp(docker)
    async with app.run_test(size=(120, 45)) as pilot:
        table = app.query_one(DataTable)
        assert not app.selected
        app.query_one(TextArea).load_text("^alias:\n^db:\n\n")
        await pilot.pause()
        await pilot.click("#select")
        assert app.selected == set(ids[:2])
        table.focus()
        table.move_cursor(row=1)
        await pilot.press("space")
        table.move_cursor(row=table.get_row_index(ids[2]))
        await pilot.press("enter")
        assert app.selected == {ids[0], ids[2]}
        await pilot.click("#preview")
        assert table.row_count == 2
        assert str(table.get_cell(ids[0], "tags")) == "app:1\nalias:latest"
        assert str(table.get_cell(ids[2], "tags")) == "None"
        table.move_cursor(row=table.get_row_index(ids[0]))
        await pilot.click("#details")
        details = str(app.screen.query_one("#image-details", Static).render())
        assert ids[0] in details and "alias:latest" in details and "app:1" in details
        await pilot.press("escape")
        await pilot.resize_terminal(100, 45)
        assert table.row_count == 2
        assert not app.query_one("#confirm", Button).disabled
        await pilot.click("#cancel")
        assert table.row_count == 4 and not docker.calls
        await pilot.click("#preview")
        await pilot.click("#confirm")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert docker.calls == [ids[0], ids[2]]
        assert set(docker.images) == {ids[1], ids[3]}
        assert app.query_one("#confirm", Button).disabled
        await pilot.press("escape")
        await pilot.click("#confirm")
        assert len(docker.calls) == 2


async def test_invalid_empty_rules_and_preview_invalidation():
    docker = DockerFixture()
    app = WhitelistApp(docker)
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.click("#select")
        await pilot.click("#preview")
        assert app.query_one("#confirm", Button).disabled
        assert app.query_one(DataTable).row_count == 0
        await pilot.click("#cancel")
        await pilot.click("#images", offset=(2, 1))
        assert len(app.selected) == 1
        await pilot.click("#preview")
        app.query_one(TextArea).load_text("app\n[")
        await pilot.pause()
        assert app.query_one("#confirm", Button).disabled
        assert app.query_one(DataTable).row_count == 4
        before = set(app.selected)
        await pilot.click("#select")
        assert app.selected == before
        assert "第 2 行" in str(app.query_one("#status", Static).render())
        await pilot.click("#clear")
        assert not app.selected and not docker.calls


async def test_external_change_and_inventory_failure():
    docker = DockerFixture()
    app = WhitelistApp(docker)
    async with app.run_test(size=(120, 45)) as pilot:
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        await pilot.click("#preview")
        key = next(iter(app.selected))
        docker.images[key] = replace(docker.images[key], tags=("new:1",))
        await pilot.click("#confirm")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert not docker.calls
        assert "已變更" in str(app.cleanup.query_one(".cleanup-entry", Static).render())
        await pilot.press("escape")
        def fail():
            raise CleanError("inventory unavailable")
        docker.snapshot = fail
        await pilot.click("#preview")
        assert "inventory unavailable" in str(app.query_one("#status", Static).render())
        assert app.query_one("#confirm", Button).disabled


async def test_default_eink_theme_has_white_surfaces_and_black_text():
    from textual.color import Color
    app = WhitelistApp(DockerFixture())
    async with app.run_test(size=(120, 45)) as pilot:
        assert app.theme == "e-ink"
        assert app.screen.styles.background == Color.parse("#ffffff")
        for widget in [app.query_one(TextArea), app.query_one(DataTable),
                       app.query_one("#select", Button)]:
            assert widget.styles.background == Color.parse("#ffffff")
            assert widget.styles.color == Color.parse("#000000")
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        await pilot.click("#preview")
        assert not app.query_one("#confirm", Button).disabled
