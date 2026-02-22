#!/usr/bin/env python3
"""Generate SVG stats images for GitHub profile.

This script collects GitHub statistics using GraphQL and REST APIs,
then generates SVG images for display on a GitHub profile README.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp


def sanitize_text(text: str, secrets: list[str]) -> str:
    """Sanitize sensitive information from text."""
    if not text:
        return text
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[REDACTED]")
    return text


@dataclass(slots=True)
class Queries:
    """Handles GraphQL and REST API queries to GitHub."""

    username: str
    access_token: str
    session: aiohttp.ClientSession
    max_concurrent: int = 10
    semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

    async def query(self, generated_query: str, retries: int = 3) -> dict:
        """Execute a GraphQL query against GitHub API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        for attempt in range(retries):
            async with self.semaphore:
                try:
                    r = await self.session.post(
                        "https://api.github.com/graphql",
                        headers=headers,
                        json={"query": generated_query},
                        timeout=aiohttp.ClientTimeout(total=30),
                    )
                    r.raise_for_status()
                    result = await r.json()
                    if "errors" in result:
                        errors = result.get("errors", [])
                        error_msg = "; ".join(
                            e.get("message", "Unknown error") for e in errors
                        )
                        print(f"GraphQL query returned errors: {error_msg}")
                        if attempt == retries - 1:
                            raise RuntimeError(f"GraphQL API errors: {error_msg}")
                        continue
                    return result
                except aiohttp.ClientError as e:
                    if attempt == retries - 1:
                        msg = f"GraphQL query failed after {retries} attempts: {e}"
                        raise RuntimeError(msg)
                    print(f"GraphQL attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
        return {}

    async def query_rest(
        self,
        path: str,
        params: dict | None = None,
        max_attempts: int = 60,
    ) -> dict:
        """Execute a REST API query against GitHub API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = params or {}
        path = path.lstrip("/")
        for attempt in range(max_attempts):
            should_retry = False
            sleep_duration = 0
            async with self.semaphore:
                try:
                    r = await self.session.get(
                        f"https://api.github.com/{path}",
                        headers=headers,
                        params=tuple(params.items()),
                        timeout=aiohttp.ClientTimeout(total=30),
                    )
                    if r.status == 200:
                        return await r.json()
                    if r.status == 404:
                        return {}
                    if r.status in (401, 403):
                        error_body = await r.text()
                        msg = (
                            f"Authentication failed for {path} "
                            f"(status {r.status}): {error_body}"
                        )
                        raise RuntimeError(msg)
                    if r.status == 202:
                        should_retry = True
                        sleep_duration = min(2 ** min(attempt // 10, 3), 8)
                    elif attempt < max_attempts - 1:
                        should_retry = True
                        sleep_duration = min(2 ** min(attempt // 5, 3), 8)
                    else:
                        error_body = await r.text()
                        msg = (
                            f"REST API request failed for {path} "
                            f"with status {r.status}: {error_body}"
                        )
                        raise RuntimeError(msg)
                except aiohttp.ClientError as e:
                    if attempt == max_attempts - 1:
                        msg = (
                            f"REST query failed for {path} "
                            f"after {max_attempts} attempts: {e}"
                        )
                        raise RuntimeError(msg)
                    should_retry = True
                    sleep_duration = min(2 ** min(attempt // 5, 3), 8)
            if should_retry:
                await asyncio.sleep(sleep_duration)
            else:
                return {}
        return {}

    @staticmethod
    def repos_overview(
        contrib_cursor: str | None = None,
        owned_cursor: str | None = None,
    ) -> str:
        """Generate GraphQL query for repositories overview."""
        return f"""
        query {{
            viewer {{
                login
                name
                repositories(first: 100, privacy: PUBLIC, isFork: false, ownerAffiliations: OWNER, orderBy: {{field: STARGAZERS, direction: DESC}}{f', after: "{owned_cursor}"' if owned_cursor else ''}) {{
                    nodes {{
                        name
                        nameWithOwner
                        stargazerCount
                        forkCount
                        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                            edges {{
                                size
                                node {{
                                    name
                                    color
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
                repositoriesContributedTo(first: 100, privacy: PUBLIC, includeUserRepositories: true, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY], orderBy: {{field: STARGAZERS, direction: DESC}}{f', after: "{contrib_cursor}"' if contrib_cursor else ''}) {{
                    nodes {{
                        name
                        nameWithOwner
                        stargazerCount
                        forkCount
                        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                            edges {{
                                size
                                node {{
                                    name
                                    color
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
        }}
        """


@dataclass(slots=True)
class Stats:
    """Collects and caches GitHub statistics for a user."""

    username: str
    access_token: str
    session: aiohttp.ClientSession
    exclude_repos: set[str] = field(default_factory=set)
    exclude_langs: set[str] = field(default_factory=set)
    consider_forked_repos: bool = False
    queries: Queries = field(init=False)
    _name: str | None = field(default=None, init=False)
    _stargazers: int | None = field(default=None, init=False)
    _forks: int | None = field(default=None, init=False)
    _total_contributions: int | None = field(default=None, init=False)
    _languages: dict[str, dict] | None = field(default=None, init=False)
    _repos: set[str] | None = field(default=None, init=False)
    _lines_changed: tuple[int, int] | None = field(default=None, init=False)
    _ignored_repos: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.queries = Queries(self.username, self.access_token, self.session)

    async def get_stats(self) -> None:
        """Fetch all repository statistics from GitHub."""
        self._stargazers = 0
        self._forks = 0
        self._languages = {}
        self._repos = set()
        self._ignored_repos = set()
        next_owned = None
        next_contrib = None
        first_iteration = True
        while True:
            query = self.queries.repos_overview(next_contrib, next_owned)
            raw = await self.queries.query(query)
            raw = raw or {}
            if not raw.get("data"):
                raise RuntimeError(
                    "GitHub API returned no data. "
                    "Check if ACCESS_TOKEN has required permissions (repo, read:user)",
                )
            viewer = raw.get("data", {}).get("viewer", {})
            if not viewer:
                msg = "GitHub API returned no viewer data. Token may be invalid."
                raise RuntimeError(msg)
            if first_iteration:
                self._name = viewer.get("name") or viewer.get("login")
                if not self._name:
                    msg = (
                        "Could not retrieve username from GitHub API. "
                        "Token may be invalid."
                    )
                    raise RuntimeError(msg)
                print(f"Fetching stats for: {self._name}")
                first_iteration = False
            contrib_repos = viewer.get("repositoriesContributedTo", {})
            owned_repos = viewer.get("repositories", {})
            repos = owned_repos.get("nodes", [])
            if self.consider_forked_repos:
                repos += contrib_repos.get("nodes", [])
            else:
                for repo in contrib_repos.get("nodes", []):
                    name = repo.get("nameWithOwner")
                    if name not in self._repos:
                        repos.append(repo)

            for repo in repos:
                name = repo.get("nameWithOwner")
                if name in self._repos or name in self.exclude_repos:
                    continue
                self._repos.add(name)
                self._stargazers += repo.get("stargazerCount", 0)
                self._forks += repo.get("forkCount", 0)

                # Process languages
                langs = repo.get("languages", {}).get("edges", [])
                for lang in langs:
                    node = lang.get("node", {})
                    lang_name = node.get("name")
                    if lang_name in self.exclude_langs:
                        continue
                    if lang_name not in self._languages:
                        self._languages[lang_name] = {
                            "size": 0,
                            "color": node.get("color"),
                        }
                    self._languages[lang_name]["size"] += lang.get("size", 0)

            # Pagination
            has_next_owned = owned_repos.get("pageInfo", {}).get("hasNextPage")
            has_next_contrib = contrib_repos.get("pageInfo", {}).get("hasNextPage")
            next_owned = owned_repos.get("pageInfo", {}).get("endCursor")
            next_contrib = contrib_repos.get("pageInfo", {}).get("endCursor")

            if not has_next_owned and not has_next_contrib:
                break

    @property
    async def name(self) -> str:
        """Get user's name or login."""
        if self._name is None:
            await self.get_stats()
        return self._name

    @property
    async def stargazers(self) -> int:
        """Get total stargazers count."""
        if self._stargazers is None:
            await self.get_stats()
        return self._stargazers

    @property
    async def forks(self) -> int:
        """Get total forks count."""
        if self._forks is None:
            await self.get_stats()
        return self._forks

    @property
    async def languages(self) -> dict[str, dict]:
        """Get languages statistics."""
        if self._languages is None:
            await self.get_stats()
        return self._languages


def _write_svg(title: str, lines: list[str], output_path: Path) -> None:
    """Write a very simple SVG file with the given title and text lines."""
    # Basic layout: one line per row, simple vertical spacing.
    width = 500
    line_height = 20
    height = max(60, 40 + line_height * len(lines))

    escaped_title = html.escape(title)
    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'  <title>{escaped_title}</title>',
        '  <style>',
        '    text {',
        '      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";',
        '      font-size: 14px;',
        '      fill: #24292e;',
        '    }',
        '  </style>',
        f'  <text x="20" y="30" font-size="16" font-weight="bold">{escaped_title}</text>',
    ]

    y = 55
    for line in lines:
        if not line:
            y += line_height
            continue
        svg_lines.append(f'  <text x="20" y="{y}">{html.escape(str(line))}</text>')
        y += line_height

    svg_lines.append('</svg>')
    output_path.write_text("\n".join(svg_lines), encoding="utf-8")


async def generate_overview(stats: Stats, output_dir: Path) -> None:
    """Generate overview SVG."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Retrieve core stats. These are defined as async properties on the Stats class.
    followers = await stats.followers
    contributions = await stats.contributions
    stargazers = await stats.stargazers
    forks = await stats.forks

    lines: list[str] = [
        f"Followers: {followers}",
        f"Contributions (last year): {contributions}",
        f"Stars: {stargazers}",
        f"Forks: {forks}",
    ]

    overview_path = output_dir / "overview.svg"
    _write_svg("GitHub Overview", lines, overview_path)


async def generate_languages(stats: Stats, output_dir: Path) -> None:
    """Generate languages SVG."""
    output_dir.mkdir(parents=True, exist_ok=True)

    languages_stats = await stats.languages

    # languages_stats is expected to be a dict like {language: { ... }}.
    # We try to sort by a "size" field when available, otherwise keep insertion order.
    items = list(languages_stats.items()) if isinstance(languages_stats, dict) else []

    def _sort_key(item: tuple[str, object]) -> int:
        lang_data = item[1]
        if isinstance(lang_data, dict):
            size = lang_data.get("size") or lang_data.get("bytes") or 0
            try:
                return int(size)
            except (TypeError, ValueError):
                return 0
        return 0

    items.sort(key=_sort_key, reverse=True)

    lines: list[str] = []
    for name, data in items[:10]:
        display = str(name)
        if isinstance(data, dict):
            size = data.get("size") or data.get("bytes")
            if size is not None:
                display = f"{name}: {size}"
        lines.append(display)

    if not lines:
        lines.append("No language data available.")

    languages_path = output_dir / "languages.svg"
    _write_svg("Top Languages", lines, languages_path)


async def generate_combined(stats: Stats, output_dir: Path) -> None:
    """Generate combined stats SVG."""
    output_dir.mkdir(parents=True, exist_ok=True)

    followers = await stats.followers
    contributions = await stats.contributions
    stargazers = await stats.stargazers
    forks = await stats.forks
    languages_stats = await stats.languages

    items = list(languages_stats.items()) if isinstance(languages_stats, dict) else []

    def _sort_key(item: tuple[str, object]) -> int:
        lang_data = item[1]
        if isinstance(lang_data, dict):
            size = lang_data.get("size") or lang_data.get("bytes") or 0
            try:
                return int(size)
            except (TypeError, ValueError):
                return 0
        return 0

    items.sort(key=_sort_key, reverse=True)
    top_langs = [str(name) for name, _ in items[:5]]

    lines: list[str] = [
        f"Followers: {followers}",
        f"Contributions (last year): {contributions}",
        f"Stars: {stargazers}",
        f"Forks: {forks}",
    ]

    if top_langs:
        lines.append("")
        lines.append("Top languages:")
        for lang in top_langs:
            lines.append(f"- {lang}")

    combined_path = output_dir / "combined.svg"
    _write_svg("GitHub Stats", lines, combined_path)
# ... (rest of the file)
