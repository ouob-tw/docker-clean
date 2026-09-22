"""Blocked fake Docker calls exercise UI responsiveness without real deletion."""
import asyncio
from threading import Event

import pytest
from textual.widgets import Button, DataTable, Static, TextArea
from textual.containers import VerticalScroll

from docker_clean.engine import Image
from docker_clean.config import CleanError
from docker_clean.plan import Result
from docker_clean.tui import CleanerApp
from docker_clean.whitelist import WhitelistApp


class SlowDocker:
    def __init__(self):
        self.images = {str(i): Image(str(i), (f"app:{i}",), 1, "2026-01-01") for i in range(2)}
        self.entered, self.release = Event(), Event()
        self.finished = False
        self.calls = []

    def snapshot(self):
        return dict(self.images)

    def remove(self, target, force):
        self.calls.append(target)
        self.entered.set()
        self.release.wait(3)
        self.finished = True
        self.images.pop(target)
        return f"Deleted: {target}"

    def forceDeleteImage(self, target):
        return self.remove(target, True)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("block_stage", ["query", "delete"])
async def test_delete_keeps_ui_responsive_and_logs_oldest_first(tmp_path, legacy, block_stage):
    docker = SlowDocker()
    app = CleanerApp(tmp_path / "config.yaml", docker) if legacy else WhitelistApp(docker)
    async with app.run_test(size=(120, 60)) as pilot:
        if legacy:
            await pilot.click("#save")
        else:
            app.query_one(TextArea).load_text("app:")
            await pilot.pause()
            await pilot.click("#select")
        await pilot.click("#preview")
        if block_stage == "query":
            snapshot = docker.snapshot

            def blocked_snapshot():
                docker.entered.set()
                docker.release.wait(3)
                docker.finished = True
                return snapshot()

            docker.snapshot = blocked_snapshot
        try:
            await pilot.click("#confirm")
            assert await asyncio.to_thread(docker.entered.wait, 1)
            assert not docker.finished, "confirmation blocked UI until Docker finished"
            assert app.query_one("#confirm", Button).disabled
            assert app.query_one("#refresh", Button).disabled
            before = set(app.selected)
            app.query_one(DataTable).focus()
            await pilot.press("space")
            assert app.selected == before
            assert not docker.finished
            assert app.screen is app.cleanup
            await pilot.press("escape")
            assert app.screen is app.cleanup
            await pilot.press("ctrl+q")
            assert app.is_running and app.cleanup.running
            text = str(app.cleanup.query_one("#cleanup-status", Static).render())
            assert "0／2" in text and "app:0" in text
            if not legacy:
                colors = {color.get_truecolor()
                          for strip in app.screen._compositor.render_strips()
                          for segment in strip if segment.style
                          for color in (segment.style.color, segment.style.bgcolor)
                          if color and not color.is_default}
                assert colors <= {(0, 0, 0), (255, 255, 255)}
        finally:
            docker.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert docker.calls == ["0", "1"]
        assert "2／2" in str(app.cleanup.query_one("#cleanup-status", Static).render())
        entries = list(app.cleanup.query(".cleanup-entry"))
        assert "app:0" in str(entries[0].render())
        assert "app:1" in str(entries[1].render())
        assert "Deleted: 1" in str(entries[1].render())
        assert not app.query_one("#refresh", Button).disabled
        assert app.query_one("#confirm", Button).disabled
        await pilot.press("escape")
        assert not app.screen.is_modal
        if legacy:
            app.query_one(TextArea).load_text("app:")
            await pilot.pause()
            assert app.query_one("#output", Static).display


