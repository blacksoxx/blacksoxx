from profile_readme.github import collect, language_of


def item(repo, number, *, state="open", merged_at=None, kind="pr", user="blacksoxx"):
    record = {
        "number": number,
        "title": f"{repo} #{number}",
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "repository_url": f"https://api.github.com/repos/{repo}",
        "created_at": f"2026-10-{number:02d}T00:00:00Z",
        "state": state,
        "user": {"login": user},
    }
    if kind == "pr":
        record["pull_request"] = {"merged_at": merged_at}
    return record


def repo(full_name, *, private=False, stars=10):
    owner = full_name.split("/")[0]
    return {
        "full_name": full_name,
        "private": private,
        "owner": {"login": owner},
        "html_url": f"https://github.com/{full_name}",
        "stargazers_count": stars,
        "description": f"{full_name} description",
    }


REPOS = {
    "/repos/acme/widgets": repo("acme/widgets", stars=4825),
    "/repos/secret/vault": repo("secret/vault", private=True),
    "/repos/blacksoxx/mine": repo("blacksoxx/mine"),
}

FILES = [
    {"filename": "pkg/server.go", "additions": 10, "deletions": 2},
    {"filename": "go.sum", "additions": 500, "deletions": 0},
    {"filename": "vendor/x/y.go", "additions": 900, "deletions": 0},
    {"filename": "api/zz_generated.deepcopy.go", "additions": 70, "deletions": 0},
    {"filename": "docs/README.md", "additions": 3, "deletions": 1},
    {"filename": "Dockerfile", "additions": 1, "deletions": 1},
    {"filename": "LICENSE", "additions": 1, "deletions": 0},
]


class FakeClient:
    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        if query.startswith("type:pr author:"):
            return [
                item("Acme/Widgets", 1, state="closed", merged_at="2026-10-02T00:00:00Z"),
                item("acme/widgets", 2),
                item("acme/widgets", 3, state="closed"),
                item("secret/vault", 4, state="closed", merged_at="2026-10-05T00:00:00Z"),
                item("blacksoxx/mine", 5, state="closed", merged_at="2026-10-06T00:00:00Z"),
            ]
        if "reviewed-by:" in query:
            return [item("acme/widgets", 6, user="someone"), item("secret/vault", 7, user="x")]
        return [item("acme/widgets", 8, kind="issue"), item("blacksoxx/mine", 9, kind="issue")]

    def get(self, path, params=None):
        return REPOS[path]

    def pull_files(self, repo, number):
        assert (repo, number) == ("acme/widgets", 1)
        return FILES


def test_collect_keeps_only_public_repositories_owned_by_others():
    client = FakeClient()
    data = collect(client, "blacksoxx")

    assert [(p["repo"], p["number"]) for p in data["merged"]] == [("acme/widgets", 1)]
    assert [(p["repo"], p["number"]) for p in data["open"]] == [("acme/widgets", 2)]
    assert [(p["repo"], p["number"]) for p in data["reviewed"]] == [("acme/widgets", 6)]
    assert [(p["repo"], p["number"]) for p in data["issues"]] == [("acme/widgets", 8)]
    assert list(data["projects"]) == ["acme/widgets"]
    assert data["projects"]["acme/widgets"] == {
        "url": "https://github.com/acme/widgets",
        "description": "acme/widgets description",
        "stars": 4825,
        "merged": 1,
        "open": 1,
        "reviewed": 1,
        "issues": 1,
    }
    assert data["reviewed"][0]["author"] == "someone"
    assert data["merged"][0]["merged_at"] == "2026-10-02T00:00:00Z"


def test_collect_searches_public_scope_only():
    client = FakeClient()
    collect(client, "blacksoxx")
    assert len(client.queries) == 3
    for query in client.queries:
        assert "is:public" in query
        assert "-user:blacksoxx" in query
    assert any("reviewed-by:blacksoxx -author:blacksoxx" in q for q in client.queries)


def test_collect_tallies_languages_without_generated_files():
    data = collect(FakeClient(), "blacksoxx")
    assert data["languages"] == {"Go": 12, "Markdown": 4, "Docker": 2}


def test_language_of():
    assert language_of("cmd/main.go") == "Go"
    assert language_of("modules/vpc/main.tf") == "HCL"
    assert language_of("Dockerfile") == "Docker"
    assert language_of("deploy/Makefile") == "Makefile"
    assert language_of("go.sum") is None
    assert language_of("vendor/github.com/x/y.go") is None
    assert language_of("pkg/api.pb.go") is None
    assert language_of("web/package-lock.json") is None
    assert language_of(".gitignore") is None
    assert language_of("LICENSE") is None
