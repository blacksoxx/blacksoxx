#!/usr/bin/env python3
"""Regenerate the open source contributions section of README.md.

Lists every public repository owned by someone else that the user has merged
or currently open pull requests in, with per-project counts. Pull requests
that were closed without merging are ignored.

Private work must never reach this file, so visibility is filtered twice: the
search query carries `is:public`, and every repository is then re-checked
through the repos API before any of its pull requests are counted.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
START = "<!-- OSS-CONTRIBUTIONS:START -->"
END = "<!-- OSS-CONTRIBUTIONS:END -->"
MAX_ROWS = 24

USER = os.environ.get("GH_USER") or "blacksoxx"
TOKEN = os.environ.get("GITHUB_TOKEN")
README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")


def get(url):
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", f"{USER}-profile-readme")
    if TOKEN:
        request.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search_prs():
    query = f"type:pr author:{USER} is:public -user:{USER}"
    items, page = [], 1
    while True:
        params = urllib.parse.urlencode({"q": query, "per_page": 100, "page": page})
        batch = get(f"{API}/search/issues?{params}").get("items", [])
        items.extend(batch)
        if len(batch) < 100 or page >= 10:
            return items
        page += 1


def pr_link(full_name, state):
    query = urllib.parse.quote(f"is:pr author:{USER} is:{state}")
    return f"https://github.com/{full_name}/pulls?q={query}"


def main():
    try:
        prs = search_prs()
    except urllib.error.HTTPError as exc:
        print(f"GitHub search failed: {exc}", file=sys.stderr)
        return 1

    tally = {}
    for pr in prs:
        full_name = "/".join(pr["repository_url"].split("/")[-2:])
        counts = tally.setdefault(full_name, {"merged": 0, "open": 0})
        if (pr.get("pull_request") or {}).get("merged_at"):
            counts["merged"] += 1
        elif pr.get("state") == "open":
            counts["open"] += 1
        # Closed without merging is deliberately not counted.

    rows = []
    for full_name, counts in tally.items():
        if not counts["merged"] and not counts["open"]:
            continue
        meta = get(f"{API}/repos/{full_name}")
        # Second visibility gate: never list anything non-public.
        if meta.get("private") or meta.get("owner", {}).get("login", "").lower() == USER.lower():
            continue
        rows.append((meta, counts))

    # Projects with merged work first, then the largest projects.
    rows.sort(key=lambda r: (r[1]["merged"], r[0].get("stargazers_count", 0)), reverse=True)

    if not rows:
        body = "_No public contributions found yet._"
    else:
        merged_total = sum(c["merged"] for _, c in rows)
        open_total = sum(c["open"] for _, c in rows)
        shown = rows[:MAX_ROWS]

        lines = [
            f"**{merged_total + open_total} pull requests across {len(rows)} open source "
            f"projects** &nbsp;·&nbsp; {merged_total} merged &nbsp;·&nbsp; {open_total} in review",
            "",
            "| Project | Stars | Merged | In review |",
            "| --- | ---: | ---: | ---: |",
        ]
        for meta, counts in shown:
            name = meta["full_name"]
            merged = (
                f"[{counts['merged']}]({pr_link(name, 'merged')})" if counts["merged"] else "–"
            )
            opened = f"[{counts['open']}]({pr_link(name, 'open')})" if counts["open"] else "–"
            lines.append(
                f"| [{name}]({meta['html_url']}) "
                f"| {meta.get('stargazers_count', 0):,} | {merged} | {opened} |"
            )
        if len(rows) > MAX_ROWS:
            lines.append(f"\n<sub>…and {len(rows) - MAX_ROWS} more projects.</sub>")
        body = "\n".join(lines)

    with open(README, encoding="utf-8") as handle:
        readme = handle.read()

    if START not in readme or END not in readme:
        print(f"Markers {START} / {END} not found in README.md", file=sys.stderr)
        return 1

    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n\n{body}\n\n{END}",
        readme,
        flags=re.DOTALL,
    )

    if updated == readme:
        print("No changes.")
        return 0

    with open(README, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print("README.md updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
