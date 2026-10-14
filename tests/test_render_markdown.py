import pytest

from profile_readme.render_markdown import (
    END,
    START,
    compact,
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


def test_merged_table_is_newest_first_and_escaped(data):
    section = render_section(data)
    rows = [line for line in section.splitlines() if line.startswith("| 2026-")]
    assert [row.split(" | ")[0] for row in rows] == ["| 2026-10-03", "| 2026-09-30", "| 2026-09-22"]
    assert "fix(api): return &lt;b&gt;typed&lt;/b&gt; errors \\| not strings" in rows[0]
    assert "<b>" not in section
    assert "[All " not in section


def test_summary_picture_and_alt_text(data):
    section = render_section(data)
    assert 'srcset="profile/oss-summary-dark.svg"' in section
    assert 'src="profile/oss-summary-light.svg"' in section
    assert (
        "3 merged pull requests, 1 review, 1 issue opened, 2 projects with merged work" in section
    )
    assert "Merged pull requests by project: acme/widgets 2, acme/gadgets 1" in section
    assert "Lines changed by language in merged pull requests: Go 1.2k, Markdown 300, YAML 50" in (
        section
    )


def test_reviews_and_issues_lines(data):
    section = render_section(data)
    assert "- Reviewed [1 pull request](" in section
    assert "in [acme/widgets](https://github.com/acme/widgets)." in section
    assert "- Opened [1 issue](" in section
    assert "in [other/tool](https://github.com/other/tool)." in section


def test_project_table_ranks_merged_then_reviewed_then_stars(data):
    section = render_section(data)
    assert "<summary>All 4 projects, including 3 open pull requests</summary>" in section
    table = [line for line in section.splitlines() if line.startswith("| [")]
    names = [line.split("](")[0][3:] for line in table]
    assert names == ["acme/widgets", "acme/gadgets", "big/platform", "other/tool"]
    merged_link = "https://github.com/acme/widgets/pulls?q=is%3Apr+author%3Ablacksoxx+is%3Amerged"
    assert f"| 4.8k | [2]({merged_link}) | [1](" in table[0]
    assert "| 25.8k | – | – | [2](" in table[2]


def test_empty_data_renders_placeholders():
    data = {
        "user": "x",
        "merged": [],
        "open": [],
        "reviewed": [],
        "issues": [],
        "projects": {},
        "languages": {},
    }
    section = render_section(data)
    assert "_Nothing merged yet._" in section
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
