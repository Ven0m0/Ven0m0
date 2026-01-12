#!/usr/bin/env python3
"""Generate SVG stats images for GitHub profile."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
from github_stats import Stats

TEMPLATE_OVERVIEW = """<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">
  <defs>
    <style>
      .header{font: 600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#ba68c8}
      .stat{font:400 14px 'Segoe UI',Ubuntu,sans-serif;fill:#f8bbd0}
      .label{font:400 12px 'Segoe UI',Ubuntu,sans-serif;fill:#b39ddb}
      .value{font:600 16px 'Segoe UI',Ubuntu,sans-serif;fill:#fff}
    </style>
  </defs>
  <rect width="495" height="195" fill="#0d1117" rx="6"/>
  <text x="20" y="35" class="header">{{ name }}'s GitHub Stats</text>
  <g transform="translate(20, 60)">
    <text y="20" class="label">Total Stars Earned</text>
    <text y="20" x="200" class="value">{{ stars }}</text>
  </g>
  <g transform="translate(20, 90)">
    <text y="20" class="label">Total Commits</text>
    <text y="20" x="200" class="value">{{ contributions }}</text>
  </g>
  <g transform="translate(20, 120)">
    <text y="20" class="label">Total Repositories</text>
    <text y="20" x="200" class="value">{{ repos }}</text>
  </g>
  <g transform="translate(20, 150)">
    <text y="20" class="label">Lines Changed</text>
    <text y="20" x="200" class="value">{{ lines_changed }}</text>
  </g>
</svg>"""

TEMPLATE_LANGUAGES = """<svg xmlns="http://www.w3.org/2000/svg" width="495" height="285" viewBox="0 0 495 285">
  <defs>
    <style>
      .header{font:600 18px 'Segoe UI',Ubuntu,sans-serif;fill:#ba68c8}
      .lang{font:400 14px 'Segoe UI',Ubuntu,sans-serif;fill:#fff}
      .percent{font:600 14px 'Segoe UI',Ubuntu,sans-serif;fill:#b39ddb}
      .progress-item{height:8px;display:inline-block}
      li{list-style:none;margin:8px 0;display:flex;align-items:center;animation:slideIn 0.3s ease-in-out forwards;opacity:0}
      @keyframes slideIn{to{opacity:1}}
    </style>
  </defs>
  <rect width="495" height="285" fill="#0d1117" rx="6"/>
  <text x="20" y="35" class="header">Most Used Languages</text>
  <foreignObject x="20" y="50" width="455" height="10">
    <div xmlns="http://www.w3.org/1999/xhtml" style="display:flex;width:100%;height:8px;border-radius:4px;overflow:hidden">{{ progress }}</div>
  </foreignObject>
  <foreignObject x="20" y="70" width="455" height="200">
    <ul xmlns="http://www.w3.org/1999/xhtml" style="padding:0;margin:0">{{ lang_list }}</ul>
  </foreignObject>
</svg>"""

async def generate_overview(s: Stats, output_dir: Path) -> None:
  try:
    output = TEMPLATE_OVERVIEW
    output = output.replace("{{ name }}", html.escape(await s.name))
    output = output.replace("{{ stars }}", f"{await s.stargazers:,}")
    output = output.replace("{{ contributions }}", f"{await s.total_contributions:,}")
    output = output.replace("{{ repos }}", f"{len(await s.all_repos):,}")
    changed = sum(await s.lines_changed)
    output = output.replace("{{ lines_changed }}", f"{changed:,}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "overview.svg").write_text(output, encoding="utf-8")
    print("Generated overview.svg")
  except Exception as e:
    print(f"Error generating overview: {e}", file=sys.stderr)
    raise

async def generate_languages(s:  Stats, output_dir: Path) -> None:
  try:
    output = TEMPLATE_LANGUAGES
    progress = ""
    lang_list = ""
    sorted_langs = sorted((await s.languages).items(), reverse=True, key=lambda t: t[1].get("size", 0))
    for i, (lang, data) in enumerate(sorted_langs):
      color = data.get("color") or "#888888"
      prop = data.get("prop", 0)
      ratio = [0.99, 0.01] if prop > 50 else [0.98, 0.02]
      if i == len(sorted_langs) - 1:
        ratio = [1, 0]
      progress += f'<span style="background-color:{color};width:{ratio[0] * prop:.3f}%;margin-right:{ratio[1] * prop:.3f}%" class="progress-item"></span>'
      lang_list += f'<li style="animation-delay:{i * 150}ms"><svg xmlns="http://www.w3.org/2000/svg" style="fill:{color};margin-right:8px" viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="4"/></svg><span class="lang">{html.escape(lang)}</span><span class="percent" style="margin-left:auto">{prop:.2f}%</span></li>'
    output = output.replace("{{ progress }}", progress)
    output = output.replace("{{ lang_list }}", lang_list)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "languages.svg").write_text(output, encoding="utf-8")
    print("Generated languages.svg")
  except Exception as e:
    print(f"Error generating languages: {e}", file=sys.stderr)
    raise

async def main() -> int:
  token = os.getenv("ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")
  user = os.getenv("GITHUB_ACTOR") or os.getenv("GITHUB_REPOSITORY_OWNER")
  if not token or not user:
    print("Error: ACCESS_TOKEN and GITHUB_ACTOR required", file=sys.stderr)
    return 1
  exclude_repos_str = os.getenv("EXCLUDED", "")
  exclude_repos = {x.strip() for x in exclude_repos_str.split(",")} if exclude_repos_str else set()
  exclude_langs_str = os.getenv("EXCLUDED_LANGS", "")
  exclude_langs = {x.strip() for x in exclude_langs_str.split(",")} if exclude_langs_str else set()
  consider_forks = bool(os.getenv("COUNT_STATS_FROM_FORKS", ""))
  output_dir = Path(os.getenv("OUTPUT_DIR", "images"))
  try:
    async with aiohttp.ClientSession() as session:
      s = Stats(user, token, session, exclude_repos=exclude_repos, exclude_langs=exclude_langs, consider_forked_repos=consider_forks)
      await asyncio.gather(generate_overview(s, output_dir), generate_languages(s, output_dir))
    print(f"Generated stats images in {output_dir}/")
    return 0
  except Exception as e:
    print(f"Fatal error: {e}", file=sys.stderr)
    return 1

if __name__ == "__main__":
  sys.exit(asyncio.run(main()))
