# Agent Documentation for GitHub Profile Repository

[![Maintainability](https://qlty.sh/gh/Ven0m0/projects/Ven0m0/maintainability.svg)](https://qlty.sh/gh/Ven0m0/projects/Ven0m0)

GitHub profile README automation. Python 3.13, GitHub Actions, Markdown. Package manager: `uv`.

## Gotchas

- `scripts/update_profile_activity.py` rewrites the README blocks between `<!--LAST_REPOS:START/END-->` and `<!--TOP_STARRED_REPOS:START/END-->`. Manual edits inside those markers are overwritten; edit outside them (e.g. the hand-written "Spotlight drops" table).
- The script filters out archived, disabled, forked and `.github` repos.
- It uses only the standard library but must still be run via `uv run --python 3.13 ...`.
- `.github/actions/git-auto-commit` stages only the requested file pattern, commits only if something is staged, and retries `git push` with exponential backoff.
- The profile uses externally hosted stat widgets; do not add generated SVG/metrics files that `README.md` does not reference.

## Conventions

- Python 3.13 syntax; prefer the standard library unless a dependency is clearly necessary.
- Keep workflows small and purpose-specific; put logic in one script, not inline workflow scripts.
- Preserve the existing Markdown/HTML style of `README.md`.

## Running locally

Needs `GITHUB_ACTOR` and `GITHUB_TOKEN` in the environment.

```bash
uv run --python 3.13 scripts/update_profile_activity.py --dry-run
```

Validate edits: `python3 -m py_compile scripts/update_profile_activity.py` and `yamllint .github`.

## Troubleshooting

- `uv: command not found`: install `uv` locally (CI uses `astral-sh/setup-uv`).
- Updater changes nothing: both marker pairs must still exist in `README.md`; the workflow commits only when the generated list differs.
