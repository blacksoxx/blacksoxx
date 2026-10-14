"""Render the open source section of README.md from collected data."""

from __future__ import annotations

import html
import urllib.parse

START = "<!-- OSS-CONTRIBUTIONS:START -->"
END = "<!-- OSS-CONTRIBUTIONS:END -->"
MERGED_ROWS = 12
PROJECT_ROWS = 40
PHRASE_PROJECTS = 3


def compact(n: int) -> str:
    """4825 -> 4.8k, 25789 -> 25.8k, 1000 -> 1k, 48 -> 48."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def cell(text: str) -> str:
    return html.escape(text, quote=False).replace("|", "\\|")


def search_url(kind: str, *terms: str) -> str:
    query = urllib.parse.quote_plus(" ".join(terms))
    return f"https://github.com/search?q={query}&type={kind}"


def repo_url(repo: str, kind: str, *terms: str) -> str:
    query = urllib.parse.quote_plus(" ".join(terms))
    return f"https://github.com/{repo}/{kind}?q={query}"


def picture(name: str, alt: str, width: str) -> list[str]:
    return [
        "<picture>",
        f'  <source media="(prefers-color-scheme: dark)" srcset="profile/{name}-dark.svg">',
        f'  <img alt="{html.escape(alt, quote=True)}" '
        f'src="profile/{name}-light.svg" width="{width}">',
        "</picture>",
    ]


def project_phrase(projects: dict[str, dict], counts: dict[str, int]) -> str:
    """'[a](url), [b](url) and 2 more' for the projects with the highest counts."""
    ranked = sorted(counts, key=lambda name: (-counts[name], name))
    links = [f"[{name}]({projects[name]['url']})" for name in ranked[:PHRASE_PROJECTS]]
    rest = len(ranked) - len(links)
    if rest:
        links.append(f"{rest} more")
    if len(links) == 1:
        return links[0]
    return ", ".join(links[:-1]) + " and " + links[-1]


def count_link(n: int, url: str) -> str:
    return f"[{n}]({url})" if n else "–"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def render_section(data: dict) -> str:
    user = data["user"]
    projects = data["projects"]
    merged = sorted(data["merged"], key=lambda p: p["merged_at"], reverse=True)
    reviewed = data["reviewed"]
    issues = data["issues"]
    opened = data["open"]
    merged_projects = sum(1 for p in projects.values() if p["merged"])

    lines: list[str] = []
    lines += picture(
        "oss-summary",
        f"Open source summary: {plural(len(merged), 'merged pull request')}, "
        f"{plural(len(reviewed), 'review')}, {plural(len(issues), 'issue')} opened, "
        f"{plural(merged_projects, 'project')} with merged work",
        "100%",
    )

    lines += ["", "### Merged pull requests", ""]
    if merged:
        lines += ["| Merged | Project | Pull request |", "| --- | --- | --- |"]
        for pr in merged[:MERGED_ROWS]:
            lines.append(
                f"| {pr['merged_at'][:10]} "
                f"| [{pr['repo']}]({projects[pr['repo']]['url']}) "
                f"| [{cell(pr['title'])}]({pr['url']}) |"
            )
        if len(merged) > MERGED_ROWS:
            url = search_url(
                "pullrequests", "is:pr", f"author:{user}", "is:merged", f"-user:{user}"
            )
            lines += ["", f"<sub>[All {len(merged)} merged pull requests]({url})</sub>"]
    else:
        lines.append("_Nothing merged yet._")

    activity: list[str] = []
    if reviewed:
        url = search_url("pullrequests", "is:pr", f"reviewed-by:{user}", f"-author:{user}")
        counts = {name: p["reviewed"] for name, p in projects.items() if p["reviewed"]}
        activity.append(
            f"- Reviewed [{plural(len(reviewed), 'pull request')}]({url}) "
            f"in {project_phrase(projects, counts)}."
        )
    if issues:
        url = search_url("issues", "is:issue", f"author:{user}", f"-user:{user}")
        counts = {name: p["issues"] for name, p in projects.items() if p["issues"]}
        activity.append(
            f"- Opened [{plural(len(issues), 'issue')}]({url}) "
            f"in {project_phrase(projects, counts)}."
        )
    if activity:
        lines += ["", "### Reviews and issues", "", *activity]

    by_project = sorted(
        ((name, p["merged"]) for name, p in projects.items() if p["merged"]),
        key=lambda item: (-item[1], item[0]),
    )
    languages = sorted(data["languages"].items(), key=lambda item: (-item[1], item[0]))
    lines += ["", '<p align="center">']
    lines += picture(
        "oss-projects",
        "Merged pull requests by project: "
        + (", ".join(f"{name} {n}" for name, n in by_project) or "none yet"),
        "49%",
    )
    lines += picture(
        "oss-languages",
        "Lines changed by language in merged pull requests: "
        + (", ".join(f"{name} {compact(n)}" for name, n in languages) or "none yet"),
        "49%",
    )
    lines.append("</p>")

    ranked = sorted(
        projects.items(),
        key=lambda item: (-item[1]["merged"], -item[1]["reviewed"], -item[1]["stars"], item[0]),
    )
    if ranked:
        summary = f"All {plural(len(ranked), 'project')}"
        if opened:
            summary += f", including {plural(len(opened), 'open pull request')}"
        lines += [
            "",
            "<details>",
            f"<summary>{summary}</summary>",
            "",
            "| Project | Stars | Merged | Reviewed | Open |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for name, p in ranked[:PROJECT_ROWS]:
            merged_cell = count_link(
                p["merged"], repo_url(name, "pulls", "is:pr", f"author:{user}", "is:merged")
            )
            reviewed_cell = count_link(
                p["reviewed"],
                repo_url(name, "pulls", "is:pr", f"reviewed-by:{user}", f"-author:{user}"),
            )
            open_cell = count_link(
                p["open"], repo_url(name, "pulls", "is:pr", f"author:{user}", "is:open")
            )
            lines.append(
                f"| [{name}]({p['url']}) | {compact(p['stars'])} "
                f"| {merged_cell} | {reviewed_cell} | {open_cell} |"
            )
        if len(ranked) > PROJECT_ROWS:
            lines += ["", f"<sub>…and {len(ranked) - PROJECT_ROWS} more.</sub>"]
        lines += ["", "</details>"]

    return "\n".join(lines)


def update_readme(readme: str, section: str) -> str:
    start = readme.find(START)
    end = readme.find(END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"README is missing the {START} / {END} markers")
    return f"{readme[:start]}{START}\n\n{section}\n\n{readme[end:]}"
