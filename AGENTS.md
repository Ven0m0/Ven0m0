# Agent Documentation for GitHub Profile Repository

[![Maintainability](https://qlty.sh/gh/Ven0m0/projects/Ven0m0/maintainability.svg)](https://qlty.sh/gh/Ven0m0/projects/Ven0m0)

**Repository Type**: GitHub profile README automation  
**Primary Purpose**: Keep the profile README current with a lightweight scheduled workflow  
**Tech Stack**: Python 3.13, GitHub Actions, Markdown  
**Package Manager**: `uv`

---

## Repository Overview

This repository powers the `Ven0m0` GitHub profile page.

Current automation is intentionally minimal:

- `README.md` contains the profile content shown on GitHub
- `scripts/update_profile_activity.py` refreshes the `<!--LAST_REPOS:START-->` block
- `.github/workflows/profile-activity.yml` runs that script on a schedule using `uv run`
- `.github/actions/git-auto-commit/action.yml` commits workflow-generated README changes

The profile relies on externally hosted stat widgets, so the repository no longer keeps separate generated SVG stats or metrics files.

---

## Directory Structure

```text
/home/runner/work/Ven0m0/Ven0m0/
├── .github/
│   ├── actions/
│   │   └── git-auto-commit/
│   │       └── action.yml
│   └── workflows/
│       └── profile-activity.yml
├── README.md
├── scripts/
│   └── update_profile_activity.py
├── AGENTS.md
└── CLAUDE.md
```

---

## Core Components

### `scripts/update_profile_activity.py`

- Fetches the repository owner's latest repositories from the GitHub REST API
- Filters out archived, disabled, forked, and `.github` repositories
- Rewrites the README section between `<!--LAST_REPOS:START-->` and `<!--LAST_REPOS:END-->`
- Supports `--readme`, `--dry-run`, `--max-repos`, `--username`, and `--log-level`
- Uses only the Python standard library, but should still be executed through `uv run`

### `.github/workflows/profile-activity.yml`

- Runs daily and on `workflow_dispatch`
- Sets up `uv`
- Executes `uv run --python 3.13 scripts/update_profile_activity.py`
- Commits README changes through the local `git-auto-commit` action

### `.github/actions/git-auto-commit/action.yml`

- Stages only the requested file pattern
- Creates a commit only when there are staged changes
- Retries `git push` with exponential backoff

---

## Conventions

### Python

- Use Python 3.13 syntax
- Prefer the standard library unless an external dependency is clearly necessary
- Execute repository Python scripts with `uv run --python 3.13 ...`

### README automation

- Treat the `<!--LAST_REPOS:START-->` block as workflow-managed content
- Keep manual edits outside the auto-updated markers
- Preserve the existing Markdown/HTML style used in `README.md`

### Workflows

- Keep workflows small and purpose-specific
- Prefer a single script over duplicated logic spread across inline workflow scripts
- Avoid adding generated assets that are not referenced by `README.md`

---

## Common Tasks

### Run the README updater locally

```bash
export GITHUB_ACTOR="Ven0m0"
export GITHUB_TOKEN="ghp_..."
uv run --python 3.13 scripts/update_profile_activity.py --dry-run
```

### Update the latest repos section manually

```bash
export GITHUB_ACTOR="Ven0m0"
export GITHUB_TOKEN="ghp_..."
uv run --python 3.13 scripts/update_profile_activity.py
```

### Validate edited files

```bash
python3 -m py_compile scripts/update_profile_activity.py
yamllint .github
```

---

## Troubleshooting

### `uv: command not found`

Install `uv` locally before running repository Python commands. In CI, `astral-sh/setup-uv` handles this.

### README markers missing

Ensure `README.md` still contains both:

- `<!--LAST_REPOS:START-->`
- `<!--LAST_REPOS:END-->`

### No README changes were committed

The workflow only commits when the generated repo list differs from the current README content.
