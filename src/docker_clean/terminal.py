"""Cell-coordinate input compatibility for Textual's Linux terminal driver."""
from collections.abc import Iterable

from textual import events
from textual._xterm_parser import XTermParser
from textual.drivers import linux_driver
from textual.message import Message


class CellCoordinateParser(XTermParser):
    def parse_mouse_code(self, code: str) -> Message | None:
        # Textual 8 still enables pixel decoding on an unsolicited CSI 48 report,
        # even with TEXTUAL_SMOOTH_SCROLL=0 and terminal mode 1016 disabled.
        self.mouse_pixels = False
        return super().parse_mouse_code(code)

    def feed(self, data: str) -> Iterable[Message]:
        for message in super().feed(data):
            # In-band resize was disabled at startup. SIGWINCH + the PTY size
            # remain authoritative; a delayed outer-terminal report may be stale.
            if not isinstance(message, events.Resize):
                yield message


def use_cell_coordinates() -> None:
    # LinuxDriver has no parser injection hook. Keep this process-local shim at
    # the CLI boundary, covered by real PTY and ZMX protocol regression tests.
    setattr(linux_driver, "XTermParser", CellCoordinateParser)
