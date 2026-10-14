import re
import xml.etree.ElementTree as ET

from profile_readme.charts import bar_chart, render_all, short_name, truncate
from profile_readme.palette import INK_ROLES, MODES

SVG = "{http://www.w3.org/2000/svg}"


def test_render_all_produces_both_modes_of_every_chart(data):
    files = render_all(data)
    assert sorted(files) == [
        "oss-languages-dark.svg",
        "oss-languages-light.svg",
        "oss-projects-dark.svg",
        "oss-projects-light.svg",
        "oss-summary-dark.svg",
        "oss-summary-light.svg",
    ]
    for svg in files.values():
        ET.fromstring(svg)


def test_text_wears_ink_tokens_and_marks_wear_the_series_hue(data):
    for name, svg in render_all(data).items():
        mode = "dark" if name.endswith("-dark.svg") else "light"
        tokens = MODES[mode]
        inks = {tokens[role] for role in INK_ROLES}
        root = ET.fromstring(svg)
        for node in root.iter(f"{SVG}text"):
            assert node.get("fill") in inks, (name, node.text)
        marks = [n for n in root.iter(f"{SVG}path")] + [
            n for n in root.iter(f"{SVG}rect") if n.get("rx") is None
        ]
        for mark in marks:
            assert mark.get("fill") == tokens["series"], name


def test_charts_are_deterministic(data):
    assert render_all(data) == render_all(data)


def test_summary_card_lists_the_four_figures(data):
    svg = render_all(data)["oss-summary-light.svg"]
    labels = re.findall(r">([^<]+)</text>", svg)
    assert labels[2:] == [
        "Merged pull requests",
        "3",
        "Reviews",
        "1",
        "Issues opened",
        "1",
        "Projects merged into",
        "2",
    ]


def test_bar_charts_share_a_height_and_rank_by_value(data):
    files = render_all(data)
    projects = ET.fromstring(files["oss-projects-light.svg"])
    languages = ET.fromstring(files["oss-languages-light.svg"])
    assert projects.get("height") == languages.get("height")
    labels = [n.text for n in projects.iter(f"{SVG}text")][1:]
    assert labels == ["widgets", "2", "gadgets", "1"]
    bars = [n.get("d") for n in projects.iter(f"{SVG}path")]
    assert len(bars) == 2
    widths = [float(re.search(r"h([\d.]+)", d).group(1)) for d in bars]
    assert widths[0] > widths[1]


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


def test_short_name_falls_back_to_the_full_name_on_collision():
    repos = ["org-a/tool", "org-b/tool", "org-c/other"]
    assert short_name("org-a/tool", repos) == "org-a/tool"
    assert short_name("org-c/other", repos) == "other"


def test_tiny_values_still_get_a_visible_bar():
    svg = bar_chart("Tiny", [("big", 1000), ("tiny", 1)], "light")
    widths = [float(m) for m in re.findall(r'<rect x="\d+" y="\d+" width="([\d.]+)"', svg)]
    assert widths == [2.0]
