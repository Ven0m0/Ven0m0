#!/usr/bin/env python3
"""GitHub stats collector using GraphQL & REST APIs."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import aiohttp


@dataclass(slots=True)
class Queries:
    username: str
    access_token: str
    session: aiohttp.ClientSession
    max_concurrent: int = 10
    semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

    async def query(self, generated_query: str, retries: int = 3) -> dict:
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
            # Sleep outside the semaphore context to avoid blocking other requests
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
        return {}

    async def query_rest(
        self,
        path: str,
        params: dict | None = None,
        max_attempts: int = 60,
    ) -> dict:
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
            # Sleep outside the semaphore context to avoid blocking other requests
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
        owned_cursor_json = json.dumps(owned_cursor)
        contrib_cursor_json = json.dumps(contrib_cursor)
        return f"""{{
  viewer {{
    login name
    repositories(first: 100, orderBy: {{field: UPDATED_AT, direction: DESC}}, \
isFork: false, after: {owned_cursor_json}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        nameWithOwner
        stargazers {{ totalCount }}
        forkCount
        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
          edges {{ size node {{ name color }} }}
        }}
      }}
    }}
    repositoriesContributedTo(first: 100, includeUserRepositories: false, \
orderBy: {{field: UPDATED_AT, direction: DESC}}, \
contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY, PULL_REQUEST_REVIEW], \
after: {contrib_cursor_json}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        nameWithOwner
        stargazers {{ totalCount }}
        forkCount
        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
          edges {{ size node {{ name color }} }}
        }}
      }}
    }}
  }}
}}"""

    @staticmethod
    def contrib_years() -> str:
        return (
            "query { viewer { contributionsCollection "
            "{ contributionYears } } }"
        )

    @staticmethod
    def contribs_by_year(year: str) -> str:
        next_year = int(year) + 1
        return (
            f'year{year}: contributionsCollection('
            f'from: "{year}-01-01T00:00:00Z", '
            f'to: "{next_year}-01-01T00:00:00Z") '
            f"{{ contributionCalendar {{ totalContributions }} }}"
        )

    @classmethod
    def all_contribs(cls, years: list[str]) -> str:
        by_years = "\n".join(map(cls.contribs_by_year, years))
        return f"query {{ viewer {{ {by_years} }} }}"


@dataclass(slots=True)
class Stats:
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
    _views: int | None = field(default=None, init=False)
    _ignored_repos: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.queries = Queries(self.username, self.access_token, self.session)

    async def get_stats(self) -> None:
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
                    if name not in self._ignored_repos:
                        if name not in self.exclude_repos:
                            self._ignored_repos.add(name)
            for repo in repos:
                name = repo.get("nameWithOwner")
                if name in self._repos or name in self.exclude_repos:
                    continue
                self._repos.add(name)
                self._stargazers += repo.get("stargazers", {}).get("totalCount", 0)
                self._forks += repo.get("forkCount", 0)
                for lang in repo.get("languages", {}).get("edges", []):
                    lname = lang.get("node", {}).get("name", "Other")
                    if lname in self.exclude_langs:
                        continue
                    if lname in self._languages:
                        self._languages[lname]["size"] += lang.get("size", 0)
                        self._languages[lname]["occurrences"] += 1
                    else:
                        self._languages[lname] = {
                            "size": lang.get("size", 0),
                            "occurrences": 1,
                            "color": lang.get("node", {}).get("color"),
                        }
            owned_has_next = owned_repos.get("pageInfo", {}).get("hasNextPage")
            contrib_has_next = contrib_repos.get("pageInfo", {}).get("hasNextPage")
            if owned_has_next or contrib_has_next:
                next_owned = owned_repos.get("pageInfo", {}).get(
                    "endCursor", next_owned,
                )
                next_contrib = contrib_repos.get("pageInfo", {}).get(
                    "endCursor", next_contrib,
                )
            else:
                break
        langs_total = sum(v.get("size", 0) for v in self._languages.values())
        for v in self._languages.values():
            v["prop"] = (100 * v.get("size", 0) / langs_total) if langs_total else 0

    @property
    async def name(self) -> str:
        if self._name is None:
            await self.get_stats()
        if not self._name:
            msg = "Unable to fetch GitHub username. API authentication may have failed."
            raise RuntimeError(msg)
        return self._name

    @property
    async def stargazers(self) -> int:
        if self._stargazers is None:
            await self.get_stats()
        return self._stargazers or 0

    @property
    async def forks(self) -> int:
        if self._forks is None:
            await self.get_stats()
        return self._forks or 0

    @property
    async def languages(self) -> dict:
        if self._languages is None:
            await self.get_stats()
        return self._languages or {}

    @property
    async def all_repos(self) -> set[str]:
        if self._repos is None:
            await self.get_stats()
        return (self._repos or set()) | (self._ignored_repos or set())

    @property
    async def total_contributions(self) -> int:
        if self._total_contributions is not None:
            return self._total_contributions
        total = 0
        years_query = await self.queries.query(self.queries.contrib_years())
        years = (
            years_query.get("data", {})
            .get("viewer", {})
            .get("contributionsCollection", {})
            .get("contributionYears", [])
        )
        if years:
            contribs_query = await self.queries.query(
                self.queries.all_contribs(years),
            )
            by_year = contribs_query.get("data", {}).get("viewer", {}).values()
            for year in by_year:
                if isinstance(year, dict):
                    total += (
                        year.get("contributionCalendar", {})
                        .get("totalContributions", 0)
                    )
        self._total_contributions = total
        return self._total_contributions

    @property
    async def lines_changed(self) -> tuple[int, int]:
        if self._lines_changed is not None:
            return self._lines_changed
        additions = deletions = 0
        repos = await self.all_repos
        tasks = [
            self.queries.query_rest(f"/repos/{repo}/stats/contributors")
            for repo in repos
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) or not isinstance(r, list):
                continue
            for author_obj in r:
                if not isinstance(author_obj, dict):
                    continue
                author = author_obj.get("author", {})
                if not isinstance(author, dict):
                    continue
                if author.get("login") != self.username:
                    continue
                for week in author_obj.get("weeks", []):
                    additions += week.get("a", 0)
                    deletions += week.get("d", 0)
        self._lines_changed = (additions, deletions)
        return self._lines_changed

    @property
    async def views(self) -> int:
        if self._views is not None:
            return self._views
        repos = {r for r in await self.all_repos if r not in self._ignored_repos}
        tasks = [
            self.queries.query_rest(f"/repos/{repo}/traffic/views")
            for repo in repos
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total = 0
        for r in results:
            if isinstance(r, Exception) or not isinstance(r, dict):
                continue
            for view in r.get("views", []):
                total += view.get("count", 0)
        self._views = total
        return total
