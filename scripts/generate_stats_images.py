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

# =============================================================================
# GitHub API Client Classes
# =============================================================================


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
        """Generate GraphQL query for repository overview."""
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
        """Generate GraphQL query for contribution years."""
        return (
            "query { viewer { contributionsCollection "
            "{ contributionYears } } }"
        )

    @staticmethod
    def contribs_by_year(year: str) -> str:
        """Generate GraphQL query fragment for contributions in a year."""
        next_year = int(year) + 1
        return (
            f'year{year}: contributionsCollection('
            f'from: "{year}-01-01T00:00:00Z", '
            f'to: "{next_year}-01-01T00:00:00Z") '
            f"{{ contributionCalendar {{ totalContributions }} }}"
        )

    @classmethod
    def all_contribs(cls, years: list[str]) -> str:
        """Generate GraphQL query for all contribution years."""
        by_years = "\n".join(map(cls.contribs_by_year, years))
        return f"query {{ viewer {{ {by_years} }} }}"


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
    _views: int | None = field(default=None, init=False)
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
                    "endCursor",
                    next_owned,
                )
                next_contrib = contrib_repos.get("pageInfo", {}).get(
                    "endCursor",
                    next_contrib,
                )
            else:
                break
        langs_total = sum(v.get("size", 0) for v in self._languages.values())
        for v in self._languages.values():
            v["prop"] = (100 * v.get("size", 0) / langs_total) if langs_total else 0

    @property
    async def name(self) -> str:
        """Get user's display name."""
        if self._name is None:
            await self.get_stats()
        if not self._name:
            msg = "Unable to fetch GitHub username. API authentication may have failed."
            raise RuntimeError(msg)
        return self._name

    @property
    async def stargazers(self) -> int:
        """Get total stargazers across all repositories."""
        if self._stargazers is None:
            await self.get_stats()
        return self._stargazers or 0

    @property
    async def forks(self) -> int:
        """Get total forks across all repositories."""
        if self._forks is None:
            await self.get_stats()
        return self._forks or 0

    @property
    async def languages(self) -> dict:
        """Get language statistics."""
        if self._languages is None:
            await self.get_stats()
        return self._languages or {}

    @property
    async def all_repos(self) -> set[str]:
        """Get all repository names."""
        if self._repos is None:
            await self.get_stats()
        return (self._repos or set()) | (self._ignored_repos or set())

    @property
    async def total_contributions(self) -> int:
        """Get total contributions across all years."""
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
                        year.get("contributionCalendar", {}).get("totalContributions", 0)
                    )
        self._total_contributions = total
        return self._total_contributions

    @property
    async def lines_changed(self) -> tuple[int, int]:
        """Get total lines added and deleted."""
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
        """Get total repository views."""
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


# =============================================================================
# SVG Templates
# =============================================================================

TEMPLATE_OVERVIEW = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" '
    'viewBox="0 0 495 195">\n'
    "  <defs>\n"
    "    <style>\n"
    "      .header{font: 600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#ba68c8}\n"
    "      .stat{font:400 14px 'Segoe UI',Ubuntu,sans-serif;fill:#f8bbd0}\n"
    "      .label{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:#b39ddb}\n"
    "      .value{font:600 16px 'Segoe UI',Ubuntu,sans-serif;fill:#fff}\n"
    "    </style>\n"
    "  </defs>\n"
    '  <rect width="495" height="195" fill="#0d1117" rx="6"/>\n'
    '  <text x="20" y="35" class="header">{{ name }}\'s GitHub Stats</text>\n'
    '  <g transform="translate(20, 60)">\n'
    '    <text y="20" class="label">Total Stars Earned</text>\n'
    '    <text y="20" x="200" class="value">{{ stars }}</text>\n'
    "  </g>\n"
    '  <g transform="translate(20, 90)">\n'
    '    <text y="20" class="label">Total Commits</text>\n'
    '    <text y="20" x="200" class="value">{{ contributions }}</text>\n'
    "  </g>\n"
    '  <g transform="translate(20, 120)">\n'
    '    <text y="20" class="label">Total Repositories</text>\n'
    '    <text y="20" x="200" class="value">{{ repos }}</text>\n'
    "  </g>\n"
    '  <g transform="translate(20, 150)">\n'
    '    <text y="20" class="label">Lines Changed</text>\n'
    '    <text y="20" x="200" class="value">{{ lines_changed }}</text>\n'
    "  </g>\n"
    "</svg>"
)

