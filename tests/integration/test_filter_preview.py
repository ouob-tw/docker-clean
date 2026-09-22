"""Real input and preview transitions with fake Docker only."""
import pytest
from dataclasses import replace
from unittest.mock import patch
from textual.widgets import Button, DataTable, Static, TextArea

from docker_clean.engine import Image, Reference
from docker_clean.tui import CleanerApp
from docker_clean.whitelist import WhitelistApp


class Inventory:
    def __init__(self):
        self.images = {
            "sha256:a": Image("sha256:a", ("app:1", "alias:1"), 1, "2026-01-01",
                              (Reference("container-a", "worker", "running"),)),
            "sha256:b": Image("sha256:b", ("db:1",), 2, "2026-01-02"),
            "sha256:c": Image("sha256:c", (), 3, "2026-01-03"),
        }
        self.calls = []

    def snapshot(self):
        return dict(self.images)

    def forceDeleteImage(self, key):
        self.calls.append(key)
        self.images.pop(key)
        return f"Deleted: {key}"


@pytest.mark.parametrize("legacy", [False, True])
async def test_help_top_right_static_title_and_space_button(tmp_path, legacy):
    app = CleanerApp(tmp_path / "config.yaml", Inventory()) if legacy else WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        help_button = app.query_one("#help", Button)
        assert help_button.region.y == 0 and help_button.region.right == 100
        before = app.query_one(DataTable).region
        await pilot.click("#app-title")
        assert len(app.screen_stack) == 1
        assert app.query_one(DataTable).region == before
        help_button.focus()
        await pilot.press("space")
        assert app.screen.is_modal
        app.screen.query_one("#close-help", Button).focus()
        await pilot.press("space")
        assert not app.screen.is_modal
        assert str(app.query_one("#refresh", Button).label) == "刷新"


async def test_space_activates_focused_button_without_changing_text_input():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        app.query_one(TextArea).load_text("app:")
        await pilot.pause()
        app.query_one("#select", Button).focus()
        await pilot.press("space")
        assert app.selected == {"sha256:a"}
        app.query_one(TextArea).focus()
        await pilot.press("space")
        assert " " in app.query_one(TextArea).text


async def test_filter_is_display_only_and_preview_allows_reversible_deselection():
    docker = Inventory()
    app = WhitelistApp(docker)
    async with app.run_test(size=(120, 35)) as pilot:
        rules = app.query_one(TextArea)
        table = app.query_one(DataTable)
        rules.load_text("app:|db:")
        await pilot.pause()
        await pilot.click("#select")
        assert app.selected == {"sha256:a", "sha256:b"}
        rules.load_text("alias:")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 1
        assert app.selected == {"sha256:a", "sha256:b"}
        assert not docker.calls
        await pilot.click("#preview")
        assert table.display and table.row_count == 2
        assert "worker" in str(table.get_cell("sha256:a", "reason"))
        table.focus()
        table.move_cursor(row=table.get_row_index("sha256:a"))
        await pilot.press("space")
        assert app.preview is not None and table.row_count == 2
        assert table.get_cell("sha256:a", "selected") == "□"
        assert not app.query_one("#confirm", Button).disabled
        await pilot.press("space")
        assert app.selected == {"sha256:a", "sha256:b"}
        await pilot.press("space", "down", "space")
        assert not app.selected and app.query_one("#confirm", Button).disabled
        await pilot.press("space")
        app.query_one("#confirm", Button).focus()
        await pilot.press("space")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert docker.calls == ["sha256:b"]


async def test_invalid_filter_preserves_view_and_empty_filter_restores_all():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        rules = app.query_one(TextArea)
        table = app.query_one(DataTable)
        rules.load_text("db:")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 1
        rules.load_text("[")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 1
        assert "Regex 無效" in str(app.query_one("#status", Static).render())
        rules.load_text("")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 3 and not app.selected


