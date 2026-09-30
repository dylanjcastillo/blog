"""Publish posts from _scheduled/ once their `publish-on` time has arrived.

Scheduled posts live in _scheduled/ (gitignored), so nothing reaches GitHub
before its publish time. A post is due when its front matter has
`publish-on: YYYY-MM-DD` or `publish-on: YYYY-MM-DD HH:MM` (local time) in the
past. Due posts are committed to posts/ on top of origin/main from a temporary
worktree and pushed, which triggers the regular publish workflow. Your own
checkout is never touched. Published sources are moved to _scheduled/published/.

Usage: python3 scripts/publish_scheduled.py [--dry-run]
"""

import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEDULED = REPO / "_scheduled"
PUBLISHED = SCHEDULED / "published"

PUBLISH_ON_RE = re.compile(r"^publish-on:\s*[\"']?([^\"'\n]+?)[\"']?\s*\n", re.MULTILINE)
DATE_RE = re.compile(r"^date:.*$", re.MULTILINE)


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def notify(message: str) -> None:
    subprocess.run(
        ["osascript", "-e", f'display notification "{message}" with title "Blog"'],
        check=False,
    )


def git(*args: str, cwd: Path = REPO) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def prepare(text: str, path: Path) -> tuple[datetime, str] | None:
    """Return (publish time, final post text), or None if not scheduled."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3) + 1
    if end == 0:
        return None
    front_matter, body = text[:end], text[end:]
    match = PUBLISH_ON_RE.search(front_matter)
    if not match:
        return None
    try:
        publish_on = datetime.fromisoformat(match.group(1))
    except ValueError:
        log(f"{path.name}: can't parse publish-on {match.group(1)!r}, skipping")
        return None
    front_matter = PUBLISH_ON_RE.sub("", front_matter, count=1)
    new_date = f"date: {publish_on:%Y-%m-%d}"
    if DATE_RE.search(front_matter):
        front_matter = DATE_RE.sub(new_date, front_matter, count=1)
    else:
        front_matter += new_date + "\n"
    return publish_on, front_matter + body


def publish(name: str, content: str, dry_run: bool) -> None:
    git("fetch", "--quiet", "origin", "main")
    worktree = Path(tempfile.mkdtemp(prefix="blog-publish-"))
    git("worktree", "add", "--quiet", "--detach", str(worktree), "origin/main")
    try:
        target = worktree / "posts" / name
        if target.exists():
            raise RuntimeError(f"posts/{name} already exists on origin/main")
        target.write_text(content)
        git("add", f"posts/{name}", cwd=worktree)
        git("commit", "--quiet", "-m", f"Publish {name}", cwd=worktree)
        if dry_run:
            log(f"dry run: would push posts/{name}")
        else:
            git("push", "--quiet", "origin", "HEAD:main", cwd=worktree)
    finally:
        git("worktree", "remove", "--force", str(worktree))


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    now = datetime.now()
    for path in sorted(SCHEDULED.glob("*.qmd")):
        prepared = prepare(path.read_text(), path)
        if prepared is None:
            continue
        publish_on, content = prepared
        if publish_on > now:
            continue
        try:
            publish(path.name, content, dry_run)
        except (subprocess.CalledProcessError, RuntimeError) as error:
            log(f"{path.name}: failed: {error}")
            notify(f"Failed to publish {path.name}, see ~/Library/Logs/blog-publish-scheduled.log")
            continue
        if dry_run:
            continue
        PUBLISHED.mkdir(exist_ok=True)
        shutil.move(path, PUBLISHED / path.name)
        log(f"published posts/{path.name}")
        notify(f"Published {path.name}")


if __name__ == "__main__":
    main()
