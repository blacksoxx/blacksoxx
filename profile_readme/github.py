"""Read-only GitHub collectors.

Only public repositories owned by someone else are ever recorded. The search
queries carry `is:public` and `-user:<login>`, and every repository is then
re-checked through the repos API before anything from it is kept.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

API = "https://api.github.com"
SEARCH_PAGE = 100
SEARCH_PAGES = 10
FILES_PAGES = 3
REVIEW_PAGES = 2
RETRIES = 4
AVATAR_WALL = 64
AVATAR_CARD = 40

LANGUAGES = {
    ".go": "Go",
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".tf": "HCL",
    ".hcl": "HCL",
    ".tfvars": "HCL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".proto": "Protobuf",
    ".sql": "SQL",
    ".ps1": "PowerShell",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
}
FILENAMES = {"Dockerfile": "Docker", "Containerfile": "Docker", "Makefile": "Makefile"}
GENERATED_FILES = {
    "go.sum",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "uv.lock",
}
GENERATED_MARKERS = (
    "/vendor/",
    "/node_modules/",
    "zz_generated",
    ".pb.go",
    ".pb.gw.go",
    "_generated.",
    ".gen.go",
    ".min.js",
    ".min.css",
)


def language_of(path: str) -> str | None:
    """Map a changed file to a language, or None for generated and unknown files."""
    name = path.rsplit("/", 1)[-1]
    if name in GENERATED_FILES or any(marker in f"/{path}" for marker in GENERATED_MARKERS):
        return None
    if name in FILENAMES:
        return FILENAMES[name]
    dot = name.rfind(".")
    if dot <= 0:
        return None
    return LANGUAGES.get(name[dot:].lower())


class Client:
    def __init__(self, token: str | None = None, user_agent: str = "profile-readme") -> None:
        self.token = token
        self.user_agent = user_agent

    def get(self, path: str, params: dict | None = None):
        url = path if path.startswith("http") else f"{API}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", self.user_agent)
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        for attempt in range(RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and attempt < RETRIES - 1:
                    time.sleep(_backoff(exc.headers, attempt))
                    continue
                raise
        raise RuntimeError("unreachable")

    def search(self, query: str) -> list[dict]:
        items: list[dict] = []
        for page in range(1, SEARCH_PAGES + 1):
            params = {
                "q": query,
                "per_page": SEARCH_PAGE,
                "page": page,
                "advanced_search": "true",
            }
            batch = self.get("/search/issues", params).get("items", [])
            items.extend(batch)
            if len(batch) < SEARCH_PAGE:
                break
        return items

    def pull_files(self, repo: str, number: int) -> list[dict]:
        return self._pages(f"/repos/{repo}/pulls/{number}/files", FILES_PAGES)

    def pull_reviews(self, repo: str, number: int) -> list[dict]:
        return self._pages(f"/repos/{repo}/pulls/{number}/reviews", REVIEW_PAGES)

    def _pages(self, path: str, limit: int) -> list[dict]:
        items: list[dict] = []
        for page in range(1, limit + 1):
            batch = self.get(path, {"per_page": 100, "page": page})
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def get_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url)
        request.add_header("User-Agent", self.user_agent)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()


def _backoff(headers, attempt: int) -> float:
    retry_after = headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        return min(int(retry_after), 120)
    if headers.get("X-RateLimit-Remaining") == "0":
        reset = headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            return max(0, min(int(reset) - time.time() + 1, 300))
    return 5.0 * 2**attempt


def sized(avatar_url: str, pixels: int) -> str:
    joiner = "&" if "?" in avatar_url else "?"
    return f"{avatar_url}{joiner}s={pixels}"


def _first_review(client: Client, repo: str, number: int, login: str) -> str | None:
    stamps = [
        review["submitted_at"]
        for review in client.pull_reviews(repo, number)
        if (review.get("user") or {}).get("login", "").lower() == login
        and review.get("submitted_at")
    ]
    return min(stamps) if stamps else None


def _avatar(client: Client, url: str, cache: dict[str, str | None]) -> str | None:
    if url not in cache:
        try:
            cache[url] = base64.b64encode(client.get_bytes(url)).decode("ascii")
        except (urllib.error.URLError, OSError):
            cache[url] = None
    return cache[url]


def _record(repo: str, item: dict) -> dict:
    return {
        "repo": repo,
        "number": item["number"],
        "title": item["title"],
        "url": item["html_url"],
        "created_at": item["created_at"],
    }


def collect(
    client: Client, user: str, now: datetime | None = None, exclude: tuple[str, ...] = ()
) -> dict:
    """Gather merged and open pull requests, reviews, issues and a language tally.

    `exclude` lists repository owners to leave out even though they are public,
    such as an employer's organisation.
    """
    login = user.lower()
    excluded = {owner.lower() for owner in exclude}
    scope = f"is:public -user:{user}"
    authored = client.search(f"type:pr author:{user} {scope}")
    reviewed = client.search(f"type:pr reviewed-by:{user} -author:{user} {scope}")
    issues = client.search(f"type:issue author:{user} {scope}")

    metadata: dict[str, dict] = {}

    def public_repo(item: dict) -> str | None:
        key = "/".join(item["repository_url"].split("/")[-2:]).lower()
        if key not in metadata:
            metadata[key] = client.get(f"/repos/{key}")
        meta = metadata[key]
        owner = meta.get("owner", {}).get("login", "").lower()
        if meta.get("private") or owner == login or owner in excluded:
            return None
        return meta["full_name"]

    merged: list[dict] = []
    open_prs: list[dict] = []
    for item in authored:
        repo = public_repo(item)
        if not repo:
            continue
        merged_at = (item.get("pull_request") or {}).get("merged_at")
        if merged_at:
            merged.append(_record(repo, item) | {"merged_at": merged_at})
        elif item.get("state") == "open":
            open_prs.append(_record(repo, item))

    reviews: list[dict] = []
    for item in reviewed:
        repo = public_repo(item)
        if not repo:
            continue
        record = _record(repo, item) | {"author": item["user"]["login"]}
        record["reviewed_at"] = (
            _first_review(client, repo, item["number"], login)
            or item.get("updated_at")
            or item["created_at"]
        )
        reviews.append(record)

    issue_records: list[dict] = []
    for item in issues:
        repo = public_repo(item)
        if repo:
            issue_records.append(_record(repo, item) | {"state": item["state"]})

    merged.sort(key=lambda p: p["merged_at"], reverse=True)
    reviews.sort(key=lambda r: r["reviewed_at"], reverse=True)
    for records in (open_prs, issue_records):
        records.sort(key=lambda r: r["created_at"], reverse=True)

    projects: dict[str, dict] = {}
    for kind, records in (
        ("merged", merged),
        ("open", open_prs),
        ("reviewed", reviews),
        ("issues", issue_records),
    ):
        for record in records:
            meta = metadata[record["repo"].lower()]
            project = projects.setdefault(
                record["repo"],
                {
                    "url": meta["html_url"],
                    "description": meta.get("description") or "",
                    "stars": meta.get("stargazers_count", 0),
                    "avatar_url": sized(meta["owner"]["avatar_url"], AVATAR_WALL),
                    "avatar": None,
                    "merged": 0,
                    "open": 0,
                    "reviewed": 0,
                    "issues": 0,
                },
            )
            project[kind] += 1

    languages: dict[str, int] = {}
    for pr in merged:
        per_language: dict[str, int] = {}
        additions = deletions = 0
        for changed in client.pull_files(pr["repo"], pr["number"]):
            additions += changed.get("additions", 0)
            deletions += changed.get("deletions", 0)
            language = language_of(changed["filename"])
            if language:
                lines = changed.get("additions", 0) + changed.get("deletions", 0)
                per_language[language] = per_language.get(language, 0) + lines
        pr["additions"] = additions
        pr["deletions"] = deletions
        pr["language"] = max(per_language, key=per_language.get) if per_language else None
        for language, lines in per_language.items():
            languages[language] = languages.get(language, 0) + lines

    avatars: dict[str, str | None] = {}
    for name, project in projects.items():
        if project["merged"]:
            owner_avatar = metadata[name.lower()]["owner"]["avatar_url"]
            project["avatar"] = _avatar(client, sized(owner_avatar, AVATAR_CARD), avatars)

    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "user": user,
        "generated_at": stamp,
        "merged": merged,
        "open": open_prs,
        "reviewed": reviews,
        "issues": issue_records,
        "projects": projects,
        "languages": languages,
    }


def default_user() -> str:
    return os.environ.get("GH_USER") or "blacksoxx"


def default_exclude() -> tuple[str, ...]:
    raw = os.environ.get("GH_EXCLUDE_OWNERS", "")
    return tuple(owner.strip() for owner in raw.split(",") if owner.strip())
