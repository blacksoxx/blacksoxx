"""Small formatting helpers shared by the markdown and chart renderers."""

from __future__ import annotations

from datetime import date, timedelta


def compact(n: int) -> str:
    """4825 -> 4.8k, 25789 -> 25.8k, 1000 -> 1k, 48 -> 48."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def short_name(repo: str, repos: list[str]) -> str:
    """The repository name alone, unless two projects share it."""
    name = repo.split("/")[-1]
    if sum(1 for other in repos if other.split("/")[-1] == name) > 1:
        return repo
    return name


def parse_day(stamp: str) -> date:
    return date.fromisoformat(stamp[:10])


def pretty_date(stamp: str) -> str:
    """2026-10-14T... -> 14 Oct 2026."""
    day = parse_day(stamp)
    return f"{day.day} {day.strftime('%b %Y')}"


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly(stamps: list[str], now: date, weeks: int) -> list[int]:
    """Count stamps per ISO week over the `weeks` weeks ending in the week of `now`."""
    first = week_start(now) - timedelta(weeks=weeks - 1)
    counts = [0] * weeks
    for stamp in stamps:
        index = (week_start(parse_day(stamp)) - first).days // 7
        if 0 <= index < weeks:
            counts[index] += 1
    return counts


def within_days(stamps: list[str], now: date, days: int) -> int:
    floor = now - timedelta(days=days)
    return sum(1 for stamp in stamps if parse_day(stamp) > floor)
