import subprocess
import os
import time
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def git(*args):
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=REPO_DIR,
    )


def has_changes():
    r = git("status", "--porcelain")
    return bool((r.stdout or "").strip())


def push(message: str) -> bool:
    """Commit any data changes and push. Returns True if pushed."""
    if not has_changes():
        return False

    git("add", "-A")
    commit = git("commit", "-m", message)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout or ""):
        return False

    push = git("push")
    return push.returncode == 0


def autopush():
    """Build a descriptive commit message and push."""
    from social import feed
    posts = feed.load_feed()
    if not posts:
        msg = "init bot data"
    else:
        newest = posts[0]
        n_comments = sum(len(p.comments) for p in posts[:5])
        n_likes = sum(len(p.likes) for p in posts[:5])
        ts = datetime.now().strftime("%b %d %H:%M")
        msg = f"bot update {ts}: {len(posts)} posts, {n_likes} likes, {n_comments} comments"
    push(msg)