async def test_new_logs_preserve_reader_position_and_follow_only_at_bottom():
    app = WhitelistApp(SlowDocker())
    async with app.run_test(size=(120, 60)) as pilot:
        progress = app.cleanup
        progress.start(20, lambda notify: [], lambda error: None)
        await pilot.pause()
        await app.workers.wait_for_complete()
        image = Image("sha256:" + "a" * 64, ("app:old",), 1, "2026-01-01")
        for i in range(10):
            progress.update_progress(image, "已處理", (Result("成功", image.id, f"receipt {i}"),))
            await pilot.pause()
        log = progress.query_one("#cleanup-log", VerticalScroll)
        log.scroll_to(y=8, animate=False, immediate=True)
        await pilot.pause()
        anchor = next(child for child in log.children if child.region.bottom > log.content_region.y)
        before = anchor.region.y
        progress.update_progress(image, "已處理", (Result("成功", image.id, "new receipt"),))
        await pilot.pause()
        assert anchor.region.y == before
        log.scroll_end(animate=False, immediate=True)
        await pilot.pause()
        progress.update_progress(image, "已處理", (Result("成功", image.id, "newest receipt"),))
        await pilot.pause()
        assert log.scroll_y == log.max_scroll_y
        assert "newest receipt" in str(log.children[-1].render())


async def test_progress_modal_can_close_and_a_second_run_starts_fresh():
    docker = SlowDocker()
    docker.release.set()
    app = WhitelistApp(docker)
    async with app.run_test(size=(100, 30)) as pilot:
        app.query_one(TextArea).load_text("app:")
        await pilot.pause()
        for total in (2, 1):
            await pilot.click("#refresh")
            await pilot.click("#select")
            await pilot.click("#preview")
            await pilot.click("#confirm")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.screen is app.cleanup
            assert app.cleanup.completed == total and app.cleanup.total == total
            assert len(app.cleanup.query(".cleanup-entry")) == total
            await pilot.click("#close-progress")
            assert len(app.screen_stack) == 1
            docker.images = {"2": Image("2", ("app:2",), 1, "2026-01-01")}


@pytest.mark.parametrize("failure", ["query", "delete", "refresh"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_failures_keep_receipts_unlock_controls_and_do_not_fake_completion(failure, legacy, tmp_path):
    docker = SlowDocker()
    docker.release.set()
    app = CleanerApp(tmp_path / "config.yaml", docker) if legacy else WhitelistApp(docker)
    async with app.run_test(size=(120, 60)) as pilot:
        if legacy:
            await pilot.click("#save")
        else:
            app.query_one(TextArea).load_text("app:")
            await pilot.pause()
            await pilot.click("#select")
        await pilot.click("#preview")
        snapshot = docker.snapshot
        remove = docker.remove
        calls = 0

        def failing_snapshot():
            nonlocal calls
            calls += 1
            if failure == "query" or (failure == "refresh" and calls == 3):
                raise CleanError("inventory unavailable")
            return snapshot()

        def failing_remove(target, force):
            if failure == "delete" and target == "0":
                docker.calls.append(target)
                raise CleanError("delete denied")
            return remove(target, force)

        docker.snapshot = failing_snapshot
        docker.remove = failing_remove
        await pilot.click("#confirm")
        await app.workers.wait_for_complete()
        await pilot.pause()
        status = str(app.cleanup.query_one("#cleanup-status", Static).render())
        logs = "\n".join(str(entry.render()) for entry in app.cleanup.query(".cleanup-entry"))
        if failure == "query":
            assert "1／2" in status and "尚有 1 個未處理" in status
            assert "inventory unavailable" in logs and not docker.calls
        else:
            assert "2／2" in status and docker.calls == ["0", "1"]
            assert "Deleted: 1" in logs
            if failure == "delete":
                assert "失敗 1" in status and "delete denied" in logs
            else:
                assert "請查看錯誤紀錄" in status and "inventory unavailable" in logs
        if failure in {"query", "refresh"}:
            assert app.query_one(DataTable).row_count == 0
            assert "inventory unavailable" in str(app.query_one("#status", Static).render())
            assert "請刷新" in str(app.query_one("#status", Static).render())
        assert not app.cleanup.running
        assert not app.query_one("#refresh", Button).disabled
        assert app.query_one("#confirm", Button).disabled
