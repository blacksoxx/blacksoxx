"""Render the open source section of README.md from collected data."""

from __future__ import annotations

import html
import urllib.parse

from .charts import CARDS
from .format import compact, plural

START = "<!-- OSS-CONTRIBUTIONS:START -->"
END = "<!-- OSS-CONTRIBUTIONS:END -->"
PROJECT_ROWS = 40
PHRASE_PROJECTS = 3
WALL_COLUMNS = 6
OPEN_LOGOS = 30


def cell(text: str) -> str:
    return html.escape(text, quote=False).replace("|", "\\|")


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def search_url(kind: str, *terms: str) -> str:
    query = urllib.parse.quote_plus(" ".join(terms))
    return f"https://github.com/search?q={query}&type={kind}"


def repo_url(repo: str, kind: str, *terms: str) -> str:
    query = urllib.parse.quote_plus(" ".join(terms))
    return f"https://github.com/{repo}/{kind}?q={query}"


def count_link(n: int, url: str) -> str:
    return f"[{n}]({url})" if n else "–"


def picture(name: str, alt: str, width: str) -> list[str]:
    return [
        "<picture>",
        f'  <source media="(prefers-color-scheme: dark)" srcset="profile/{name}-dark.svg">',
        f'  <img alt="{attr(alt)}" src="profile/{name}-light.svg" width="{width}">',
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


def by_owner(projects: dict[str, dict], key: str) -> list[tuple[str, int, int, str]]:
    """(owner, count, stars, avatar_url) for owners with a non-zero `key`, ranked."""
    owners: dict[str, list] = {}
    for name, p in projects.items():
        if not p[key]:
            continue
        owner = name.split("/")[0]
        entry = owners.setdefault(owner, [0, 0, p["avatar_url"]])
        entry[0] += p[key]
        entry[1] = max(entry[1], p["stars"])
    return sorted(
        ((owner, c, s, a) for owner, (c, s, a) in owners.items()),
        key=lambda item: (-item[1], -item[2], item[0]),
    )


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

    lines += ["", "### Recent merged work", ""]
    if merged:
        lines.append('<p align="center">')
        for index, pr in enumerate(merged[:CARDS], 1):
            lines.append(f'<a href="{pr["url"]}">')
            lines += picture(f"pr-{index}", f"{pr['repo']}: {pr['title']}", "49%")
            lines.append("</a>")
        lines.append("</p>")
        url = search_url("pullrequests", "is:pr", f"author:{user}", "is:merged", f"-user:{user}")
        lines += ["", f"<sub>[All {len(merged)} merged pull requests]({url})</sub>"]
    else:
        lines.append("_Nothing merged yet._")

    wall = by_owner(projects, "merged")
    if wall:
        lines += ["", "### Projects", "", "<table>"]
        for start in range(0, len(wall), WALL_COLUMNS):
            lines.append("<tr>")
            for owner, count, _, avatar in wall[start : start + WALL_COLUMNS]:
                url = search_url(
                    "pullrequests", "is:pr", f"author:{user}", "is:merged", f"user:{owner}"
                )
                lines.append(
                    f'<td align="center" width="{100 // WALL_COLUMNS}%">'
                    f'<a href="{url}"><img src="{avatar}" width="48" height="48" '
                    f'alt="{attr(owner)}"><br><sub><b>{html.escape(owner)}</b></sub></a>'
                    f"<br><sub>{count} merged</sub></td>"
                )
            lines.append("</tr>")
        lines.append("</table>")

    merged_owners = {owner for owner, *_ in wall}
    others = [entry for entry in by_owner(projects, "open") if entry[0] not in merged_owners]
    if others:
        lines += ["", f"Open pull requests in {plural(len(others), 'more organisation')}:", ""]
        lines.append("<p>")
        for owner, _, _, avatar in others[:OPEN_LOGOS]:
            url = search_url("pullrequests", "is:pr", f"author:{user}", "is:open", f"user:{owner}")
            lines.append(
                f'<a href="{url}" title="{attr(owner)}"><img src="{avatar}" width="28" '
                f'height="28" alt="{attr(owner)}"></a>'
            )
        if len(others) > OPEN_LOGOS:
            lines.append(f"<sub>+{len(others) - OPEN_LOGOS} more</sub>")
        lines.append("</p>")

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

    languages = sorted(data["languages"].items(), key=lambda item: (-item[1], item[0]))
    lines += ["", '<p align="center">']
    lines += picture(
        "oss-activity",
        "Merged pull requests and reviews per week over the last twelve weeks",
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
