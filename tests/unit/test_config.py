import pytest

from docker_clean.config import CleanError, Config, load, save


@pytest.mark.parametrize("text", ["", "[]", "keep: null", "keep: x", "keep: [1]",
    "keep: ['[']", "keep: []\ncleanup: []", "keep: []\ncleanup: {force: 'false'}",
    "keep: []\ncleanup: {remove_tags: 1}", "keep: []\ncleanup: {forcee: true}",
    "keep: []\nother: []", "keep: ["])
def test_invalid_configuration_fails_closed(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    with pytest.raises(CleanError):
        load(path)


def test_create_roundtrip_and_external_change(tmp_path):
    path = tmp_path / "sub/config.yaml"
    assert load(path, allow_missing=True) == (Config(), None)
    with pytest.raises(CleanError, match="設定不存在"):
        load(path)
    config = Config((r"^postgres:16$",), True, True)
    revision = save(path, config, None)
    assert load(path) == (config, revision)
    path.write_text("keep: []")
    with pytest.raises(CleanError, match="外部修改"):
        save(path, config, revision)
    assert path.read_text() == "keep: []"


def test_defaults_do_not_install_example_rules(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("keep: []")
    assert load(path)[0] == Config()