async def test_show_all_restores_rows_preserving_regex_selection_and_invalidating_preview():
    docker = Inventory()
    app = WhitelistApp(docker)
    async with app.run_test(size=(80, 24)) as pilot:
        rules = app.query_one(TextArea)
        table = app.query_one(DataTable)
        show_all = app.query_one("#show-all", Button)
        assert show_all.disabled
        assert app.query_one("#details", Button).region.right <= 80
        table.focus()
        await pilot.press("space")
        rules.load_text("db:")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 1 and not show_all.disabled
        await pilot.click("#show-all")
        assert table.row_count == 3 and show_all.disabled
        assert rules.text == "db:" and app.selected == {"sha256:a"}
        await pilot.click("#filter")
        await pilot.click("#preview")
        assert app.preview is not None and not app.query_one("#confirm", Button).disabled
        show_all.focus()
        await pilot.press("space")
        assert table.row_count == 3 and app.preview is None
        assert app.query_one("#confirm", Button).disabled
        assert rules.text == "db:" and app.selected == {"sha256:a"}
        assert show_all.disabled and not docker.calls


async def test_untagged_displays_none_and_can_be_filtered_without_selecting():
    docker = Inventory()
    app = WhitelistApp(docker)
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one(DataTable)
        assert str(table.get_cell("sha256:c", "tags")) == "None"
        app.query_one(TextArea).load_text("^None$")
        await pilot.pause()
        await pilot.click("#filter")
        assert table.row_count == 1
        assert table.ordered_rows[0].key.value == "sha256:c"
        assert not app.selected and not docker.calls
        assert docker.images["sha256:c"].tags == ()
        table.focus()
        await pilot.press("space")
        assert app.selected == {"sha256:c"}
        await pilot.click("#preview")
        assert table.row_count == 1 and app.preview is not None
        await pilot.click("#details")
        details = str(app.screen.query_one("#image-details", Static).render())
        assert "sha256:c" in details and "None" in details


@pytest.mark.parametrize("filter_first", [False, True])
async def test_regex_selects_untagged_none_and_deletes_only_confirmed_id(filter_first):
    docker = Inventory()
    app = WhitelistApp(docker)
    async with app.run_test(size=(100, 30)) as pilot:
        app.query_one(TextArea).load_text("^None$")
        await pilot.pause()
        if filter_first:
            await pilot.click("#filter")
            assert not app.selected
        await pilot.click("#select")
        assert app.selected == {"sha256:c"}
        assert docker.images["sha256:c"].tags == () and not docker.calls
        await pilot.click("#preview")
        assert app.query_one(DataTable).row_count == 1
        assert app.preview[0].tags == ()
        await pilot.click("#confirm")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert docker.calls == ["sha256:c"]
        assert set(docker.images) == {"sha256:a", "sha256:b"}


@pytest.mark.parametrize("legacy, selector", [(False, "#help"), (True, "#help"), (False, "#details")])
async def test_double_click_opens_only_one_dialog(tmp_path, legacy, selector):
    app = CleanerApp(tmp_path / "config.yaml", Inventory()) if legacy else WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click(selector, times=2)
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        assert not app.screen.is_modal


async def test_preview_focuses_table_for_immediate_keyboard_deselection():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one(DataTable)
        table.focus()
        await pilot.press("space")
        await pilot.click("#preview")
        assert app.focused is table
        await pilot.press("space")
        assert app.preview is not None and not app.selected


async def test_preview_reselection_keeps_references_visible_without_rebuilding_rows():
    docker = Inventory()
    key = "sha256:a"
    docker.images[key] = replace(docker.images[key], tags=("app:1",),
                                 references=(Reference("c", "ab", "up"),))
    app = WhitelistApp(docker)
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one(DataTable)
        table.focus()
        await pilot.press("space")
        await pilot.click("#preview")
        table.focus()
        await pilot.press("space")
        await pilot.resize_terminal(101, 30)
        await pilot.resize_terminal(100, 30)
        rows, offset = list(table.ordered_rows), table.scroll_offset
        with patch.object(table, "clear", wraps=table.clear) as clear:
            await pilot.press("space")
            assert not clear.called
        assert table.ordered_rows == rows and table.scroll_offset == offset
        reason = table.get_cell(key, "reason")
        width = table.ordered_columns[-1].width
        assert table.get_row_height(key) >= len(reason.wrap(app.console, width))
        rendered = "\n".join("".join(segment.text for segment in strip)
                             for strip in app.screen._compositor.render_strips())
        assert "ab (up)" in rendered
