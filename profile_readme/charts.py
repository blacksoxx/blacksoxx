"""Static SVG charts: a stat card, pull request cards, a weekly activity chart
and a single-series bar chart.

Each chart is rendered once per colour mode. Marks carry the series hues, text
only ever wears text tokens, and nothing in the output depends on the clock
(the data file's own timestamp anchors the time windows), so unchanged data
produces byte-identical files.
"""

from __future__ import annotations

from datetime import timedelta
from xml.sax.saxutils import escape

from .format import compact, parse_day, pretty_date, week_start, weekly
from .palette import FONT, MODES

CHAR_WIDTH = 0.56
MAX_BARS = 5
BAR_HEIGHT = 14
ROW_HEIGHT = 30
RADIUS = 4
MIN_BAR = 2
CARDS = 8
CARD_WIDTH = 440
CARD_HEIGHT = 118
TITLE_CHARS = 50
WEEKS = 12


def text(
    x: float, y: float, value: str, size: int, fill: str, weight: int = 400, anchor: str = "start"
) -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'
    )


def bar(x: float, y: float, width: float, height: float, radius: float, fill: str) -> str:
    """A horizontal bar, square at the baseline and rounded at the data end."""
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


def column(x: float, y: float, width: float, height: float, radius: float, fill: str) -> str:
    """A vertical column, square at the baseline and rounded at the top."""
    if height <= 0:
        return ""
    if height < radius * 2:
        return f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="{fill}"/>'
    return (
        f'<path d="M{x:g},{y + radius:g} a{radius},{radius} 0 0 1 {radius},-{radius} '
        f"h{width - 2 * radius:g} a{radius},{radius} 0 0 1 {radius},{radius} "
        f'v{height - radius:g} h-{width:g} z" fill="{fill}"/>'
    )


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def wrap(value: str, limit: int, max_lines: int) -> list[str]:
    """Greedy word wrap; the last allowed line is truncated with an ellipsis."""
    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        rest = " ".join(lines[max_lines - 1 :])
        lines = lines[: max_lines - 1] + [truncate(rest, limit)]
    return [truncate(line, limit) for line in lines]


def nice_step(largest: int) -> int:
    for step in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        if largest / step <= 5:
            return step
    return 1000


def frame(width: int, height: int, title: str, body: list[str], mode: str, defs: str = "") -> str:
    tokens = MODES[mode]
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(title)}</title>',
            f"<style>text{{font-family:{FONT};}}</style>",
            *([defs] if defs else []),
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" '
            f'fill="{tokens["surface"]}" stroke="{tokens["border"]}" '
            f'stroke-opacity="{tokens["border_opacity"]}"/>',
            *[line for line in body if line],
            "</svg>",
        ]
    )


def stat_card(
    title: str,
    subtitle: str,
    stats: list[tuple[str, int]],
    mode: str,
    width: int = 840,
) -> str:
    tokens = MODES[mode]
    pad = 24
    body = [
        text(pad, 34, title, 15, tokens["ink"], weight=600),
        text(pad, 54, subtitle, 12, tokens["ink_muted"]),
        f'<line x1="{pad}" y1="68" x2="{width - pad}" y2="68" stroke="{tokens["grid"]}"/>',
    ]
    col = (width - 2 * pad) / max(len(stats), 1)
    for index, (label, value) in enumerate(stats):
        x = pad + index * col
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


