#!/usr/bin/env python3
"""Update the latest repository activity section in README.md."""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error as urlerror
from urllib import request
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

START_MARKER = "<!--LAST_REPOS:START-->"
END_MARKER = "<!--LAST_REPOS:END-->"


@dataclass(slots=True)
class RepoEntry:
    name: str
    html_url: str
    description: str
    pushed_at: str

    def to_markdown(self) -> str:
        date = self.pushed_at.split("T", maxsplit=1)[0]
        return (
            f"- [{html.escape(self.name)}]({self.html_url})"
            f" — {html.escape(self.description)} <sub>{date}</sub>"
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

    def fetch_latest_repos(self, limit: int) -> list[RepoEntry]:
        latest: list[RepoEntry] = []

        query_params = {
            "sort": "pushed",
            "direction": "desc",
            "per_page": 100,
            "page": 1,
        }

        for page in range(1, 11):
            query_params["page"] = page
            query = urlencode(query_params)
            url = (
                f"https://api.github.com/users/{self.username}/repos?{query}"
            )
            repos = self._request_json(url)
            if not repos:
                break

            for repo in repos:
                if repo.get("archived") or repo.get("disabled") or repo.get("fork"):
                    continue
                if repo.get("name") == ".github":
                    continue

                latest.append(
                    RepoEntry(
                        name=repo["name"],
                        html_url=repo["html_url"],
                        description=(repo.get("description") or "No description yet").strip(),
                        pushed_at=repo["pushed_at"],
                    )
                )
                if len(latest) >= limit:
                    return latest

        return latest


def replace_latest_repo_section(readme_text: str, repo_lines: list[str]) -> str:
    start_index = readme_text.find(START_MARKER)
    end_index = readme_text.find(END_MARKER)

    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise ValueError("Required README markers are missing or out of order.")

    section_body = "\n".join(repo_lines) if repo_lines else "- No recent repos right now."
    replacement = f"{START_MARKER}\n{section_body}\n{END_MARKER}"
    return f"{readme_text[:start_index]}{replacement}{readme_text[end_index + len(END_MARKER):]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", default="README.md", help="Path to profile markdown")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
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
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
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
        repo_entries = GitHubClient(args.username).fetch_latest_repos(args.max_repos)
        updated = replace_latest_repo_section(
            current,
            [entry.to_markdown() for entry in repo_entries],
        )
    except (RuntimeError, ValueError, urlerror.URLError) as exc:
        logger.error("Failed to update profile activity: %s", exc)
        return 1

    if updated == current:
        logger.info("Latest repos section is already up to date")
        return 0

    if args.dry_run:
        logger.info("Dry run: latest repos section would be updated")
        return 0

    path.write_text(updated, encoding="utf-8")
    logger.info("Updated latest repos section in %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
