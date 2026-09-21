"""Real PTY rendering with an empty Engine fixture; no Docker operations."""
import os
import pty
import select
import subprocess
import sys
import time


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
        while b"Docker Clean" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                output += os.read(master, 65536)
        assert b"Docker Clean" in output, output[-1000:]
        header = output[:output.index(b"Docker Clean") + len(b"Docker Clean")]
        assert b"38;2;0;0;0;48;2;0;0;0m" not in header, "Header rendered black on black"
    finally:
        os.write(master, b"\x11")
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)
