"""Wheel events routed through the screen with fake Docker inventory."""
import pytest
from textual import events
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static, TextArea

from docker_clean.engine import Image
from docker_clean.scrolling import ContainedTextArea, ContainedVerticalScroll
from docker_clean.tui import CleanerApp, ImageTable
from docker_clean.whitelist import WhitelistApp


class Inventory:
    def snapshot(self):
        return {str(i): Image(str(i), (f"app:{i:03}",), 1, "2026-01-01") for i in range(40)}


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("bottom", [False, True])
async def test_table_wheel_at_edge_does_not_move_outer_scroll(tmp_path, legacy, bottom):
    app = CleanerApp(tmp_path / "config.yaml", Inventory()) if legacy else WhitelistApp(Inventory())
    async with app.run_test(size=(100, 24)) as pilot:
        table = app.query_one(DataTable)
        outer = app.screen
        await pilot.pause()
        table.scroll_to(y=table.max_scroll_y if bottom else 0, animate=False, immediate=True)
        await pilot.pause()
        assert outer.max_scroll_y == 0
        before = outer.scroll_offset
        wheel = events.MouseScrollDown if bottom else events.MouseScrollUp
        assert await pilot._post_mouse_events([wheel], table, offset=(5, 3))
        await pilot.pause()
        assert outer.scroll_offset == before
        # The reverse direction must still scroll the table normally.
        inside = table.scroll_y
        reverse = events.MouseScrollUp if bottom else events.MouseScrollDown
        await pilot._post_mouse_events([reverse], table, offset=(5, 3))
        assert abs(table.scroll_y - inside) == app.scroll_sensitivity_y
        assert outer.scroll_offset == before


class NestedScrollHarness(App):
    """Exercise containment with an actual outer scroller, independent of the flat app layout."""
    CSS = "#rules {height: 6;} #images, #cleanup-log {height: 12;}"

    def __init__(self, overflow=True):
        super().__init__()
        self.overflow = overflow

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="outer"):
            yield Static("before\n" * 6)
            yield ContainedTextArea("\n".join(f"app:{i}" for i in range(40)) if self.overflow else "", id="rules")
            yield ImageTable(id="images")
            with ContainedVerticalScroll(id="cleanup-log"):
                yield Static("\n".join(f"line {i}" for i in range(40)) if self.overflow else "empty")
            yield Static("\n".join(["outer content"] * 40), id="output")

    def on_mount(self):
        table = self.query_one(ImageTable)
        table.add_column("image")
        for i in range(40 if self.overflow else 0):
            table.add_row(str(i))


@pytest.mark.parametrize("selector", ["#rules", "#images", "#cleanup-log"])
@pytest.mark.parametrize("bottom", [False, True])
@pytest.mark.parametrize("overflow", [False, True])
async def test_all_inner_scroll_regions_contain_wheel(selector, bottom, overflow):
    app = NestedScrollHarness(overflow)
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        inner = app.query_one(selector)
        outer = app.query_one("#outer", VerticalScroll)
        outer.scroll_to(y=max(1, inner.region.y - 4), animate=False, immediate=True)
        inner.scroll_to(y=inner.max_scroll_y if bottom else 0, animate=False, immediate=True)
        await pilot.pause()
        assert 0 < outer.scroll_y < outer.max_scroll_y
        before = outer.scroll_offset
        wheel = events.MouseScrollDown if bottom else events.MouseScrollUp
        await pilot._post_mouse_events([wheel], inner, offset=(3, 2))
        await pilot.pause()
        assert outer.scroll_offset == before
        assert inner.scroll_y == (inner.max_scroll_y if bottom else 0)
        if overflow:
            inside = inner.scroll_y
            reverse = events.MouseScrollUp if bottom else events.MouseScrollDown
            await pilot._post_mouse_events([reverse], inner, offset=(3, 2))
            await pilot.pause()
            assert abs(inner.scroll_y - inside) == app.scroll_sensitivity_y
            assert outer.scroll_offset == before


async def test_outer_region_still_scrolls_when_pointer_is_outside_inner_regions():
    app = NestedScrollHarness()
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        output = app.query_one("#output", Static)
        outer = app.query_one("#outer", VerticalScroll)
        outer.scroll_to(y=output.region.y - 4, animate=False, immediate=True)
        await pilot.pause()
        before = outer.scroll_y
        assert await pilot._post_mouse_events([events.MouseScrollDown], output, offset=(3, 2))
        await pilot.pause()
        assert outer.scroll_y - before == app.scroll_sensitivity_y
