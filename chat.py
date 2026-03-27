#!/usr/bin/env python3
"""Black Oracle — Textual TUI chat client."""

import threading

import requests
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Footer, Input, RichLog, Static

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
        width: 36;
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
            yield Static(f"[dim]{i}.[/dim] {name}", markup=True)

    def load(self, sources: list) -> None:
        self.sources = sources


# ── Chat pane ─────────────────────────────────────────────────────────────────

class ChatPane(RichLog):
    DEFAULT_CSS = """
    ChatPane {
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

        tmp = Console(width=65, highlight=False)
        with tmp.capture() as cap:
            tmp.print(Markdown(text))
        rendered = cap.get().rstrip()

        self.write("")
        self.write(Text.assemble(("│ ", BAR), ("Oracle", BAR)))
        for line in rendered.splitlines():
            t = Text()
            t.append("│ ", style=BAR)
            t.append_text(Text.from_ansi(line))
            self.write(t)

    def add_error(self, text: str) -> None:
        self.write(f"[bold error]Error:[/bold error] {text}")


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
        Binding("ctrl+s", "show_sources", "Source details"),
        Binding("ctrl+c", "quit", "Quit", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.chat_history: list[list[str]] = []

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
        self.query_one("#question", Input).focus()

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal, Vertical
        with Horizontal(id="body"):
            yield ChatPane(id="chat", markup=True, highlight=False, wrap=True)
            yield SourcesPanel(id="sources")
        yield ThinkingIndicator(id="thinking")
        with Vertical(id="input-bar"):
            yield Input(placeholder="Ask the Oracle…", id="question")
        yield Footer()

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
            self.call_from_thread(thinking.stop)
            self.call_from_thread(chat.add_oracle, answer)
            self.call_from_thread(sources_panel.load, raw_sources)
            self.chat_history.append([question, answer])

        threading.Thread(target=fetch, daemon=True).start()


if __name__ == "__main__":
    OracleApp().run()
