import re
import xml.etree.ElementTree as ET

from profile_readme.charts import activity_chart, bar_chart, nice_step, render_all, truncate, wrap
from profile_readme.palette import MODES, SERIES_ROLES, TEXT_ROLES

SVG = "{http://www.w3.org/2000/svg}"


def test_render_all_produces_both_modes_of_every_chart(data):
    files = render_all(data)
    assert sorted(files) == sorted(
        [
            f"{name}-{mode}.svg"
            for mode in ("light", "dark")
            for name in ("oss-activity", "oss-languages", "oss-summary", "pr-1", "pr-2", "pr-3")
        ]
    )
    for svg in files.values():
        ET.fromstring(svg)


def test_text_wears_text_tokens_and_marks_wear_series_hues(data):
    for name, svg in render_all(data).items():
        mode = "dark" if name.endswith("-dark.svg") else "light"
        tokens = MODES[mode]
        inks = {tokens[role] for role in TEXT_ROLES}
        hues = {tokens[role] for role in SERIES_ROLES}
        root = ET.fromstring(svg)
        for node in root.iter(f"{SVG}text"):
            assert node.get("fill") in inks, (name, node.text)
        for node in root.iter(f"{SVG}path"):
            assert node.get("fill") in hues, name
        for node in root.iter(f"{SVG}rect"):
            if node.get("rx") is None and node.get("fill") not in (None,):
                assert node.get("fill") in hues, (name, node.attrib)


def test_charts_are_deterministic(data):
    assert render_all(data) == render_all(data)


def test_summary_card_lists_the_figures_and_deltas(data):
    svg = render_all(data)["oss-summary-light.svg"]
    labels = re.findall(r">([^<]+)</text>", svg)
    assert labels[2:] == [
        "Merged pull requests",
        "3",
        "+3 in 30 days",
        "Reviews",
        "1",
        "+1 in 30 days",
        "Issues opened",
        "1",
        "+1 in 30 days",
        "Projects merged into",
        "2",
    ]
    assert svg.count(MODES["light"]["delta_up"]) == 3


def test_pr_card_shows_repo_title_footer_and_avatar(data):
    svg = render_all(data)["pr-1-light.svg"]
    labels = re.findall(r">([^<]+)</text>", svg)
    assert labels == [
        "acme/widgets",
        "fix(api): return &lt;b&gt;typed&lt;/b&gt; errors | not strings",
        "Merged 3 Oct 2026  ·  +41 −7  ·  Go",
    ]
    assert '<image href="data:image/png;base64,iVBOR' in svg
    assert '<title id="title">acme/widgets: fix(api): return &lt;b&gt;typed' in svg
    ET.fromstring(svg)


def test_pr_card_without_avatar_or_language(data):
    svg = render_all(data)["pr-2-light.svg"]
    labels = re.findall(r">([^<]+)</text>", svg)
    assert labels[0] == "acme/gadgets"
    assert labels[-1] == "Merged 30 Sep 2026  ·  +2 −2"
    assert "<image" not in svg
    assert "<circle" in svg


def test_activity_chart_has_legend_gridlines_and_columns():
    svg = activity_chart(
        "Activity",
        [("Merged", [0, 3, 1, 7]), ("Reviews", [2, 0, 0, 4])],
        ["a", "b", "c", "d"],
        "light",
    )
    root = ET.fromstring(svg)
    labels = [n.text for n in root.iter(f"{SVG}text")]
    assert labels[:3] == ["Activity", "Merged", "Reviews"]
    assert "0" in labels and "8" in labels
    columns = [n for n in root.iter(f"{SVG}path")]
    assert len(columns) == 5
    fills = {n.get("fill") for n in columns}
    assert fills == {MODES["light"]["series"], MODES["light"]["series_2"]}
    assert labels[-2:] == ["a", "d"]


def test_bar_charts_share_the_activity_height(data):
    files = render_all(data)
    languages = ET.fromstring(files["oss-languages-light.svg"])
    activity = ET.fromstring(files["oss-activity-light.svg"])
    assert languages.get("height") == activity.get("height") == "210"


def test_empty_bar_chart_says_so():
    svg = bar_chart("Nothing", [], "light")
    assert "No data yet" in svg
    assert "<path" not in svg
    ET.fromstring(svg)


def test_labels_are_truncated_not_clipped():
    svg = bar_chart("Long", [("a" * 40, 1)], "light", label_chars=10)
    assert "aaaaaaaaa…" in svg
    assert "a" * 11 not in svg
    assert truncate("short", 10) == "short"


def test_tiny_values_still_get_a_visible_bar():
    svg = bar_chart("Tiny", [("big", 1000), ("tiny", 1)], "light")
    widths = [float(m) for m in re.findall(r'<rect x="\d+" y="\d+" width="([\d.]+)"', svg)]
    assert widths == [2.0]


def test_wrap_and_nice_step():
    assert wrap("one two three four", 9, 2) == ["one two", "three fo…"]
    assert wrap("short title", 50, 2) == ["short title"]
    assert wrap("a" * 60, 50, 2) == ["a" * 49 + "…"]
    assert wrap("fix: a b c d e f g h", 7, 2) == ["fix: a", "b c d…"]
    assert [nice_step(n) for n in (0, 4, 5, 6, 10, 11, 25, 26, 51)] == [1, 1, 1, 2, 2, 5, 5, 10, 20]
