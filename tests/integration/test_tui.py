from textual.widgets import Button, Checkbox, DataTable, Static, TextArea

from docker_clean.config import Config, load
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


async def test_edit_save_reopen_preview_invalidation_and_cancel(tmp_path):
    path = tmp_path / "config.yaml"
    docker = DockerFixture()
    app = CleanerApp(path, docker)
    async with app.run_test(size=(140, 60)) as pilot:
        await pilot.pause(0.3)
        rules = app.query_one("#rules", TextArea)
        rules.load_text("^other:1$")
        await pilot.pause(0.3)
        assert "保留" in str(app.query_one("#output", Static).render())
        await pilot.click("#save")
        assert load(path)[0] == Config(("^other:1$",))
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
