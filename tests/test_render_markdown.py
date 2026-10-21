from datetime import date

import pytest

from profile_readme.format import compact, plural, pretty_date, weekly, within_days
from profile_readme.render_markdown import (
    END,
    START,
    by_owner,
    project_phrase,
    render_section,
    update_readme,
)


def test_compact():
    assert compact(48) == "48"
    assert compact(999) == "999"
    assert compact(1000) == "1k"
    assert compact(4825) == "4.8k"
    assert compact(25789) == "25.8k"
    assert compact(1_260_000) == "1.3M"


def test_format_helpers():
    assert plural(1, "review") == "1 review"
    assert plural(2, "review") == "2 reviews"
    assert pretty_date("2026-10-03T09:00:00Z") == "3 Oct 2026"
    stamps = ["2026-10-03T09:00:00Z", "2026-09-22T09:00:00Z", "2026-07-01T00:00:00Z"]
    assert weekly(stamps, date(2026, 10, 14), 4) == [1, 1, 0, 0]
    assert within_days(stamps, date(2026, 10, 14), 30) == 2


def test_cards_are_newest_first_and_linked(data):
    section = render_section(data)
    hrefs = [
        line
        for line in section.splitlines()
        if line.startswith('<a href="https://github.com/acme/')
    ]
    assert hrefs == [
        '<a href="https://github.com/acme/widgets/pull/12">',
        '<a href="https://github.com/acme/gadgets/pull/4">',
        '<a href="https://github.com/acme/widgets/pull/9">',
    ]
    assert 'srcset="profile/pr-1-dark.svg"' in section
    assert 'src="profile/pr-3-light.svg"' in section
    assert 'alt="acme/widgets: fix(api): return &lt;b&gt;typed&lt;/b&gt; errors | not strings"' in (
        section
    )
    assert "<b>typed</b>" not in section
    assert "[All 3 merged pull requests](https://github.com/search?q=" in section


def test_summary_picture_and_alt_text(data):
    section = render_section(data)
    assert 'srcset="profile/oss-summary-dark.svg"' in section
    assert 'src="profile/oss-summary-light.svg"' in section
    assert (
        "3 merged pull requests, 1 review, 1 issue opened, 2 projects with merged work" in section
    )
    assert "Lines changed by language in merged pull requests: Go 1.2k, Markdown 300, YAML 50" in (
        section
    )
    assert 'src="profile/oss-activity-light.svg"' in section


def test_project_wall_groups_by_owner(data):
    section = render_section(data)
    assert section.count("<td ") == 1
    cell = next(line for line in section.splitlines() if line.startswith("<td "))
    assert 'src="https://avatars.githubusercontent.com/acme?s=64"' in cell
    assert "<sub><b>acme</b></sub>" in cell
    assert "<sub>3 merged</sub>" in cell
    assert "is%3Apr+author%3Ablacksoxx+is%3Amerged+user%3Aacme" in cell
    assert "Open pull requests in 1 more organisation:" in section
    assert 'title="big"' in section
    assert 'title="acme"' not in section


def test_reviews_and_issues_lines(data):
    section = render_section(data)
    assert "- Reviewed [1 pull request](" in section
    assert "in [acme/widgets](https://github.com/acme/widgets)." in section
    assert "- Opened [1 issue](" in section
    assert "in [other/tool](https://github.com/other/tool)." in section


def test_project_table_ranks_merged_then_reviewed_then_stars(data):
    section = render_section(data)
    assert "<summary>All 4 projects, including 4 open pull requests</summary>" in section
    table = [line for line in section.splitlines() if line.startswith("| [")]
    names = [line.split("](")[0][3:] for line in table]
    assert names == ["acme/widgets", "acme/gadgets", "big/platform", "other/tool"]
    merged_link = "https://github.com/acme/widgets/pulls?q=is%3Apr+author%3Ablacksoxx+is%3Amerged"
    assert f"| 4.8k | [2]({merged_link}) | [1](" in table[0]
    assert "| 25.8k | – | – | [2](" in table[2]


def test_by_owner():
    projects = {
        "a/one": {"merged": 2, "open": 0, "stars": 5, "avatar_url": "a.png"},
        "a/two": {"merged": 1, "open": 1, "stars": 50, "avatar_url": "a.png"},
        "b/one": {"merged": 3, "open": 0, "stars": 1, "avatar_url": "b.png"},
        "c/one": {"merged": 0, "open": 4, "stars": 9, "avatar_url": "c.png"},
    }
    assert by_owner(projects, "merged") == [("a", 3, 50, "a.png"), ("b", 3, 1, "b.png")]
    assert by_owner(projects, "open") == [("c", 4, 9, "c.png"), ("a", 1, 50, "a.png")]


def test_empty_data_renders_placeholders():
    data = {
        "user": "x",
        "generated_at": "2026-10-14T00:00:00Z",
        "merged": [],
        "open": [],
        "reviewed": [],
        "issues": [],
        "projects": {},
        "languages": {},
    }
    section = render_section(data)
    assert "_Nothing merged yet._" in section
    assert "### Projects" not in section
    assert "### Reviews and issues" not in section
    assert "<details>" not in section
    assert "none yet" in section


def test_project_phrase():
    projects = {name: {"url": f"https://github.com/{name}"} for name in "abcde"}
    assert project_phrase(projects, {"a": 1}) == "[a](https://github.com/a)"
    assert project_phrase(projects, {"a": 1, "b": 3}) == (
        "[b](https://github.com/b) and [a](https://github.com/a)"
    )
    assert project_phrase(projects, dict.fromkeys("abcde", 1)) == (
        "[a](https://github.com/a), [b](https://github.com/b), [c](https://github.com/c) and 2 more"
    )


def test_update_readme_replaces_between_markers_idempotently():
    readme = f"# Title\n\n## Open source\n\n{START}\nold\n{END}\n\n## After\n"
    once = update_readme(readme, "new section")
    assert once == f"# Title\n\n## Open source\n\n{START}\n\nnew section\n\n{END}\n\n## After\n"
    assert update_readme(once, "new section") == once


def test_update_readme_requires_markers():
    with pytest.raises(ValueError):
        update_readme("# No markers", "section")
