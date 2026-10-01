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
    assets = {}
    links = []
    for index, repo in enumerate(selected, 1):
        name = repo['name']
        language = repo.get('language') or 'Source'
        description = ' '.join((repo.get('description') or DESCRIPTIONS.get(name) or 'Explore the source and documentation.').split())
        lines = textwrap.wrap(description, width=43)
        if len(lines) > 2:
            lines = [lines[0], textwrap.shorten(' '.join(lines[1:]), width=43, placeholder='…')]
        body = ''.join(f'<text x="24" y="{92 + n * 24}" fill="#a6adb8">{escape(line)}</text>' for n, line in enumerate(lines))
        title = textwrap.shorten(name, width=30, placeholder='…')
        asset = f'img/projects/{name}.svg'
        assets[asset] = f'''<svg xmlns="http://www.w3.org/2000/svg" width="470" height="182" viewBox="0 0 470 182">
<title>{escape(name)}: {escape(description)}</title>
<rect x="1" y="1" width="468" height="180" rx="12" fill="#0d1117" stroke="#30363d"/>
<g font-family="monospace" font-size="15">
<text x="24" y="29" fill="#6e7681" font-size="11">PROJECT / {index:02}</text>
<text x="24" y="58" fill="#79c0ff" font-size="19">{escape(title)}</text>
<text x="445" y="29" fill="#79c0ff" text-anchor="end">↗</text>
{body}
<path d="M24 137h422" stroke="#21262d"/>
<text x="24" y="162" fill="#d2a8ff" font-size="13">{escape(language)}</text>
<text x="446" y="162" fill="#8b949e" font-size="13" text-anchor="end">stars {repo.get('stargazers_count', 0)}</text>
</g></svg>'''
        alt = escape(f'{name}: {description}', {'"': '&quot;'})
        links.append(f'<a href="https://github.com/{owner}/{name}"><img src="{asset}" width="49%" alt="{alt}"></a>')
    if len(selected) % 2:
        asset = 'img/browse-all.svg'
        assets[asset] = '''<svg xmlns="http://www.w3.org/2000/svg" width="470" height="182" viewBox="0 0 470 182">
<title>Browse all GitHub repositories</title>
<rect x="1" y="1" width="468" height="180" rx="12" fill="#0d1117" stroke="#30363d"/>
<g font-family="monospace" font-size="15">
<text x="24" y="29" fill="#6e7681" font-size="11">EXPLORE / MORE</text>
<text x="24" y="58" fill="#7ee787" font-size="19">❯ <tspan fill="#79c0ff">Browse all</tspan></text>
<text x="445" y="29" fill="#79c0ff" text-anchor="end">↗</text>
<text x="24" y="92" fill="#a6adb8">More tools, experiments, and source code.</text>
<path d="M24 137h422" stroke="#21262d"/>
<text x="24" y="162" fill="#d2a8ff" font-size="13">~/repos</text>
<text x="446" y="162" fill="#8b949e" font-size="13" text-anchor="end">open GitHub ↗</text>
</g></svg>'''
        links.append(f'<a href="https://github.com/{owner}?tab=repositories"><img src="{asset}" width="49%" alt="Browse all GitHub repositories"></a>')
    rows = ['<p>' + ' '.join(links[i:i+2]) + '</p>' for i in range(0, len(links), 2)]
    return assets, '\n\n'.join(rows)


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
    assets, projects = render(fetch_repos(owner), owner)
    update_followers(owner, root / 'img/follow.svg')
    for name, svg in assets.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg)
    update(root / 'README.md', projects)
