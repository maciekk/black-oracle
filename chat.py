#!/usr/bin/env python3
"""Black Oracle — Textual TUI chat client."""

import re
import subprocess
import threading
from pathlib import Path

import requests
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Footer, Input, RichLog, Static

HISTORY_FILE = Path.home() / ".local" / "share" / "black-oracle" / "history"

ENDPOINT = "http://localhost:8000/chat"

ORACLE_THEME = Theme(
    name="oracle",
    primary="#E0712A",
    secondary="#C4611F",
    accent="#F5A633",
    warning="#FFC107",
    error="#FF4444",
    success="#66BB6A",
    background="#111111",
    surface="#1E1E1E",
    panel="#2A2A2A",
    foreground="#E8E8E8",
    dark=True,
)

BAR = "bold #FF7A1E"


# ── Thinking spinner ───────────────────────────────────────────────────────────

class ThinkingIndicator(Static):
    """Single-line braille spinner shown in the chat area while waiting."""

    DEFAULT_CSS = """
    ThinkingIndicator {
        height: 1;
        padding: 0 1;
        display: none;
        color: $text-muted;
    }
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    _frame: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        if self.display:
            self._frame = (self._frame + 1) % len(self.FRAMES)
            self.update(f"[{BAR}]{self.FRAMES[self._frame]}[/{BAR}] [dim]Thinking…[/dim]")

    def start(self) -> None:
        self._frame = 0
        self.display = True
        self.update(f"[{BAR}]{self.FRAMES[0]}[/{BAR}] [dim]Thinking…[/dim]")

    def stop(self) -> None:
        self.display = False


# ── Sources overlay (full-screen modal) ───────────────────────────────────────

class SourcesScreen(ModalScreen):
    """Full-screen scrollable overlay showing all source documents."""

    DEFAULT_CSS = """
    SourcesScreen {
        align: center middle;
    }
    SourcesScreen > RichLog {
        width: 100%;
        height: 100%;
        background: $surface;
        border: solid $primary-darken-2;
        padding: 0 2;
    }
    """

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, sources: list) -> None:
        super().__init__()
        self._sources = sources

    def compose(self) -> ComposeResult:
        yield RichLog(id="sources-log", markup=True, highlight=False, wrap=True, auto_scroll=False)
        yield Footer()

    def on_mount(self) -> None:
        from rich.rule import Rule
        from rich.text import Text

        log = self.query_one("#sources-log", RichLog)
        log.write(Text.assemble(("│ ", BAR), ("Sources", BAR)))
        log.write(Text("│", style=BAR))

        from rich.console import Console
        from rich.markdown import Markdown
        from rich.text import Text

        tmp = Console(width=self.app.console.width - 6, highlight=False)

        for i, s in enumerate(self._sources, 1):
            path = s.get("metadata", {}).get("source", "unknown")
            name = path.split("/")[-1]
            content = s.get("content", "").strip()

            with tmp.capture() as cap:
                tmp.print(Markdown(content))

            log.write("")
            log.write(f"[bold]{i}. {name}[/bold]")
            log.write("")
            log.write(Text.from_ansi(cap.get().rstrip()))
            if i < len(self._sources):
                log.write("")
                log.write(Rule(style="dim"))


# ── Source panel (filenames only) ─────────────────────────────────────────────

class SourcesPanel(Widget):
    """Narrow right-hand panel showing source filenames. Ctrl+S for full view."""

    DEFAULT_CSS = """
    SourcesPanel {
        width: 1fr;
        border-left: solid $primary-darken-2;
        padding: 0 1;
        background: $surface;
    }
    """

    sources: reactive[list] = reactive([], recompose=True)

    def compose(self) -> ComposeResult:
        hint = "[dim](ctrl+s: details)[/dim]" if self.sources else ""
        yield Static(f"[bold]Sources[/bold] {hint}\n", markup=True)

        if not self.sources:
            yield Static("[dim]—[/dim]", markup=True)
            return

        for i, s in enumerate(self.sources, 1):
            path = s.get("metadata", {}).get("source", "unknown")
            name = path.split("/")[-1]
            # Truncate to fit on one line (panel width minus padding and index prefix)
            max_len = max(12, self.content_size.width - 4)
            if len(name) > max_len:
                # First try stripping leading digits+underscores (e.g. "20230415_123_")
                name = re.sub(r"^[\d_]+", "\u2026", name)
            if len(name) > max_len:
                name = name[:max_len - 1] + "\u2026"
            yield Static(f"[dim]{i}.[/dim] {name}", markup=True)

    def load(self, sources: list) -> None:
        self.sources = sources


# ── Chat pane ─────────────────────────────────────────────────────────────────

class ChatPane(RichLog):
    DEFAULT_CSS = """
    ChatPane {
        width: 3fr;
        min-width: 69;
        border: none;
        padding: 0 1;
        background: $background;
        scrollbar-gutter: stable;
    }
    """

    def add_user(self, text: str) -> None:
        self.write(f"\n[bold cyan]You[/bold cyan]")
        self.write(text)

    def add_oracle(self, text: str) -> None:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.text import Text

        MAX_WIDTH = 120
        pane_width = self.content_size.width
        render_width = max(65, min(MAX_WIDTH, pane_width))
        left_pad = max(0, (pane_width - render_width) // 2)
        pad = " " * left_pad

        tmp = Console(width=render_width, highlight=False)
        with tmp.capture() as cap:
            tmp.print(Markdown(text))
        rendered = cap.get().rstrip()

        self.write("")
        header = Text()
        header.append(pad)
        header.append("│ ", style=BAR)
        header.append("Oracle", style=BAR)
        self.write(header)
        for line in rendered.splitlines():
            t = Text()
            t.append(pad)
            t.append("│ ", style=BAR)
            t.append_text(Text.from_ansi(line))
            self.write(t)

    def add_error(self, text: str) -> None:
        self.write(f"[bold error]Error:[/bold error] {text}")


# ── History-aware input ───────────────────────────────────────────────────────

class HistoryInput(Input):
    """Input widget with Up/Down history navigation, persisted across runs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: list[str] = []
        self._history_index: int = 0
        self._saved_value: str = ""
        self._load_history()

    def _load_history(self) -> None:
        if HISTORY_FILE.exists():
            self._history = [l for l in HISTORY_FILE.read_text().splitlines() if l.strip()]
        self._history_index = len(self._history)

    def save_entry(self, text: str) -> None:
        """Append a new entry and reset the navigation cursor."""
        self._history.append(text)
        self._history_index = len(self._history)
        self._saved_value = ""
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_FILE.open("a") as f:
            f.write(text + "\n")

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            event.prevent_default()
            if self._history and self._history_index > 0:
                if self._history_index == len(self._history):
                    self._saved_value = self.value
                self._history_index -= 1
                self.value = self._history[self._history_index]
                self.cursor_position = len(self.value)
        elif event.key == "down":
            event.prevent_default()
            if self._history_index < len(self._history):
                self._history_index += 1
                self.value = (
                    self._saved_value
                    if self._history_index == len(self._history)
                    else self._history[self._history_index]
                )
                self.cursor_position = len(self.value)


