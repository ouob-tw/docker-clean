"""Theme selection through the actual command palette, with fake inventory."""
import pytest
from textual.widgets import Checkbox, DataTable, OptionList, TextArea

from docker_clean.config import Config, load, save
from docker_clean.engine import Image
from docker_clean.tui import CleanerApp
from docker_clean.whitelist import WhitelistApp


class Inventory:
    def snapshot(self):
        image = Image("sha256:a", ("app:1",), 1, "2026-01-01")
        return {image.id: image}


@pytest.mark.parametrize("legacy", [False, True])
async def test_eink_available_in_theme_picker_and_can_be_selected(tmp_path, legacy):
    path = tmp_path / "config.yaml"
    if legacy:
        save(path, Config(("^saved:",)), None)
    app = CleanerApp(path, Inventory()) if legacy else WhitelistApp(Inventory())
    async with app.run_test(size=(100, 30)) as pilot:
        app.theme = "nord"
        await pilot.pause()
        app.query_one(TextArea).load_text("unfinished[")
        await pilot.press("ctrl+t", "e", "-", "i", "n", "k")
        await pilot.pause(0.3)
        assert app.screen.query_one(OptionList).option_count == 1
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.theme == "e-ink" and not app.screen.is_modal
        assert app.query_one(TextArea).text == "unfinished["
        for control in [app.query_one(DataTable), *app.query(Checkbox)]:
            control.focus()
            await pilot.pause()
            colors = {color.get_truecolor()
                      for strip in app.screen._compositor.render_strips()
                      for segment in strip if segment.style
                      for color in (segment.style.color, segment.style.bgcolor)
                      if color and not color.is_default}
            assert colors <= {(0, 0, 0), (255, 255, 255)}
        if legacy:
            assert load(path)[0] == Config(("^saved:",), theme="e-ink")
    if legacy:
        async with CleanerApp(path, Inventory()).run_test() as pilot:
            assert pilot.app.theme == "e-ink"
