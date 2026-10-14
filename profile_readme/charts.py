"""Static SVG charts: a stat card and two single-series horizontal bar charts.

Each chart is rendered once per colour mode. Marks carry the series hue, text
only ever wears ink tokens, and nothing in the output depends on the clock, so
unchanged data produces byte-identical files.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from .palette import FONT, MODES
from .render_markdown import compact

CHAR_WIDTH = 0.56
MAX_BARS = 8
BAR_HEIGHT = 14
ROW_HEIGHT = 30
RADIUS = 4
MIN_BAR = 2


def text(
    x: float, y: float, value: str, size: int, fill: str, weight: int = 400, anchor: str = "start"
) -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'
    )


def bar(x: float, y: float, width: float, height: float, radius: float, fill: str) -> str:
    """A bar that is square at the baseline and rounded at the data end."""
    if width <= 0:
        return ""
    if width < radius * 2:
        return f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="{fill}"/>'
    straight = width - radius
    return (
        f'<path d="M{x:g},{y:g} h{straight:g} a{radius},{radius} 0 0 1 {radius},{radius} '
        f"v{height - 2 * radius:g} a{radius},{radius} 0 0 1 -{radius},{radius} "
        f'h-{straight:g} z" fill="{fill}"/>'
    )


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def frame(width: int, height: int, title: str, body: list[str], mode: str) -> str:
    tokens = MODES[mode]
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(title)}</title>',
            f"<style>text{{font-family:{FONT};}}</style>",
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" '
            f'fill="{tokens["surface"]}" stroke="{tokens["border"]}" '
            f'stroke-opacity="{tokens["border_opacity"]}"/>',
            *[line for line in body if line],
            "</svg>",
        ]
    )


def stat_card(
    title: str, subtitle: str, stats: list[tuple[str, int]], mode: str, width: int = 840
) -> str:
    tokens = MODES[mode]
    pad = 24
    body = [
        text(pad, 34, title, 15, tokens["ink"], weight=600),
        text(pad, 54, subtitle, 12, tokens["ink_muted"]),
        f'<line x1="{pad}" y1="68" x2="{width - pad}" y2="68" stroke="{tokens["grid"]}"/>',
    ]
    column = (width - 2 * pad) / max(len(stats), 1)
    for index, (label, value) in enumerate(stats):
        x = pad + index * column
        body.append(text(x, 96, label, 12, tokens["ink_secondary"]))
        body.append(text(x, 132, compact(value), 30, tokens["ink"], weight=600))
    return frame(width, 156, title, body, mode)


def bar_chart(
    title: str,
    rows: list[tuple[str, int]],
    mode: str,
    width: int = 440,
    min_rows: int = 0,
    label_chars: int = 22,
) -> str:
    tokens = MODES[mode]
    pad = 20
    label_width = 150
    value_width = 52
    top = 56
    rows = rows[:MAX_BARS]
    count = max(len(rows), min_rows, 1)
    height = top + count * ROW_HEIGHT + pad - (ROW_HEIGHT - BAR_HEIGHT)
    x0 = pad + label_width + 12
    span = width - pad - value_width - x0
    largest = max((value for _, value in rows), default=0) or 1

    body = [text(pad, 34, title, 15, tokens["ink"], weight=600)]
    if not rows:
        body.append(text(pad, top + BAR_HEIGHT, "No data yet", 12, tokens["ink_muted"]))
        return frame(width, height, title, body, mode)

    baseline_end = top + (len(rows) - 1) * ROW_HEIGHT + BAR_HEIGHT
    body.append(
        f'<line x1="{x0}" y1="{top}" x2="{x0}" y2="{baseline_end}" stroke="{tokens["baseline"]}"/>'
    )
    for index, (label, value) in enumerate(rows):
        y = top + index * ROW_HEIGHT
        middle = y + BAR_HEIGHT / 2 + 4
        body.append(
            text(
                pad + label_width,
                middle,
                truncate(label, label_chars),
                12,
                tokens["ink_secondary"],
                anchor="end",
            )
        )
        length = max(span * value / largest, MIN_BAR) if value else 0
        body.append(bar(x0, y, length, BAR_HEIGHT, RADIUS, tokens["series"]))
        body.append(text(x0 + length + 8, middle, compact(value), 12, tokens["ink_muted"]))
    return frame(width, height, title, body, mode)


def short_name(repo: str, repos: list[str]) -> str:
    """The repository name alone, unless two projects share it."""
    name = repo.split("/")[-1]
    if sum(1 for other in repos if other.split("/")[-1] == name) > 1:
        return repo
    return name


def render_all(data: dict) -> dict[str, str]:
    """Return {filename: svg} for every chart in both colour modes."""
    projects = data["projects"]
    merged_projects = sorted(
        ((name, p["merged"]) for name, p in projects.items() if p["merged"]),
        key=lambda item: (-item[1], item[0]),
    )
    names = [name for name, _ in merged_projects]
    project_rows = [(short_name(name, names), n) for name, n in merged_projects]
    language_rows = sorted(data["languages"].items(), key=lambda item: (-item[1], item[0]))
    min_rows = min(max(len(project_rows), len(language_rows)), MAX_BARS)

    stats = [
        ("Merged pull requests", len(data["merged"])),
        ("Reviews", len(data["reviewed"])),
        ("Issues opened", len(data["issues"])),
        ("Projects merged into", len(merged_projects)),
    ]

    files: dict[str, str] = {}
    for mode in MODES:
        files[f"oss-summary-{mode}.svg"] = stat_card(
            "Open source contributions",
            "Public repositories owned by others, refreshed daily",
            stats,
            mode,
        )
        files[f"oss-projects-{mode}.svg"] = bar_chart(
            "Merged pull requests by project", project_rows, mode, min_rows=min_rows
        )
        files[f"oss-languages-{mode}.svg"] = bar_chart(
            "Lines changed by language", language_rows, mode, min_rows=min_rows
        )
    return files
