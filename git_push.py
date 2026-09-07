import subprocess
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def git(*args):
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=REPO_DIR,
    )


def has_changes(paths=("data",)):
    """Check if any tracked changes exist under given path(s)."""
    r = git("status", "--porcelain")
    lines = (r.stdout or "").splitlines()
    rel = os.path.relpath(REPO_DIR, REPO_DIR)
    for line in lines:
        p = line[3:].strip().replace("\\", "/")
        if any(p.startswith(base) for base in paths):
            return True
    return False


def push(message: str) -> bool:
    """Commit data changes and push. Returns True if pushed."""
    # Only stage our own data; GitHub Actions rebuilds docs/ from it.
    if not has_changes(("data",)):
        return False

    git("add", "--", "data")
    commit = git("commit", "-m", message)
    if commit.returncode != 0:
        return False

    # Pull remote (e.g. rebuild commits from Actions) then push, with retries.
    for attempt in range(3):
        if _try_push():
            return True
        # Remote is ahead: rebase local commits on top of it, then retry.
        pull = git("pull", "--rebase", "--autostash")
        if pull.returncode != 0:
            return False
        rc = _try_push()
        if rc:
            return True
    return _try_push()


def _try_push() -> bool:
    r = git("push")
    return r.returncode == 0


def build_site():
    """Rebuild the static Pages site from feed data."""
    sys.path.insert(0, REPO_DIR)
    try:
        import build_site
        build_site.generate()
        return True
    except Exception as e:
        print(f"[build_site] error: {e}")
        return False


def autopush():
    """Commit feed data and push. docs/ is rebuilt by GitHub Actions."""
    from social import feed
    posts = feed.load_feed()
    if not posts:
        msg = "init bot data"
    else:
        n_comments = sum(len(p.comments) for p in posts[:5])
        n_likes = sum(len(p.likes) for p in posts[:5])
        ts = datetime.now().strftime("%b %d %H:%M")
        msg = f"bot update {ts}: {len(posts)} posts, {n_likes} likes, {n_comments} comments"

    push(msg)