TEMPLATE_LANGUAGES = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="285" '
    'viewBox="0 0 495 285">\n'
    "  <defs>\n"
    "    <style>\n"
    "      .header{font:600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#ba68c8}\n"
    "      .lang{font:400 14px 'Segoe UI',Ubuntu,sans-serif;fill:#fff}\n"
    "      .percent{font:600 14px 'Segoe UI',Ubuntu,sans-serif;fill:#b39ddb}\n"
    "      .progress-item{height:8px;display:inline-block}\n"
    "      li{list-style:none;margin:8px 0;display:flex;align-items:center;"
    "animation:slideIn 0.3s ease-in-out forwards;opacity:0}\n"
    "      @keyframes slideIn{to{opacity:1}}\n"
    "    </style>\n"
    "  </defs>\n"
    '  <rect width="495" height="285" fill="#0d1117" rx="6"/>\n'
    '  <text x="20" y="35" class="header">Most Used Languages</text>\n'
    '  <foreignObject x="20" y="50" width="455" height="10">\n'
    '    <div xmlns="http://www.w3.org/1999/xhtml" style="display:flex;'
    'width:100%;height:8px;border-radius:4px;overflow:hidden">'
    "{{ progress }}</div>\n"
    "  </foreignObject>\n"
    '  <foreignObject x="20" y="70" width="455" height="200">\n'
    '    <ul xmlns="http://www.w3.org/1999/xhtml" style="padding:0;margin:0">'
    "{{ lang_list }}</ul>\n"
    "  </foreignObject>\n"
    "</svg>"
)


# =============================================================================
# SVG Generation Functions
# =============================================================================


