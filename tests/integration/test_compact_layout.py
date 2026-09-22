"""Compact layout behavior using a fake inventory and actual Textual input."""
import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Footer, Static, TextArea

from docker_clean.engine import Image
from docker_clean.tui import CleanerApp
from docker_clean.whitelist import WhitelistApp


class Inventory:
    def snapshot(self):
        return {str(i): Image(str(i), (f"app:{i:03}",), 1, "2026-01-01") for i in range(100)}


@pytest.mark.parametrize("legacy", [False, True])
async def test_main_list_has_one_scroll_region_and_fixed_bottom_controls(tmp_path, legacy):
    app = CleanerApp(tmp_path / "config.yaml", Inventory()) if legacy else WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one(DataTable)
        controls = app.query_one("#preview", Button).region
        assert controls.y >= app.size.height - 3
        assert not any(region.display for region in app.query(VerticalScroll))
        assert app.screen.max_scroll_y == 0
        table.focus()
        await pilot.press("end")
        assert app.query_one("#preview", Button).region == controls
        assert app.query_one(Footer).region.y == 29
        assert app.query_one(Footer).region.y == controls.y
        assert app.query_one(Footer).region.x >= app.query_one("#cancel", Button).region.right
        assert app.query_one(Footer).region.right <= app.size.width
        bindings = app.screen.active_bindings
        assert not bindings["ctrl+t"].binding.show
        footer_keys = list(app.query("FooterKey"))
        assert footer_keys[0].region.x > 50
        await pilot.click("#help")
        assert app.screen.is_modal
        assert "Regex" in str(app.screen.query_one("#help-content", Static).render())
        if not legacy:
            colors = {color.get_truecolor()
                      for strip in app.screen._compositor.render_strips()
                      for segment in strip if segment.style
                      for color in (segment.style.color, segment.style.bgcolor)
                      if color and not color.is_default}
            assert colors <= {(0, 0, 0), (255, 255, 255)}
        await pilot.press("escape")
        assert not app.screen.is_modal
        if legacy:
            await pilot.click("#save")
        else:
            table.focus()
            await pilot.press("space")
        await pilot.click("#preview")
        if legacy:
            assert not table.display
            assert app.query_one("#preview-details", VerticalScroll).display
        else:
            assert table.display and table.row_count == 1
        assert app.query_one("#preview", Button).region == controls
        await pilot.click("#cancel")
        assert table.display


async def test_whitelist_input_grows_from_two_to_four_content_lines_then_scrolls():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        rules = app.query_one(TextArea)
        await pilot.pause()
        assert rules.content_size.height == 2
        rules.load_text("a\nb\nc")
        await pilot.pause()
        assert rules.content_size.height == 3
        rules.load_text("\n".join(str(i) for i in range(20)))
        await pilot.pause()
        assert rules.content_size.height == 4 and rules.max_scroll_y > 0
        rules.load_text("")
        await pilot.pause()
        assert rules.content_size.height == 2
