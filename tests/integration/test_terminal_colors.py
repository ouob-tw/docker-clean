"""Real PTY rendering with an empty Engine fixture; no Docker operations."""
import os
import pty
import select
import subprocess
import sys
import time

import pytest


def test_no_color_terminal_theme_keeps_default_foreground_and_background(tmp_path):
    master, slave = pty.openpty()
    code = """
from pathlib import Path
import sys
from docker_clean.tui import CleanerApp
class EmptyEngine:
    def snapshot(self): return {}
CleanerApp(Path(sys.argv[1]), EmptyEngine()).run()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path / "config.yaml")],
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "NO_COLOR": "1", "TERM": "xterm-256color", "COLORTERM": "truecolor"},
    )
    os.close(slave)
    output = b""
    try:
        deadline = time.monotonic() + 10
        while b"Docker Image Clean" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                output += os.read(master, 65536)
        assert b"Docker Image Clean" in output, output[-1000:]
        header = output[:output.index(b"Docker Image Clean") + len(b"Docker Image Clean")]
        assert b"38;2;0;0;0;48;2;0;0;0m" not in header, "Header rendered black on black"
    finally:
        os.write(master, b"\x11")
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)


@pytest.mark.parametrize("legacy", [False, True])
def test_eink_renders_black_on_white_with_no_color(tmp_path, legacy):
    master, slave = pty.openpty()
    code = """
from docker_clean import cli
from docker_clean.whitelist import WhitelistApp
class EmptyEngine:
    def snapshot(self): return {}
"""
    code += """
from pathlib import Path
import sys
from docker_clean.config import Config, save
from docker_clean.tui import CleanerApp
path = Path(sys.argv[1])
save(path, Config(theme="e-ink"), None)
CleanerApp(path, EmptyEngine()).run()
""" if legacy else "WhitelistApp(EmptyEngine()).run()\n"
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path / "config.yaml")],
        stdin=slave, stdout=slave, stderr=slave,
        env={**os.environ, "NO_COLOR": "1", "TERM": "xterm-256color", "COLORTERM": "truecolor"},
    )
    os.close(slave)
    output = b""
    try:
        deadline = time.monotonic() + 5
        while b"Docker Image Clean" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                output += os.read(master, 65536)
        assert b"Docker Image Clean" in output
        assert b"38;2;0;0;0;48;2;255;255;255" in output
    finally:
        os.write(master, b"\x11")
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)