# ── Main app ──────────────────────────────────────────────────────────────────

class OracleApp(App):
    THEME = "oracle"

    CSS = """
    Screen {
        layout: vertical;
    }
    #body {
        layout: horizontal;
        height: 1fr;
        min-height: 10;
    }
    #input-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary-darken-2;
    }
    #input-bar Input {
        border: none;
        background: $surface;
        width: 1fr;
        color: $foreground;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Palette"),
        Binding("ctrl+s", "show_sources", "Source details"),
        Binding("ctrl+y", "copy_last", "Copy last answer"),
        Binding("ctrl+c", "quit", "Quit", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.chat_history: list[list[str]] = []
        self._last_answer: str = ""

    def on_mount(self) -> None:
        self.register_theme(ORACLE_THEME)
        self.theme = "oracle"
        chat = self.query_one("#chat", ChatPane)
        from rich.panel import Panel
        from rich.text import Text
        chat.write(
            Panel(
                Text.assemble(
                    ("Black Oracle", "bold primary"),
                    (" — Personal Knowledge Assistant\n", ""),
                    ("Ask anything · ", "dim"),
                    ("Ctrl-S", "bold dim"),
                    (" for source details · Ctrl-C to quit", "dim"),
                ),
                border_style="#FF7A1E",
                expand=False,
            )
        )
        self.query_one("#question", HistoryInput).focus()

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal, Vertical
        with Horizontal(id="body"):
            yield ChatPane(id="chat", markup=True, highlight=False, wrap=True)
            yield SourcesPanel(id="sources")
        yield ThinkingIndicator(id="thinking")
        with Vertical(id="input-bar"):
            yield HistoryInput(placeholder="Ask the Oracle…", id="question")
        yield Footer()

    def action_copy_last(self) -> None:
        if not self._last_answer:
            self.notify("Nothing to copy yet.", severity="warning")
            return
        try:
            subprocess.run(["wl-copy"], input=self._last_answer, text=True, check=True)
            self.notify("Copied to clipboard.")
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                subprocess.run(["xclip", "-selection", "clipboard"], input=self._last_answer, text=True, check=True)
                self.notify("Copied to clipboard.")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                self.notify(f"Copy failed: {e}", severity="error")

    def action_show_sources(self) -> None:
        sources = self.query_one("#sources", SourcesPanel).sources
        if sources:
            self.push_screen(SourcesScreen(sources))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        if not question:
            return
        event.input.clear()

        chat = self.query_one("#chat", ChatPane)
        sources_panel = self.query_one("#sources", SourcesPanel)
        thinking = self.query_one("#thinking", ThinkingIndicator)

        if question == "/clear":
            self.chat_history.clear()
            chat.clear()
            sources_panel.load([])
            return

        self.query_one("#question", HistoryInput).save_entry(question)
        chat.add_user(question)
        thinking.start()

        def fetch():
            try:
                body = {"question": question, "chat_history": self.chat_history}
                resp = requests.post(ENDPOINT, json=body, timeout=120)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                self.call_from_thread(thinking.stop)
                self.call_from_thread(chat.add_error, str(e))
                return

            answer = data.get("answer", "")
            raw_sources = data.get("sources", [])
            self._last_answer = answer
            self.call_from_thread(thinking.stop)
            self.call_from_thread(chat.add_oracle, answer)
            self.call_from_thread(sources_panel.load, raw_sources)
            self.chat_history.append([question, answer])

        threading.Thread(target=fetch, daemon=True).start()


if __name__ == "__main__":
    import os
    import logging
    # Silence Python logging and redirect OS-level stderr so no stray output
    # from libraries (tokenizers, urllib3, etc.) can corrupt the Textual TUI.
    logging.disable(logging.CRITICAL)
    _stderr_log = open("/tmp/black-oracle-chat.log", "a")
    os.dup2(_stderr_log.fileno(), 2)
    import sys; sys.stderr = _stderr_log
    OracleApp().run()