def activity_chart(
    title: str,
    series: list[tuple[str, list[int]]],
    labels: list[str],
    mode: str,
    width: int = 440,
    height: int = 210,
) -> str:
    """Grouped weekly columns, one hue per series in fixed order, legend on top."""
    tokens = MODES[mode]
    hues = [tokens["series"], tokens["series_2"]]
    pad = 20
    left = 46
    top = 60
    bottom = height - 34
    plot_height = bottom - top
    weeks = len(labels)
    band = (width - pad - left) / max(weeks, 1)
    largest = max((v for _, values in series for v in values), default=0)
    step = nice_step(largest)
    ceiling = max(step, -(-largest // step) * step)

    body = [text(pad, 34, title, 15, tokens["ink"], weight=600)]
    legend = [
        (name, hue, len(name) * 12 * CHAR_WIDTH + 16)
        for (name, _), hue in zip(series, hues, strict=False)
    ]
    x = width - pad - sum(w for _, _, w in legend) - 14 * (len(legend) - 1)
    for name, hue, w in legend:
        body.append(f'<rect x="{x:g}" y="25" width="10" height="10" rx="2" fill="{hue}"/>')
        body.append(text(x + 16, 34, name, 12, tokens["ink_secondary"]))
        x += w + 14

    for value in range(0, ceiling + 1, step):
        y = bottom - plot_height * value / ceiling
        stroke = tokens["baseline"] if value == 0 else tokens["grid"]
        body.append(
            f'<line x1="{left}" y1="{y:g}" x2="{width - pad}" y2="{y:g}" stroke="{stroke}"/>'
        )
        body.append(text(left - 8, y + 4, str(value), 11, tokens["ink_muted"], anchor="end"))

    gap = 2
    col = min(11, (band - 8 - gap * (len(series) - 1)) / max(len(series), 1))
    group = col * len(series) + gap * (len(series) - 1)
    for week in range(weeks):
        x0 = left + band * week + (band - group) / 2
        for index, (_, values) in enumerate(series):
            value = values[week]
            h = plot_height * value / ceiling
            body.append(column(x0 + index * (col + gap), bottom - h, col, h, 3, hues[index]))
        if week % 4 == 0 or week == weeks - 1:
            body.append(
                text(
                    left + band * week + band / 2,
                    bottom + 18,
                    labels[week],
                    11,
                    tokens["ink_muted"],
                    anchor="middle",
                )
            )
    return frame(width, height, title, body, mode)


def pr_card(pr: dict, project: dict, mode: str) -> str:
    tokens = MODES[mode]
    pad = 20
    width, height = CARD_WIDTH, CARD_HEIGHT
    defs = (
        f'<clipPath id="frame"><rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'rx="8"/></clipPath><clipPath id="avatar"><circle cx="{pad + 10}" cy="30" r="10"/>'
        "</clipPath>"
    )
    body = [
        f'<rect x="0.5" y="0.5" width="4" height="{height - 1}" fill="{tokens["series"]}" '
        'clip-path="url(#frame)"/>'
    ]
    if project.get("avatar"):
        body.append(
            f'<image href="data:image/png;base64,{project["avatar"]}" x="{pad}" y="20" '
            'width="20" height="20" clip-path="url(#avatar)"/>'
        )
    else:
        body.append(f'<circle cx="{pad + 10}" cy="30" r="10" fill="{tokens["grid"]}"/>')
    body.append(text(pad + 28, 34, pr["repo"], 12, tokens["ink_secondary"]))
    for index, line in enumerate(wrap(pr["title"], TITLE_CHARS, 2)):
        body.append(text(pad, 62 + index * 20, line, 14, tokens["ink"], weight=600))
    footer = [f"Merged {pretty_date(pr['merged_at'])}"]
    if pr.get("additions") or pr.get("deletions"):
        footer.append(f"+{compact(pr.get('additions', 0))} −{compact(pr.get('deletions', 0))}")
    if pr.get("language"):
        footer.append(pr["language"])
    body.append(text(pad, height - 18, "  ·  ".join(footer), 12, tokens["ink_muted"]))
    return frame(width, height, f"{pr['repo']}: {pr['title']}", body, mode, defs=defs)


def render_all(data: dict) -> dict[str, str]:
    """Return {filename: svg} for every chart in both colour modes."""
    now = parse_day(data["generated_at"])
    projects = data["projects"]
    merged = sorted(data["merged"], key=lambda p: p["merged_at"], reverse=True)
    reviewed = data["reviewed"]
    issues = data["issues"]
    merged_projects = sum(1 for p in projects.values() if p["merged"])

    stats = [
        ("Merged pull requests", len(merged)),
        ("Reviews", len(reviewed)),
        ("Issues opened", len(issues)),
        ("Projects merged into", merged_projects),
    ]

    first_week = week_start(now) - timedelta(weeks=WEEKS - 1)
    labels = [
        f"{(first_week + timedelta(weeks=w)).day} {(first_week + timedelta(weeks=w)):%b}"
        for w in range(WEEKS)
    ]
    series = [
        ("Merged", weekly([p["merged_at"] for p in merged], now, WEEKS)),
        ("Reviews", weekly([r["reviewed_at"] for r in reviewed], now, WEEKS)),
    ]
    language_rows = sorted(data["languages"].items(), key=lambda item: (-item[1], item[0]))

    files: dict[str, str] = {}
    for mode in MODES:
        files[f"oss-summary-{mode}.svg"] = stat_card(
            "Open source contributions",
            "Public repositories owned by others, refreshed every six hours",
            stats,
            mode,
        )
        files[f"oss-activity-{mode}.svg"] = activity_chart(
            f"Activity, last {WEEKS} weeks", series, labels, mode
        )
        files[f"oss-languages-{mode}.svg"] = bar_chart(
            "Lines changed by language", language_rows, mode, min_rows=MAX_BARS
        )
        for index, pr in enumerate(merged[:CARDS], 1):
            files[f"pr-{index}-{mode}.svg"] = pr_card(pr, projects[pr["repo"]], mode)
    return files
