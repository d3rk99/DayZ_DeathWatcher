"""Theme definitions for the DayZ Death Watcher GUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    name: str
    bg: str
    fg: str
    muted: str
    panel_bg: str
    entry_bg: str
    entry_fg: str
    placeholder: str
    console_bg: str
    console_fg: str
    canvas_bg: str
    accent: str
    button_bg: str
    button_fg: str


LIGHT_THEME = ThemePalette(
    name="light",
    bg="#f0f0f0",
    fg="#111111",
    muted="#444444",
    panel_bg="#ffffff",
    entry_bg="#ffffff",
    entry_fg="#111111",
    placeholder="#666666",
    console_bg="#ffffff",
    console_fg="#111111",
    canvas_bg="#f8f8f8",
    accent="#0078d4",
    button_bg="#e6e6e6",
    button_fg="#111111",
)


DARK_THEME = ThemePalette(
    name="dark",
    bg="#1e1e1e",
    fg="#f3f3f3",
    muted="#b3b3b3",
    panel_bg="#2b2b2b",
    entry_bg="#3a3a3a",
    entry_fg="#f3f3f3",
    placeholder="#9a9a9a",
    console_bg="#1b1b1b",
    console_fg="#f3f3f3",
    canvas_bg="#1e1e1e",
    accent="#569cd6",
    button_bg="#3d3d3d",
    button_fg="#f3f3f3",
)


def get_theme(dark: bool) -> ThemePalette:
    """Return the palette for the requested mode."""

    return DARK_THEME if dark else LIGHT_THEME


__all__ = ["ThemePalette", "LIGHT_THEME", "DARK_THEME", "get_theme"]
