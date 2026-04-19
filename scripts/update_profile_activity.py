#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Update the latest repository activity section in README.md."""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error as urlerror
from urllib import request
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

LATEST_START_MARKER = "<!--LAST_REPOS:START-->"
LATEST_END_MARKER = "<!--LAST_REPOS:END-->"
TOP_STARRED_START_MARKER = "<!--TOP_STARRED_REPOS:START-->"
TOP_STARRED_END_MARKER = "<!--TOP_STARRED_REPOS:END-->"
MAX_PAGES = 10


@dataclass(slots=True)
class RepoEntry:
    name: str
    html_url: str
    description: str
    pushed_at: str
    stargazers_count: int
    fork: bool = False

    def to_markdown(self) -> str:
        date = self.pushed_at.split("T", maxsplit=1)[0]
        return (
            f"- [{html.escape(self.name)}]({self.html_url})"
            f" — {html.escape(self.description)} <sub>{date}</sub>"
        )

    def to_top_starred_markdown(self) -> str:
        star_label = "stars" if self.stargazers_count != 1 else "star"
        return (
            f"- ⭐ **[{html.escape(self.name)}]({self.html_url})**"
            f" — {self.stargazers_count} {star_label} · "
            f"{html.escape(self.description)}"
        )


class GitHubClient:
    """Fetch repository data from the GitHub REST API."""

    def __init__(self, username: str, token: str | None = None) -> None:
        self.username = username
        self.token = (
            token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        )

    def _request_json(self, url: str) -> list[dict]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-activity-script",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not isinstance(payload, list):
            raise RuntimeError(
                f"Unexpected GitHub API response for {url!r}: "
                f"expected list, got {type(payload).__name__}"
            )
        return payload

    def _is_valid_repo(self, repo: dict, repo_name: str) -> bool:
        return not any(
            (
                repo.get("archived"),
                repo.get("disabled"),
                repo_name == ".github",
                repo_name.casefold() == self.username.casefold(),
            )
        )

    def fetch_repos(self, max_concurrent: int = 5) -> list[RepoEntry]:
        repos_to_display: list[RepoEntry] = []
        encoded_username = quote(self.username, safe="")

        query_params = {
            "sort": "pushed",
            "direction": "desc",
            "per_page": 100,
            "page": 1,
        }

        def process_repos(repos_list):
            for repo in repos_list:
                repo_name = repo.get("name", "")
                if not self._is_valid_repo(repo, repo_name):
                    continue
                repos_to_display.append(
                    RepoEntry(
                        name=repo_name,
                        html_url=repo["html_url"],
                        description=(
                            repo.get("description") or "No description yet"
                        ).strip(),
                        pushed_at=repo["pushed_at"],
                        stargazers_count=repo.get("stargazers_count", 0),
                        fork=repo.get("fork", False),
                    )
                )

        query = urlencode(query_params)
        url = f"https://api.github.com/users/{encoded_username}/repos?{query}"
        try:
            repos = self._request_json(url)
        except Exception as e:
            logger.warning("Failed to fetch page 1: %s", e)
            raise

        if not repos:
            return repos_to_display

        process_repos(repos)

        if len(repos) < 100 or MAX_PAGES <= 1:
            return repos_to_display

        urls = []
        for page in range(2, MAX_PAGES + 1):
            query_params["page"] = page
            query = urlencode(query_params)
            urls.append(f"https://api.github.com/users/{encoded_username}/repos?{query}")

        def fetch_page(page_url):
            try:
                return self._request_json(page_url)
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", page_url, e)
                # Use a sentinel value (None) to distinguish request failure
                # from a successful but empty page.
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            pages = list(executor.map(fetch_page, urls))

        # If any page failed to load, abort to avoid updating with partial data.
        if any(page is None for page in pages):
            raise RuntimeError(
                "Failed to fetch all repository pages; aborting to avoid partial data."
            )

        for repos_page in pages:
            if repos_page is None:
                continue
            if not repos_page:
                break
            process_repos(repos_page)

        return repos_to_display


def replace_repo_section(
    readme_text: str,
    start_marker: str,
    end_marker: str,
    repo_lines: list[str],
    empty_message: str,
) -> str:
    start_index = readme_text.find(start_marker)
    end_index = readme_text.find(end_marker)

    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise ValueError("Required README markers are missing or out of order.")

    section_body = "\n".join(repo_lines) if repo_lines else empty_message
    replacement = f"{start_marker}\n{section_body}\n{end_marker}"
    return f"{readme_text[:start_index]}{replacement}{readme_text[end_index + len(end_marker):]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--readme", default="README.md", help="Path to profile markdown"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without writing"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent API requests",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=5,
        help="Number of repositories to include in the latest section",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("GITHUB_ACTOR"),
        help="GitHub username to query (defaults to GITHUB_ACTOR)",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level = LOG_LEVELS.get(args.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    if not args.username:
        logger.error("A GitHub username is required via --username or GITHUB_ACTOR")
        return 1

    path = Path(args.readme)
    if not path.is_file():
        logger.error("README not found at %s", path)
        return 1

    current = path.read_text(encoding="utf-8")

    try:
        repo_entries = GitHubClient(args.username).fetch_repos(args.max_concurrent)
        latest_entries = [
            entry for entry in repo_entries if not entry.fork
        ][: args.max_repos]
        top_starred_entries = sorted(
            repo_entries,
            key=lambda entry: (-entry.stargazers_count, entry.name.lower()),
        )[: args.max_repos]
        updated = replace_repo_section(
            current,
            TOP_STARRED_START_MARKER,
            TOP_STARRED_END_MARKER,
            [entry.to_top_starred_markdown() for entry in top_starred_entries],
            "- No standout repos to highlight just yet.",
        )
        updated = replace_repo_section(
            updated,
            LATEST_START_MARKER,
            LATEST_END_MARKER,
            [entry.to_markdown() for entry in latest_entries],
            "- No recent repos right now.",
        )
    except (RuntimeError, ValueError, urlerror.URLError) as exc:
        logger.error("Failed to update profile activity: %s", exc)
        return 1

    if updated == current:
        logger.info("Profile activity sections are already up to date")
        return 0

    if args.dry_run:
        logger.info("Dry run: profile activity sections would be updated")
        return 0

    path.write_text(updated, encoding="utf-8")
    logger.info("Updated profile activity sections in %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