async def generate_overview(s: Stats, output_dir: Path) -> None:
    """Generate the overview statistics SVG."""
    print("Fetching overview stats...")
    output = TEMPLATE_OVERVIEW
    name = await s.name
    output = output.replace("{{ name }}", html.escape(name))
    stars = await s.stargazers
    output = output.replace("{{ stars }}", f"{stars:,}")
    contributions = await s.total_contributions
    output = output.replace("{{ contributions }}", f"{contributions:,}")
    repos = await s.all_repos
    output = output.replace("{{ repos }}", f"{len(repos):,}")
    lines = await s.lines_changed
    changed = sum(lines)
    output = output.replace("{{ lines_changed }}", f"{changed:,}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "overview.svg"
    output_file.write_text(output, encoding="utf-8")
    print(
        f"✓ Generated {output_file} "
        f"({stars:,} stars, {contributions:,} contributions)",
    )


async def generate_languages(s: Stats, output_dir: Path) -> None:
    """Generate the languages statistics SVG."""
    print("Fetching language stats...")
    output = TEMPLATE_LANGUAGES
    progress_parts: list[str] = []
    lang_list_parts: list[str] = []
    languages = await s.languages
    sorted_langs = sorted(
        languages.items(),
        reverse=True,
        key=lambda t: t[1].get("size", 0),
    )
    print(f"Found {len(sorted_langs)} languages")
    if not sorted_langs:
        print(
            "Warning: No languages found. "
            "This may indicate an issue with repository access.",
        )
    for i, (lang, data) in enumerate(sorted_langs):
        color = data.get("color") or "#888888"
        prop = data.get("prop", 0)
        ratio = [0.99, 0.01] if prop > 50 else [0.98, 0.02]
        if i == len(sorted_langs) - 1:
            ratio = [1, 0]
        progress_parts.append(
            f'<span style="background-color:{color};'
            f"width:{ratio[0] * prop:.3f}%;"
            f'margin-right:{ratio[1] * prop:.3f}%" '
            f'class="progress-item"></span>',
        )
        lang_list_parts.append(
            f'<li style="animation-delay:{i * 150}ms">'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'style="fill:{color};margin-right:8px" '
            f'viewBox="0 0 16 16" width="16" height="16">'
            f'<circle cx="8" cy="8" r="4"/></svg>'
            f'<span class="lang">{html.escape(lang)}</span>'
            f'<span class="percent" style="margin-left:auto">'
            f"{prop:.2f}%</span></li>",
        )
    output = output.replace("{{ progress }}", "".join(progress_parts))
    output = output.replace("{{ lang_list }}", "".join(lang_list_parts))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "languages.svg"
    output_file.write_text(output, encoding="utf-8")
    top_lang = sorted_langs[0][0] if sorted_langs else "none"
    print(f"✓ Generated {output_file} (top: {top_lang})")


# =============================================================================
# Main Entry Point
# =============================================================================


async def try_generate_stats(
    user: str,
    token: str,
    token_name: str,
    output_dir: Path,
    exclude_repos: set[str],
    exclude_langs: set[str],
    consider_forks: bool,
) -> bool:
    """Try to generate stats with a given token. Returns True on success."""
    print(f"Trying {token_name}...")
    try:
        async with aiohttp.ClientSession() as session:
            s = Stats(
                user,
                token,
                session,
                exclude_repos=exclude_repos,
                exclude_langs=exclude_langs,
                consider_forked_repos=consider_forks,
            )
            await asyncio.gather(
                generate_overview(s, output_dir),
                generate_languages(s, output_dir),
            )
        print(f"✓ Successfully generated stats images in {output_dir}/")
        return True
    except RuntimeError as e:
        error_str = str(e).lower()
        # Check if it's an authentication error
        if "authentication" in error_str or "401" in error_str or "403" in error_str:
            print(f"✗ {token_name} authentication failed: {e}", file=sys.stderr)
            return False
        # For non-auth errors, re-raise
        raise


async def main() -> int:
    """Main entry point for the script."""
    access_token = os.getenv("ACCESS_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN")
    user = os.getenv("GITHUB_ACTOR") or os.getenv("GITHUB_REPOSITORY_OWNER")

    if not access_token and not github_token:
        print(
            "Error: ACCESS_TOKEN or GITHUB_TOKEN environment variable required",
            file=sys.stderr,
        )
        print(
            "The token must have 'repo' and 'read:user' scopes",
            file=sys.stderr,
        )
        return 1
    if not user:
        print(
            "Error: GITHUB_ACTOR or GITHUB_REPOSITORY_OWNER "
            "environment variable required",
            file=sys.stderr,
        )
        return 1

    exclude_repos_str = os.getenv("EXCLUDED", "")
    if exclude_repos_str:
        exclude_repos = {x.strip() for x in exclude_repos_str.split(",")}
    else:
        exclude_repos = set()
    exclude_langs_str = os.getenv("EXCLUDED_LANGS", "")
    if exclude_langs_str:
        exclude_langs = {x.strip() for x in exclude_langs_str.split(",")}
    else:
        exclude_langs = set()
    consider_forks = bool(os.getenv("COUNT_STATS_FROM_FORKS", ""))
    output_dir = Path(os.getenv("OUTPUT_DIR", "images"))

    print(f"Generating GitHub stats for user: {user}")
    print(f"Output directory: {output_dir}")

    # Build list of tokens to try (ACCESS_TOKEN first, then GITHUB_TOKEN)
    tokens_to_try: list[tuple[str, str]] = []
    if access_token:
        tokens_to_try.append((access_token, "ACCESS_TOKEN"))
    if github_token and github_token != access_token:
        tokens_to_try.append((github_token, "GITHUB_TOKEN"))

    last_error: Exception | None = None
    for token, token_name in tokens_to_try:
        try:
            success = await try_generate_stats(
                user=user,
                token=token,
                token_name=token_name,
                output_dir=output_dir,
                exclude_repos=exclude_repos,
                exclude_langs=exclude_langs,
                consider_forks=consider_forks,
            )
            if success:
                return 0
        except RuntimeError as e:
            last_error = e
            print(f"✗ Failed with {token_name}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"✗ Unexpected error with {token_name}: {e}", file=sys.stderr)
            traceback.print_exc()
            last_error = e

    # All tokens failed
    print("\n✗ All tokens failed.", file=sys.stderr)
    print("\nTroubleshooting:", file=sys.stderr)
    print(
        "1. Ensure ACCESS_TOKEN is set with a valid GitHub PAT",
        file=sys.stderr,
    )
    print(
        "2. Token must have these scopes: 'repo', 'read:user'",
        file=sys.stderr,
    )
    print(
        "3. Create a token at: https://github.com/settings/tokens/new",
        file=sys.stderr,
    )
    if last_error:
        print(f"\nLast error: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
