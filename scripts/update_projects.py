"""Refresh only the marked README project section using public GitHub repos."""
import json
import os
from pathlib import Path
import subprocess
import re
import textwrap
from xml.sax.saxutils import escape

START = '<!-- PROJECTS:START -->'
END = '<!-- PROJECTS:END -->'
DESCRIPTIONS = {
    'omarchy-lyricify': 'A lyrics island for Omarchy / Hyprland, with timed lyrics and playback controls for Spotify and MPRIS players.',
    'omarchy-mfa': 'A native, keyboard-driven TOTP plugin with system keyring storage.',
    'pfwd': 'Network namespace-aware port forwarding in Rust.',
    'fs-bench-rs': 'Filesystem benchmarking and integrity checking in Rust.',
}


def fetch_repos(owner):
    repos = []
    for page in range(1, 101):
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'profile-projects'}
        if os.environ.get('GH_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
        command = ['curl', '--fail', '--silent', '--show-error', '--retry', '3', '--max-time', '30']
        for key, value in headers.items():
            command.extend(['-H', f'{key}: {value}'])
        command.append(f'https://api.github.com/users/{owner}/repos?per_page=100&sort=pushed&page={page}')
        batch = json.loads(subprocess.check_output(command, text=True))
        repos.extend(batch)
        if len(batch) < 100:
            return repos
    raise RuntimeError('Repository pagination limit exceeded')


def render(repos, owner):
    selected = sorted(
        (r for r in repos if not any(r.get(k) for k in ('fork', 'archived', 'disabled', 'private'))
         and r['name'].lower() != owner.lower()),
        key=lambda r: (r.get('pushed_at') or '', r['name']), reverse=True,
    )[:6]
    if not selected:
        raise RuntimeError('No eligible projects; preserving existing README')
    rows = []
    y = 100
    for index, repo in enumerate(selected, 1):
        name = repo['name']
        language = repo.get('language') or 'Source'
        description = ' '.join((repo.get('description') or DESCRIPTIONS.get(name) or 'Explore the source and documentation.').split())
        lines = textwrap.wrap(description, width=94)
        rows.append(f'<text x="30" y="{y}" fill="#79c0ff" font-size="20">{index:02} / {escape(name)}</text>')
        rows.append(f'<text x="930" y="{y}" text-anchor="end" fill="#7ee787" font-size="14">{escape(language)} / stars {repo.get("stargazers_count", 0)}</text>')
        for n, line in enumerate(lines):
            rows.append(f'<text x="30" y="{y+34+n*23}" fill="#8b949e">{escape(line)}</text>')
        y += 64 + len(lines)*23
        if index < len(selected):
            rows.append(f'<path d="M30 {y-25}h900" stroke="#21262d"/>')
    height = y + 8
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}">
<title>{escape(owner)} projects: {escape(', '.join(r['name'] for r in selected))}</title>
<rect x="1" y="1" width="958" height="{height-2}" rx="14" fill="#0d1117" stroke="#30363d"/>
<g font-family="monospace" font-size="16">
<text x="30" y="39" fill="#7ee787" font-size="19">❯ <tspan fill="#e6edf3">ls ~/projects</tspan></text>
<text x="930" y="39" text-anchor="end" fill="#8b949e" font-size="12">public repos / sorted by push</text>
<path d="M30 60h900" stroke="#30363d"/>
{''.join(rows)}</g></svg>'''


def update_followers(owner, header):
    command = ['curl', '--fail', '--silent', '--show-error', '--retry', '3', '--max-time', '30']
    if os.environ.get('GH_TOKEN'):
        command.extend(['-H', 'Authorization: Bearer ' + os.environ['GH_TOKEN']])
    command.append(f'https://api.github.com/users/{owner}')
    user = json.loads(subprocess.check_output(command, text=True))
    content = header.read_text()
    result, count = re.subn(r'(<text id="followers"[^>]*>).*?(</text>)',
                            lambda m: m[1] + f'Followers / {user["followers"]}' + m[2], content)
    if count != 1:
        raise RuntimeError('Missing followers element in terminal SVG')
    header.write_text(result)


def update(readme, projects):
    content = readme.read_text()
    if content.count(START) != 1 or content.count(END) != 1:
        raise RuntimeError('Expected exactly one pair of project markers')
    before, remainder = content.split(START)
    _, after = remainder.split(END)
    result = before + START + '\n\n' + projects + '\n\n' + END + after
    if result != content:
        readme.write_text(result)


if __name__ == '__main__':
    owner = os.environ.get('PROFILE_OWNER', 'kuryrc')
    root = Path(__file__).resolve().parents[1]
    projects = render(fetch_repos(owner), owner)
    update_followers(owner, root / 'img/follow.svg')
    (root / 'img/projects-panel.svg').write_text(projects)
    update(root / 'README.md', f'[![Automatically updated projects](img/projects-panel.svg)](https://github.com/{owner}?tab=repositories)')
