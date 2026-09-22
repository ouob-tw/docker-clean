"""Keep wheel input inside the scroll region under the pointer."""
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import TextArea


class ScrollContainment:
    # Textual also dispatches to the base handler. Stop bubbling only; calling
    # super() here would apply the normal scroll step twice.
    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()

    def _on_mouse_scroll_left(self, event: events.MouseScrollLeft) -> None:
        event.stop()

    def _on_mouse_scroll_right(self, event: events.MouseScrollRight) -> None:
        event.stop()


class ContainedTextArea(ScrollContainment, TextArea):
    pass


class ContainedVerticalScroll(ScrollContainment, VerticalScroll):
    pass
