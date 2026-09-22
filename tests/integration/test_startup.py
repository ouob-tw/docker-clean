"""Real PTY/ZMX startup, fake inventory only; never issues Docker deletion."""
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
@pytest.mark.parametrize("resize_support", [False, True])
@pytest.mark.parametrize("dimensions", [(100, 40), (76, 20)])
@pytest.mark.parametrize("late_size_report", [False, True])
def test_whitelist_accepts_input_without_initial_resize(
        tmp_path, multiplexer, resize_support, dimensions, late_size_report):
    if multiplexer == "zmx" and not shutil.which("zmx"):
        pytest.skip("zmx is not installed")
    state = tmp_path / "state.json"
    code = '''
import json, sys
from pathlib import Path
from docker_clean import cli, whitelist
from docker_clean.engine import Image
from textual.widgets import TextArea, DataTable
class Engine:
    def snapshot(self):
        return {"sha256:a": Image("sha256:a", ("example:1",), 100, "2026-09-21T00:00:00Z")}
class Probe(whitelist.WhitelistApp):
    def __init__(self): super().__init__(Engine())
    def on_mount(self):
        super().on_mount()
        self.set_interval(0.05, self.report)
    def report(self):
        table = self.query_one(DataTable)
        Path(sys.argv[-1]).write_text(json.dumps({
            "selected": sorted(self.selected), "text": self.query_one(TextArea).text,
            "row": list(table.region), "size": list(self.size),
            "input": list(self.query_one(TextArea).region), "focus": str(self.focused)}))
whitelist.WhitelistApp = Probe
raise SystemExit(cli.main())
'''
    master, slave = pty.openpty()
    columns, rows = dimensions
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    command = [sys.executable, "-c", code, "whitelist", "--config", str(state)]
    session = "docker-clean-startup-" + uuid.uuid4().hex
    if multiplexer == "zmx":
        command = ["zmx", "attach", session, *command]
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                               env={**os.environ, "TERM": "xterm-256color"})
    os.close(slave)
    output = b""
    replied = typed = clicked = False
    observed = {}
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                output += os.read(master, 65536)
            if not replied and b"\x1b[?2048$p" in output:
                os.write(master, b"\x1b[?2048;2$y" if resize_support else b"\x1b[?2048;0$y")
                replied = True
            # No user resize / SIGWINCH: input must work at the initial PTY size.
            if state.exists():
                try:
                    observed = json.loads(state.read_text())
                except json.JSONDecodeError:
                    continue
                if not typed and b"example:1" in output:
                    if late_size_report:
                        # A size report already in flight can arrive after mode 2048 is reset.
                        os.write(master, f"\x1b[48;{rows+5};{columns+10};{(rows+5)*22};{(columns+10)*7}t".encode())
                    x, y, _, _ = observed["input"]
                    os.write(master, f"\x1b[<0;{x+3};{y+2}M\x1b[<0;{x+3};{y+2}mexample".encode())
                    typed = True
                if not clicked and observed.get("text") == "example":
                    x, y, _, _ = observed["row"]
                    os.write(master, f"\x1b[<0;{x+3};{y+2}M\x1b[<0;{x+3};{y+2}m".encode())
                    clicked = True
                if observed.get("selected") == ["sha256:a"]:
                    break
        assert observed.get("text") == "example", (observed, output[-500:])
        assert observed.get("selected") == ["sha256:a"], (observed, output[-500:])
        assert observed["size"] == [columns, rows]
    finally:
        os.write(master, b"\x11")
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master)
        if multiplexer == "zmx":
            subprocess.run(["zmx", "kill", session], capture_output=True, check=False)


def test_zmx_two_clients_late_report_cannot_override_leader_size(tmp_path):
    if not shutil.which("zmx"):
        pytest.skip("zmx is not installed")
    state = tmp_path / "shared.json"
    code = '''
import json, sys, os
from pathlib import Path
from docker_clean import cli, whitelist
class Engine:
    def snapshot(self): return {}
class Probe(whitelist.WhitelistApp):
    def __init__(self): super().__init__(Engine())
    def on_mount(self):
        super().on_mount()
        self.set_interval(0.05, self.report)
    def report(self):
        self.reports = getattr(self, "reports", 0) + 1
        Path(sys.argv[-1]).write_text(json.dumps({
            "app": list(self.size), "pty": list(os.get_terminal_size()), "reports": self.reports}))
whitelist.WhitelistApp = Probe
raise SystemExit(cli.main())
'''
    session = "docker-clean-two-clients-" + uuid.uuid4().hex
    clients = []

    def attach(columns, rows, command=()):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        process = subprocess.Popen(["zmx", "attach", session, *command],
                                   stdin=slave, stdout=slave, stderr=slave,
                                   env={**os.environ, "TERM": "xterm-256color"})
        os.close(slave)
        clients.append((master, process))
        return master

    def wait_for(predicate):
        observed = {}
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for fd in select.select([fd for fd, _ in clients], [], [], 0.05)[0]:
                os.read(fd, 65536)
            if state.exists():
                try:
                    observed = json.loads(state.read_text())
                except json.JSONDecodeError:
                    continue
                if predicate(observed):
                    return observed
        pytest.fail(f"Shared terminal state: {observed}")

    try:
        first = attach(100, 40, [sys.executable, "-c", code, "whitelist", "--config", str(state)])
        wait_for(lambda s: s["app"] == s["pty"] == [100, 40])
        second = attach(76, 20)
        # Ordinary input makes the second client the sizing leader.
        os.write(second, b"\t")
        previous = wait_for(lambda s: s["app"] == s["pty"] == [76, 20])
        # A delayed report from the current leader must not override its PTY
        # size. ZMX drops pure protocol replies from non-leader clients.
        os.write(second, b"\x1b[48;40;100;880;700t")
        # Observe several event-loop ticks after the reply without sending user
        # input (which would promote that client and mask a stale-size bug).
        result = wait_for(lambda s: s["reports"] >= previous["reports"] + 3)
        assert result["app"] == result["pty"] == [76, 20], result
        # Real input from the first client still resizes via ZMX / SIGWINCH.
        os.write(first, b"\t")
        wait_for(lambda s: s["app"] == s["pty"] == [100, 40])
    finally:
        for master, process in clients:
            os.write(master, b"\x1c")  # Detach only these test clients.
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            os.close(master)
        subprocess.run(["zmx", "kill", session], capture_output=True, check=False)
