# Agent Documentation for GitHub Profile Repository

**Repository Type**: GitHub Profile (README)  
**Primary Purpose**: Automated GitHub profile with dynamic statistics, metrics, and activity tracking  
**Tech Stack**: Python 3.13, GitHub Actions, Shell scripting  
**Package Managers**: `uv` (Python)  

---

## Table of Contents

- [Repository Overview](#repository-overview)
- [Directory Structure](#directory-structure)
- [Core Components](#core-components)
- [Development Workflows](#development-workflows)
- [Code Conventions](#code-conventions)
- [Automation & CI/CD](#automation--cicd)
- [Configuration Files](#configuration-files)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)

---

## Repository Overview

This is a special GitHub profile repository (`Ven0m0/Ven0m0`) that displays on the user's profile page. It features:

- **Dynamic Statistics**: Auto-generated SVG graphics showing GitHub stats (stars, commits, repos, lines of code)
- **Language Analytics**: Visualizations of programming language usage across repositories
- **Activity Tracking**: Recent repository activity with status indicators
- **Automated Updates**: Scheduled workflows keep content fresh without manual intervention
- **Metrics Integration**: Uses `lowlighter/metrics` for detailed GitHub analytics

### Key Features

- 🔄 **Auto-updating**: Multiple scheduled workflows refresh content daily/weekly
- 📊 **Visual Analytics**: Custom SVG generation for stats and language breakdowns
- 🎨 **Aesthetic Design**: Pink/purple color scheme (#ba68c8, #f8bbd0, #b39ddb)
- 🧰 **Modern Tooling**: Uses `uv` for Python, supports latest Python 3.13
- 🔒 **Quality Assurance**: MegaLinter, ShellCheck, EditorConfig enforcement

---

## Directory Structure

```
/workspace/
├── .github/
│   ├── actions/
│   │   └── git-auto-commit/          # Reusable composite action for commits
│   │       └── action.yml
│   ├── workflows/                     # GitHub Actions automation
│   │   ├── dependabot-auto-merge.yml # Auto-merge Dependabot PRs
│   │   ├── github-stats.yml          # Generate stats SVGs (12h)
│   │   ├── image-optimizer.yml       # Compress images (weekly)
│   │   ├── profile-activity.yml      # Update repo list (daily)
│   │   └── update-readme.yml         # Metrics generation (daily)
│   └── dependabot.yml                # Dependabot configuration
├── images/                            # Generated SVG stats
│   ├── github-stats.svg              # Combined stats view
│   ├── languages.svg                 # Language breakdown
│   └── overview.svg                  # Overview statistics
├── scripts/                           # Python automation scripts
│   ├── generate_stats_images.py      # GraphQL-based stats generator
│   └── update_profile_activity.py    # Repository activity updater
├── .editorconfig                      # Universal editor settings
├── .gitattributes                     # Git file handling rules
├── .gitignore                         # Ignored files/patterns
├── .megalinter.yml                    # Linter configuration
├── .shellcheckrc                      # ShellCheck settings
└── README.md                          # Profile page content
```

---

## Core Components

### 1. Statistics Generator (@scripts/generate_stats_images.py)

**Purpose**: Fetches GitHub data via GraphQL/REST APIs and generates SVG visualizations

**Key Classes**:
- `Queries`: Handles GitHub API interactions with retry logic and rate limiting
- `Stats`: Aggregates and caches user statistics (stars, forks, commits, languages)

**Generated Outputs**:
- `images/overview.svg`: Total stars, commits, repos, lines changed
- `images/languages.svg`: Top programming languages with progress bars
- `images/github-stats.svg`: Combined overview + top 5 languages

**Dependencies**: `aiohttp>=3.11,<4`

**Environment Variables**:
- `ACCESS_TOKEN` / `GITHUB_TOKEN`: Authentication (requires `repo`, `read:user` scopes)
- `GITHUB_ACTOR`: Username to generate stats for
- `EXCLUDED`: Comma-separated list of repos to exclude
- `EXCLUDED_LANGS`: Comma-separated list of languages to exclude
- `COUNT_STATS_FROM_FORKS`: Include forked repos in stats
- `OUTPUT_DIR`: Output directory (default: `images`)

**Execution**:
```bash
uv run --python 3.13 --with 'aiohttp>=3.11,<4' scripts/generate_stats_images.py
```

**API Features**:
- Concurrent requests with semaphore-based rate limiting (10 concurrent)
- Exponential backoff retry logic (3 attempts for GraphQL, 60 for REST)
- Pagination support for large repository lists
- Automatic fallback between `ACCESS_TOKEN` and `GITHUB_TOKEN`

**Color Scheme**:
- Background: `#0d1117` (GitHub dark)
- Primary header: `#ba68c8` (purple-pink)
- Labels: `#b39ddb` (light purple)
- Values: `#fff` (white)

---

### 2. Profile Activity Updater (@scripts/update_profile_activity.py)

**Purpose**: Updates repository activity status indicators in README.md

**Status Categories**:
- 🟢 **Active**: Pushed within 120 days (default)
- 🟡 **Partially maintained**: Pushed within 240 days
- 🔴 **Inactive**: No push in 240+ days
- 📥 **Archived**: Repository is archived

**Command-Line Options**:
```bash
--readme README.md          # Path to markdown file
--dry-run                   # Preview changes without writing
--active-days 120           # Days threshold for "active"
--partially-days 240        # Days threshold for "partially maintained"
--max-repos N               # Limit number of repos processed
--log-level INFO            # Logging verbosity
```

**Pattern Matching**:
- Finds GitHub URLs in markdown lines
- Updates status emoji and label inline
- Preserves markdown formatting

**Execution**:
```bash
uv run --python 3.13 scripts/update_profile_activity.py
```

---

### 3. Git Auto-Commit Action (@.github/actions/git-auto-commit/action.yml)

**Purpose**: Reusable composite action for committing and pushing changes

**Inputs**:
- `commit_message`: Commit message (required)
- `file_pattern`: Files to stage (default: `.`)

**Features**:
- Skips commit if no changes detected
- Exponential backoff retry logic for push failures (4 attempts: 1s, 2s, 4s, 8s)
- Uses `github-actions[bot]` as committer
- Set with `set -e` for fail-fast behavior

**Usage in Workflows**:
```yaml
- name: Commit changes
  uses: ./.github/actions/git-auto-commit
  with:
    commit_message: "chore: update stats"
    file_pattern: "images/*.svg"
```

---

## Development Workflows

### Workflow Schedule Overview

| Workflow | Trigger | Frequency | Purpose |
|----------|---------|-----------|---------|
| `github-stats.yml` | Cron | Every 12 hours | Generate stats SVGs |
| `update-readme.yml` | Cron | Daily at midnight | Generate metrics |
| `profile-activity.yml` | Cron | Daily at 4 AM | Update repo list |
| `image-optimizer.yml` | Cron | Weekly (Sunday 2 AM) | Compress images |
| `dependabot-auto-merge.yml` | PR | On Dependabot PRs | Auto-merge dependencies |

### Workflow Details

#### 1. Generate Stats Images (@.github/workflows/github-stats.yml)

**Triggers**:
- Scheduled: Every 12 hours (`0 */12 * * *`)
- Manual: `workflow_dispatch`
- Push: When script or workflow file changes

**Steps**:
1. Checkout repository
2. Setup `uv` with caching enabled
3. Run `generate_stats_images.py` with environment variables
4. Commit generated SVGs using git-auto-commit action

**Timeout**: 15 minutes

**Required Secrets**:
- `ACCESS_TOKEN`: GitHub PAT with `repo`, `read:user` scopes
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions

---

#### 2. Metrics Generation (@.github/workflows/update-readme.yml)

**Triggers**:
- Scheduled: Daily at midnight (`0 0 * * *`)
- Manual: `workflow_dispatch`

**Steps**:
1. Checkout repository
2. Generate `metrics.classic.svg` (with languages, stars, traffic, calendar plugins)
3. Generate `metrics.svg` (basic metrics)
4. Commit both SVGs

**Concurrency**: `metrics-update` group (cancel-in-progress)

**Timeout**: 30 minutes

**Plugin Configuration**:
- Languages: Limited to top 4
- Traffic: Repository traffic statistics
- Calendar: Last 1 year of contributions
- Timezone: `Europe/Berlin`

**Required Secrets**:
- `METRICS_TOKEN`: GitHub PAT for lowlighter/metrics

---

#### 3. Profile Activity Update (@.github/workflows/profile-activity.yml)

**Triggers**:
- Scheduled: Daily at 4 AM (`0 4 * * *`)
- Manual: `workflow_dispatch`

**Steps**:
1. Checkout repository
2. Setup `uv` with caching
3. Run `update_profile_activity.py` to update status indicators
4. Run GitHub Script to update `<!--LAST_REPOS:START-->...<!--LAST_REPOS:END-->` section
   - Fetches user's repos sorted by push date
   - Filters out archived, disabled, and forked repos
   - Displays top 5 with description and date
5. Commit README.md changes

**Timeout**: 10 minutes

---

#### 4. Image Optimizer (@.github/workflows/image-optimizer.yml)

**Triggers**:
- Scheduled: Weekly on Sunday at 2 AM (`0 2 * * 0`)
- Manual: `workflow_dispatch`

**Steps**:
1. Compress images using `stellasoftio/image-optimizer-action`
2. Export WebP versions
3. Ignore metrics SVGs (they're regenerated frequently)
4. Create PR if images were compressed

**Timeout**: 15 minutes

---

#### 5. Dependabot Auto-Merge (@.github/workflows/dependabot-auto-merge.yml)

**Triggers**: PR opened/synced/reopened by `dependabot[bot]`

**Action**: Automatically enables auto-merge with squash strategy

---

## Code Conventions

### Python (@.editorconfig, @.megalinter.yml)

**Style Guide**:
- **Indentation**: 4 spaces
- **Line Length**: 88 characters (Black default)
- **Quotes**: Double quotes preferred
- **Imports**: Sorted with `isort`

**Linters**:
- `black`: Code formatting
- `isort`: Import sorting
- `pylint`: Static analysis

**Type Hints**:
- Use `from __future__ import annotations` for forward references
- Prefer modern type syntax: `dict[str, int]` over `Dict[str, int]`
- Use `dataclass(slots=True)` for performance

**Async Patterns**:
- Use `aiohttp` for HTTP requests
- Implement semaphore-based concurrency control
- Apply exponential backoff for retries

**Docstrings**:
- Google-style docstrings for modules, classes, and functions
- First line is imperative mood summary

**Example**:
```python
"""Generate SVG stats images for GitHub profile.

This script collects GitHub statistics using GraphQL and REST APIs,
then generates SVG images for display on a GitHub profile README.
"""
```

---

### Shell Scripts (@.shellcheckrc, @.editorconfig)

**Style Guide**:
- **Indentation**: 2 spaces
- **Shell Variant**: Bash
- **Quoting**: Always quote variables: `"$variable"`
- **Error Handling**: Use `set -e` for fail-fast

**ShellCheck**:
- Enabled with external sources
- Disabled rules: SC1079, SC1078, SC1073, SC1072, SC1083, SC1090, SC1091, SC2002, SC2016, SC2034, SC2086, SC2154, SC2155, SC2236, SC2250, SC2312

**Example** (@.github/actions/git-auto-commit/action.yml):
```bash
#!/bin/bash
set -e
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
```

---

### YAML (@.editorconfig, @.megalinter.yml)

**Style Guide**:
- **Indentation**: 2 spaces
- **Line Length**: 120 characters
- **Quotes**: Prefer unquoted strings unless necessary

**Linters**:
- `yamllint`: YAML syntax validation
- `prettier`: Formatting (via MegaLinter)

---

### Markdown (@.editorconfig, @.megalinter.yml)

**Style Guide**:
- **Indentation**: 2 spaces
- **Line Length**: 80 characters (recommended, not enforced in README)
- **Trailing Whitespace**: Disabled for markdown (for line breaks)

**Linters**:
- `markdownlint`: Markdown style checking

**Comment Markers**:
- `<!--LAST_REPOS:START-->...<!--LAST_REPOS:END-->`: Auto-updated repo list
- `<!--START_SECTION:activity-->...<!--END_SECTION:activity-->`: Activity feed

---

### JSON (@.editorconfig, @.megalinter.yml)

**Style Guide**:
- **Indentation**: 2 spaces
- **Linter**: `prettier`

---

## Automation & CI/CD

### Concurrency Control

Workflows use concurrency groups to prevent simultaneous runs:

```yaml
concurrency:
  group: metrics-update
  cancel-in-progress: true
```

### Retry Strategies

**Git Push** (@.github/actions/git-auto-commit):
- Max attempts: 4
- Backoff: 1s, 2s, 4s, 8s

**GraphQL Queries** (@scripts/generate_stats_images.py):
- Max attempts: 3
- Backoff: 1s, 2s, 4s

**REST API Queries** (@scripts/generate_stats_images.py):
- Max attempts: 60
- Backoff: Exponential with cap at 8s
- Special handling for HTTP 202 (data processing)

### Secrets Management

**Required Secrets**:
- `ACCESS_TOKEN`: GitHub PAT for stats generation (scopes: `repo`, `read:user`)
- `METRICS_TOKEN`: GitHub PAT for lowlighter/metrics
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions

**Optional Secrets**:
- `EXCLUDED`: Comma-separated repo names to exclude from stats
- `EXCLUDED_LANGS`: Comma-separated language names to exclude
- `COUNT_STATS_FROM_FORKS`: Set to any value to include forked repos

---

## Configuration Files

### @.editorconfig

**Purpose**: Universal editor configuration for consistent formatting

**Key Settings**:
- Line endings: LF (Unix-style)
- Charset: UTF-8
- Trim trailing whitespace: Yes (except markdown)
- Insert final newline: Yes
- Language-specific indent sizes (Python: 4, Shell: 2, YAML: 2)

**Shell Script Detection**:
- Matches `**.{sh,bash}`, `bash_*`, `.bash*`, `.profile`
- Enforces 2-space indentation
- Configures operators and bracket spacing

---

### @.megalinter.yml

**Purpose**: Centralized linting configuration

**Strategy**: `APPLY_FIXES: all` - Auto-fix issues when possible

**Enabled Linters**:
- `YAML_PRETTIER`, `YAML_YAMLLINT`
- `MARKDOWN_MARKDOWNLINT`
- `PYTHON_BLACK`, `PYTHON_ISORT`, `PYTHON_PYLINT`
- `JSON_PRETTIER`
- `BASH_SHELLCHECK`, `BASH_SHFMT`

**Disabled Linters**:
- `COPYPASTE_JSCPD`: Too aggressive for profile README
- `SPELL_CSPELL`: Too many false positives with usernames/repos

**Exclusions**: `megalinter-reports/`

---

### @.gitignore

**Ignored Patterns**:
- Temporary files: `*.log`, `*.tmp`, `*.temp`, `*.bak`, `*.swp`
- OS files: `.DS_Store`, `Thumbs.db`
- Editors: `.vscode/`, `.idea/`, `*.sublime-workspace`
- Linter reports: `megalinter-reports/`
- Python: `__pycache__/`, `*.pyc`, `.Python`

---

### @.shellcheckrc

**Purpose**: Configure ShellCheck for shell script linting

**Key Settings**:
- `shell=bash`: Assume Bash syntax
- `external-sources=true`: Follow external source files
- `enable=all`: Enable all checks except disabled list
- `source-path=SCRIPTDIR`: Look for sourced files in script directory

**Disabled Rules**: 16 rules disabled (mostly related to quoting, unused vars, SC2086)

---

### @.github/dependabot.yml

**Purpose**: Automated dependency updates for GitHub Actions

**Configuration**:
- Package ecosystem: `github-actions`
- Schedule: Weekly
- Grouping: All updates in single PR (minor + patch)

---

## Common Tasks

### Adding New Statistics

1. **Modify** @scripts/generate_stats_images.py
2. **Add new GraphQL query** in `Queries` class
3. **Add property** to `Stats` class with caching
4. **Update SVG template** (e.g., `TEMPLATE_OVERVIEW`)
5. **Test locally**:
   ```bash
   export ACCESS_TOKEN="ghp_..."
   export GITHUB_ACTOR="Ven0m0"
   uv run --python 3.13 --with 'aiohttp>=3.11,<4' scripts/generate_stats_images.py
   ```
6. **Commit and push** - workflow will run automatically

---

### Modifying Workflow Schedule

1. **Edit** workflow file in @.github/workflows/
2. **Update cron expression**:
   ```yaml
   schedule:
     - cron: "0 */6 * * *"  # Every 6 hours
   ```
3. **Cron syntax**: `minute hour day month weekday`
4. **Test with**: `workflow_dispatch` trigger
5. **Commit and push**

---

### Updating README Content

**Manual Sections**: Edit directly in @README.md

**Auto-Updated Sections**:
- `<!--LAST_REPOS:START-->...<!--LAST_REPOS:END-->`: Updated by profile-activity workflow
- `<!--START_SECTION:activity-->...<!--END_SECTION:activity-->`: Updated by external action
- Embedded SVGs: Point to files in `images/` directory

**Best Practices**:
- Don't manually edit auto-updated sections
- Keep markdown clean and semantic
- Use HTML for advanced formatting (centering, custom styling)
- Test external image URLs for availability

---

### Adding New Secrets

1. **Navigate to**: Repository Settings → Secrets and variables → Actions
2. **Click**: "New repository secret"
3. **Add secret**: Name and value
4. **Reference in workflow**:
   ```yaml
   env:
     MY_SECRET: ${{ secrets.MY_SECRET }}
   ```
5. **Update workflow** to use the secret

---

### Testing Workflows Locally

**Using `act`** (GitHub Actions local runner):
```bash
# Install act
brew install act  # or appropriate package manager

# Run workflow
act -j generate  # Run "generate" job

# With secrets
act -j generate -s ACCESS_TOKEN="ghp_..."
```

**Using direct script execution**:
```bash
# Set environment variables
export ACCESS_TOKEN="ghp_..."
export GITHUB_ACTOR="Ven0m0"
export OUTPUT_DIR="images"

# Run Python script
uv run --python 3.13 --with 'aiohttp>=3.11,<4' scripts/generate_stats_images.py

# Run profile activity updater
uv run --python 3.13 scripts/update_profile_activity.py --dry-run
```

---

### Debugging Failed Workflows

1. **Check workflow run logs**: Actions tab → Select failed workflow → View logs
2. **Look for error patterns**:
   - Authentication errors: Check token validity and scopes
   - Rate limiting: GitHub API rate limits (5000/hour authenticated)
   - Timeout: Increase `timeout-minutes` in workflow
3. **Common fixes**:
   - Regenerate `ACCESS_TOKEN` with correct scopes (`repo`, `read:user`)
   - Clear `uv` cache if Python dependencies fail
   - Check for breaking changes in external actions
4. **Manual re-run**: Click "Re-run jobs" in workflow run view

---

### Linting Code

**Run MegaLinter locally** (requires Docker):
```bash
docker run --rm -v "$(pwd)":/tmp/lint oxsecurity/megalinter:latest
```

**Run specific linters**:
```bash
# Python
black --check scripts/
isort --check scripts/
pylint scripts/

# Shell
shellcheck .github/actions/git-auto-commit/action.yml

# YAML
yamllint .github/workflows/
```

**Auto-fix**:
```bash
# Python
black scripts/
isort scripts/

# YAML
prettier --write .github/workflows/*.yml
```

---

## Troubleshooting

### Issue: Stats not updating

**Symptoms**: SVGs in `images/` directory are stale

**Possible Causes**:
1. Workflow not running (check Actions tab)
2. Token expired or invalid
3. GitHub API rate limit exceeded
4. Network issues during workflow run

**Solutions**:
1. **Check workflow status**: Actions → github-stats → View recent runs
2. **Verify token**:
   ```bash
   curl -H "Authorization: Bearer $ACCESS_TOKEN" https://api.github.com/user
   ```
3. **Check rate limit**:
   ```bash
   curl -H "Authorization: Bearer $ACCESS_TOKEN" https://api.github.com/rate_limit
   ```
4. **Manually trigger workflow**: Actions → Generate Stats Images → Run workflow

---

### Issue: Authentication errors in workflow

**Error Messages**:
- `Authentication failed for ... (status 401)`
- `GraphQL API returned no data. Check if ACCESS_TOKEN has required permissions`

**Solutions**:
1. **Regenerate token**: Settings → Developer settings → Personal access tokens
2. **Required scopes**: `repo`, `read:user`
3. **Update secret**: Repository Settings → Secrets → ACCESS_TOKEN
4. **Verify token format**: Should start with `ghp_` (classic) or `github_pat_` (fine-grained)

---

### Issue: MegaLinter fails

**Symptoms**: Linting errors in local or CI environment

**Solutions**:
1. **Check configuration**: @.megalinter.yml
2. **Run locally**:
   ```bash
   docker run --rm -v "$(pwd)":/tmp/lint oxsecurity/megalinter:latest
   ```
3. **Review logs**: Look for specific linter errors
4. **Disable problematic linters**:
   ```yaml
   DISABLE_LINTERS:
     - LINTER_NAME
   ```
5. **Auto-fix locally**: MegaLinter applies fixes with `APPLY_FIXES: all`

---

### Issue: Workflow timeout

**Symptoms**: Workflow fails with "The operation was canceled" after timeout

**Solutions**:
1. **Increase timeout**:
   ```yaml
   jobs:
     job-name:
       timeout-minutes: 30  # Increase from 15
   ```
2. **Optimize API calls**: Add caching, reduce concurrent requests
3. **Check GitHub status**: https://www.githubstatus.com/
4. **Reduce scope**: Use `EXCLUDED` secret to skip large/slow repos

---

### Issue: README markers missing

**Error**: `Required README markers are missing or out of order`

**Cause**: Auto-update markers deleted or malformed

**Solution**: Restore markers in @README.md:
```markdown
<!--LAST_REPOS:START-->
<!-- Content will be auto-generated -->
<!--LAST_REPOS:END-->

<!--START_SECTION:activity-->
<!-- Content will be auto-generated -->
<!--END_SECTION:activity-->
```

---

### Issue: `uv` installation fails

**Symptoms**: `setup-uv` action fails in workflow

**Solutions**:
1. **Update action version**: `astral-sh/setup-uv@v7`
2. **Disable cache** if corrupted:
   ```yaml
   - name: Setup uv
     uses: astral-sh/setup-uv@v7
     with:
       enable-cache: false
   ```
3. **Check `uv` compatibility**: Ensure Python 3.13 is supported

---

### Issue: Images not displaying on profile

**Symptoms**: Broken image icons on GitHub profile

**Causes**:
1. SVG syntax errors
2. File not committed to repository
3. Incorrect file path in README

**Solutions**:
1. **Validate SVG**: Open file in browser or use validator
2. **Check commit**: Ensure files in `images/` are committed
3. **Verify path**: Should be `images/overview.svg`, not `./images/overview.svg`
4. **Clear cache**: Add `?raw=true` query parameter to force refresh:
   ```markdown
   ![Stats](images/overview.svg?raw=true)
   ```

---

## Additional Resources

### GitHub API Documentation
- **GraphQL API**: https://docs.github.com/en/graphql
- **REST API**: https://docs.github.com/en/rest
- **Rate Limiting**: https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting

### Tool Documentation
- **uv**: https://docs.astral.sh/uv/
- **lowlighter/metrics**: https://github.com/lowlighter/metrics
- **MegaLinter**: https://megalinter.io/
- **ShellCheck**: https://www.shellcheck.net/
- **EditorConfig**: https://editorconfig.org/

### GitHub Actions
- **Workflow Syntax**: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- **Contexts**: https://docs.github.com/en/actions/learn-github-actions/contexts
- **Expressions**: https://docs.github.com/en/actions/learn-github-actions/expressions

---

## Quick Reference

### File Patterns
- **Python scripts**: `scripts/*.py`
- **Workflows**: `.github/workflows/*.yml`
- **Generated images**: `images/*.svg`
- **Config files**: `.*rc`, `*.yml`, `*.yaml`, `.editorconfig`

### Commands
```bash
# Run stats generation locally
uv run --python 3.13 --with 'aiohttp>=3.11,<4' scripts/generate_stats_images.py

# Run profile activity updater
uv run --python 3.13 scripts/update_profile_activity.py --dry-run

# Lint Python code
black --check scripts/
isort --check scripts/

# Run ShellCheck
shellcheck .github/actions/git-auto-commit/action.yml

# Test workflow locally
act -j generate -s ACCESS_TOKEN="ghp_..."
```

### Environment Variables
- `ACCESS_TOKEN`: GitHub PAT for stats
- `GITHUB_TOKEN`: Auto-provided by Actions
- `GITHUB_ACTOR`: GitHub username
- `EXCLUDED`: Repos to exclude (comma-separated)
- `EXCLUDED_LANGS`: Languages to exclude (comma-separated)
- `OUTPUT_DIR`: Output directory for images

---

**Last Updated**: 2026-02-04  
**Maintainer**: Ven0m0  
**License**: Not specified
