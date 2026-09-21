"""Exercise the real terminal parser against cell-coordinate multiplexer input."""
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
import uuid

import pytest


@pytest.mark.parametrize("multiplexer", ["direct", "zmx"])
def test_multiplexer_cell_click_selects_row_instead_of_opening_palette(tmp_path, multiplexer):
    if multiplexer == "zmx" and not shutil.which("zmx"):
        pytest.skip("Optional real zmx transport is not installed")
    code = '''
import json, sys
from pathlib import Path
from docker_clean import cli
from docker_clean import tui
from docker_clean.engine import Image
class Engine:
    def snapshot(self):
        return {"sha256:a": Image("sha256:a", ("example:1",), 100, "2026-09-21T00:00:00Z")}
class Probe(tui.CleanerApp):
    def __init__(self, path): super().__init__(path, Engine())
    def on_mount(self):
        super().on_mount()
        self.set_interval(0.05, self.report)
    def report(self):
        Path(sys.argv[-1] + ".state").write_text(json.dumps({
            "selected": sorted(self.selected), "screens": [type(s).__name__ for s in self.screen_stack]}))
tui.CleanerApp = Probe
raise SystemExit(cli.main())
'''
    config = tmp_path / "config.yaml"
    state = config.with_name(config.name + ".state")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 85, 595, 528))
    command = [sys.executable, "-c", code, "tui", "--config", str(config)]
    session = "docker-clean-test-" + uuid.uuid4().hex
    if multiplexer == "zmx":
        command = ["zmx", "attach", session, *command]
    process = subprocess.Popen(
        command,
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "TERM": "xterm-256color", "TEXTUAL_SMOOTH_SCROLL": "1"},
    )
    os.close(slave)
    output = b""
    replied = resized = clicked = False
    observed = {}
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                output += os.read(master, 65536)
            if not replied and b"\x1b[?2048$p" in output:
                os.write(master, b"\x1b[?2048;2$y")
                replied = True
            if not resized and b"\x1b[?2048h" in output:
                os.write(master, b"\x1b[48;24;85;528;595t")
                resized = True
            if not clicked and b"example:1" in output and state.exists() and replied:
                # HERDR 0.9.0 can send cell SGR even after a child requests 1016.
                os.write(master, b"\x1b[<0;3;13M\x1b[<0;3;13m")
                clicked = True
            if state.exists():
                try:
                    observed = json.loads(state.read_text())
                except json.JSONDecodeError:
                    continue
                if observed.get("selected") or len(observed.get("screens", [])) > 1:
                    break
        assert observed.get("selected") == ["sha256:a"], (observed, output[-500:])
        assert len(observed["screens"]) == 1
        assert b"\x1b[?1016h" not in output
        assert b"\x1b[?1016l" in output and b"\x1b[?2048l" in output
    finally:
        os.write(master, b"\x11")
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)
        if multiplexer == "zmx":
            subprocess.run(["zmx", "kill", session], capture_output=True, check=False)
