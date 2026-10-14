"""Command line entry point.

python -m profile_readme fetch    # GitHub API -> data/contributions.json
python -m profile_readme render   # data -> README section + profile/*.svg
python -m profile_readme update   # both
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .charts import render_all
from .github import Client, collect, default_user
from .render_markdown import render_section, update_readme

ROOT = Path(__file__).resolve().parent.parent


def fetch(args: argparse.Namespace) -> int:
    client = Client(os.environ.get("GITHUB_TOKEN"), user_agent=f"{args.user}-profile-readme")
    data = collect(client, args.user)
    args.data.parent.mkdir(parents=True, exist_ok=True)
    args.data.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{args.data}: {len(data['merged'])} merged, {len(data['open'])} open, "
        f"{len(data['reviewed'])} reviewed, {len(data['issues'])} issues, "
        f"{len(data['projects'])} projects"
    )
    return 0


def render(args: argparse.Namespace) -> int:
    data = json.loads(args.data.read_text(encoding="utf-8"))

    args.charts.mkdir(parents=True, exist_ok=True)
    changed = []
    for name, svg in render_all(data).items():
        target = args.charts / name
        if not target.exists() or target.read_text(encoding="utf-8") != svg:
            target.write_text(svg, encoding="utf-8")
            changed.append(name)
    if changed:
        print(f"{args.charts}: {len(changed)} chart(s) changed")
    else:
        print(f"{args.charts}: unchanged")

    readme = args.readme.read_text(encoding="utf-8")
    updated = update_readme(readme, render_section(data))
    if updated != readme:
        args.readme.write_text(updated, encoding="utf-8")
        print(f"{args.readme}: updated")
    else:
        print(f"{args.readme}: unchanged")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile_readme", description=__doc__)
    parser.add_argument("--user", default=default_user(), help="GitHub login (default: $GH_USER)")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "contributions.json")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--charts", type=Path, default=ROOT / "profile")
    parser.add_argument("command", choices=("fetch", "render", "update"))
    args = parser.parse_args(argv)

    if args.command in ("fetch", "update") and fetch(args):
        return 1
    if args.command in ("render", "update"):
        return render(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
