"""Shared E-Ink palette and pure black-and-white widget styles."""
from textual.theme import Theme


E_INK_THEME = Theme(
    name="e-ink", primary="#000000", secondary="#000000", accent="#000000",
    foreground="#000000", background="#ffffff", surface="#ffffff", panel="#ffffff",
    warning="#000000", error="#000000", success="#000000", dark=False,
    luminosity_spread=0, text_alpha=1,
    variables={
        "text": "#000000", "text-muted": "#000000", "text-disabled": "#000000",
        "border": "#000000", "border-blurred": "#000000",
        "block-cursor-background": "#000000", "block-cursor-foreground": "#ffffff",
        "input-cursor-background": "#000000", "input-cursor-foreground": "#ffffff",
        "input-selection-background": "#000000", "input-selection-foreground": "#ffffff",
        "footer-background": "#ffffff", "footer-key-foreground": "#000000",
        "footer-description-foreground": "#000000",
        "scrollbar": "#000000", "scrollbar-hover": "#000000",
        "scrollbar-active": "#000000", "scrollbar-background": "#ffffff",
        "scrollbar-background-hover": "#ffffff", "scrollbar-background-active": "#ffffff",
        "boost": "#ffffff 0%",
    },
)

E_INK_CSS = """
.-theme-e-ink Screen, .-theme-e-ink TextArea, .-theme-e-ink DataTable,
.-theme-e-ink Header, .-theme-e-ink Footer, .-theme-e-ink Button {
    background: #ffffff;
    color: #000000;
}
.-theme-e-ink Button { text-opacity: 100%; }
.-theme-e-ink DialogScreen { background: transparent; }
.-theme-e-ink Button:disabled { opacity: 1; text-style: strike; }
.-theme-e-ink Button:focus, .-theme-e-ink Button:hover {
    background: #000000;
    color: #ffffff;
    tint: transparent;
}
.-theme-e-ink TextArea .text-area--cursor-line {
    background: #ffffff;
}
.-theme-e-ink DataTable .datatable--header {
    background: #ffffff;
    color: #000000;
    text-style: bold underline;
}
.-theme-e-ink DataTable .datatable--cursor,
.-theme-e-ink DataTable .datatable--hover {
    background: #000000;
    color: #ffffff;
}
.-theme-e-ink * {
    tint: transparent;
    background-tint: transparent;
}
.-theme-e-ink TextArea:light .text-area--cursor,
.-theme-e-ink TextArea .text-area--selection {
    background: #000000;
    color: #ffffff;
}
.-theme-e-ink TextArea .text-area--matching-bracket,
.-theme-e-ink TextArea .text-area--cursor-gutter,
.-theme-e-ink FooterKey, .-theme-e-ink FooterKey .footer-key--key {
    background: #ffffff;
    color: #000000;
}
.-theme-e-ink FooterKey:hover, .-theme-e-ink FooterKey:hover .footer-key--key {
    background: #000000;
    color: #ffffff;
}
.-theme-e-ink Footer FooterKey.-command-palette {
    border-left: vkey #000000;
}
.-theme-e-ink DataTable .datatable--header-hover,
.-theme-e-ink DataTable .datatable--header-cursor {
    background: #000000;
    color: #ffffff;
}
"""
