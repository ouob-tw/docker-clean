"""Actual Textual rendering and input; Docker inventory is a fixture."""
from unittest.mock import patch

from textual.widgets import Button, DataTable

from docker_clean.engine import Image
from docker_clean.whitelist import WhitelistApp


class Inventory:
    def snapshot(self):
        return {str(i): Image(str(i), (tag,), size, date) for i, (tag, size, date) in enumerate([
            ("delta:1", 1024, "2026-03-01"),
            ("alpha:1", 900, "2026-02-01"),
            ("charlie:1", 10000, "2026-01-01"),
            ("bravo:1", 50, "2026-04-01"),
        ])}


def row_ids(table):
    return [row.key.value for row in table.ordered_rows]


async def test_default_tag_order_and_click_headers_toggle_numeric_date_sort():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(120, 45)) as pilot:
        table = app.query_one(DataTable)
        assert row_ids(table) == ["1", "3", "2", "0"]
        for key, ascending in [("tags", ["1", "3", "2", "0"]),
                               ("size", ["3", "1", "0", "2"]),
                               ("created", ["2", "1", "0", "3"])]:
            x = sum(c.width + 2 for c in table.ordered_columns[:table.get_column_index(key)]) + 1
            await pilot.click("#images", offset=(x, 0))
            expected = ascending[::-1] if key == "tags" else ascending
            assert row_ids(table) == expected
            await pilot.click("#images", offset=(x, 0))
            assert row_ids(table) == expected[::-1]
        assert not app.selected


async def test_sort_preserves_selection_and_confirmed_preview_after_resize():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(120, 45)) as pilot:
        table = app.query_one(DataTable)
        table.focus()
        await pilot.press("space")
        selected = set(app.selected)
        for key in ("selected", "reason"):
            x = sum(c.width + 2 for c in table.ordered_columns[:table.get_column_index(key)]) + 1
            await pilot.click("#images", offset=(x, 0))
            assert app.selected == selected
            before = row_ids(table)
            await pilot.click("#images", offset=(x, 0))
            assert row_ids(table) == before[::-1]
        await pilot.click("#preview")
        preview = app.preview
        await pilot.resize_terminal(100, 45)
        assert app.preview == preview
        assert row_ids(table) == list(selected)
        assert not app.query_one("#confirm", Button).disabled


async def test_selection_updates_in_place_preserving_rows_cursor_and_scroll():
    inventory = Inventory()
    inventory.snapshot = lambda: {str(i): Image(str(i), (f"app:{i:04}",), 1, "2026-01-01")
                                  for i in range(500)}
    app = WhitelistApp(inventory)
    async with app.run_test(size=(100, 40)) as pilot:
        table = app.query_one(DataTable)
        table.focus()
        table.move_cursor(row=25)
        await pilot.pause()
        rows, offset = list(table.ordered_rows), table.scroll_offset
        with patch.object(table, "clear", wraps=table.clear) as clear:
            await pilot.press("space")
            assert clear.call_count == 0, "selection clears the table and rebuilds every row"
        assert table.ordered_rows == rows
        assert table.cursor_row == 25 and table.scroll_offset == offset
        assert app.selected == {"25"}
        assert table.get_cell("25", "selected") == "✓"
        assert "強制刪除" in str(table.get_cell("25", "reason"))
        await pilot.press("enter")
        assert not app.selected


async def test_eink_render_contains_only_black_and_white():
    app = WhitelistApp(Inventory())
    async with app.run_test(size=(100, 40)) as pilot:
        for selector in ("#rules", "#images", "#select"):
            app.query_one(selector).focus()
            await pilot.hover(selector)
            await pilot.pause()
            colors = set()
            for strip in app.screen._compositor.render_strips():
                for segment in strip:
                    if segment.style:
                        for color in (segment.style.color, segment.style.bgcolor):
                            if color and not color.is_default:
                                colors.add(color.get_truecolor())
            assert colors <= {(0, 0, 0), (255, 255, 255)}, colors
