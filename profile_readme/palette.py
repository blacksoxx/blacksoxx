"""Chart tokens.

Two categorical hues in fixed order, one of them doubling as the single-series
hue, every piece of text in an ink token, and the dark set stepped for the dark
surface rather than inverted from the light one.
"""

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

MODES = {
    "light": {
        "surface": "#fcfcfb",
        "border": "#0b0b0b",
        "border_opacity": "0.10",
        "ink": "#0b0b0b",
        "ink_secondary": "#52514e",
        "ink_muted": "#898781",
        "grid": "#e1e0d9",
        "baseline": "#c3c2b7",
        "series": "#2a78d6",
        "series_2": "#eb6834",
    },
    "dark": {
        "surface": "#1a1a19",
        "border": "#ffffff",
        "border_opacity": "0.10",
        "ink": "#f0efec",
        "ink_secondary": "#c3c2b7",
        "ink_muted": "#898781",
        "grid": "#2c2c2a",
        "baseline": "#383835",
        "series": "#3987e5",
        "series_2": "#d95926",
    },
}

TEXT_ROLES = ("ink", "ink_secondary", "ink_muted")
SERIES_ROLES = ("series", "series_2")
