import sys

import pytest

from docker_clean import cli
from docker_clean.config import CleanError, Config, save
from docker_clean.engine import Image


class FakeDocker:
    calls = []
    failure = False

    def snapshot(self):
        image = Image("sha256:" + "b" * 64, ("test:1",), 10, "today")
        return {image.id: image}

    def remove(self, target, force):
        self.calls.append((target, force))
        if self.failure:
            raise CleanError("conflict")
        return "Deleted: " + target


@pytest.mark.parametrize("answer,failure,expected", [("no", False, 0), ("DELETE", True, 1), ("DELETE", False, 0)])
def test_public_clean_preview_confirmation_results(tmp_path, monkeypatch, capsys, answer, failure, expected):
    path = tmp_path / "config.yaml"
    save(path, Config(), None)
    FakeDocker.calls = []
    FakeDocker.failure = failure
    monkeypatch.setattr(cli, "Docker", FakeDocker)
    monkeypatch.setattr(sys, "argv", ["docker-clean", "clean", "--config", str(path)])
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert cli.main() == expected
    text = capsys.readouterr().out
    assert "沒有保留規則" in text and "sha256:" + "b" * 64 in text
    assert len(FakeDocker.calls) == (1 if answer == "DELETE" else 0)
    if answer == "DELETE":
        assert f"失敗 {int(failure)}" in text
    else:
        assert "失敗" not in text


def test_missing_config_never_connects(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["docker-clean", "clean", "--config", str(tmp_path / "absent")])
    monkeypatch.setattr(cli, "Docker", lambda: pytest.fail("must not connect"))
    assert cli.main() == 1
    assert "設定不存在" in capsys.readouterr().out


def test_whitelist_entry_does_not_require_legacy_config(tmp_path, monkeypatch):
    from docker_clean.whitelist import WhitelistApp
    calls = []
    monkeypatch.setattr(sys, "argv", ["docker-clean", "whitelist", "--config", str(tmp_path / "absent")])
    monkeypatch.setattr(WhitelistApp, "run", lambda self: calls.append("run"))
    assert cli.main() == 0
    assert calls == ["run"]


@pytest.mark.parametrize("mode", ["keep", "delete"])
def test_dc_image_tui_routes_and_titles(tmp_path, monkeypatch, mode):
    from docker_clean import automation
    from docker_clean.tui import CleanerApp
    from docker_clean.whitelist import WhitelistApp

    path = tmp_path / "custom.yaml"
    calls = []
    def keep_run(self):
        assert self.path == path
        calls.append(self.title)
    monkeypatch.setattr(CleanerApp, "run", keep_run)
    monkeypatch.setattr(WhitelistApp, "run", lambda self: calls.append(self.title))
    args = ["dc", "image", mode]
    if mode == "keep":
        args.extend(["--config", str(path)])
    monkeypatch.setattr(sys, "argv", args)
    assert automation.main() == 0
    assert len(calls) == 1 and "Image" in calls[0] and mode.capitalize() in calls[0]


@pytest.mark.parametrize("command", ["delete", "whitelist"])
def test_delete_entry_accepts_config_before_command(tmp_path, monkeypatch, command):
    from docker_clean.whitelist import WhitelistApp
    calls = []
    monkeypatch.setattr(WhitelistApp, "run", lambda self: calls.append("run"))
    assert cli.main(["--config", str(tmp_path / "absent"), command]) == 0
    assert calls == ["run"]
