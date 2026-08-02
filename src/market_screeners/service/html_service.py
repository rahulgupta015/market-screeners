"""Capture ANSI-colored console output and export it as a self-contained HTML report.

Design note: display_service.py writes fully-formed ANSI color codes via plain print().
Rather than rewriting that table-building logic to use rich.Table directly, this module
captures the exact text that was printed, hands each line to rich.text.Text.from_ansi()
-- which parses standard ANSI SGR color codes into a Rich Text object -- and lets Rich
export that as self-contained HTML. The terminal experience and existing display_service
tests are unaffected.
"""

import contextlib
import io
import re
import sys
from typing import Callable

from rich.console import Console
from rich.text import Text

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# Dark navy theme — easy on the eyes, indicator colors pop against the background.
_BODY_OVERRIDE = """\
body {
    color: #cdd6f4;
    background-color: #0f1923;
}
pre { padding: 1em; }
"""


def _apply_dark_theme(html: str) -> str:
    """Replace Rich's default white body style with the dark navy theme."""
    return html.replace(
        "color: #000000;\n    background-color: #ffffff;",
        "color: #cdd6f4;\n    background-color: #0f1923;",
    ).replace(
        # Also tint the uncolored text (table borders +-| and plain text) to a
        # soft slate so they don't burn as bright white against the dark bg.
        "<pre style=\"font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace\">",
        "<pre style=\"font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace;padding:1em;\">",
    )


def capture_output(render_fn: Callable[..., None], *args, **kwargs) -> str:
    """Call `render_fn` once, capturing everything it prints into a buffer,
    then immediately echo that buffer to the real terminal. One call, one
    source of truth between what the terminal sees and what gets saved to HTML.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        render_fn(*args, **kwargs)
    captured = buffer.getvalue()
    sys.stdout.write(captured)
    sys.stdout.flush()
    return captured


def save_html(captured_text: str, html_path: str) -> None:
    """Convert ANSI-colored console text into a self-contained HTML file
    using Rich, preserving the exact colors seen in the terminal.
    """
    lines = captured_text.splitlines()
    # Use visible width (ANSI codes stripped) so Rich doesn't wrap lines.
    # Raw len() includes invisible escape sequences and causes mid-row wrapping.
    width = max((_ANSI_RE.sub("", line).__len__() for line in lines), default=80) + 2

    # file=io.StringIO() makes the console silent -- it only records for export.
    console = Console(record=True, width=width, file=io.StringIO())
    for line in lines:
        console.print(Text.from_ansi(line))

    html = console.export_html()
    html = _apply_dark_theme(html)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
