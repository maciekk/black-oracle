---
name: UI preferences
description: Textual TUI design choices and style preferences for chat.py
type: feedback
---

Custom "oracle" Textual theme: black background (#111111), orange primary (#E0712A), bright orange (#FF7A1E) for accents.

**Why:** User asked for black background with orange accents explicitly.

**How to apply:** Use `#FF7A1E` for the `│` bar and spinner character. Use `[dim]` for secondary info (numbers in source list, path hints). Keep oracle theme as the default.

Key layout decisions:
- Oracle responses use a bright orange `│` left-edge bar on every line (including content, not just header)
- Chat content pre-rendered at 65 chars wide to avoid horizontal scrollbar
- Braille spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) in bright orange, shown between chat and input bar while waiting
- Sources side panel: filenames only, dim numbered list (`[dim]{i}.[/dim] {name}`)
- Ctrl+S opens full-screen scrollable modal overlay for source details (Markdown-rendered, auto_scroll=False)
- Escape dismisses the overlay
- Intro box at startup uses Rich Panel with orange border
